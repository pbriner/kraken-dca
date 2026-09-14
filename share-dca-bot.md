# DCA Bot — Agent Build Guide

Everything a Claude agent needs to build an equivalent Kraken DCA bot from scratch, at the same quality and security level.

---

## What it does

Runs a continuous Dollar Cost Averaging loop against the Kraken exchange in one of two modes:

**Recurring** — you deposit fiat every month on a fixed day. The bot spreads buys evenly until the next deposit day, restarting the cycle each month.

**Lump Sum** — you deposit a large chunk once and set an end date. The bot spreads buys evenly between now and that date, stopping once it is reached. Designed for bear market windows where you have a target entry period.

Both modes share: dip buying, max price guard, max monthly spend cap, deposit detection, and portfolio summary.

Optionally, a Telegram bot runs alongside the trading loop in a background thread: `/status` reports current holdings, average price, last/next buy, and mode; `/buy` places an immediate confirm-gated manual buy for the exchange minimum; `/chart` (or `/chart price`) sends a chart of BTC held and price over time. Every executed buy also sends an automatic notification, regardless of which command (if any) triggered it.

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
- **Dependencies:** zero third-party Python packages — stdlib only (`urllib`, `hmac`, `hashlib`, `json`, `datetime`, `threading`, etc.). The one deliberate exception to "no external services" is `/chart`, which points Telegram at a QuickChart.io URL instead of rendering images locally — this adds no package dependency, just an optional outbound call
- **Persistence:** single `transactions.json` file, appended on every buy
- **Concurrency:** main thread runs the trading loop; a daemon thread runs the Telegram long-poll loop (only started if `telegram_bot_token` is configured)
- **Deployment:** Docker + Docker Compose, non-root user, all Linux capabilities dropped

---

## Architecture — 5 classes

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

### `TelegramBot`

Minimal Telegram Bot API client, `urllib`-only, same "no HTTP library" philosophy as `KrakenAPI`. Talks to `https://api.telegram.org/bot{token}/{method}` with JSON POST bodies.

**Methods:**
| Method | Telegram API | Purpose |
|--------|--------------|---------|
| `get_updates(offset, poll_timeout)` | `getUpdates` | Long-poll for new messages/button presses (30s timeout) |
| `send_message(chat_id, text, reply_markup=None)` | `sendMessage` | Send a message, optionally with an inline keyboard. Always `parse_mode='HTML'` |
| `send_photo(chat_id, photo_url, caption=None)` | `sendPhoto` | Send an image by URL — Telegram's servers fetch it, the bot never downloads or hosts the image itself. Used by `/chart` |
| `answer_callback_query(id, text=None)` | `answerCallbackQuery` | Acknowledge a button press (stops the client-side loading spinner) |
| `edit_message_reply_markup(chat_id, message_id, reply_markup=None)` | `editMessageReplyMarkup` | Strip a message's buttons after it's been acted on |
| `set_my_commands(commands)` | `setMyCommands` | Register the `/` command menu shown natively in the Telegram client |

No polling state lives in this class — the offset (which update to resume from) is tracked by the caller (`KrakenDCA.telegram_loop`).

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
- `add_transaction` — appends and rewrites the whole file (small file, safe). Guarded by a `threading.Lock` since a Telegram-triggered manual buy can now race with the scheduled-buy thread
- `get_statistics(pair)` → `(total_amount, avg_price, last_price, total_spent)`
- `get_last_transaction(pair)` → most recent transaction dict or `None` (used for Telegram `/status`'s last-buy date/price)
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
| `telegram_bot_token` | string | no | Enables the Telegram thread if non-empty. Prefer `TELEGRAM_BOT_TOKEN` env var over storing in the JSON file |
| `telegram_chat_id` | string | no | The only chat the bot will respond to with real data. Prefer `TELEGRAM_CHAT_ID` env var. If empty, the bot only ever replies with the sender's chat ID (onboarding), never portfolio data |

Validation runs on load; startup fails fast with a descriptive error if invalid. `dca_end_date` must be in the future when mode is `lump_sum`. Telegram fields are unvalidated/optional — their absence simply disables the feature (`self.telegram = None`).

---

### `KrakenDCA` — main loop

```
startup
├── show_banner
├── test_connection (exits on failure)
├── print config summary (shows mode, end date or deposit day)
├── if telegram_bot_token set → spawn daemon thread: telegram_loop()
├── display existing portfolio (if transactions exist)
├── execute_buy()            ← immediate buy on startup
└── outer loop (forever, main thread)
    ├── calculate_next_buy() → next_buy_time, hours_between_buys, remaining_hours
    ├── print status summary
    └── inner polling loop
        ├── sleep(poll_interval_seconds)
        ├── if now >= next_buy_time → execute_buy(), break to outer loop
        ├── dip detection → execute_buy() if triggered, recalculate schedule
        └── deposit detection → recalculate schedule if balance increased

telegram_loop() (background daemon thread, runs concurrently with the above)
├── set_my_commands([/status, /buy, /chart, /help])   ← registers the '/' menu in Telegram clients
└── forever
    ├── get_updates(offset)                    ← long-poll, 30s timeout
    └── for each update:
        ├── message present  → handle_telegram_message()
        └── callback_query present → handle_telegram_callback()  (inline button press)
```

**`execute_buy()` (scheduled/dip) and `execute_manual_buy()` (Telegram `/buy`) both delegate order placement to a shared `_place_buy(amount, price, label)` helper** — order submission, transaction recording, and the portfolio-summary print are not duplicated between the two paths.

Because the Telegram thread can trigger a buy at the same moment the main thread does, both `execute_buy` and `execute_manual_buy` wrap their check-and-place section in a shared `self._buy_lock` (a `threading.Lock`). Without it, two concurrent buys could both pass the `max_monthly_amount` check before either recorded its transaction, exceeding the configured cap.

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

## Telegram integration

Enabled only if `telegram_bot_token` (or the `TELEGRAM_BOT_TOKEN` env var) is set. Disabled entirely otherwise — `self.telegram` stays `None` and no thread starts.

### Authorization model

`telegram_chat_id` is the single allowlisted chat. Handled in `handle_telegram_message` / `handle_telegram_callback`:

```python
if not self.config.telegram_chat_id:
    # onboarding: reply with the sender's chat_id only, no portfolio data, no buy capability
    send_message(chat_id, f"Your chat ID is: {chat_id}. Add it to config.json to authorize.")
    return
if str(chat_id) != self.config.telegram_chat_id:
    send_message(chat_id, "Unauthorized.")
    return
```

This means the bot is safe to leave with an empty `telegram_chat_id` while you find your ID — it never leaks data to an unauthorized sender, it only ever discloses the sender's own chat ID (needed to fill in the config).

### Commands

| Command | Behavior |
|---------|----------|
| `/start`, `/help` | Lists available commands |
| `/status` | Builds and sends `build_telegram_status()`: mode, BTC amount, average buy price, last buy date + price, next buy time, current price, P/L% |
| `/buy` | Fetches current price, shows it plus estimated cost, and sends an inline keyboard: `✅ Confirm buy {MIN_BUY_BTC} BTC` / `❌ Cancel` |
| `/chart` | Sends a photo from `build_chart_url()`: cumulative BTC held (left axis) + daily average price + overall average buy price (right axis), aggregated per day |
| `/chart price` | Same as `/chart` but `mode='price'` — omits the BTC-held dataset and left axis entirely, single-axis price-only chart |

### Automatic buy notifications

Every successful buy — scheduled, dip, or manual — triggers a Telegram message, not just `/buy`. `_place_buy()` (the single order-placement path shared by `execute_buy()` and `execute_manual_buy()`) calls `_notify_buy(order_number, amount, price, label)` after recording the transaction:

```python
def _notify_buy(self, order_number, amount, price, label):
    if not (self.telegram and self.config.telegram_chat_id):
        return  # Telegram not configured, or chat_id not yet authorized — no-op
    try:
        self.telegram.send_message(self.config.telegram_chat_id, f"✅ {label.capitalize()} #{order_number}\n...")
    except Exception:
        pass  # best-effort — a Telegram failure must never break the buy that already executed
```

`label` is threaded through from the call site so the notification reads correctly: `execute_buy(reason="scheduled")` (default) or `execute_buy(reason="dip")` from the dip-detection branch, and `"manual buy"` from `execute_manual_buy`. Because this fires from inside `_place_buy`, `execute_manual_buy` no longer sends its own separate "bought" confirmation — that would double-notify the same buy.

### Chart rendering (`build_chart_url`)

No local charting library — the bot builds a Chart.js config as a dict, JSON-encodes and URL-encodes it, and points a [QuickChart.io](https://quickchart.io) URL at it. Telegram's `sendPhoto` accepts that URL directly; Telegram's own servers fetch the image, not the bot.

Key details:
- **Aggregated per calendar day**, not per transaction — with hundreds of dip/scheduled buys, a per-transaction chart would be both unreadable and produce a URL too long to be reliable. Grouping by `tx['date'][:10]` keeps both the image and the URL manageable (tested at ~3.7KB URL for 916 real transactions).
- **Downsampling**: if aggregated days exceed `max_points` (default 60), an even stride selects a subset of indices (always including the last day) so old history doesn't make the chart unreadable either.
- **`mode='full'`** (default): three datasets — `BTC Held` (filled area, left axis `y`), `Daily Avg Price` (right axis `y1`), `Overall Avg Buy Price` (flat dashed reference line on `y1`, from `store.get_statistics()`'s cost-basis average — distinct from the fluctuating daily average).
- **`mode='price'`**: drops the `BTC Held` dataset and the left axis entirely; both price datasets move to the single remaining axis `y`.
- Uses Chart.js v2-style option keys (`yAxes` array, `scaleLabel`, `gridLines`) since that's QuickChart's default rendering version — v3-style `scales.y`/`scales.y1` objects will not render correctly.

### `/buy` confirmation flow (`handle_telegram_callback`)

A single tap can't fire a real order — `/buy` only *shows* a button; a separate button press is required to execute:

```
user sends /buy
  → bot fetches current price, replies with price/cost + inline [Confirm] [Cancel]
user taps a button → Telegram sends a callback_query update
  → handle_telegram_callback:
      1. verify chat_id against telegram_chat_id (same allowlist as messages)
      2. edit_message_reply_markup(chat_id, message_id)   ← strip the buttons immediately,
                                                              so a double-tap can't fire twice
      3. if data == 'buy_confirm': answer_callback_query(...) then execute_manual_buy(chat_id)
      4. if data == 'buy_cancel':  answer_callback_query(...) then send "Buy cancelled."
```

`execute_manual_buy` always buys `KrakenDCA.MIN_BUY_BTC` (0.0001 BTC — Kraken's minimum), not `config.crypto_amount`. It still checks `max_price` and `max_monthly_amount` before placing the order — the button skips the *schedule*, not the safety guards.

### Registering commands with Telegram's native menu

`telegram_loop()` calls `set_my_commands()` once at startup so `/status`, `/buy`, `/chart`, `/help` show up with descriptions when the user taps the `/` icon in Telegram, instead of relying on them remembering command names.

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

**With Telegram enabled, add (either mode):**
```json
{
  "telegram_bot_token": "",
  "telegram_chat_id": "123456789"
}
```
Leave `telegram_bot_token` empty in the JSON file and set `TELEGRAM_BOT_TOKEN` via env var instead — same pattern as the Kraken credentials. `telegram_chat_id` isn't a secret and can live in `config.json`, but `TELEGRAM_CHAT_ID` env var also works if preferred.

---

## Security — what to do and what not to do

### Credentials
- **Never** put `api_key` / `api_secret` / `telegram_bot_token` in `config.json` or any file that gets baked into the Docker image.
- Pass credentials only via environment variables (`KRAKEN_API_KEY`, `KRAKEN_API_SECRET`, `TELEGRAM_BOT_TOKEN`), loaded from a `.env` file that is never committed to git.
- The `.env` file lives only on the production host.
- If a Telegram bot token is ever pasted into chat/logs/an issue, treat it as compromised — regenerate it via @BotFather's `/revoke`.

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
echo "TELEGRAM_BOT_TOKEN=zzz" >> /production/kraken-dca/.env  # optional
touch /production/kraken-dca/transactions.json

# Every code update (transactions.json is never touched)
cp main.py config.json /production/kraken-dca/
cd /production/kraken-dca && docker compose up -d --build
```

---

## Known limitation to fix

`Config._load()` still accepts `api_key`/`api_secret` fields from `config.json` as a fallback. This is a latent risk: if someone adds credentials to the JSON file and rebuilds the image, they get baked in. The fix is to remove those two `config.get('api_key')` / `config.get('api_secret')` fallbacks and hard-require the env vars.
