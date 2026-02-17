#!/usr/bin/env python3
"""Probe E8 Markets MatchTrader API endpoints to diagnose connection issues."""
import httpx
import json
import sys

base = 'https://mtr.e8markets.com'

print("=" * 60)
print("E8 Markets API Probe")
print("=" * 60)

# 1. Platform Details (public, no auth)
print("\n--- 1. GET /manager/platform-details ---")
try:
    r = httpx.get(
        f'{base}/manager/platform-details',
        headers={'Accept': 'application/json', 'User-Agent': 'ForexiaAgent/1.0'},
        timeout=15,
        follow_redirects=True,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    print(f"Content-Type: {ct}")
    if 'json' in ct:
        print(f"Body: {json.dumps(r.json(), indent=2)}")
    else:
        body = r.text[:500]
        is_cf = 'cloudflare' in body.lower() or 'cf-' in str(r.headers).lower() or 'challenge' in body.lower()
        print(f"Cloudflare challenge: {is_cf}")
        print(f"Body (first 300): {body[:300]}")
except Exception as e:
    print(f"Error: {e}")

# 2. Login attempt with dummy creds
print("\n--- 2. POST /manager/mtr-login (dummy creds) ---")
try:
    r = httpx.post(
        f'{base}/manager/mtr-login',
        json={'email': 'test@test.com', 'password': 'testpass123', 'brokerId': '2'},
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'ForexiaAgent/1.0',
        },
        timeout=15,
        follow_redirects=True,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    print(f"Content-Type: {ct}")
    if 'json' in ct:
        print(f"Body: {json.dumps(r.json(), indent=2)[:500]}")
    else:
        body = r.text[:500]
        is_cf = 'cloudflare' in body.lower() or 'challenge' in body.lower() or 'cf_chl' in body
        print(f"Cloudflare challenge: {is_cf}")
        print(f"Body (first 300): {body[:300]}")
    # Check CF headers
    cf_headers = {k: v for k, v in r.headers.items() if 'cf-' in k.lower() or 'cloudflare' in k.lower()}
    if cf_headers:
        print(f"Cloudflare headers: {cf_headers}")
except Exception as e:
    print(f"Error: {e}")

# 3. Check if there's a different API domain
print("\n--- 3. Alternative API domains ---")
alt_domains = [
    'https://mtr-api.e8markets.com',
    'https://api.e8markets.com',
    'https://trading.e8markets.com',
    'https://platform.e8markets.com',
]
for domain in alt_domains:
    try:
        r = httpx.get(
            f'{domain}/manager/platform-details',
            headers={'Accept': 'application/json', 'User-Agent': 'ForexiaAgent/1.0'},
            timeout=8,
            follow_redirects=True,
        )
        ct = r.headers.get('content-type', '')
        if 'json' in ct:
            print(f"  {domain}: {r.status_code} JSON -> {r.json()}")
        else:
            is_cf = 'challenge' in r.text[:200].lower()
            print(f"  {domain}: {r.status_code} (CF={is_cf})")
    except httpx.ConnectError:
        print(f"  {domain}: CONNECTION REFUSED")
    except httpx.ConnectTimeout:
        print(f"  {domain}: TIMEOUT")
    except Exception as e:
        print(f"  {domain}: {type(e).__name__}: {e}")

# 4. Try the demo/sandbox server (should work without Cloudflare)
print("\n--- 4. Match-Trader Demo (sandbox) ---")
demo = 'https://mtr-demo-prod.match-trader.com'
try:
    r = httpx.get(
        f'{demo}/manager/platform-details',
        headers={'Accept': 'application/json'},
        timeout=15,
        follow_redirects=True,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    if 'json' in ct:
        print(f"Body: {json.dumps(r.json(), indent=2)}")
    else:
        print(f"Content-Type: {ct}")
        print(f"Body (first 200): {r.text[:200]}")
except Exception as e:
    print(f"Error: {e}")

# 5. Try the demo login
print("\n--- 5. Demo login attempt ---")
try:
    r = httpx.post(
        f'{demo}/manager/mtr-login',
        json={'email': 'test@test.com', 'password': 'testpass123', 'brokerId': '0'},
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        timeout=15,
        follow_redirects=True,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    if 'json' in ct:
        body = json.dumps(r.json(), indent=2)
        print(f"Body: {body[:400]}")
    else:
        print(f"Content-Type: {ct}")
        print(f"Body (first 300): {r.text[:300]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("Probe complete")
