import sys

file_path = '/etc/nginx/sites-available/mcq-portal'
with open(file_path, 'r') as f:
    text = f.read()

target = """server {
    if ($host = mcq-platform.duckdns.org) {
        return 301 https://$host$request_uri;
    } # managed by Certbot


    listen 80;
    listen [::]:80;
    server_name mcq-platform.duckdns.org;
    return 404; # managed by Certbot


}"""

replacement = """server {
    listen 80;
    listen [::]:80;
    server_name mcq-platform.duckdns.org;

    location / {
        if ($host = mcq-platform.duckdns.org) {
            return 301 https://$host$request_uri;
        }
        return 200 "OK";
    }
}"""

idx = text.rfind('server {')
if idx != -1:
    text = text[:idx] + replacement + '\n'
    with open(file_path, 'w') as f:
        f.write(text)
    print('REPLACED_SUCCESSFULLY')
else:
    print('FAILED_TO_FIND_SERVER_BLOCK')
