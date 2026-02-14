# Kraken DCA - Automated Cryptocurrency Dollar Cost Averaging

**Built by Pascal Briner**

A secure, production-ready Docker application for automated Dollar Cost Averaging (DCA) on Kraken cryptocurrency exchange.

## 🎯 Features

- ✅ **Automated DCA Strategy**: Intelligently spreads purchases until next deposit day
- ✅ **Secure API Integration**: Direct HTTPS communication with Kraken API
- ✅ **Zero External Dependencies**: Uses only Python standard library (urllib, hmac, json)
- ✅ **Transaction Tracking**: JSON-based persistent storage of all trades
- ✅ **Real-time P/L Monitoring**: Color-coded profit/loss reporting
- ✅ **Docker Containerized**: Isolated, reproducible deployment
- ✅ **Security Hardened**: Non-root user, minimal permissions, input validation
- ✅ **Production Ready**: Suitable for penetration testing

## 📋 Prerequisites

- Docker (20.10+)
- Docker Compose (1.29+)
- Kraken account with API credentials

## 🔐 Kraken API Setup

1. Log in to your Kraken account
2. Navigate to Settings → API
3. Create a new API key with the following permissions:
   - ✅ **Query Funds** (to check balance)
   - ✅ **Create & Modify Orders** (to place buy orders)
   - ❌ **Withdraw Funds** (NOT required - keep disabled for security)
4. Save your API Key and Private Key (API Secret)

**Security Note**: Never share your API credentials. The application only needs query and order permissions - never enable withdrawal permissions.

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd kraken-dca
```

### 2. Configure the Application

Edit `config.json` with your settings:

```json
{
  "trading_pair": "XXBTZUSD",
  "deposit_day": 1,
  "api_key": "YOUR_KRAKEN_API_KEY_HERE",
  "api_secret": "YOUR_KRAKEN_API_SECRET_HERE",
  "crypto_amount": 0.0001
}
```

**Configuration Options:**

- `trading_pair`: Kraken trading pair (e.g., "XXBTZUSD" for BTC/USD, "XETHZUSD" for ETH/USD)
- `deposit_day`: Day of month (1-28) when you deposit funds
- `api_key`: Your Kraken API public key
- `api_secret`: Your Kraken API private key
- `crypto_amount`: Amount of crypto to buy per transaction (e.g., 0.0001 BTC)

**Finding Trading Pairs:**
Common Kraken pairs:
- Bitcoin: `XXBTZUSD`, `XXBTZEUR`
- Ethereum: `XETHZUSD`, `XETHZEUR`
- See full list: https://api.kraken.com/0/public/AssetPairs

### 3. Build and Run

```bash
# Build the Docker image
docker-compose build

# Start the application
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Stop the Application

```bash
docker-compose down
```

## 📊 How It Works

### DCA Logic

1. **Calculate Remaining Time**: Determines hours until next deposit day (configured in `deposit_day`)
2. **Distribute Purchases**: Spreads buys evenly across remaining time
3. **Execute Trades**: Places market orders at calculated intervals
4. **Record Transactions**: Saves all trades to `transactions.json`
5. **Display Statistics**: Shows P/L after each purchase

### Example

If today is the 15th and your deposit day is the 1st:
- Remaining days: ~16 days
- Remaining hours: ~384 hours
- Strategy: Buy approximately every 24 hours until deposit day

## 📈 Output Format

After each purchase, the application displays:

```
================================================================================
PORTFOLIO SUMMARY
================================================================================
Crypto Amount       Avg Buy Price       Last Buy Price      P/L %               
--------------------------------------------------------------------------------
0.00050000          43310.20            44200.00            +2.05%

Current Price       Total Invested      Current Value       P/L Fiat            
--------------------------------------------------------------------------------
44200.00            2165.51             2210.00             +44.49
================================================================================
```

**Color Coding:**
- 🟢 Green: Profitable (positive P/L)
- 🔴 Red: Loss (negative P/L)

## 📁 File Structure

```
kraken-dca/
├── main.py              # Main application code
├── config.json          # Configuration file (edit this)
├── transactions.json    # Transaction history (auto-generated)
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore       # Docker ignore rules
├── .gitignore          # Git ignore rules
└── README.md           # This file
```

## 🔒 Security Features

### Application Security

1. **Minimal Dependencies**: Uses only Python standard library (no third-party packages)
2. **Input Validation**: All config values are validated on startup
3. **Secure API Communication**: HTTPS only, proper HMAC signature generation
4. **API Key Protection**: Never logged or exposed
5. **Error Handling**: Graceful failure without exposing sensitive data

### Docker Security

1. **Non-root User**: Runs as `krakenuser` (UID 1000)
2. **Read-only Filesystem**: Limited write access
3. **Dropped Capabilities**: `cap_drop: ALL`
4. **No New Privileges**: `no-new-privileges:true`
5. **Minimal Base Image**: Uses `python:3.11-slim`

### API Permissions

The application requires only:
- ✅ Query Funds
- ✅ Create & Modify Orders

**Never enable:**
- ❌ Withdraw Funds
- ❌ Close/Cancel Order (if not needed)

## 🧪 Testing

### Test API Connection

```bash
docker-compose up
```

The application will:
1. Display the startup banner
2. Test API connection
3. Show configuration
4. Begin DCA loop

### Manual Testing

```bash
# Run without Docker (for development)
python3 main.py
```

### Penetration Testing Notes

The application is designed to withstand:
- ✅ SQL Injection (no database, uses JSON files)
- ✅ Command Injection (no shell execution)
- ✅ Path Traversal (validates file paths)
- ✅ API Key Exposure (not logged or stored in plaintext in code)
- ✅ Privilege Escalation (runs as non-root)
- ✅ DoS (rate limiting by design - one buy per calculated interval)

## 📝 Transaction Storage

Transactions are stored in `transactions.json`:

```json
[
  {
    "date": "2025-01-15T10:30:00.000000",
    "trading_pair": "XXBTZUSD",
    "amount": 0.0001,
    "price": 42500.50
  }
]
```

**Fields:**
- `date`: ISO 8601 timestamp
- `trading_pair`: Kraken pair identifier
- `amount`: Crypto amount purchased
- `price`: Price per unit in fiat

## 🐛 Troubleshooting

### API Connection Failed

**Error**: `API Connection Failed: Invalid API key`

**Solution**:
1. Verify API key and secret in `config.json`
2. Check API key permissions on Kraken
3. Ensure API key is not expired

### Trading Pair Not Found

**Error**: `Trading pair XXBTZUSD not found`

**Solution**:
1. Verify pair format (use Kraken's exact naming)
2. Check available pairs: https://api.kraken.com/0/public/AssetPairs
3. Ensure pair includes both base and quote (e.g., `XXBTZUSD` not `BTCUSD`)

### Insufficient Balance

**Error**: Order placement fails

**Solution**:
1. Check your Kraken account balance
2. Ensure sufficient funds for the trade
3. Reduce `crypto_amount` in config if needed

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

## 🔄 Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## 📜 License

This software is provided as-is for personal use. Use at your own risk.

## ⚠️ Disclaimer

**This application handles real financial transactions. Use with caution.**

- Test with small amounts first
- Never invest more than you can afford to lose
- Cryptocurrency trading carries significant risk
- This is not financial advice
- The author is not responsible for financial losses

## 💰 Support the Developer

If you find this application useful, consider donating:

**Bitcoin Address**: `bc1qf9xsdlnffq0hlupcask0lvm702zndk3hf3tns4`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📞 Support

For issues and questions:
1. Check the troubleshooting section
2. Review Kraken API documentation
3. Open a GitHub issue

---

**Built with ❤️ by Pascal Briner**
