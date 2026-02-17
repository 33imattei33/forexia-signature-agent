#!/usr/bin/env python3
"""Dump the full E8 Markets login response to understand its structure."""
from curl_cffi.requests import Session
import json, sys

base = 'https://mtr.e8markets.com'

# Read credentials from settings.json
with open('settings.json') as f:
    settings = json.load(f)
email = settings['broker']['matchtrader_login']
password = settings['broker']['matchtrader_password']
print(f"Email: {email}")
print(f"Password: {'*' * len(password)}")

s = Session(impersonate='chrome')

r = s.post(
    f'{base}/manager/mtr-login',
    json={'email': email, 'password': password, 'brokerId': '2'},
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    timeout=15,
)
print(f"\nStatus: {r.status_code}")
print(f"Content-Type: {r.headers.get('content-type', '')}")

if r.status_code == 200:
    data = r.json()
    # Print full structure with keys at each level
    print(f"\n=== TOP-LEVEL KEYS ===")
    for k, v in data.items():
        vtype = type(v).__name__
        if isinstance(v, str):
            print(f"  {k}: ({vtype}) {v[:80]}{'...' if len(v) > 80 else ''}")
        elif isinstance(v, (int, float, bool)):
            print(f"  {k}: ({vtype}) {v}")
        elif isinstance(v, list):
            print(f"  {k}: ({vtype}) len={len(v)}")
        elif isinstance(v, dict):
            print(f"  {k}: ({vtype}) keys={list(v.keys())}")
        elif v is None:
            print(f"  {k}: None")
        else:
            print(f"  {k}: ({vtype})")

    # Dump important sub-objects
    if 'selectedTradingAccount' in data:
        print(f"\n=== selectedTradingAccount ===")
        print(json.dumps(data['selectedTradingAccount'], indent=2, default=str)[:2000])
    else:
        print(f"\n!!! No 'selectedTradingAccount' key !!!")

    if 'tradingAccounts' in data:
        print(f"\n=== tradingAccounts ===")
        accts = data['tradingAccounts']
        print(f"Count: {len(accts)}")
        if accts:
            print(json.dumps(accts[0], indent=2, default=str)[:2000])
    else:
        print(f"\n!!! No 'tradingAccounts' key !!!")

    # Dump full response (truncated)
    print(f"\n=== FULL RESPONSE (truncated) ===")
    full = json.dumps(data, indent=2, default=str)
    print(full[:5000])
    if len(full) > 5000:
        print(f"... ({len(full)} total chars)")
else:
    print(f"\nBody: {r.text[:1000]}")
