#!/usr/bin/env python3
"""Check curl_cffi async API and 401 body format."""
from curl_cffi import requests as cffi_requests
import json

base = 'https://mtr.e8markets.com'

# Check 401 body raw
print("--- 401 body raw ---")
r = cffi_requests.post(
    f'{base}/manager/mtr-login',
    json={'email': 'test@test.com', 'password': 'testpass123', 'brokerId': '2'},
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    impersonate='chrome',
    timeout=15,
)
print(f"Status: {r.status_code}")
print(f"Raw body: {repr(r.text)}")
print(f"Headers: {dict(r.headers)}")

# Check curl_cffi async module
print("\n--- curl_cffi async API check ---")
try:
    from curl_cffi.requests import AsyncSession
    print("AsyncSession available")
except ImportError:
    print("AsyncSession NOT available")

import asyncio

async def test_async():
    async with AsyncSession(impersonate='chrome') as s:
        r = await s.get(f'{base}/manager/platform-details', headers={'Accept': 'application/json'})
        print(f"Async GET status: {r.status_code}")
        if r.status_code == 200:
            print(f"Async body: {r.json()}")

asyncio.run(test_async())
print("Async works!")
