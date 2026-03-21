#!/bin/bash

# SSL Certificate Setup Script for Production
# Sets up Let's Encrypt SSL certificates for dev-swat.com

set -e

echo "=========================================="
echo "🔒 SSL Certificate Setup for Production"
echo "=========================================="
echo ""

# Configuration
DOMAIN="dev-swat.com"
EMAIL="info@dev-swat.com"
WEBROOT="/var/www/certbot"
NGINX_CONF="/etc/nginx/sites-available"
SSL_PATH="/etc/letsencrypt/live/$DOMAIN"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "INFO")
            echo -e "${BLUE}ℹ️  $message${NC}"
            ;;
    esac
}

# Function to check if running on production server
check_production_server() {
    if [ ! -f "/etc/nginx/sites-available" ]; then
        print_status "ERROR" "This script must be run on the production server"
        exit 1
    fi
}

# Function to install Certbot
install_certbot() {
    print_status "INFO" "Installing Certbot..."
    
    # Update package list
    apt-get update
    
    # Install Certbot and Nginx plugin
    apt-get install -y certbot python3-certbot-nginx
    
    print_status "SUCCESS" "Certbot installed successfully"
}

# Function to create webroot directory
create_webroot() {
    print_status "INFO" "Creating webroot directory..."
    
    mkdir -p $WEBROOT
    chown -R www-data:www-data $WEBROOT
    chmod -R 755 $WEBROOT
    
    print_status "SUCCESS" "Webroot directory created"
}

# Function to setup Nginx for SSL
setup_nginx_ssl() {
    print_status "INFO" "Setting up Nginx for SSL..."
    
    # Create Nginx sites-available directory if it doesn't exist
    mkdir -p /etc/nginx/sites-available
    
    # Copy fixed Nginx configuration
    cp /app/nginx/nginx-production-https-fixed.conf /etc/nginx/sites-available/$DOMAIN
    
    # Create symlink to sites-enabled
    ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/
    
    # Remove default site
    rm -f /etc/nginx/sites-enabled/default
    
    # Test Nginx configuration
    nginx -t
    
    print_status "SUCCESS" "Nginx SSL configuration setup"
}

# Function to obtain SSL certificate
obtain_ssl_certificate() {
    print_status "INFO" "Obtaining SSL certificate for $DOMAIN..."
    
    # Obtain SSL certificate
    certbot --nginx -d $DOMAIN -d www.$DOMAIN --email $EMAIL --agree-tos --non-interactive --webroot-path=$WEBROOT
    
    print_status "SUCCESS" "SSL certificate obtained"
}

# Function to setup auto-renewal
setup_auto_renewal() {
    print_status "INFO" "Setting up auto-renewal..."
    
    # Add certbot renewal cron job
    (crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -
    
    print_status "SUCCESS" "Auto-renewal setup complete"
}

# Function to verify SSL certificate
verify_ssl_certificate() {
    print_status "INFO" "Verifying SSL certificate..."
    
    if [ -f "$SSL_PATH/fullchain.pem" ] && [ -f "$SSL_PATH/privkey.pem" ]; then
        print_status "SUCCESS" "SSL certificate files found"
        
        # Check certificate expiration
        openssl x509 -in $SSL_PATH/fullchain.pem -noout -dates
        
        # Test SSL configuration
        nginx -t
        
        # Restart Nginx
        systemctl reload nginx
        
        print_status "SUCCESS" "SSL certificate verified and Nginx reloaded"
    else
        print_status "ERROR" "SSL certificate files not found"
        exit 1
    fi
}

# Function to test SSL configuration
test_ssl() {
    print_status "INFO" "Testing SSL configuration..."
    
    # Test SSL certificate
    curl -I https://$DOMAIN
    
    # Test SSL security
    curl -I https://www.$DOMAIN
    
    print_status "SUCCESS" "SSL configuration tested"
}

# Main execution
main() {
    print_status "INFO" "Starting SSL certificate setup for $DOMAIN"
    
    # Check if running on production server
    check_production_server
    
    # Install Certbot
    install_certbot
    
    # Create webroot directory
    create_webroot
    
    # Setup Nginx for SSL
    setup_nginx_ssl
    
    # Obtain SSL certificate
    obtain_ssl_certificate
    
    # Setup auto-renewal
    setup_auto_renewal
    
    # Verify SSL certificate
    verify_ssl_certificate
    
    # Test SSL configuration
    test_ssl
    
    echo ""
    echo "=========================================="
    print_status "SUCCESS" "SSL Certificate Setup Complete"
    echo "=========================================="
    echo ""
    print_status "INFO" "SSL Certificate Details:"
    echo "  - Domain: $DOMAIN"
    echo "  - Certificate Path: $SSL_PATH"
    echo "  - Auto-renewal: Enabled (daily at 12:00 UTC)"
    echo "  - Nginx: Reloaded with SSL configuration"
    echo ""
    print_status "INFO" "Next Steps:"
    echo "  1. Verify SSL certificate in browser: https://$DOMAIN"
    echo "  2. Test API endpoints: https://$DOMAIN/api/health"
    echo "  3. Test WebSocket: wscat -c wss://$DOMAIN/ws"
    echo "  4. Monitor certificate renewal: certbot certificates"
    echo ""
}

# Run main function
main "$@"
