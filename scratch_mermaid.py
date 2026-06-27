import base64
import urllib.request
import json

mermaid_code = """graph TB
    subgraph Public_Internet [Public Internet]
        User[Student Browser]
        Admin[Administrator Client]
    end

    subgraph AWS_VPC [Custom VPC: 10.0.0.0/16]
        subgraph Public_Subnets [Public Subnets: AZ-A & AZ-B]
            ALB[Application Load Balancer: Port 80/443]
            EC2[EC2 App Server: Nginx & Gunicorn: Port 80/443/22]
        end

        subgraph Private_Subnets [Private Subnets: AZ-A & AZ-B]
            RDS[(Private AWS RDS MySQL DB: Port 3306)]
        end
    end

    subgraph External_Integrations [External Services]
        S3[AWS S3 Backup Bucket]
        GitHub[GitHub Actions Runner]
    end

    User -->|HTTPS: 443| ALB
    Admin -->|HTTPS: 443| ALB
    ALB -->|HTTP: 80| EC2
    Admin -->|SSH: 22| EC2
    EC2 -->|MySQL Protocol: 3306| RDS
    EC2 -->|Daily Logical Dump| S3
    GitHub -->|SSH CD Deployment| EC2"""

# Create the JSON structure required by mermaid.live/mermaid.ink
config = {
    "code": mermaid_code,
    "mermaid": {"theme": "default"},
    "updateEditor": False,
    "autoSync": True,
    "updateDiagram": False
}

# Encode to base64
json_str = json.dumps(config)
json_bytes = json_str.encode('utf-8')
base64_bytes = base64.b64encode(json_bytes)
base64_string = base64_bytes.decode('utf-8')

# The URL format for mermaid.ink
url = f"https://mermaid.ink/img/{base64_string}"

print(f"Fetching URL: {url}")
try:
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    with urllib.request.urlopen(req, timeout=15) as response:
        with open("c:\\Desktop\\mcq-portal\\devops\\architecture_diagram.png", "wb") as f:
            f.write(response.read())
    print("Success! Image saved to devops\\architecture_diagram.png")
except Exception as e:
    print(f"Error fetching image: {e}")
