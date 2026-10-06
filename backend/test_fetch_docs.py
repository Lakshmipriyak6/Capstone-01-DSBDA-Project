import json, urllib.request
login_url = 'http://127.0.0.1:8000/auth/login'
login_payload = json.dumps({'email':'mentordemo@example.com','password':'Demo@12345'}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_payload, headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())['access_token']
req = urllib.request.Request('http://127.0.0.1:8000/documents', headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode())
