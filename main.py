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
from datetime import datetime, timedelta, timezone
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
                     private: bool = False, max_retries: int = 3) -> Dict:
        """Make API request to Kraken with automatic retry on transient failures"""
        for attempt in range(max_retries):
            url = f"{self.API_URL}{endpoint}"
            req_data = dict(data) if data else {}

            if private:
                nonce = str(int(time.time() * 1000))
                req_data['nonce'] = nonce

                headers = {
                    'API-Key': self.api_key,
                    'API-Sign': self._get_kraken_signature(endpoint, req_data, nonce),
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                postdata = urllib.parse.urlencode(req_data).encode('utf-8')
                req = urllib.request.Request(url, data=postdata, headers=headers)
            else:
                if req_data:
                    postdata = urllib.parse.urlencode(req_data).encode('utf-8')
                    req = urllib.request.Request(url, data=postdata)
                else:
                    req = urllib.request.Request(url)

            try:
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))

                    if result.get('error') and len(result['error']) > 0:
                        raise Exception(f"Kraken API Error: {', '.join(result['error'])}")

                    return result.get('result', {})
            except Exception as e:
                is_last_attempt = attempt == max_retries - 1
                if is_last_attempt:
                    if isinstance(e, urllib.error.HTTPError):
                        raise Exception(f"HTTP Error {e.code}: {e.reason}")
                    elif isinstance(e, urllib.error.URLError):
                        raise Exception(f"Connection Error: {e.reason}")
                    raise
                wait = 5 * (2 ** attempt)
                print(f"API request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait}s: {e}")
                time.sleep(wait)
    
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
    
    def get_transaction_count(self, trading_pair: str = None) -> int:
        """Get total number of transactions, optionally filtered by trading pair"""
        if trading_pair:
            return len([tx for tx in self.transactions if tx['trading_pair'] == trading_pair])
        return len(self.transactions)
    
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

    def get_monthly_spent(self, trading_pair: str, deposit_day: int, buy_hour: int = 0) -> float:
        now = datetime.now()
        cycle_started = now.day > deposit_day or (now.day == deposit_day and now.hour >= buy_hour)
        if cycle_started:
            period_start = now.replace(day=deposit_day, hour=buy_hour, minute=0, second=0, microsecond=0)
        else:
            first_of_month = now.replace(day=1)
            prev_month = first_of_month - timedelta(days=1)
            period_start = prev_month.replace(day=deposit_day, hour=buy_hour, minute=0, second=0, microsecond=0)
        pair_txs = [
            tx for tx in self.transactions
            if tx['trading_pair'] == trading_pair
            and datetime.fromisoformat(tx['date']) >= period_start
        ]
        return sum(tx['amount'] * tx['price'] for tx in pair_txs)


class Config:
    """Configuration loader and validator"""
    
    def __init__(self, config_path: str = 'config.json'):
        self.config_path = Path(config_path)
        self.mode: str = 'recurring'
        self.trading_pair: str = ''
        self.deposit_day: int = 1
        self.api_key: str = ''
        self.api_secret: str = ''
        self.crypto_amount: float = 0.0
        self.dip_threshold_percent: float = 5.0
        self.poll_interval_seconds: int = 600
        self.buy_hour: int = 8
        self.dip_buy_cooldown_hours: float = 24.0
        self.max_price: Optional[float] = None
        self.max_monthly_amount: Optional[float] = None
        self.dca_end_date: Optional[datetime] = None
        self._load()
    
    def _load(self):
        """Load and validate configuration"""
        if not self.config_path.exists():
            self._create_template()
            raise Exception(f"Config file created at {self.config_path}. Please fill in your details.")
        
        with open(self.config_path, 'r') as f:
            config = json.load(f)
        
        # Load and validate
        self.mode = config.get('mode', 'recurring').lower()
        self.trading_pair = config.get('trading_pair', '').upper()
        self.deposit_day = int(config.get('deposit_day', 1))
        self.api_key = os.environ.get('KRAKEN_API_KEY') or config.get('api_key', '')
        self.api_secret = os.environ.get('KRAKEN_API_SECRET') or config.get('api_secret', '')
        self.crypto_amount = float(config.get('crypto_amount', 0.0))
        self.dip_threshold_percent = float(config.get('dip_threshold_percent', 5.0))
        self.poll_interval_seconds = int(config.get('poll_interval_seconds', 600))
        self.buy_hour = int(config.get('buy_hour', 8))
        self.dip_buy_cooldown_hours = float(config.get('dip_buy_cooldown_hours', 24.0))
        max_price_raw = config.get('max_price')
        self.max_price = float(max_price_raw) if max_price_raw is not None else None
        max_monthly_raw = config.get('max_monthly_amount')
        self.max_monthly_amount = float(max_monthly_raw) if max_monthly_raw is not None else None
        dca_end_raw = config.get('dca_end_date')
        self.dca_end_date = datetime.fromisoformat(dca_end_raw).astimezone() if dca_end_raw else None

        # Validation
        if self.mode not in ('recurring', 'lump_sum'):
            raise Exception("mode must be 'recurring' or 'lump_sum'")
        if not self.trading_pair:
            raise Exception("trading_pair is required in config")
        if self.mode == 'recurring' and not (1 <= self.deposit_day <= 28):
            raise Exception("deposit_day must be between 1 and 28 (limited to 28 to ensure validity in February)")
        if self.mode == 'lump_sum':
            if self.dca_end_date is None:
                raise Exception("dca_end_date is required when mode is 'lump_sum' (e.g. \"2027-06-01\")")
            if self.dca_end_date <= datetime.now().astimezone():
                raise Exception("dca_end_date must be in the future")
        if not self.api_key or not self.api_secret:
            raise Exception("api_key and api_secret are required")
        if self.crypto_amount <= 0:
            raise Exception("crypto_amount must be greater than 0")
        if not (0 < self.dip_threshold_percent <= 100):
            raise Exception("dip_threshold_percent must be between 0 and 100")
        if self.poll_interval_seconds < 60:
            raise Exception("poll_interval_seconds must be at least 60")
        if not (0 <= self.buy_hour <= 23):
            raise Exception("buy_hour must be between 0 and 23")
        if self.dip_buy_cooldown_hours < 0:
            raise Exception("dip_buy_cooldown_hours must be 0 or greater")
    
    def _create_template(self):
        """Create template configuration file"""
        template = {
            "trading_pair": "XXBTZUSD",
            "deposit_day": 1,
            "api_key": "YOUR_API_KEY_HERE",
            "api_secret": "YOUR_API_SECRET_HERE",
            "crypto_amount": 0.0001,
            "dip_threshold_percent": 5.0,
            "poll_interval_seconds": 600,
            "buy_hour": 8,
            "dip_buy_cooldown_hours": 24.0
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
{Colors.CYAN}{Colors.BOLD}                            ___
                         .-'   `'.
                        /         \\
                        |         ;
                        |         |           ___.--,
               _.._     |0) ~ (0) |    _.---'`__.-( (_.
        __.--'`_.. '.__.\\    '--. \\_.-' ,.--'`     `""`
       ( ,.--'`   ',__ /./;   ;, '.__.'`    __
       _`) )  .---.__.' / |   |\\   \\__..--\"\"  \"\"\"--.,_
      `---' .'.''-._.-'`_./  /\\ '.  \\ _.-~~~````~~~-._`-.__.'{Colors.RESET}
{Colors.MAGENTA}            | |  .' _.-' |  |  \\  \\  '.               `~---`
             \\ \\/ .'     \\  \\   '. '-._)
              \\/ /        \\  \\    `=.__`~-.
              / /\\         `) )    / / `"".`\\
        , _.-'.'\\ \\        / /    ( (     / /
         `--~`   ) )    .-'.'      '.'.  | (
                (/`    ( (`          ) )  '-;
                 `      '-;         (-'{Colors.RESET}

{Colors.CYAN}{Colors.BOLD}    KRAKEN DCA - Automated Dollar Cost Averaging{Colors.RESET}
    
    {Colors.WHITE}Built by: {Colors.GREEN}Pascal Briner{Colors.RESET}
    {Colors.WHITE}Donations: {Colors.YELLOW}bc1qf9xsdlnffq0hlupcask0lvm702zndk3hf3tns4{Colors.RESET}
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
    
    def get_fiat_currency(self) -> str:
        """Extract fiat currency from trading pair"""
        pair = self.config.trading_pair
        if pair.startswith('X'):
            pair = pair[1:]
        quote_currency = pair[-3:]
        if quote_currency.startswith('Z'):
            quote_currency = quote_currency[1:]
        return quote_currency

    def get_fiat_balance(self, balance: Dict) -> float:
        """Get fiat balance, handling Kraken's Z-prefix format"""
        currency = self.get_fiat_currency()
        return balance.get(f'Z{currency}', balance.get(currency, 0.0))
    
    def calculate_next_buy(self) -> Tuple[datetime, float, int]:
        """Calculate next buy time based on mode.
        Returns: (next_buy_datetime, hours_until_buy, remaining_hours_in_period)
        """
        now = datetime.now().astimezone()
        buy_hour = self.config.buy_hour

        if self.config.mode == 'lump_sum':
            period_end = self.config.dca_end_date
            if now >= period_end:
                print(f"{Colors.YELLOW}DCA end date reached ({period_end.strftime('%Y-%m-%d')}), no more scheduled buys.{Colors.RESET}")
                return period_end, 0.0, 0
            remaining_hours = (period_end - now).total_seconds() / 3600
        else:
            current_day = now.day
            if current_day < self.config.deposit_day:
                period_end = now.replace(day=self.config.deposit_day, hour=buy_hour, minute=0, second=0, microsecond=0)
            elif current_day == self.config.deposit_day and now.hour < buy_hour:
                period_end = now.replace(hour=buy_hour, minute=0, second=0, microsecond=0)
            elif now.month == 12:
                period_end = now.replace(year=now.year + 1, month=1, day=self.config.deposit_day, hour=buy_hour, minute=0, second=0, microsecond=0)
            else:
                period_end = now.replace(month=now.month + 1, day=self.config.deposit_day, hour=buy_hour, minute=0, second=0, microsecond=0)
            remaining_hours = (period_end - now).total_seconds() / 3600

        # Get current price and available balance
        current_price = self.api.get_ticker(self.config.trading_pair)
        balance = self.api.get_balance()
        quote_currency = self.get_fiat_currency()
        available_fiat = self.get_fiat_balance(balance)

        if available_fiat <= 0:
            print(f"{Colors.YELLOW}Warning: No {quote_currency} balance available{Colors.RESET}")
            return period_end, 24.0, int(remaining_hours)

        cost_per_buy = self.config.crypto_amount * current_price
        max_buys = int(available_fiat / cost_per_buy)

        if max_buys <= 0:
            print(f"{Colors.YELLOW}Warning: Insufficient balance for buy (need {cost_per_buy:.2f} {quote_currency}){Colors.RESET}")
            return period_end, 24.0, int(remaining_hours)

        hours_between_buys = remaining_hours / max_buys
        next_buy_time = now + timedelta(hours=hours_between_buys)

        return next_buy_time, hours_between_buys, int(remaining_hours)
    
    def execute_buy(self):
        """Execute a buy order"""
        try:
            if self.config.mode == 'lump_sum' and datetime.now().astimezone() >= self.config.dca_end_date:
                print(f"{Colors.YELLOW}⚠ Buy skipped: DCA end date {self.config.dca_end_date.strftime('%Y-%m-%d')} has been reached{Colors.RESET}")
                return

            # Get current price
            current_price = self.api.get_ticker(self.config.trading_pair)

            if self.config.max_price is not None and current_price > self.config.max_price:
                print(f"{Colors.YELLOW}⚠ Buy skipped: price {current_price:.2f} is above max_price {self.config.max_price:.2f}{Colors.RESET}")
                return

            if self.config.max_monthly_amount is not None:
                monthly_spent = self.store.get_monthly_spent(self.config.trading_pair, self.config.deposit_day, self.config.buy_hour)
                buy_cost = self.config.crypto_amount * current_price
                if monthly_spent + buy_cost > self.config.max_monthly_amount:
                    print(f"{Colors.YELLOW}⚠ Buy skipped: monthly spend {monthly_spent:.2f} + {buy_cost:.2f} would exceed limit {self.config.max_monthly_amount:.2f}{Colors.RESET}")
                    return
            
            # Get next order number
            order_number = self.store.get_transaction_count(self.config.trading_pair) + 1
            
            # Place order
            print(f"\n{Colors.BOLD}Executing buy order #{order_number}...{Colors.RESET}")
            print(f"  Amount: {self.config.crypto_amount:.8f} BTC at {current_price:.2f} {self.get_fiat_currency()}")
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
    
    def display_statistics(self, current_price: float, next_buy_time: Optional[datetime] = None):
        """Display trading statistics in table format"""
        total_amount, avg_price, last_price, total_spent = self.store.get_statistics(
            self.config.trading_pair
        )

        if total_amount == 0:
            return

        # Get fiat currency
        fiat_currency = self.get_fiat_currency()

        # Calculate P/L
        current_value = total_amount * current_price
        pl_fiat = current_value - total_spent
        pl_percent = (pl_fiat / total_spent * 100) if total_spent > 0 else 0

        # Determine color
        color = Colors.GREEN if pl_fiat >= 0 else Colors.RED

        if self.config.mode == 'lump_sum':
            days_total = max(1, (self.config.dca_end_date - datetime.now().astimezone()).days)
            mode_line = f"Mode: Lump Sum  |  DCA End Date: {self.config.dca_end_date.strftime('%Y-%m-%d')}  |  {days_total}d remaining"
        else:
            mode_line = f"Mode: Recurring  |  Deposit Day: {self.config.deposit_day}  |  Buy Hour: {self.config.buy_hour:02d}:00"

        print(f"\n{Colors.BOLD}{'='*110}{Colors.RESET}")
        print(f"{Colors.BOLD}{'PORTFOLIO SUMMARY':<110}{Colors.RESET}")
        print(f"{Colors.CYAN}{mode_line:<110}{Colors.RESET}")
        print(f"{Colors.BOLD}{'='*110}{Colors.RESET}")

        # Table header - First row with fixed column widths
        print(f"{Colors.BOLD}{'Crypto Amount':<30}{'Avg Buy Price (' + fiat_currency + ')':<30}{'Last Buy Price (' + fiat_currency + ')':<30}{'P/L %':<20}{Colors.RESET}")
        print(f"{'-'*110}")

        # Table data - First row with matching column widths
        pl_percent_str = f"{pl_percent:.2f}%"
        print(f"{total_amount:<30.8f}{avg_price:<30.2f}{last_price:<30.2f}{color}{pl_percent_str:<20}{Colors.RESET}")

        # Table header - Second row with fixed column widths
        print(f"\n{Colors.BOLD}{'Current Price (' + fiat_currency + ')':<30}{'Total Invested (' + fiat_currency + ')':<30}{'Current Value (' + fiat_currency + ')':<30}{'P/L Fiat (' + fiat_currency + ')':<20}{Colors.RESET}")
        print(f"{'-'*110}")

        # Table data - Second row with matching column widths
        print(f"{current_price:<30.2f}{total_spent:<30.2f}{current_value:<30.2f}{color}{pl_fiat:<20.2f}{Colors.RESET}")

        # Table header - Third row: spend info and end condition
        max_price_str = f"{self.config.max_price:.2f}" if self.config.max_price else "disabled"
        if self.config.mode == 'lump_sum':
            days_left = max(0, (self.config.dca_end_date - datetime.now().astimezone()).days)
            end_date_str = f"{self.config.dca_end_date.strftime('%Y-%m-%d')} ({days_left}d left)"
            print(f"\n{Colors.BOLD}{'DCA End Date':<55}{'Max Buy Price (' + fiat_currency + ')':<55}{Colors.RESET}")
            print(f"{'-'*110}")
            print(f"{Colors.CYAN}{end_date_str:<55}{max_price_str:<55}{Colors.RESET}")
        else:
            monthly_spent = self.store.get_monthly_spent(self.config.trading_pair, self.config.deposit_day, self.config.buy_hour)
            cycle_spent_str = f"{monthly_spent:.2f}"
            if self.config.max_monthly_amount is not None:
                cycle_spent_str += f" / {self.config.max_monthly_amount:.2f}"
            print(f"\n{Colors.BOLD}{'Cycle Spent (' + fiat_currency + ')':<55}{'Max Buy Price (' + fiat_currency + ')':<55}{Colors.RESET}")
            print(f"{'-'*110}")
            print(f"{Colors.CYAN}{cycle_spent_str:<55}{max_price_str:<55}{Colors.RESET}")

        # Table header - Fourth row: next buy schedule
        if next_buy_time is not None:
            now = datetime.now().astimezone()
            hours_until_buy = max(0.0, (next_buy_time - now).total_seconds() / 3600)
            formatted_next_buy = next_buy_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            print(f"\n{Colors.BOLD}{'Next Scheduled Buy':<55}{'Hours Until Next Buy':<55}{Colors.RESET}")
            print(f"{'-'*110}")
            print(f"{Colors.CYAN}{formatted_next_buy:<55}{hours_until_buy:<55.1f}{Colors.RESET}")

        print(f"{Colors.BOLD}{'='*110}{Colors.RESET}\n")
    
    def run(self):
        """Main application loop"""
        self.show_banner()
        self.test_connection()
        
        print(f"{Colors.BOLD}Configuration:{Colors.RESET}")
        print(f"  Mode: {Colors.CYAN}{'Lump Sum' if self.config.mode == 'lump_sum' else 'Recurring'}{Colors.RESET}")
        print(f"  Trading Pair: {Colors.CYAN}{self.config.trading_pair}{Colors.RESET}")
        if self.config.mode == 'lump_sum':
            print(f"  DCA End Date: {Colors.CYAN}{self.config.dca_end_date.strftime('%Y-%m-%d')}{Colors.RESET}")
        else:
            print(f"  Deposit Day: {Colors.CYAN}{self.config.deposit_day} at {self.config.buy_hour}:00{Colors.RESET}")
        print(f"  Crypto Amount per Buy: {Colors.CYAN}{self.config.crypto_amount}{Colors.RESET}")
        print(f"  Dip Threshold: {Colors.CYAN}{self.config.dip_threshold_percent}%{Colors.RESET}")
        print(f"  Dip Buy Cooldown: {Colors.CYAN}{self.config.dip_buy_cooldown_hours}h{Colors.RESET}")
        print(f"  Max Price: {Colors.CYAN}{self.config.max_price:.2f} {self.get_fiat_currency()}{Colors.RESET}" if self.config.max_price else f"  Max Price: {Colors.CYAN}disabled{Colors.RESET}")
        print(f"  Max Monthly: {Colors.CYAN}{self.config.max_monthly_amount:.2f} {self.get_fiat_currency()}{Colors.RESET}" if self.config.max_monthly_amount else f"  Max Monthly: {Colors.CYAN}disabled{Colors.RESET}")
        print(f"  Poll Interval: {Colors.CYAN}{self.config.poll_interval_seconds}s{Colors.RESET}\n")
        
        # Display existing portfolio if we have transactions
        total_amount, _, _, _ = self.store.get_statistics(self.config.trading_pair)
        if total_amount > 0:
            print(f"{Colors.BOLD}Loading existing portfolio...{Colors.RESET}")
            try:
                current_price = self.api.get_ticker(self.config.trading_pair)
                next_buy_preview, _, _ = self.calculate_next_buy()
                self.display_statistics(current_price, next_buy_preview)
            except Exception as e:
                print(f"{Colors.YELLOW}Warning: Could not fetch current price: {str(e)}{Colors.RESET}\n")
        
        print(f"{Colors.GREEN}Application started successfully!{Colors.RESET}")
        print(f"{Colors.YELLOW}Press Ctrl+C to stop{Colors.RESET}\n")

        try:
            # Execute a buy immediately on startup
            self.execute_buy()
            last_dip_buy_time = None

            while True:
                next_buy_time, hours_until_buy, remaining_hours = self.calculate_next_buy()

                # Get current balance and calculate stats
                current_price = self.api.get_ticker(self.config.trading_pair)
                balance = self.api.get_balance()
                fiat_currency = self.get_fiat_currency()
                available_fiat = self.get_fiat_balance(balance)

                # Calculate estimated buy actions
                cost_per_buy = self.config.crypto_amount * current_price
                estimated_buys = int(available_fiat / cost_per_buy) if cost_per_buy > 0 else 0

                # Get last buy price for dip detection
                _, _, last_buy_price, _ = self.store.get_statistics(self.config.trading_pair)
                dip_factor = 1.0 - (self.config.dip_threshold_percent / 100.0)
                dip_threshold = last_buy_price * dip_factor if last_buy_price > 0 else 0

                # Format the next buy time with timezone
                formatted_time = next_buy_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                poll_minutes = self.config.poll_interval_seconds // 60

                print(f"{Colors.BOLD}Next scheduled buy: {Colors.CYAN}{formatted_time}{Colors.RESET}")
                print(f"Current price: {Colors.CYAN}{current_price:.2f} {fiat_currency}{Colors.RESET}")
                print(f"Dip buy threshold ({self.config.dip_threshold_percent}%): {Colors.CYAN}{dip_threshold:.2f} {fiat_currency}{Colors.RESET}")
                print(f"Dip buy cooldown: {Colors.CYAN}{self.config.dip_buy_cooldown_hours}h{Colors.RESET}")
                print(f"Current fiat available: {Colors.CYAN}{available_fiat:.2f} {fiat_currency}{Colors.RESET}")
                print(f"Estimated buy actions till deposit day: {Colors.CYAN}{estimated_buys}{Colors.RESET}")
                print(f"Remaining hours until deposit day: {Colors.CYAN}{remaining_hours}{Colors.RESET}")
                print(f"Monitoring every {poll_minutes} minutes...\n")

                # Track balance for deposit detection
                previous_fiat = available_fiat

                # Poll until next buy time
                while True:
                    time.sleep(self.config.poll_interval_seconds)

                    now = datetime.now().astimezone()

                    # Check if it's time for the scheduled buy
                    if now >= next_buy_time:
                        print(f"{Colors.BOLD}Scheduled buy time reached.{Colors.RESET}")
                        self.execute_buy()
                        break

                    try:
                        current_price = self.api.get_ticker(self.config.trading_pair)
                        balance = self.api.get_balance()
                        available_fiat = self.get_fiat_balance(balance)

                        # Dip detection: buy if price dropped below threshold
                        _, _, last_buy_price, _ = self.store.get_statistics(self.config.trading_pair)
                        dip_factor = 1.0 - (self.config.dip_threshold_percent / 100.0)
                        dip_threshold = last_buy_price * dip_factor if last_buy_price > 0 else 0

                        if dip_threshold > 0 and current_price <= dip_threshold:
                            cooldown_ok = (
                                last_dip_buy_time is None or
                                (now - last_dip_buy_time).total_seconds() / 3600 >= self.config.dip_buy_cooldown_hours
                            )
                            if cooldown_ok:
                                print(f"\n{Colors.MAGENTA}{Colors.BOLD}DIP DETECTED!{Colors.RESET} "
                                      f"Price {current_price:.2f} is ≥{self.config.dip_threshold_percent}% below last buy price {last_buy_price:.2f}")
                                self.execute_buy()
                                last_dip_buy_time = now
                                # Recalculate schedule after dip buy
                                next_buy_time, hours_until_buy, remaining_hours = self.calculate_next_buy()
                                formatted_time = next_buy_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                                print(f"{Colors.BOLD}Recalculated next buy: {Colors.CYAN}{formatted_time}{Colors.RESET}\n")
                            else:
                                remaining_cooldown = self.config.dip_buy_cooldown_hours - (now - last_dip_buy_time).total_seconds() / 3600
                                print(f"[{now.strftime('%H:%M:%S')}] Dip detected but cooldown active ({remaining_cooldown:.1f}h remaining)")

                        # Deposit detection: new fiat arrived
                        if available_fiat > previous_fiat:
                            deposit_amount = available_fiat - previous_fiat
                            print(f"\n{Colors.GREEN}{Colors.BOLD}NEW DEPOSIT DETECTED!{Colors.RESET} "
                                  f"+{deposit_amount:.2f} {fiat_currency} "
                                  f"(balance: {available_fiat:.2f} {fiat_currency})")
                            previous_fiat = available_fiat
                            # Recalculate schedule with new balance
                            next_buy_time, hours_until_buy, remaining_hours = self.calculate_next_buy()
                            formatted_time = next_buy_time.strftime("%Y-%m-%d %H:%M:%S %Z")
                            print(f"{Colors.BOLD}Recalculated next buy: {Colors.CYAN}{formatted_time}{Colors.RESET}\n")

                        print(f"[{now.strftime('%H:%M:%S')}] Price: {current_price:.2f} | "
                              f"Dip at: {dip_threshold:.2f} | "
                              f"Balance: {available_fiat:.2f} {fiat_currency}")
                        self.display_statistics(current_price, next_buy_time)

                    except Exception as e:
                        print(f"{Colors.YELLOW}Warning: Check cycle error: {str(e)}{Colors.RESET}")
                
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
