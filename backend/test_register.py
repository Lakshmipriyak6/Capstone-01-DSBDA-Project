import json
import urllib.request

url = 'http://127.0.0.1:8000/auth/register'
payload = {
    'email': 'mentordemo@example.com',
    'username': 'mentordemo',
    'password': 'Demo@12345',
    'full_name': 'Mentor Demo User'
}
req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print(resp.status)
        print(resp.read().decode('utf-8'))
except Exception as e:
    import sys
    print('ERROR', e)
    if hasattr(e, 'read'):
        try:
            print(e.read().decode())
        except Exception:
            pass
    sys.exit(1)
