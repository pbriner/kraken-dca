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

# Edit configuration
nano config.json

# Update these values:
{
  "trading_pair": "XXBTZUSD",      # BTC/USD or your preferred pair
  "deposit_day": 1,                 # Day of month (1-28) when you deposit
  "api_key": "YOUR_KEY_HERE",      # Your Kraken API key
  "api_secret": "YOUR_SECRET_HERE", # Your Kraken API secret
  "crypto_amount": 0.0001           # Amount to buy per transaction
}
```

### 3. Run

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## 🔐 Security Setup

### Set File Permissions
```bash
chmod 600 config.json
chmod 600 transactions.json
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
  Trading Pair: XXBTZUSD
  Deposit Day: 1
  Crypto Amount per Buy: 0.0001

Application started successfully!
```

## 📁 Project Structure

```
kraken-dca/
├── main.py              # Application code
├── config.json          # Your configuration
├── transactions.json    # Trade history
├── Dockerfile           # Container definition
├── docker-compose.yml   # Deployment config
├── README.md           # Full documentation
├── SECURITY.md         # Security guide
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
docker-compose logs  # Check logs
docker-compose down
docker-compose build --no-cache
docker-compose up -d
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
