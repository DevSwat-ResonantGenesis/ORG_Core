#!/bin/bash
# Production Firewall Setup for DigitalOcean Droplet
# Configures UFW firewall with security hardening

set -e

echo "🔥 Production Firewall Configuration"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ This script must be run as root (sudo)${NC}"
    exit 1
fi

echo "🛡️  Configuring UFW firewall rules..."

# Reset existing rules
ufw --force reset

# Default policies - DENY everything by default
ufw default deny incoming
ufw default allow outgoing
ufw default deny forwarded

# Allow SSH (with rate limiting)
ufw limit ssh comment 'Rate limited SSH'

# Allow HTTP/HTTPS (web traffic)
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Allow Docker networks (internal)
ufw allow from 172.16.0.0/12 comment 'Docker internal networks'
ufw allow from 172.17.0.0/12 comment 'Docker bridge networks'
ufw allow from 172.18.0.0/12 comment 'Docker custom networks'
ufw allow from 172.19.0.0/12 comment 'Docker custom networks'
ufw allow from 172.20.0.0/12 comment 'Docker custom networks'
ufw allow from 172.21.0.0/12 comment 'Docker custom networks'
ufw allow from 172.22.0.0/12 comment 'Docker custom networks'
ufw allow from 172.23.0.0/12 comment 'Docker custom networks'
ufw allow from 172.24.0.0/12 comment 'Docker custom networks'
ufw allow from 172.25.0.0/12 comment 'Docker custom networks'
ufw allow from 172.26.0.0/12 comment 'Docker custom networks'
ufw allow from 172.27.0.0/12 comment 'Docker custom networks'
ufw allow from 172.28.0.0/12 comment 'Docker custom networks'
ufw allow from 172.29.0.0/12 comment 'Docker custom networks'
ufw allow from 172.30.0.0/12 comment 'Docker custom networks'
ufw allow from 172.31.0.0/12 comment 'Docker custom networks'

# Allow localhost/loopback
ufw allow from 127.0.0.0/8 comment 'Localhost'

# Allow specific monitoring IPs (replace with your monitoring server IPs)
# ufw allow from YOUR_MONITORING_IP to any port 9100 comment 'Prometheus monitoring'
# ufw allow from YOUR_MONITORING_IP to any port 9090 comment 'Grafana access'

# Block common attack vectors
ufw deny 23/tcp comment 'Block Telnet'
ufw deny 21/tcp comment 'Block FTP'
ufw deny 25/tcp comment 'Block SMTP (except through relay)'
ufw deny 53/tcp comment 'Block DNS (TCP)'
ufw deny 110/tcp comment 'Block POP3'
ufw deny 143/tcp comment 'Block IMAP'
ufw deny 993/tcp comment 'Block IMAPS'
ufw deny 995/tcp comment 'Block POP3S'

# Rate limiting for web services
ufw limit 80/tcp comment 'Rate limited HTTP'
ufw limit 443/tcp comment 'Rate limited HTTPS'

# Enable logging
ufw logging on

# Enable firewall
ufw --force enable

echo ""
echo -e "${GREEN}✅ Firewall configured successfully!${NC}"
echo ""

# Show status
echo "📊 Current firewall status:"
ufw status verbose

echo ""
echo -e "${YELLOW}🔥 Firewall Rules Summary:${NC}"
echo "  ✅ SSH (rate limited)"
echo "  ✅ HTTP/HTTPS (rate limited)"
echo "  ✅ Docker internal networks"
echo "  ✅ Localhost access"
echo "  ❌ All other incoming traffic"
echo "  ❌ Common attack ports blocked"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "1. Test SSH access before closing this session"
echo "2. Add your monitoring server IPs if needed"
echo "3. Consider fail2ban for additional protection"
echo "4. Regularly check: ufw status"
echo ""

# Create fail2ban configuration
echo "🔧 Setting up fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = ssh
logpath = %(sshd_log)s
maxretry = 3
bantime = 3600

[nginx-http-auth]
enabled = true
port = http,https
logpath = %(nginx_error_log)s
maxretry = 5
bantime = 1800

[nginx-limit-req]
enabled = true
port = http,https
logpath = %(nginx_error_log)s
maxretry = 10
bantime = 600

[nginx-botsearch]
enabled = true
port = http,https
logpath = %(nginx_access_log)s
maxretry = 2
bantime = 86400
EOF

# Restart fail2ban
systemctl restart fail2ban
systemctl enable fail2ban

echo ""
echo -e "${GREEN}✅ Fail2ban configured and enabled${NC}"
echo ""
echo "🔍 Monitor bans with: fail2ban-client status sshd"
