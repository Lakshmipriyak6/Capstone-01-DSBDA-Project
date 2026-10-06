import json
import urllib.request
import urllib.parse
import http.client

# login to get token
login_url = 'http://127.0.0.1:8000/auth/login'
login_payload = json.dumps({'email':'mentordemo@example.com','password':'Demo@12345'}).encode('utf-8')
req = urllib.request.Request(login_url, data=login_payload, headers={'Content-Type':'application/json'}, method='POST')
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode('utf-8'))
    token = data['access_token']

# upload file
upload_url = 'http://127.0.0.1:8000/documents/upload'
boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
headers = {
    'Authorization': f'Bearer {token}',
}
from pathlib import Path
file_path = Path('test_upload.pdf')
with open(file_path, 'rb') as f:
    file_bytes = f.read()

body = []
body.append(f'--{boundary}')
body.append('Content-Disposition: form-data; name="file"; filename="test_upload.pdf"')
body.append('Content-Type: application/pdf')
body.append('')
body_bytes = '\r\n'.join(body).encode('utf-8') + b'\r\n' + file_bytes + b'\r\n' + f'--{boundary}--\r\n'.encode('utf-8')

req = urllib.request.Request(upload_url, data=body_bytes, headers=headers)
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
with urllib.request.urlopen(req) as resp:
    print(resp.status)
    print(resp.read().decode('utf-8'))
