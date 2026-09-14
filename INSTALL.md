# Kraken DCA - Quick Installation Guide

## 📦 What You Have

A complete, production-ready Docker application for automated cryptocurrency DCA on Kraken.

## 🚀 Installation Steps

### 1. Prerequisites
- Install Docker: https://docs.docker.com/get-docker/
- Install Docker Compose: https://docs.docker.com/compose/install/
- Get Kraken API credentials: https://www.kraken.com/u/security/api

### 2. Setup

```bash
# Navigate to the project directory
cd kraken-dca

# Add your Kraken credentials — never put these in config.json
nano .env
```
```
KRAKEN_API_KEY=your_key_here
KRAKEN_API_SECRET=your_secret_here
```

```bash
# Edit trading configuration
nano config.json
```
```json
{
  "mode": "recurring",              # "recurring" or "lump_sum"
  "dca_end_date": null,             # required if mode is "lump_sum", e.g. "2027-06-01"
  "trading_pair": "XXBTZUSD",       # BTC/USD or your preferred pair
  "deposit_day": 1,                 # day of month (1-28) when you deposit (recurring mode)
  "buy_hour": 8,                    # hour of day the scheduled buy fires
  "crypto_amount": 0.0001,          # amount to buy per transaction
  "dip_threshold_percent": 5.0,     # % drop that triggers a dip buy
  "dip_buy_cooldown_hours": 2.0,    # min hours between dip buys
  "poll_interval_seconds": 300,     # how often price/balance is checked
  "max_price": null,                # optional price ceiling, null to disable
  "max_monthly_amount": null        # optional spend cap, null to disable
}
```

Optionally, add Telegram bot access — see `README.md` → Telegram Integration.

### 3. Run

```bash
# Build and start
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

## 🔐 Security Setup

### Set File Permissions
```bash
chmod 600 config.json
chmod 600 transactions.json
chmod 600 .env
```

### Kraken API Permissions
Enable ONLY:
- ✅ Query Funds
- ✅ Create & Modify Orders

Never enable:
- ❌ Withdraw Funds

## 📊 What You'll See

```
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║              KRAKEN DCA - CRYPTO AUTOMATION              ║
║                                                           ║
║  Built by: Pascal Briner                                ║
║  Donations: bc1qf9xsdlnffq0hlupcask0lvm702zndk3hf3tns4  ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

Testing Kraken API Connection...
✓ API Connection Successful

Configuration:
  Mode: Recurring
  Trading Pair: XXBTZUSD
  Deposit Day: 1 at 8:00
  Crypto Amount per Buy: 0.0001
  Dip Threshold: 5.0%
  Dip Buy Cooldown: 2.0h
  Max Price: disabled
  Max Monthly: disabled
  Poll Interval: 300s

✓ Telegram bot listening for commands   (only if telegram_bot_token is set)
Application started successfully!
```

## 📁 Project Structure

```
kraken-dca/
├── main.py              # Application code
├── config.json          # Your configuration
├── transactions.json    # Trade history
├── .env                 # KRAKEN_API_KEY / KRAKEN_API_SECRET / TELEGRAM_* (never committed)
├── Dockerfile           # Container definition
├── docker-compose.yml   # Deployment config
├── README.md           # Full documentation
├── SECURITY.md         # Security guide
├── docs.html            # Standalone HTML documentation page
└── LICENSE             # MIT License
```

## 🐛 Common Issues

### "API Connection Failed"
- Check API key and secret
- Verify API permissions on Kraken
- Ensure API key is not expired

### "Trading pair not found"
- Use Kraken's exact pair format (e.g., XXBTZUSD)
- Check: https://api.kraken.com/0/public/AssetPairs

### Container won't start
```bash
docker compose logs  # Check logs
docker compose down
docker compose build --no-cache
docker compose up -d
```

## 📚 Next Steps

1. Read `README.md` for comprehensive documentation
2. Review `SECURITY.md` for security best practices
3. Test with small amounts first
4. Monitor logs regularly

## 💰 Support

Bitcoin Donations: `bc1qf9xsdlnffq0hlupcask0lvm702zndk3hf3tns4`

## ⚠️ Important

- Test with small amounts first
- Never invest more than you can afford to lose
- This is not financial advice
- Use at your own risk

---

Built by Pascal Briner
