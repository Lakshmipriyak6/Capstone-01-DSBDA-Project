import json, urllib.request
login_url = 'http://127.0.0.1:8000/auth/login'
login_payload = json.dumps({'email':'mentordemo@example.com','password':'Demo@12345'}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_payload, headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req) as resp:
    token = json.loads(resp.read().decode())['access_token']
headers = {'Authorization': f'Bearer {token}'}
for ep in ['/analytics/overview','/analytics/topics','/analytics/similarity','/analytics/clusters','/analytics/knowledge-graph','/analytics/trends','/analytics/outliers','/analytics/activity']:
    req = urllib.request.Request('http://127.0.0.1:8000'+ep, headers=headers)
    with urllib.request.urlopen(req) as resp:
        print(ep, resp.status)
        data = resp.read().decode()
        print(data[:800])
