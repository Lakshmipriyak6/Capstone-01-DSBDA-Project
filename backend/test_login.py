import json
import urllib.request

url = 'http://127.0.0.1:8000/auth/login'
payload = {'email': 'mentordemo@example.com', 'password': 'Demo@12345'}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
