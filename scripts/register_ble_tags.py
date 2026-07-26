#!/usr/bin/env python3
"""Register BLE ear tags for all Loch Vaal animals."""
import requests
import json
import sys

api = 'http://localhost:8000'
farm_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'

# Login
resp = requests.post(f'{api}/api/auth/login', json={
    'email': 'africa.mydrive@gmail.com', 'password': 'demo123'
})
token = resp.json()['access_token']
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}

# Get Loch Vaal animals
resp = requests.get(f'{api}/api/animals?farm_id={farm_id}', headers=headers)
animals = resp.json()
print(f'Found {len(animals)} Loch Vaal animals')

# Register a BLE tag for each
macs = [
    'A1:B2:C3:D4:E5:01', 'A1:B2:C3:D4:E5:02', 'A1:B2:C3:D4:E5:03',
    'A1:B2:C3:D4:E5:04', 'A1:B2:C3:D4:E5:05', 'A1:B2:C3:D4:E5:06',
    'A1:B2:C3:D4:E5:07', 'A1:B2:C3:D4:E5:08', 'A1:B2:C3:D4:E5:09',
    'A1:B2:C3:D4:E5:10',
]

registered = 0
for i, animal in enumerate(animals[:10]):
    tag_data = {
        'farm_id': farm_id,
        'animal_id': animal['id'],
        'mac_address': macs[i],
        'tag_name': f"Tag-{animal['name']}",
    }
    r = requests.post(f'{api}/api/gateway/tags', json=tag_data, headers=headers)
    if r.status_code in (201, 409):
        registered += 1
        status = 'registered' if r.status_code == 201 else 'exists'
        print(f'  {macs[i]} -> {animal["name"]} ({status})')
    else:
        print(f'  FAILED {macs[i]}: {r.status_code} {r.text[:80]}')

print(f'\n{registered}/10 BLE tags ready')
