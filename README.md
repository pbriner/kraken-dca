# Kraken DCA - Automated Cryptocurrency Dollar Cost Averaging

**Built by Pascal Briner**

A secure, production-ready Docker application for automated Dollar Cost Averaging (DCA) on Kraken cryptocurrency exchange.

## 🎯 Features

- ✅ **Two DCA Modes**: `recurring` (spread buys between monthly deposits) or `lump_sum` (spread a one-time deposit evenly until a target end date)
- ✅ **Smart Dip Buying**: Automatically buys when price drops below a configurable threshold from the last purchase (with a cooldown)
- ✅ **Real-time Price Monitoring**: Checks price on a configurable poll interval for dip and deposit opportunities
- ✅ **Guardrails**: Optional `max_price` (skip buys above a price ceiling) and `max_monthly_amount` (spend cap per cycle)
- ✅ **Enhanced Transaction Display**: Shows order numbers and detailed statistics
- ✅ **Timezone-Aware Scheduling**: Displays exact date/time for next purchases
- ✅ **Live Balance Tracking**: Shows current fiat available and estimated buy actions
- ✅ **Secure API Integration**: Direct HTTPS communication with Kraken API
- ✅ **Zero External Dependencies**: Uses only Python standard library (urllib, hmac, json)
- ✅ **Telegram Integration**: Query status, chart your history, trigger manual buys, and get notified on every buy — all from Telegram (optional)
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

Put your Kraken API credentials in `.env` (never in `config.json`):

```
KRAKEN_API_KEY=your_key_here
KRAKEN_API_SECRET=your_secret_here
```

Edit `config.json` with your trading settings:

```json
{
  "mode": "recurring",
  "dca_end_date": null,
  "trading_pair": "XXBTZUSD",
  "deposit_day": 1,
  "buy_hour": 8,
  "crypto_amount": 0.0001,
  "dip_threshold_percent": 5.0,
  "dip_buy_cooldown_hours": 2.0,
  "poll_interval_seconds": 300,
  "max_price": null,
  "max_monthly_amount": null
}
```

**Configuration Options:**

- `mode`: `"recurring"` (spread buys between monthly deposits) or `"lump_sum"` (spread a one-time deposit evenly until `dca_end_date`)
- `dca_end_date`: Required in `lump_sum` mode — ISO date (`YYYY-MM-DD`) after which buying stops. Unused in `recurring` mode.
- `trading_pair`: Kraken trading pair (e.g., "XXBTZUSD" for BTC/USD, "XETHZUSD" for ETH/USD)
- `deposit_day`: Day of month (1-28) when you deposit funds (recurring mode only — the cycle resets and the scheduled buy fires on this day)
- `buy_hour`: Hour of day (0-23) the scheduled buy fires
- `crypto_amount`: Amount of crypto to buy per scheduled/dip order (e.g., 0.0001 BTC — Kraken's minimum)
- `dip_threshold_percent`: % price drop below the last buy that triggers an extra dip buy
- `dip_buy_cooldown_hours`: Minimum hours between two consecutive dip buys
- `poll_interval_seconds`: How often the bot checks price/balance (minimum 60)
- `max_price`: Skip any buy if price is above this value. `null` to disable
- `max_monthly_amount`: Cap fiat spend per cycle (recurring) or calendar month (lump_sum). `null` to disable
- Telegram integration (`TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`): Optional, env-var only — see [Telegram Integration](#-telegram-integration-optional) below

**Finding Trading Pairs:**
Common Kraken pairs:
- Bitcoin: `XXBTZUSD`, `XXBTZEUR`, `XXBTZCHF`
- Ethereum: `XETHZUSD`, `XETHZEUR`, `XETHZCHF`
- See full list: https://api.kraken.com/0/public/AssetPairs

### 3. Build and Run

```bash
# Build the Docker image (use --no-cache for a clean build)
docker compose build --no-cache

# Start the application
docker compose up -d

# View logs
docker compose logs -f
```

### 4. Stop the Application

```bash
docker compose down
```

## 📊 How It Works

### DCA Logic

1. **Calculate Remaining Time**: In `recurring` mode, hours until the next `deposit_day` at `buy_hour`. In `lump_sum` mode, hours until `dca_end_date`.
2. **Distribute Purchases**: Spreads buys evenly across the remaining time so the available fiat balance is deployed gradually rather than in one hit.
3. **Monitor Price Changes**: Checks price every `poll_interval_seconds` (default 300s) for dip buying opportunities.
4. **Execute Trades**: Places market orders at calculated intervals, or immediately when a dip is detected — subject to `max_price` and `max_monthly_amount` guards.
5. **Record Transactions**: Saves all trades to `transactions.json` with sequential order numbers.
6. **Display Statistics**: Shows P/L with currency labels after each purchase.

### Smart Dip Buying

The application polls the price every `poll_interval_seconds` and triggers an additional buy when:
- Current price drops **`dip_threshold_percent`% or more** below the last purchase price (default 5%)
- The cooldown since the last dip buy (`dip_buy_cooldown_hours`) has elapsed
- Sufficient fiat balance is available and `max_price`/`max_monthly_amount` aren't exceeded

This combines regular DCA (spreading purchases evenly) with opportunistic buying during price dips.

### Example

**Recurring mode** — Today is the 15th, your deposit day is the 1st, you have 5000 CHF available:
- Remaining time until next deposit (1st at 8 AM): ~384 hours
- Current BTC price: 50,000 CHF
- Cost per buy (0.0001 BTC): 5 CHF
- Maximum buys possible: 1000 buys
- Strategy: Buy every ~0.38 hours until deposit day

**Lump sum mode** — You deposit 10,000 CHF once, `dca_end_date` is 90 days out:
- The bot spreads buys evenly across those 90 days using the same interval-calculation logic
- As the balance depletes or the price moves, the interval between buys recalculates automatically

**Dip Buying** (either mode):
- Last buy price: 50,000 CHF
- Current price drops to: 47,000 CHF (6.0% drop)
- 🔔 **Dip Alert triggered!**
- Executes immediate buy
- Recalculates next scheduled buy time

## 📈 Output Format

### Startup Information

```
Next scheduled buy: 2026-02-15 14:30:00 CET
Current price: 58138.90 CHF
Dip buy threshold (5.0%): 55231.96 CHF
Current fiat available: 5475.20 CHF
Estimated buy actions till deposit day: 12
Remaining hours until deposit day: 456
Monitoring every 5 minutes...
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

## 🤖 Telegram Integration (Optional)

Query your portfolio, trigger manual buys, chart your history, and get notified whenever a buy executes — all from Telegram.

### Setup

1. Message [@BotFather](https://t.me/BotFather) on Telegram, run `/newbot`, and copy the token it gives you.
2. Add it to `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC-your-token
   ```
3. Restart the bot and send it any message (e.g. `/start`). Since `TELEGRAM_CHAT_ID` isn't set yet, it will reply with your chat ID instead of any portfolio data.
4. Add that chat ID to `.env`:
   ```
   TELEGRAM_CHAT_ID=123456789
   ```
5. Restart. The bot now only responds to that chat.

### Commands

- `/status` — current BTC amount, average buy price, last buy (date & price), next scheduled buy, current mode, current price, P/L
- `/buy` — sends an inline confirm/cancel button; confirming places an immediate market buy for the Kraken minimum (0.0001 BTC), still respecting `max_price` and `max_monthly_amount`
- `/chart` — chart of BTC held (cumulative) and average buy price over time, rendered via [QuickChart.io](https://quickchart.io) and sent as a photo
- `/chart price` — same chart, without the BTC-held line, just price
- `/help` — lists all commands

Every executed buy — scheduled, dip, or manual — sends a Telegram notification automatically (order number, amount, price, cost), labeled by how it happened.

Only the configured `telegram_chat_id` can use the bot — everyone else gets an "Unauthorized" reply.

## 📁 File Structure

```
kraken-dca/
├── main.py              # Main application code
├── config.json          # Configuration file (edit this)
├── transactions.json    # Transaction history (auto-generated)
├── .env                 # KRAKEN_API_KEY / KRAKEN_API_SECRET / TELEGRAM_* (never committed)
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Docker Compose configuration
├── .dockerignore       # Docker ignore rules
├── .gitignore          # Git ignore rules
├── README.md            # This file
├── INSTALL.md            # Quick installation guide
├── SECURITY.md           # Security policy and hardening guide
├── docs.html             # Standalone HTML documentation page
└── share-dca-bot.md      # Full technical build guide (architecture, internals)
```

## 🔒 Security Features

### Application Security

1. **Minimal Dependencies**: Uses only Python standard library (no third-party packages)
2. **Input Validation**: All config values are validated on startup
3. **Secure API Communication**: HTTPS only, proper HMAC signature generation
4. **Credential Isolation**: API keys are read from `KRAKEN_API_KEY`/`KRAKEN_API_SECRET` environment variables (via `.env`, gitignored), never stored in `config.json`; the same pattern applies to the optional Telegram bot token
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
docker compose up
```

The application will:
1. Display the startup banner
2. Test API connection
3. Show configuration (mode, trading pair, dip threshold, cooldown, price/spend guards)
4. Display existing portfolio (if any)
5. Start the Telegram listener thread, if `telegram_bot_token` is configured
6. Show next scheduled buy with timezone
7. Display current fiat balance
8. Show estimated buy actions remaining in the cycle
9. Begin monitoring price on the configured poll interval

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
- ✅ DoS (rate limiting by design - price checks on the configured poll interval, purchases at calculated intervals)
- ✅ Telegram Bot Abuse (only the configured `telegram_chat_id` gets responses; manual buys require an explicit inline-button confirmation)

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

### Recent Updates (August 2026)

1. **Telegram Integration**: Query `/status` (BTC amount, average price, last/next buy, mode, P/L), chart your history with `/chart` (or `/chart price` for price-only), and trigger manual minimum-size buys with `/buy` — all gated to a single authorized chat ID
2. **Automatic Buy Notifications**: Every scheduled, dip, or manual buy now sends a Telegram message with the order number, amount, price, and cost
3. **Lump Sum Mode**: New `mode: "lump_sum"` spreads a one-time deposit evenly until a configured `dca_end_date`, as an alternative to the recurring monthly cycle
4. **Spend & Price Guards**: `max_price` and `max_monthly_amount` config options skip buys above a price ceiling or once a spend cap is hit
5. **Configurable Poll Interval**: `poll_interval_seconds` replaces the old fixed 60-second check
6. **Environment-Based Credentials**: `KRAKEN_API_KEY`/`KRAKEN_API_SECRET` (and the optional Telegram token) are read from environment variables, never stored in `config.json`

### Earlier Updates (February 2026)

1. **Timezone Support**: Next buy time now displays with full timezone information (e.g., "2026-02-15 14:30:00 CET")

2. **8 AM Deposit Day**: Deposit day calculation now uses 8:00 AM as the reference time for spreading purchases

3. **Order Numbering**: Buy orders now show sequential numbers (e.g., "Executing buy order #5...")

4. **Currency Labels**: All price fields in portfolio summary now show the currency (e.g., "Current Price (CHF)")

5. **Live Balance Tracking**: Shows current fiat balance and estimated buy actions remaining

6. **Smart Dip Buying**: Automatically detects and executes purchases when price drops below a configurable threshold from last buy

7. **Continuous Monitoring**: Checks price on the configured poll interval for dip opportunities while waiting for scheduled buys

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
docker compose logs

# Rebuild
docker compose down
docker compose build --no-cache
docker compose up
```

### Price Not Updating

If you notice the price isn't being checked every minute:
1. Check container logs for errors: `docker compose logs -f`
2. Verify network connectivity
3. Check Kraken API status: https://status.kraken.com/

## 🔄 Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker compose down
docker compose build
docker compose up -d
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
