#!/usr/bin/env python3
"""Test broker login with correct brokerId using curl_cffi."""
from curl_cffi.requests import Session
import json
import os

base = os.getenv('BROKER_URL', 'https://your-broker-server.com')

# Test with correct brokerId=2
print("--- Login with brokerId=2 ---")
s = Session(impersonate='chrome')

r = s.post(
    f'{base}/manager/mtr-login',
    json={
        'email': os.getenv('BROKER_EMAIL', 'your_email@example.com'),
        'password': os.getenv('BROKER_PASSWORD', 'YOUR_PASSWORD'),
        'brokerId': os.getenv('BROKER_ID', '2'),
    },
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    timeout=15,
)
print(f"Status: {r.status_code}")
ct = r.headers.get('content-type', '')
print(f"Content-Type: {ct}")

if r.status_code == 200:
    data = r.json()
    # Print important fields (mask sensitive tokens)
    print(f"Token: {data.get('token', '')[:20]}...")
    selected = data.get('selectedTradingAccount', {})
    print(f"Trading Account ID: {selected.get('tradingAccountId')}")
    print(f"Trading API Token: {str(selected.get('tradingApiToken', ''))[:20]}...")
    offer = selected.get('offer', {})
    system = offer.get('system', {})
    print(f"System UUID: {system.get('uuid')}")
    print(f"Trading API Domain: {system.get('tradingApiDomain')}")
    print(f"Offer: {offer.get('name')}")
    print(f"Currency: {offer.get('currency')}")
    print(f"Leverage: {selected.get('leverage')}")
    info = data.get('accountInfo', {})
    print(f"Account Name: {info.get('name')}")
    print(f"Account Email: {info.get('email')}")
    
    # Test balance endpoint
    uuid = system.get('uuid')
    trading_domain = system.get('tradingApiDomain', '').strip()
    if trading_domain:
        if not trading_domain.startswith('http'):
            trading_domain = f'https://{trading_domain}'
        api_base = trading_domain
    else:
        api_base = base
    
    balance_url = f'{api_base}/mtr-api/{uuid}/balance'
    print(f"\n--- GET {balance_url} ---")
    
    headers = {
        'Accept': 'application/json',
        'Auth-trading-api': selected.get('tradingApiToken', ''),
        'Cookie': f'co-auth={data.get("token", "")}',
    }
    
    r2 = s.get(balance_url, headers=headers, timeout=15)
    print(f"Status: {r2.status_code}")
    if r2.status_code == 200:
        print(f"Balance: {json.dumps(r2.json(), indent=2)}")
    else:
        print(f"Body: {r2.text[:300]}")

else:
    print(f"Body: {r.text[:500]}")

# Test with wrong brokerId
print("\n--- Login with wrong brokerId ---")
r3 = s.post(
    f'{base}/manager/mtr-login',
    json={
        'email': os.getenv('BROKER_EMAIL', 'your_email@example.com'),
        'password': os.getenv('BROKER_PASSWORD', 'YOUR_PASSWORD'),
        'brokerId': '999999',
    },
    headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    timeout=15,
)
print(f"Status: {r3.status_code}")
print(f"Body: {r3.text[:200]}")
