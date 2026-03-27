# Kraken DCA - Automated Cryptocurrency Dollar Cost Averaging

**Built by Pascal Briner**

A secure, production-ready Docker application for automated Dollar Cost Averaging (DCA) on Kraken cryptocurrency exchange.

## 🎯 Features

- ✅ **Automated DCA Strategy**: Intelligently spreads purchases until next deposit day (8 AM)
- ✅ **Smart Dip Buying**: Automatically buys when price drops 5% or more from last purchase
- ✅ **Real-time Price Monitoring**: Checks price every minute for opportunities
- ✅ **Enhanced Transaction Display**: Shows order numbers and detailed statistics
- ✅ **Timezone-Aware Scheduling**: Displays exact date/time for next purchases
- ✅ **Live Balance Tracking**: Shows current fiat available and estimated buy actions
- ✅ **Secure API Integration**: Direct HTTPS communication with Kraken API
- ✅ **Zero External Dependencies**: Uses only Python standard library (urllib, hmac, json)
- ✅ **Transaction Tracking**: JSON-based persistent storage of all trades
- ✅ **Real-time P/L Monitoring**: Color-coded profit/loss reporting with currency labels
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
- `deposit_day`: Day of month (1-28) when you deposit funds (purchases spread from 8:00 AM on this day)
- `api_key`: Your Kraken API public key
- `api_secret`: Your Kraken API private key
- `crypto_amount`: Amount of crypto to buy per transaction (e.g., 0.0001 BTC)

**Finding Trading Pairs:**
Common Kraken pairs:
- Bitcoin: `XXBTZUSD`, `XXBTZEUR`, `XXBTZCHF`
- Ethereum: `XETHZUSD`, `XETHZEUR`, `XETHZCHF`
- See full list: https://api.kraken.com/0/public/AssetPairs

### 3. Build and Run

```bash
# Build the Docker image (use --no-cache for a clean build)
docker-compose build --no-cache

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

1. **Calculate Remaining Time**: Determines hours until next deposit day at 8:00 AM (configured in `deposit_day`)
2. **Distribute Purchases**: Spreads buys evenly across remaining time to empty fiat balance by deposit day
3. **Monitor Price Changes**: Checks price every minute for dip buying opportunities
4. **Execute Trades**: Places market orders at calculated intervals or when 5% dip detected
5. **Record Transactions**: Saves all trades to `transactions.json` with sequential order numbers
6. **Display Statistics**: Shows P/L with currency labels after each purchase

### Smart Dip Buying

The application monitors the price every minute and triggers an additional buy when:
- Current price drops **5% or more** below the last purchase price
- Sufficient fiat balance is available for the purchase

This combines regular DCA (spreading purchases evenly) with opportunistic buying during price dips.

### Example

**Scenario**: Today is the 15th, your deposit day is the 1st, you have 5000 CHF available

**Regular DCA**:
- Remaining time until next deposit (1st at 8 AM): ~384 hours
- Current BTC price: 50,000 CHF
- Cost per buy (0.0001 BTC): 5 CHF
- Maximum buys possible: 1000 buys
- Strategy: Buy every ~0.38 hours until deposit day

**Dip Buying**:
- Last buy price: 50,000 CHF
- Current price drops to: 47,000 CHF (6.0% drop)
- 🔔 **Dip Alert triggered!**
- Executes immediate buy
- Recalculates next scheduled buy time

## 📈 Output Format

### Startup Information

```
Next scheduled buy: 2026-02-15 14:30:00 CET
Current fiat available: 5475.20 CHF
Estimated buy actions till deposit day: 12
Remaining hours until deposit day: 456
Monitoring for price dips...
```

### Dip Alert

```
🔔 DIP ALERT! 🔔
Price dropped 5.32% from last buy!
Last buy: 58542.21 → Current: 55420.00

Executing buy order #13...
  Amount: 0.00010000 BTC at 55420.00 CHF
✓ Order placed successfully
```

### Portfolio Summary

```
====================================================================================================
PORTFOLIO SUMMARY
====================================================================================================
Crypto Amount                 Avg Buy Price (CHF)           Last Buy Price (CHF)          P/L %               
----------------------------------------------------------------------------------------------------
0.09352571                    58542.21                      53938.60                      -7.60%

Current Price (CHF)           Total Invested (CHF)          Current Value (CHF)           P/L Fiat (CHF)      
----------------------------------------------------------------------------------------------------
54111.50                      5475.20                       5060.82                       -414.39
====================================================================================================
```

**Color Coding:**
- 🟢 Green: Profitable (positive P/L)
- 🔴 Red: Loss (negative P/L)

**What's Displayed:**
- **Crypto Amount**: Total cryptocurrency accumulated
- **Avg Buy Price**: Average price paid across all purchases (in your fiat currency)
- **Last Buy Price**: Price of the most recent purchase (in your fiat currency)
- **P/L %**: Percentage profit/loss
- **Current Price**: Current market price (in your fiat currency)
- **Total Invested**: Total fiat spent
- **Current Value**: Current worth of holdings (in your fiat currency)
- **P/L Fiat**: Profit/loss in fiat currency

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
3. Show configuration (including dip buy trigger: 5%)
4. Display existing portfolio (if any)
5. Show next scheduled buy with timezone
6. Display current fiat balance
7. Show estimated buy actions until deposit day
8. Begin monitoring price every minute

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
- ✅ DoS (rate limiting by design - price check every 60 seconds, purchases at calculated intervals)

## 📝 Transaction Storage

Transactions are stored in `transactions.json`:

```json
[
  {
    "date": "2025-01-15T10:30:00.000000",
    "trading_pair": "XXBTZUSD",
    "amount": 0.0001,
    "price": 42500.50
  },
  {
    "date": "2025-01-15T14:45:00.000000",
    "trading_pair": "XXBTZUSD",
    "amount": 0.0001,
    "price": 40375.25
  }
]
```

**Fields:**
- `date`: ISO 8601 timestamp
- `trading_pair`: Kraken pair identifier
- `amount`: Crypto amount purchased
- `price`: Price per unit in fiat

**Transaction Numbers**: Order numbers are calculated dynamically as `len(transactions) + 1`, so the first transaction will be order #1, second will be #2, etc.

## 🆕 What's New

### Recent Updates (February 2026)

1. **Timezone Support**: Next buy time now displays with full timezone information (e.g., "2026-02-15 14:30:00 CET")

2. **8 AM Deposit Day**: Deposit day calculation now uses 8:00 AM as the reference time for spreading purchases

3. **Order Numbering**: Buy orders now show sequential numbers (e.g., "Executing buy order #5...")

4. **Currency Labels**: All price fields in portfolio summary now show the currency (e.g., "Current Price (CHF)")

5. **Live Balance Tracking**: Shows current fiat balance and estimated buy actions remaining

6. **Smart Dip Buying**: Automatically detects and executes purchases when price drops 5% or more from last buy

7. **Minute-by-Minute Monitoring**: Checks price every 60 seconds for dip opportunities while waiting for scheduled buys

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

**Error**: Order placement fails or "Insufficient balance for buy"

**Solution**:
1. Check your Kraken account balance
2. Ensure sufficient funds for the trade
3. Reduce `crypto_amount` in config if needed
4. Note: Dip buys won't execute if balance is insufficient

### Container Won't Start

```bash
# Check logs
docker-compose logs

# Rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up
```

### Price Not Updating

If you notice the price isn't being checked every minute:
1. Check container logs for errors: `docker-compose logs -f`
2. Verify network connectivity
3. Check Kraken API status: https://status.kraken.com/

## 🔄 Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

## 💡 Tips & Best Practices

1. **Start Small**: Test with minimum amounts first to verify everything works
2. **Monitor Regularly**: Check logs periodically to ensure purchases are executing
3. **Adjust Deposit Day**: Set to the day after your regular income deposit
4. **Balance Management**: Ensure you have enough fiat to cover all planned purchases
5. **Dip Buying**: The 5% threshold works well for volatile assets like Bitcoin; consider your risk tolerance
6. **Timezone Awareness**: The app uses your system timezone for all time displays

## 📜 License

This software is provided as-is for personal use. Use at your own risk.

## ⚠️ Disclaimer

**This application handles real financial transactions. Use with caution.**

- Test with small amounts first
- Never invest more than you can afford to lose
- Cryptocurrency trading carries significant risk
- This is not financial advice
- The author is not responsible for financial losses
- Dip buying increases purchase frequency and may deplete balance faster than planned

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
