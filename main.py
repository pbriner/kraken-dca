#!/usr/bin/env python3
"""
Kraken DCA - Automated Dollar Cost Averaging for Cryptocurrency
Built by Pascal Briner
"""

import os
import sys
import json
import time
import hmac
import hashlib
import base64
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    RESET = '\033[0m'


class KrakenAPI:
    """Secure Kraken API client with minimal dependencies"""
    
    API_URL = "https://api.kraken.com"
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def _get_kraken_signature(self, urlpath: str, data: Dict, nonce: str) -> str:
        """Generate Kraken API signature"""
        postdata = urllib.parse.urlencode(data)
        encoded = (nonce + postdata).encode('utf-8')
        message = urlpath.encode('utf-8') + hashlib.sha256(encoded).digest()
        
        signature = hmac.new(
            base64.b64decode(self.api_secret),
            message,
            hashlib.sha512
        )
        return base64.b64encode(signature.digest()).decode()
    
    def _api_request(self, endpoint: str, data: Optional[Dict] = None, 
                     private: bool = False) -> Dict:
        """Make API request to Kraken"""
        url = f"{self.API_URL}{endpoint}"
        
        if private:
            if data is None:
                data = {}
            nonce = str(int(time.time() * 1000))
            data['nonce'] = nonce
            
            headers = {
                'API-Key': self.api_key,
                'API-Sign': self._get_kraken_signature(endpoint, data, nonce),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            postdata = urllib.parse.urlencode(data).encode('utf-8')
            req = urllib.request.Request(url, data=postdata, headers=headers)
        else:
            if data:
                postdata = urllib.parse.urlencode(data).encode('utf-8')
                req = urllib.request.Request(url, data=postdata)
            else:
                req = urllib.request.Request(url)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get('error') and len(result['error']) > 0:
                    raise Exception(f"Kraken API Error: {', '.join(result['error'])}")
                
                return result.get('result', {})
        except urllib.error.HTTPError as e:
            raise Exception(f"HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            raise Exception(f"Connection Error: {e.reason}")
    
    def test_connection(self) -> bool:
        """Test API connection and credentials"""
        try:
            result = self._api_request('/0/private/Balance', private=True)
            return True
        except Exception as e:
            raise Exception(f"API Connection Failed: {str(e)}")
    
    def get_ticker(self, pair: str) -> float:
        """Get current price for trading pair"""
        result = self._api_request('/0/public/Ticker', {'pair': pair})
        if pair not in result:
            # Try alternative pair format
            for key in result.keys():
                if key.replace('X', '').replace('Z', '') == pair.replace('X', '').replace('Z', ''):
                    pair = key
                    break
        
        if pair not in result:
            raise Exception(f"Trading pair {pair} not found")
        
        return float(result[pair]['c'][0])  # Current price
    
    def get_balance(self) -> Dict[str, float]:
        """Get account balance"""
        result = self._api_request('/0/private/Balance', private=True)
        return {k: float(v) for k, v in result.items()}
    
    def place_market_order(self, pair: str, volume: str, order_type: str = 'buy') -> Dict:
        """Place market order"""
        data = {
            'pair': pair,
            'type': order_type,
            'ordertype': 'market',
            'volume': volume
        }
        return self._api_request('/0/private/AddOrder', data, private=True)


class TransactionStore:
    """JSON-based transaction storage"""
    
    def __init__(self, filepath: str = 'transactions.json'):
        self.filepath = Path(filepath)
        self.transactions: List[Dict] = []
        self._load()
    
    def _load(self):
        """Load transactions from file"""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    self.transactions = json.load(f)
            except json.JSONDecodeError:
                print(f"{Colors.YELLOW}Warning: Could not load transactions file{Colors.RESET}")
                self.transactions = []
    
    def _save(self):
        """Save transactions to file"""
        with open(self.filepath, 'w') as f:
            json.dump(self.transactions, f, indent=2)
    
    def add_transaction(self, trading_pair: str, amount: float, price: float):
        """Add new transaction"""
        transaction = {
            'date': datetime.now().isoformat(),
            'trading_pair': trading_pair,
            'amount': amount,
            'price': price
        }
        self.transactions.append(transaction)
        self._save()
    
    def get_statistics(self, trading_pair: str) -> Tuple[float, float, float, float]:
        """Calculate statistics for trading pair
        Returns: (total_amount, avg_price, last_price, total_spent)
        """
        pair_txs = [tx for tx in self.transactions if tx['trading_pair'] == trading_pair]
        
        if not pair_txs:
            return 0.0, 0.0, 0.0, 0.0
        
        total_amount = sum(tx['amount'] for tx in pair_txs)
        total_spent = sum(tx['amount'] * tx['price'] for tx in pair_txs)
        avg_price = total_spent / total_amount if total_amount > 0 else 0.0
        last_price = pair_txs[-1]['price']
        
        return total_amount, avg_price, last_price, total_spent


class Config:
    """Configuration loader and validator"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = Path(config_path)
        self.trading_pair: str = ''
        self.deposit_day: int = 1
        self.api_key: str = ''
        self.api_secret: str = ''
        self.crypto_amount: float = 0.0
        self._load()
    
    def _load(self):
        """Load and validate configuration"""
        if not self.config_path.exists():
            self._create_template()
            raise Exception(f"Config file created at {self.config_path}. Please fill in your details.")
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Load and validate
        self.trading_pair = config.get('trading_pair', '').upper()
        self.deposit_day = int(config.get('deposit_day', 1))
        self.api_key = config.get('api_key', '')
        self.api_secret = config.get('api_secret', '')
        self.crypto_amount = float(config.get('crypto_amount', 0.0))
        
        # Validation
        if not self.trading_pair:
            raise Exception("trading_pair is required in config")
        if not (1 <= self.deposit_day <= 28):
            raise Exception("deposit_day must be between 1 and 28")
        if not self.api_key or not self.api_secret:
            raise Exception("api_key and api_secret are required")
        if self.crypto_amount <= 0:
            raise Exception("crypto_amount must be greater than 0")
    
    def _create_template(self):
        """Create template configuration file"""
        template = {
            "trading_pair": "XXBTZUSD",
            "deposit_day": 1,
            "api_key": "YOUR_API_KEY_HERE",
            "api_secret": "YOUR_API_SECRET_HERE",
            "crypto_amount": 0.0001
        }
        with open(self.config_path, 'w') as f:
            json.dump(template, f, indent=2)


class KrakenDCA:
    """Main DCA application"""
    
    def __init__(self):
        self.config = Config()
        self.api = KrakenAPI(self.config.api_key, self.config.api_secret)
        self.store = TransactionStore()
    
    def show_banner(self):
        """Display startup banner"""
        banner = f"""
{Colors.CYAN}{Colors.BOLD}╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              {Colors.MAGENTA}KRAKEN DCA - CRYPTO AUTOMATION{Colors.CYAN}              ║
║                                                           ║
║  {Colors.WHITE}Built by: {Colors.GREEN}Pascal Briner{Colors.CYAN}                                ║
║  {Colors.WHITE}Donations: {Colors.YELLOW}bc1qf9xsdlnffq0hlupcask0lvm702zndk3hf3tns4{Colors.CYAN}  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝{Colors.RESET}
"""
        print(banner)
    
    def test_connection(self):
        """Test API connection"""
        print(f"{Colors.BOLD}Testing Kraken API Connection...{Colors.RESET}")
        try:
            self.api.test_connection()
            print(f"{Colors.GREEN}✓ API Connection Successful{Colors.RESET}\n")
        except Exception as e:
            print(f"{Colors.RED}✗ {str(e)}{Colors.RESET}")
            sys.exit(1)
    
    def calculate_next_buy(self) -> Tuple[float, int]:
        """Calculate hours until next buy
        Returns: (hours_until_buy, remaining_hours_in_period)
        """
        now = datetime.now()
        current_day = now.day
        
        # Calculate next deposit day
        if current_day < self.config.deposit_day:
            next_deposit = now.replace(day=self.config.deposit_day)
        else:
            # Next month
            if now.month == 12:
                next_deposit = now.replace(year=now.year + 1, month=1, day=self.config.deposit_day)
            else:
                next_deposit = now.replace(month=now.month + 1, day=self.config.deposit_day)
        
        # Calculate remaining hours
        time_diff = next_deposit - now
        remaining_hours = time_diff.total_seconds() / 3600
        
        # Get current price
        current_price = self.api.get_ticker(self.config.trading_pair)
        
        # Calculate cost per buy
        cost_per_buy = self.config.crypto_amount * current_price
        
        # Calculate number of buys remaining
        total_amount, _, _, total_spent = self.store.get_statistics(self.config.trading_pair)
        
        # Simple DCA: divide remaining time by fixed intervals
        # Aim for one buy per day on average
        hours_between_buys = max(24, remaining_hours / max(1, int(remaining_hours / 24)))
        
        return hours_between_buys, int(remaining_hours)
    
    def execute_buy(self):
        """Execute a buy order"""
        try:
            # Get current price
            current_price = self.api.get_ticker(self.config.trading_pair)
            
            # Place order
            print(f"\n{Colors.BOLD}Executing buy order...{Colors.RESET}")
            result = self.api.place_market_order(
                self.config.trading_pair,
                str(self.config.crypto_amount)
            )
            
            # Record transaction
            self.store.add_transaction(
                self.config.trading_pair,
                self.config.crypto_amount,
                current_price
            )
            
            print(f"{Colors.GREEN}✓ Order placed successfully{Colors.RESET}")
            
            # Display statistics
            self.display_statistics(current_price)
            
        except Exception as e:
            print(f"{Colors.RED}✗ Error executing buy: {str(e)}{Colors.RESET}")
    
    def display_statistics(self, current_price: float):
        """Display trading statistics in table format"""
        total_amount, avg_price, last_price, total_spent = self.store.get_statistics(
            self.config.trading_pair
        )
        
        if total_amount == 0:
            return
        
        # Calculate P/L
        current_value = total_amount * current_price
        pl_fiat = current_value - total_spent
        pl_percent = (pl_fiat / total_spent * 100) if total_spent > 0 else 0
        
        # Determine color
        color = Colors.GREEN if pl_fiat >= 0 else Colors.RED
        
        print(f"\n{Colors.BOLD}{'='*80}{Colors.RESET}")
        print(f"{Colors.BOLD}{'PORTFOLIO SUMMARY':<80}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*80}{Colors.RESET}")
        
        # Table header
        print(f"{Colors.BOLD}{'Crypto Amount':<20}{'Avg Buy Price':<20}{'Last Buy Price':<20}{'P/L %':<20}{Colors.RESET}")
        print(f"{'-'*80}")
        
        # Table row
        print(f"{total_amount:<20.8f}{avg_price:<20.2f}{last_price:<20.2f}{color}{pl_percent:<20.2f}%{Colors.RESET}")
        
        print(f"\n{Colors.BOLD}{'Current Price':<20}{'Total Invested':<20}{'Current Value':<20}{'P/L Fiat':<20}{Colors.RESET}")
        print(f"{'-'*80}")
        print(f"{current_price:<20.2f}{total_spent:<20.2f}{current_value:<20.2f}{color}{pl_fiat:<20.2f}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*80}{Colors.RESET}\n")
    
    def run(self):
        """Main application loop"""
        self.show_banner()
        self.test_connection()
        
        print(f"{Colors.BOLD}Configuration:{Colors.RESET}")
        print(f"  Trading Pair: {Colors.CYAN}{self.config.trading_pair}{Colors.RESET}")
        print(f"  Deposit Day: {Colors.CYAN}{self.config.deposit_day}{Colors.RESET}")
        print(f"  Crypto Amount per Buy: {Colors.CYAN}{self.config.crypto_amount}{Colors.RESET}\n")
        
        # Display existing portfolio if we have transactions
        total_amount, _, _, _ = self.store.get_statistics(self.config.trading_pair)
        if total_amount > 0:
            print(f"{Colors.BOLD}Loading existing portfolio...{Colors.RESET}")
            try:
                current_price = self.api.get_ticker(self.config.trading_pair)
                self.display_statistics(current_price)
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Could not fetch current price: {str(e)}{Colors.RESET}\n")
        
        print(f"{Colors.GREEN}Application started successfully!{Colors.RESET}")
        print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.RESET}\n")
        
        try:
            while True:
                hours_until_buy, remaining_hours = self.calculate_next_buy()
                
                print(f"{Colors.BOLD}Next buy in: {Colors.CYAN}{hours_until_buy:.2f} hours{Colors.RESET}")
                print(f"Remaining hours until deposit day: {Colors.CYAN}{remaining_hours}{Colors.RESET}")
                print(f"Waiting...\n")
                
                # Convert hours to seconds and wait
                time.sleep(hours_until_buy * 3600)
                
                # Execute buy
                self.execute_buy()
                
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}Application stopped by user{Colors.RESET}")
            sys.exit(0)


if __name__ == "__main__":
    try:
        app = KrakenDCA()
        app.run()
    except Exception as e:
        print(f"{Colors.RED}Fatal Error: {str(e)}{Colors.RESET}")
        sys.exit(1)
