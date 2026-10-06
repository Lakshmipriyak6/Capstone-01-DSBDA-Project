import json
import urllib.request

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0IiwiZXhwIjoxNzg4MDkxNDMxfQ.e73JPenW4g6r5sItdbhsLe2mnbFDuKdhwzkYEdmGaBQ'
url = 'http://127.0.0.1:8000/auth/me'
req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
