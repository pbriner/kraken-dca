# DCA Bot — Agent Build Guide

Everything a Claude agent needs to build an equivalent Kraken DCA bot from scratch, at the same quality and security level.

---

## What it does

Runs a continuous Dollar Cost Averaging loop against the Kraken exchange in one of two modes:

**Recurring** — you deposit fiat every month on a fixed day. The bot spreads buys evenly until the next deposit day, restarting the cycle each month.

**Lump Sum** — you deposit a large chunk once and set an end date. The bot spreads buys evenly between now and that date, stopping once it is reached. Designed for bear market windows where you have a target entry period.

Both modes share: dip buying, max price guard, max monthly spend cap, deposit detection, and portfolio summary.

---

## Kraken account setup

### 1. Fund the account
Deposit fiat (e.g. CHF, EUR, USD) via bank transfer. Kraken calls this a "funding" deposit. The bot reads the fiat balance on startup and after every poll tick — it won't buy if the balance is zero.

### 2. Create an API key
Navigate to: **Account (top right) → Security → API → Create API key**

Give the key a name (e.g. `dca-bot`) and enable **only** these permissions:

| Permission | Why needed |
|------------|------------|
| Query Funds | Read fiat and crypto balances |
| Create & Modify Orders | Place market buy orders |

Leave everything else off — especially **Withdraw Funds** (would allow draining the account if the key is leaked).

**IP allowlist (recommended):** On the same page, restrict the key to the IP address of the machine running the bot. This limits blast radius if the key is ever exposed.

After saving, Kraken shows the **API Key** and **Private Key (secret)** once. Copy both immediately — the secret cannot be retrieved again.

### 3. Trading pair names
Kraken uses internal asset codes with `X` (crypto) and `Z` (fiat) prefixes. Use the pair string exactly as Kraken expects it:

| Pair | Kraken string |
|------|--------------|
| BTC/CHF | `XBTCHF` |
| BTC/USD | `XXBTZUSD` |
| BTC/EUR | `XXBTZEUR` |
| ETH/USD | `XETHZUSD` |

The bot's `get_ticker` method normalises these transparently, but `config.json` must use the Kraken pair string (verifiable on Kraken's asset pairs page or via `/0/public/AssetPairs`).

### 4. Minimum order sizes
Kraken enforces a minimum volume per order. For BTC the minimum is **0.0001 BTC**. Set `crypto_amount` in `config.json` to at or above this value — the bot's validation only checks `> 0`, not the exchange minimum, so an order below the minimum will be rejected at execution time with a Kraken API error.

---

## Tech stack

- **Language:** Python 3.11
- **Dependencies:** zero third-party packages — stdlib only (`urllib`, `hmac`, `hashlib`, `json`, `datetime`, etc.)
- **Persistence:** single `transactions.json` file, appended on every buy
- **Deployment:** Docker + Docker Compose, non-root user, all Linux capabilities dropped

---

## Architecture — 4 classes

### `KrakenAPI`

Handles all HTTP communication with Kraken. No external HTTP libraries.

**Authentication (Kraken's HMAC-SHA512 scheme):**

```python
nonce = str(int(time.time() * 1000))  # millisecond timestamp, must be strictly increasing
postdata = urllib.parse.urlencode(data)
encoded = (nonce + postdata).encode('utf-8')
message = url_path.encode('utf-8') + hashlib.sha256(encoded).digest()
signature = hmac.new(base64.b64decode(api_secret), message, hashlib.sha512)
header['API-Sign'] = base64.b64encode(signature.digest()).decode()
header['API-Key'] = api_key
```

**Retry logic:** exponential backoff, 3 attempts, waits 5s / 10s / give up.

**Endpoints used:**
| Method | Endpoint | Auth |
|--------|----------|------|
| `test_connection` | `/0/private/Balance` | private |
| `get_ticker(pair)` | `/0/public/Ticker` | public |
| `get_balance()` | `/0/private/Balance` | private |
| `place_market_order(pair, volume)` | `/0/private/AddOrder` | private |

**Ticker pair normalisation:** Kraken sometimes returns keys with `X`/`Z` prefixes. The ticker lookup tries the raw pair first, then falls back to stripping those prefixes for matching.

**Fiat currency extraction from pair string:**
```
XBTCHF  → strip leading X → BTCHF → last 3 chars → CHF → strip leading Z if present → CHF
XXBTZUSD → strip X → XBTZUSD → last 3 → USD → strip Z → USD
```

---

### `TransactionStore`

Simple JSON list stored in `transactions.json`. Each entry:

```json
{
  "date": "2026-05-24T08:00:00.123456",
  "trading_pair": "XBTCHF",
  "amount": 0.0001,
  "price": 93250.00
}
```

**Never rotates.** The file grows indefinitely (one entry per buy). For a weekly DCA bot this stays tiny for years.

**Key methods:**
- `add_transaction` — appends and rewrites the whole file (small file, safe)
- `get_statistics(pair)` → `(total_amount, avg_price, last_price, total_spent)`
- `get_monthly_spent(pair, deposit_day, buy_hour)` — sums fiat spent since the cycle boundary

**Cycle boundary logic** (used for both modes' `max_monthly_amount` tracking):
```python
cycle_started = now.day > deposit_day or (now.day == deposit_day and now.hour >= buy_hour)
if cycle_started:
    period_start = now.replace(day=deposit_day, hour=buy_hour, ...)
else:
    # Go back to previous month's deposit_day
    prev_month = (now.replace(day=1) - timedelta(days=1))
    period_start = prev_month.replace(day=deposit_day, hour=buy_hour, ...)
```

In lump_sum mode `deposit_day` defaults to 1, so the monthly cap tracks by calendar month.

---

### `Config`

Loads from `config.json`. **Credentials come exclusively from environment variables** (`KRAKEN_API_KEY`, `KRAKEN_API_SECRET`) — the JSON file must not contain them.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | `"recurring"` or `"lump_sum"` | yes | DCA strategy — see below |
| `dca_end_date` | ISO date string or null | lump_sum only | Last day buys are allowed, e.g. `"2027-06-01"` |
| `trading_pair` | string | yes | e.g. `XBTCHF`, `XXBTZUSD` |
| `deposit_day` | int 1–28 | recurring | Day of month the cycle resets and scheduled buy fires |
| `buy_hour` | int 0–23 | yes | Hour the scheduled buy fires |
| `crypto_amount` | float > 0 | yes | BTC amount per single buy order |
| `dip_threshold_percent` | float 0–100 | yes | % drop below last buy price that triggers a dip buy |
| `dip_buy_cooldown_hours` | float ≥ 0 | yes | Minimum hours between two consecutive dip buys |
| `poll_interval_seconds` | int ≥ 60 | yes | How often the inner loop checks price/balance |
| `max_price` | float or null | no | Skip any buy if price is above this value |
| `max_monthly_amount` | float or null | no | Skip buy if cycle spend + this buy would exceed limit |

Validation runs on load; startup fails fast with a descriptive error if invalid. `dca_end_date` must be in the future when mode is `lump_sum`.

---

### `KrakenDCA` — main loop

```
startup
├── show_banner
├── test_connection (exits on failure)
├── print config summary (shows mode, end date or deposit day)
├── display existing portfolio (if transactions exist)
├── execute_buy()            ← immediate buy on startup
└── outer loop (forever)
    ├── calculate_next_buy() → next_buy_time, hours_between_buys, remaining_hours
    ├── print status summary
    └── inner polling loop
        ├── sleep(poll_interval_seconds)
        ├── if now >= next_buy_time → execute_buy(), break to outer loop
        ├── dip detection → execute_buy() if triggered, recalculate schedule
        └── deposit detection → recalculate schedule if balance increased
```

**Schedule calculation (`calculate_next_buy`) — mode branch:**

*Recurring:*
1. Find the next occurrence of `deposit_day` at `buy_hour` (next month if already past).
2. `remaining_hours = hours until that date`

*Lump Sum:*
1. `period_end = dca_end_date`
2. If `now >= dca_end_date` → print message, return `(end_date, 0.0, 0)` — buying stops.
3. `remaining_hours = hours until dca_end_date`

*Both modes then:*
4. `cost_per_buy = crypto_amount × current_price`
5. `max_buys = floor(available_fiat / cost_per_buy)`
6. `hours_between_buys = remaining_hours / max_buys`
7. `next_buy = now + hours_between_buys`

**execute_buy guards (in order):**
1. In lump_sum mode: if `now >= dca_end_date` → skip with message.
2. Fetch current price.
3. If `max_price` set and `current_price > max_price` → skip.
4. If `max_monthly_amount` set and `cycle_spent + buy_cost > max_monthly_amount` → skip.
5. Place market order.
6. Record in `TransactionStore`.
7. Print portfolio summary.

**Dip detection:**
```python
dip_threshold = last_buy_price × (1 - dip_threshold_percent / 100)
if current_price <= dip_threshold and cooldown_ok:
    execute_buy()
    last_dip_buy_time = now
    recalculate_schedule()
```

---

## Portfolio summary output

Printed after every buy and on each poll tick. Header shows mode and key dates, followed by four data rows:

```
==============================================================================
PORTFOLIO SUMMARY
Mode: Recurring  |  Deposit Day: 24  |  Buy Hour: 08:00
==============================================================================
```
or
```
Mode: Lump Sum  |  DCA End Date: 2027-06-01  |  312d remaining
```

| Row | Recurring columns | Lump Sum columns |
|-----|-------------------|------------------|
| 1 | Crypto Amount · Avg Buy Price · Last Buy Price · P/L % | same |
| 2 | Current Price · Total Invested · Current Value · P/L Fiat | same |
| 3 | Cycle Spent (/ max if set) · Max Buy Price | DCA End Date (days left) · Max Buy Price |
| 4 | Next Scheduled Buy · Hours Until Next Buy | same |

P/L is green when positive, red when negative.

---

## Config file format

`config.json` uses a `_docs` key for inline documentation (JSON has no native comments). The `_docs` object and its keys are ignored by the bot at runtime.

**Recurring mode example:**
```json
{
  "mode": "recurring",
  "dca_end_date": null,
  "trading_pair": "XBTCHF",
  "deposit_day": 24,
  "buy_hour": 8,
  "crypto_amount": 0.0001,
  "dip_threshold_percent": 5.0,
  "dip_buy_cooldown_hours": 2.0,
  "poll_interval_seconds": 300,
  "max_price": 65000,
  "max_monthly_amount": 1000
}
```

**Lump sum mode example:**
```json
{
  "mode": "lump_sum",
  "dca_end_date": "2027-06-01",
  "trading_pair": "XBTCHF",
  "deposit_day": 1,
  "buy_hour": 8,
  "crypto_amount": 0.0001,
  "dip_threshold_percent": 5.0,
  "dip_buy_cooldown_hours": 2.0,
  "poll_interval_seconds": 300,
  "max_price": 65000,
  "max_monthly_amount": null
}
```

---

## Security — what to do and what not to do

### Credentials
- **Never** put `api_key` / `api_secret` in `config.json` or any file that gets baked into the Docker image.
- Pass credentials only via environment variables (`KRAKEN_API_KEY`, `KRAKEN_API_SECRET`), loaded from a `.env` file that is never committed to git.
- The `.env` file lives only on the production host.

### Docker hardening
```yaml
security_opt:
  - no-new-privileges:true   # process cannot gain new privileges via setuid
cap_drop:
  - ALL                      # drop all Linux capabilities
restart: unless-stopped
```

Run as a dedicated non-root user created in the Dockerfile:
```dockerfile
RUN useradd -m -u 1000 krakenuser && chown -R krakenuser:krakenuser /app
USER krakenuser
```

### Do NOT bake config into the image
Mount both `config.json` and `transactions.json` as host volumes — never rely on the COPY'd versions at runtime:
```yaml
volumes:
  - ./config.json:/app/config.json        # runtime config (no credentials)
  - ./transactions.json:/app/transactions.json  # persisted transaction log
```

With this setup, rebuilding the image never touches `transactions.json`.

### API key permissions
On Kraken, create a key with only the permissions the bot needs:
- Query Funds (read balance)
- Create & Modify Orders (place buys)

Do **not** enable: Withdraw Funds, Query Open Orders (not needed), or any admin permissions.

### No eval, no pickle, no subprocess
The entire bot uses only `json.load`, `urllib.request`, and stdlib. There is no dynamic code execution, no shell calls, no deserialization of untrusted data.

---

## File layout

```
/app/
├── main.py           # entire bot (single file)
├── config.json       # runtime config, no credentials (volume-mounted)
└── transactions.json # buy history, never deleted (volume-mounted)
```

Production host:
```
docker/kraken-dca/
├── Dockerfile
├── docker-compose.yml
├── .env              # KRAKEN_API_KEY + KRAKEN_API_SECRET (never committed)
├── config.json
└── transactions.json
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip wheel

RUN useradd -m -u 1000 krakenuser && \
    chown -R krakenuser:krakenuser /app

COPY main.py /app/
COPY config.json /app/

RUN chown krakenuser:krakenuser /app/main.py /app/config.json

USER krakenuser

RUN chmod +x /app/main.py

CMD ["python3", "-u", "/app/main.py"]
```

Note: `config.json` is copied as a fallback default; the volume mount in `docker-compose.yml` overrides it at runtime.

---

## Deploy / update workflow

```bash
# Initial setup (once)
cp main.py config.json Dockerfile /production/kraken-dca/
echo "KRAKEN_API_KEY=xxx" >> /production/kraken-dca/.env
echo "KRAKEN_API_SECRET=yyy" >> /production/kraken-dca/.env
touch /production/kraken-dca/transactions.json

# Every code update (transactions.json is never touched)
cp main.py config.json /production/kraken-dca/
cd /production/kraken-dca && docker compose up -d --build
```

---

## Known limitation to fix

`Config._load()` still accepts `api_key`/`api_secret` fields from `config.json` as a fallback. This is a latent risk: if someone adds credentials to the JSON file and rebuilds the image, they get baked in. The fix is to remove those two `config.get('api_key')` / `config.get('api_secret')` fallbacks and hard-require the env vars.
