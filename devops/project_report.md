# MCQ Battle Platform: Comprehensive Academic Project Report

This document serves as the complete academic project report package for the final submission of the MCQ Battle Platform. It covers the system architecture, security implementation, deployment guide, CI/CD automated pipeline, unified monitoring configuration, and live application walkthrough with production screenshots.

---

## 1. System Architecture

The MCQ Battle Platform is built upon a secure, highly available, multi-tier cloud infrastructure deployed inside a custom AWS Virtual Private Cloud (VPC) in the `ap-south-2` (Hyderabad) region. The architecture is designed to prevent direct external access to private data layers while offering a fast, secured web entry gateway for students.

```mermaid
graph TB
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
    GitHub -->|SSH CD Deployment| EC2
```

### Architectural Component Details

#### 1. Custom VPC (`vpc-035e3ef8d9ca6cb6a`)
* **CIDR Block**: `10.0.0.0/16`
* **Subnet Segmentation**: 
  * **Public Subnets**: `10.0.1.0/24` (AZ-A) and `10.0.2.0/24` (AZ-B). These host public-facing interfaces like the Application Load Balancer and the EC2 application instance.
  * **Private Subnets**: `10.0.10.0/24` (AZ-A) and `10.0.20.0/24` (AZ-B). These subnets are fully isolated and contain no routes to the AWS Internet Gateway.
* **Internet Access**: Public subnets connect outward to the AWS Internet Gateway (`mcq-igw`). Private subnets are entirely isolated, preventing direct ingress or egress database traffic, which eliminates NAT Gateway hosting fees.

#### 2. Private Database Tier (AWS RDS MySQL)
* **Instance ID**: `mcq-battle-db`
* **Engine & Specs**: MySQL Community Edition on a `db.t4g.micro` database instance.
* **Network Isolation**: Placed strictly within the private subnets. It has no public IP address and cannot resolve internet routes.
* **Security Group Policy**: Restricts incoming MySQL traffic (port `3306`) solely to connections originating from the EC2 web server security group (`mcq-web-sg`).

#### 3. Frontend & Application Tier (EC2 App Server)
* **Instance ID**: `i-0b8314695dc63d98` (Named `mcq-app-server`)
* **Operating System**: Ubuntu Server 22.04 LTS.
* **Hosting Stack**: 
  * **Nginx Reverse Proxy**: Directs incoming public web requests. It serves the static frontend directly from `/home/ubuntu/mcq-portal/frontend` and proxies dynamic API traffic (under `/api/`) to the backend application server.
  * **Gunicorn WSGI Server**: Hosts the Flask python backend application locally on port `5000` with multiple worker processes.
  * **Systemd**: Standardizes Gunicorn lifecycle management as a persistent background service.

#### 4. Load Balancer & DNS
* **AWS Application Load Balancer (`mcq-alb`)**: Deployed across the public subnets to act as the primary SSL termination and reverse proxy endpoint.
* **Target Group (`mcq-web-tg`)**: Automatically monitors and registers the EC2 instance on Port 80.
* **DNS Configuration**: The domain `mcq-platform.duckdns.org` points directly to the system's public entry point for routing.

---

## 2. Cyber Security Documentation

The platform implements multi-layered security controls to protect student data, session integrity, and infrastructure nodes.

| Threat / Vulnerability | Mitigation Strategy | Implementation Location |
| :--- | :--- | :--- |
| **Password Compromise** | Memory-hard password hashing using `scrypt` | `[auth.py](file:///c:/Desktop/mcq-portal/backend/blueprints/auth.py)` |
| **Data in Transit Eavesdropping** | Full-session SSL/TLS encryption with enforced HSTS | `[mcq-portal.conf](file:///c:/Desktop/mcq-portal/devops/nginx/mcq-portal.conf)` |
| **Session Hijacking (XSS/CSRF)** | HttpOnly, Secure, SameSite JWT Cookies | `[config.py](file:///c:/Desktop/mcq-portal/backend/config.py)` |
| **SQL Injection (SQLi)** | Parameterized database queries via SQLAlchemy ORM | `[models.py](file:///c:/Desktop/mcq-portal/backend/models.py)` / Blueprints |
| **Brute-Force / DoS** | Custom rate limiting and SSH intrusion prevention | `[auth.py](file:///c:/Desktop/mcq-portal/backend/blueprints/auth.py)` / Fail2ban |

### 1. Memory-Hard Password Hashing (scrypt)
* **Mechanism**: When a student registers, their password is processed using the `scrypt` algorithm (`generate_password_hash` via Werkzeug).
* **Technical Advantage**: Unlike legacy hash algorithms (MD5, SHA1) or standard bcrypt, scrypt is specifically designed to be highly memory-hard and computationally expensive. This drastically increases the cost of executing offline brute-force and dictionary attacks using GPU or ASIC hardware.

### 2. HTTPS Transport Encryption & HSTS
* **Mechanism**: Standardized on Let's Encrypt certificates.
* **Enforced Redirection**: Nginx automatically redirects all standard HTTP (Port 80) connections to HTTPS (Port 443) with HTTP Status Code `301`.
* **HSTS Configuration**: Enforces HTTP Strict Transport Security (HSTS) headers:
  ```nginx
  add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
  ```
  This instructs user browsers to automatically upgrade all requests to HTTPS and blocks any unencrypted fallbacks.

### 3. JWT Sessions & Hardened Cookies
* **Mechanism**: JWT tokens handle stateless sessions. The backend writes these tokens directly to client cookies rather than using standard local storage.
* **Hardening Parameters**:
  * **`HttpOnly`**: Set to `True`. Prevents JavaScript engines from reading the cookie, blocking token extraction via Cross-Site Scripting (XSS).
  * **`SameSite`**: Set to `Lax`. Prevents cross-site cookie transmission, securing the session against Cross-Site Request Forgery (CSRF).
  * **`Secure`**: `JWT_COOKIE_SECURE = True` is configured in `[config.py](file:///c:/Desktop/mcq-portal/backend/config.py)`. The browser will refuse to transmit the session cookie over an unencrypted channel.

### 4. Parameterized SQL Queries (SQLAlchemy ORM)
* **Mechanism**: Database interactions are built using SQLAlchemy ORM abstractions instead of concatenating raw SQL strings.
* **Technical Advantage**: SQLAlchemy compiles statements using parameterized queries. Even if an attacker inputs SQL syntax in registration or dashboard forms, the database engine treats the input as literal values rather than executable code, eliminating SQL Injection vulnerabilities.

### 5. XSS & Clickjacking Protection Headers
* **Mechanism**: Nginx injects specialized security headers into every web response:
  ```nginx
  add_header X-Frame-Options "SAMEORIGIN" always;
  add_header X-XSS-Protection "1; mode=block" always;
  add_header X-Content-Type-Options "nosniff" always;
  ```
* **Impact**: Blocks frame-embedding (preventing clickjacking) and locks down MIME types to prevent content sniffing attacks.

### 6. Custom API Rate Limiting Decorator
* **Mechanism**: A lightweight python decorator (`@rate_limit`) restricts requests based on client IP addresses using an in-memory dictionary.
* **Applied Endpoints**: Placed on `/login` and `/register` endpoints.
* **Limit**: Maximum 5 attempts per minute. Excess attempts trigger an HTTP `429 Too Many Requests` response, blocking credential-stuffing and login dictionary scripts.

---

## 3. Step-by-Step Deployment Guide & CI/CD Pipeline

### Host Package Setup
Update host repositories and install core services on the EC2 Ubuntu server:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev git nginx mysql-client fail2ban awscli
```

### Git Repository Cloning & Virtual Environment
```bash
cd /home/ubuntu
git clone https://github.com/JerinAppus/mcq-portal.git mcq-portal
cd mcq-portal
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### Environment Variable Setup (`.env`)
```bash
cp .env.example .env
nano .env
```
Inside the file:
```ini
SECRET_KEY=secure-random-string
JWT_SECRET_KEY=secure-random-jwt-string
FLASK_ENV=production
DATABASE_URL=mysql+pymysql://admin_db_user:password@mcq-battle-db.c12345.ap-south-2.rds.amazonaws.com:3306/mcqdb
S3_BACKUP_BUCKET=mcq-production-backups-s3
```

### Systemd Backend Service Creation
Create the service configuration file `/etc/systemd/system/mcq.service`:
```ini
[Unit]
Description=MCQ Battle Platform Backend Flask Service (Gunicorn)
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/mcq-portal
EnvironmentFile=/home/ubuntu/mcq-portal/.env
ExecStart=/home/ubuntu/mcq-portal/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:5000 run:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start mcq
sudo systemctl enable mcq
```

### Nginx Reverse Proxy Deployment
Copy and symlink the Nginx configuration to direct static and API requests:
```bash
sudo cp devops/nginx/mcq-portal.conf /etc/nginx/sites-available/mcq-portal
sudo ln -s /etc/nginx/sites-available/mcq-portal /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### Let's Encrypt SSL Installation
Run Certbot to secure Nginx with automatic HTTPS certificates:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d mcq-platform.duckdns.org
```

### S3 Logical Database Backups (`backup.sh`)
An automated shell script performs logical database dumps and uploads compressed files to S3:
```bash
chmod +x devops/scripts/backup.sh
```
Configure cron to run this script daily at 2:00 AM:
```bash
crontab -e
# Add the following line:
0 2 * * * /home/ubuntu/mcq-portal/devops/scripts/backup.sh > /dev/null 2>&1
```

---

### CI/CD Pipeline Configuration (GitHub Actions)

The repository integrates a robust GitHub Actions workflow in `.github/workflows/deploy.yml` that automates deployment to the EC2 server upon code updates.

```yaml
name: Deploy MCQ Battle Platform to AWS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Deploy via SSH
        uses: appleboy/ssh-action@master
        with:
          host: 18.61.65.36
          username: ubuntu
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /home/ubuntu/mcq-portal
            git stash -u
            git pull origin main
            source venv/bin/activate
            pip install -r requirements.txt
            sudo systemctl restart mcq
            sudo systemctl reload nginx
```

---

## 4. Production Monitoring & Log Auditing Setup

To ensure operational integrity and detect unauthorized access attempts, the system utilizes a unified monitoring and logging strategy.

### 1. Active Target Group Health Checks
The AWS Application Load Balancer executes periodic HTTP health checks on `/` (Port 80) every 30 seconds. A `200 OK` response maintains the **`Healthy`** green shield status.

### 2. Intrusion Prevention via Fail2ban
`fail2ban` is deployed on the EC2 host. It scans `/var/log/auth.log` for anomalous SSH connection patterns. If an IP address fails to authenticate more than 4 times within a 10-minute window, the host firewall blocks the offending IP address for 1 hour.
* **Monitor Active Bans**:
  ```bash
  sudo fail2ban-client status sshd
  ```

### 3. Unified Journal Log Streams
All backend print, warning, error, and runtime outputs are handled by systemd's unified logging.
* **Tail Live Output**:
  ```bash
  sudo journalctl -u mcq -f
  ```
* **Filter Security Violations**: Failed authentication attempts write a special warning flag to the logs. Query these alerts with:
  ```bash
  sudo journalctl -u mcq -g "SECURITY ALERT" --no-pager
  ```

---

## 5. Live Application Tour & Screenshots

Below are screenshots capturing the live production state and the student and administrator functional modules of the MCQ Battle Platform.

### 1. AWS Target Group Health Status
Shows the registered EC2 application host within the target group displaying a healthy status.

![AWS Target Group Status](file:///C:/Users/jerin/.gemini/antigravity/brain/9d5202b6-d2ee-4523-9c43-6d253b127df2/media__1780026244552.jpg)

### 2. Unified Student Dashboard
Shows the primary dashboard where students view their live streaks, practice metrics, total XP score, and standings.

![Student Dashboard Panel](file:///C:/Users/jerin/.gemini/antigravity/brain/9d5202b6-d2ee-4523-9c43-6d253b127df2/media__1780026321969.png)

### 3. Administrator Question Management Panel
The admin interface allows lecturers or administrators to add, edit, and delete MCQs, select categories, and manage answer configurations.

![Admin MCQ CRUD Dashboard](file:///C:/Users/jerin/.gemini/antigravity/brain/9d5202b6-d2ee-4523-9c43-6d253b127df2/media__1780026508088.png)

### 4. PDF Question Parsing Engine
Demonstrates the dynamic text extraction module that parses bulk question banks from PDF handouts directly into the relational MySQL database.

![PDF Question Upload Panel](file:///C:/Users/jerin/.gemini/antigravity/brain/9d5202b6-d2ee-4523-9c43-6d253b127df2/media__1780026617264.png)
