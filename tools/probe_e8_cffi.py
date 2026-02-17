#!/usr/bin/env python3
"""Test E8 Markets API with curl_cffi (browser TLS fingerprint impersonation)."""
from curl_cffi import requests as cffi_requests
import json

base = 'https://mtr.e8markets.com'

print("=" * 60)
print("E8 Markets - curl_cffi (Chrome impersonation)")
print("=" * 60)

# 1. Platform details
print("\n--- GET /manager/platform-details ---")
try:
    r = cffi_requests.get(
        f'{base}/manager/platform-details',
        headers={'Accept': 'application/json'},
        impersonate='chrome',
        timeout=15,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    print(f"Content-Type: {ct}")
    if 'json' in ct:
        print(f"Body: {json.dumps(r.json(), indent=2)}")
    else:
        print(f"Body (first 300): {r.text[:300]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

# 2. Login with dummy creds
print("\n--- POST /manager/mtr-login (dummy creds) ---")
try:
    r = cffi_requests.post(
        f'{base}/manager/mtr-login',
        json={'email': 'test@test.com', 'password': 'testpass123', 'brokerId': '2'},
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
        impersonate='chrome',
        timeout=15,
    )
    print(f"Status: {r.status_code}")
    ct = r.headers.get('content-type', '')
    print(f"Content-Type: {ct}")
    if 'json' in ct:
        print(f"Body: {json.dumps(r.json(), indent=2)[:500]}")
    else:
        print(f"Body (first 300): {r.text[:300]}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Done")
