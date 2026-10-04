#!/usr/bin/env python3
"""
Standalone check: list fiat deposits and withdrawals on the Kraken account
for a given date range and currency. Completely independent of main.py /
the DCA bot — read-only, doesn't touch config.json or transactions.json.

Usage:
    python3 check_chf_transfers.py [START_DATE] [END_DATE] [CURRENCY]
    (dates as YYYY-MM-DD; END_DATE defaults to today; CURRENCY defaults to CHF)

Reads KRAKEN_API_KEY / KRAKEN_API_SECRET from the environment, falling back
to parsing a .env file in the same directory (same as the bot expects).
"""

import os
import sys
import time
import hmac
import hashlib
import base64
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_URL = "https://api.kraken.com"


def asset_codes(currency: str) -> set:
    """Kraken's Ledgers endpoint has been seen to return fiat under both the
    bare code and the legacy Z-prefixed code depending on account/era, so
    accept either."""
    currency = currency.upper()
    return {currency, f"Z{currency}"}


def load_env():
    """Populate os.environ from a local .env file if the vars aren't already set."""
    if os.environ.get('KRAKEN_API_KEY') and os.environ.get('KRAKEN_API_SECRET'):
        return
    env_path = Path(__file__).resolve().parent / '.env'
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        os.environ.setdefault(key.strip(), value.strip())


def sign(urlpath: str, data: dict, secret: str, nonce: str) -> str:
    postdata = urllib.parse.urlencode(data)
    encoded = (nonce + postdata).encode('utf-8')
    message = urlpath.encode('utf-8') + hashlib.sha256(encoded).digest()
    signature = hmac.new(base64.b64decode(secret), message, hashlib.sha512)
    return base64.b64encode(signature.digest()).decode()


def private_request(endpoint: str, api_key: str, api_secret: str, data: dict) -> dict:
    nonce = str(int(time.time() * 1000))
    req_data = dict(data)
    req_data['nonce'] = nonce
    headers = {
        'API-Key': api_key,
        'API-Sign': sign(endpoint, req_data, api_secret, nonce),
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    postdata = urllib.parse.urlencode(req_data).encode('utf-8')
    req = urllib.request.Request(f"{API_URL}{endpoint}", data=postdata, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.loads(response.read().decode('utf-8'))
    if result.get('error'):
        raise Exception(f"Kraken API error: {', '.join(result['error'])}")
    return result['result']


def fetch_ledger_entries(api_key: str, api_secret: str, ledger_type: str, start_ts: float,
                          end_ts: float = None, currency: str = "CHF") -> list:
    """Paginate /0/private/Ledgers for a given type ('deposit' or 'withdrawal'), one currency only.
    No 'asset' filter is passed to the API — Kraken has been inconsistent about whether fiat is
    reported bare or Z-prefixed depending on account/era, so all entries of this type are fetched
    and filtered locally against asset_codes(currency) instead."""
    codes = asset_codes(currency)
    entries = []
    offset = 0
    while True:
        params = {
            'type': ledger_type,
            'start': start_ts,
            'ofs': offset,
        }
        if end_ts is not None:
            params['end'] = end_ts
        result = private_request('/0/private/Ledgers', api_key, api_secret, params)
        ledger = result.get('ledger', {})
        if not ledger:
            break
        for ledger_id, entry in ledger.items():
            if entry.get('asset') in codes:
                entry['ledger_id'] = ledger_id
                entries.append(entry)
        offset += len(ledger)
        if offset >= int(result.get('count', 0)) or len(ledger) < 50:
            break
        time.sleep(1)  # be polite to Kraken's rate limits
    return entries


def main():
    load_env()
    api_key = os.environ.get('KRAKEN_API_KEY')
    api_secret = os.environ.get('KRAKEN_API_SECRET')
    if not api_key or not api_secret:
        print("Error: KRAKEN_API_KEY / KRAKEN_API_SECRET not set (checked environment and .env)")
        sys.exit(1)

    start_date_str = sys.argv[1] if len(sys.argv) > 1 else '2022-01-01'
    end_date_str = sys.argv[2] if len(sys.argv) > 2 else None
    currency = sys.argv[3] if len(sys.argv) > 3 else 'CHF'
    start_dt = datetime.strptime(start_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc)
    start_ts = start_dt.timestamp()
    end_ts = None
    if end_date_str:
        end_ts = datetime.strptime(end_date_str, '%Y-%m-%d').replace(tzinfo=timezone.utc).timestamp()

    range_desc = f"{start_date_str} to {end_date_str}" if end_date_str else f"since {start_date_str}"
    print(f"Fetching {currency.upper()} deposits and withdrawals {range_desc}...\n")

    try:
        deposits = fetch_ledger_entries(api_key, api_secret, 'deposit', start_ts, end_ts, currency)
        withdrawals = fetch_ledger_entries(api_key, api_secret, 'withdrawal', start_ts, end_ts, currency)
    except Exception as e:
        print(f"Error calling Kraken API: {e}")
        sys.exit(1)

    def show(label, entries):
        print(f"--- {label} ({len(entries)}) ---")
        total = 0.0
        for e in sorted(entries, key=lambda x: float(x.get('time', 0))):
            when = datetime.fromtimestamp(float(e['time']), tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
            amount = float(e.get('amount', 0.0))
            total += amount
            print(f"  {when}  {amount:>12.2f} {currency.upper()}  status={e.get('status', '?')}  refid={e.get('refid', '?')}")
        print(f"  {'TOTAL':<28}{total:>12.2f} {currency.upper()}\n")
        return total

    total_deposits = show("Deposits", deposits)
    total_withdrawals = show("Withdrawals", withdrawals)

    print("=== Summary ===")
    print(f"Total deposited:    {total_deposits:>12.2f} {currency.upper()}")
    print(f"Total withdrawn:    {abs(total_withdrawals):>12.2f} {currency.upper()}")
    print(f"Net:                {total_deposits + total_withdrawals:>12.2f} {currency.upper()}")


if __name__ == "__main__":
    main()
