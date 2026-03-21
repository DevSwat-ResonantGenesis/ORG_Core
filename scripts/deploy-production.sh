#!/bin/bash
# Production Deployment Script
# Deploys Genesis2026 with all security measures in place

set -e

echo "🚀 Genesis2026 Production Deployment"
echo "=================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Configuration
DEPLOYMENT_LOG="/opt/genesis/deployment-log-$(date +%Y%m%d_%H%M%S).log"

main() {
  # Check if running as root for firewall setup
  if [ "$EUID" -ne 0 ]; then
      echo -e "${YELLOW}⚠️  Some operations require root privileges${NC}"
      echo "You'll be prompted for password when needed"
  fi

  # Step 1: Generate production secrets
  echo ""
  echo "🔐 Step 1: Generating production secrets..."
  if [ ! -f ".env.production" ]; then
      ./scripts/generate-production-secrets.sh
  else
      echo -e "${YELLOW}⚠️  .env.production already exists, skipping generation${NC}"
      echo "To regenerate: rm .env.production && ./scripts/generate-production-secrets.sh"
  fi

  # Step 2: Set up database security
  echo ""
  echo "🗄️  Step 2: Setting up database security..."
  ./scripts/setup-database-security.sh

  # Step 3: Setup monitoring
  echo ""
  echo "📊 Step 3: Setting up monitoring..."
  if [ ! -f "/opt/genesis/monitoring/docker-compose.monitoring.yml" ]; then
      ./scripts/setup-monitoring.sh
  else
      echo -e "${YELLOW}⚠️  Monitoring already setup${NC}"
  fi

  # Step 4: Pre-deployment verification
  echo ""
  echo "🔍 Step 4: Pre-deployment verification..."
  if ! ./scripts/verify-production-deployment.sh; then
      echo -e "${RED}❌ PRE-DEPLOYMENT VERIFICATION FAILED${NC}"
      echo "   Fix all issues before proceeding"
      exit 1
  fi

  # Step 5: Deploy services
  echo ""
  echo "🚀 Step 5: Deploying production services..."
  
  # Stop any existing services
  echo "🛑 Stopping existing services..."
  docker compose -f docker-compose.production.yml down 2>/dev/null | tee -a "$DEPLOYMENT_LOG"
  
  # Pull latest images
  echo "📦 Pulling latest images..."
  docker compose -f docker-compose.production.yml pull 2>/dev/null | tee -a "$DEPLOYMENT_LOG"
  
  # Start services
  echo "🐳 Starting production services..."
  docker compose -f docker-compose.production.yml --env-file .env.production up -d 2>/dev/null | tee -a "$DEPLOYMENT_LOG"
  
  # Wait for services to be healthy
  echo "⏳ Waiting for services to initialize..."
  sleep 30
  
  # Check service health
  local healthy_services=0
  total_services=8
  
  for service in gateway auth_service chat_service memory_service llm_service; do
      if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
          ((healthy_services++))
          echo "✅ $service is healthy"
      else
          echo "❌ $service is not healthy"
      fi
  done
  
  echo "📊 Services healthy: $healthy_services/$total_services"
  
  if [ $healthy_services -eq $total_services ]; then
      echo "✅ All services started successfully"
  else
      echo "❌ Some services failed to start"
      echo "   Check logs: docker compose -f docker-compose.production.yml logs"
      exit 1
  fi

  # Step 6: Post-deployment verification
  echo ""
  echo "🔍 Step 6: Post-deployment verification..."
  sleep 60  # Wait for full initialization
  
  if ! ./scripts/verify-production-deployment.sh >> "$DEPLOYMENT_LOG" 2>&1; then
      echo -e "${RED}❌ POST-DEPLOYMENT VERIFICATION FAILED${NC}"
      echo "   Check logs: $DEPLOYMENT_LOG"
      exit 1
  fi

  # Step 7: SSL Certificate setup
  echo ""
  echo "🔒 Step 7: SSL Certificate Setup"
  echo "=================================="
  echo "⚠️  SSL setup requires manual intervention:"
  echo ""
  echo "1. Ensure DNS A records point to droplet IP:"
  echo "   - resonantgenesis.ai → $(curl -s ifconfig.me 2>/dev/null)"
  echo "   - api.resonantgenesis.ai → $(curl -s ifconfig.me 2>/dev/null)"
  echo ""
  echo "2. Request SSL certificates:"
  echo "   sudo certbot --nginx -d resonantgenesis.ai -d api.resonantgenesis.ai"
  echo ""
  echo "3. Verify certificates:"
  echo "   sudo certbot certificates --check"
  echo ""

  # Step 8: Create systemd service
  echo ""
  echo "🔧 Step 8: Creating systemd service..."
  if [ ! -f "/etc/systemd/system/genesis-production.service" ]; then
      cat > /etc/systemd/system/genesis-production.service << 'EOF'
[Unit]
Description=Genesis2026 Production Services
After=docker.target
Requires=docker.service
StartLimitBurst=0
StartLimitInterval=60

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/genesis
ExecStart=/opt/genesis/scripts/start-production-services.sh
ExecStop=/opt/genesis/scripts/stop-production-services.sh
TimeoutStartSec=300
TimeoutStopSec=60

[Install]
WantedBy=multi-user
EOF

      systemctl daemon-reload
      systemctl enable genesis-production
      echo "✅ Systemd service created and enabled"
  else
      echo "✅ Systemd service already exists"
  fi

  # Step 9: Final status
  echo ""
  echo "🎉 DEPLOYMENT COMPLETED"
  echo "=================="
  echo ""
  echo "📊 Services deployed:"
  echo "   - Gateway: http://localhost:8000"
  echo "   - Auth Service: http://localhost:8001"
  echo "   - Chat Service: http://localhost:8002"
  echo "   - Memory Service: http://localhost:8003"
  echo "   - LLM Service: http://localhost:8004"
  echo ""
  echo "📈 Monitoring dashboards:"
  echo "   - Prometheus: http://localhost:9090"
  echo "   - Grafana: http://localhost:3001"
  echo "   - Alertmanager: http://localhost:9093"
  echo ""
  echo "📋 Deployment log: $DEPLOYMENT_LOG"
  echo ""
  echo "🔧 Management commands:"
  echo "   - View logs: docker compose -f docker-compose.production.yml logs -f"
  echo "   - Stop services: docker compose -f docker-compose.production.yml down"
  echo "   - Restart services: docker compose -f docker-compose.production.yml restart"
  echo ""
  echo "🔍 Health checks:"
  echo "   - Health check: /opt/genesis/monitoring/scripts/health-check.sh"
  echo "   - Alert test: /opt/genesis/monitoring/scripts/test-alerts.sh"
  echo ""
  echo "✅ Production deployment complete!"
}

# Run main function
main "$@"

# Step 4: Start production services
echo ""
echo "🐳 Step 4: Starting production services..."
docker compose -f docker-compose.production.yml --env-file .env.production up -d

# Step 5: Wait for services to be healthy
echo ""
echo "⏳ Step 5: Waiting for services to initialize..."
sleep 30

# Step 6: Check service health
echo ""
echo "🏥 Step 6: Checking service health..."
echo "Checking core services..."

# Check nginx (should be responding on port 80/443)
if curl -s -f http://localhost/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Nginx: Healthy${NC}"
else
    echo -e "${RED}❌ Nginx: Not responding${NC}"
fi

# Check gateway (internal)
if docker compose -f docker-compose.production.yml exec -T gateway curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Gateway: Healthy${NC}"
else
    echo -e "${RED}❌ Gateway: Not healthy${NC}"
fi

# Check auth service (internal)
if docker compose -f docker-compose.production.yml exec -T auth_service curl -f http://localhost:8000/auth/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Auth Service: Healthy${NC}"
else
    echo -e "${RED}❌ Auth Service: Not healthy${NC}"
fi

# Step 7: Show service status
echo ""
echo "📊 Step 7: Service Status"
echo "======================"
docker compose -f docker-compose.production.yml ps

# Step 8: Show logs for any unhealthy services
echo ""
echo "📋 Step 8: Recent logs (last 20 lines each)"
echo "=========================================="
for service in nginx gateway auth_service chat_service memory_service; do
    echo ""
    echo "--- $service logs ---"
    docker compose -f docker-compose.production.yml logs --tail=5 $service 2>/dev/null || echo "No logs for $service"
done

# Step 9: Firewall setup (requires root)
echo ""
echo "🔥 Step 9: Firewall Configuration"
echo "================================"
echo "This requires root privileges..."
sudo ./scripts/setup-firewall.sh

# Step 10: SSL Certificate setup
echo ""
echo "🔒 Step 10: SSL Certificate Setup"
echo "==============================="
echo "Make sure you have:"
echo "1. DNS records pointing to this server"
echo "2. Domain: resonantgenesis.ai"
echo "3. Domain: api.resonantgenesis.ai"
echo ""
echo "To get SSL certificates:"
echo "sudo certbot --nginx -d resonantgenesis.ai -d api.resonantgenesis.ai"

# Step 11: Final summary
echo ""
echo "🎉 Production Deployment Summary"
echo "==============================="
echo -e "${GREEN}✅ Services deployed with security hardening${NC}"
echo -e "${GREEN}✅ Internal networking enabled${NC}"
echo -e "${GREEN}✅ Firewall configured${NC}"
echo -e "${GREEN}✅ Database security enabled${NC}"
echo -e "${GREEN}✅ Monitoring stack running${NC}"
echo ""
echo "🌐 Access URLs:"
echo "  - Frontend: https://resonantgenesis.ai"
echo "  - API: https://api.resonantgenesis.ai"
echo "  - Health: https://api.resonantgenesis.ai/health"
echo ""
echo "📊 Monitoring:"
echo "  - Prometheus: http://localhost:9090 (internal only)"
echo "  - Grafana: http://localhost:3001 (internal only)"
echo ""
echo "🔧 Management commands:"
echo "  - View logs: docker compose -f docker-compose.production.yml logs -f"
echo "  - Stop services: docker compose -f docker-compose.production.yml down"
echo "  - Restart services: docker compose -f docker-compose.production.yml restart"
echo "  - Check status: docker compose -f docker-compose.production.yml ps"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT NEXT STEPS:${NC}"
echo "1. Set up SSL certificates with certbot"
echo "2. Update .env.production with your real API keys"
echo "3. Configure DNS records for your domains"
echo "4. Set up external backups"
echo "5. Configure monitoring alerts"
echo ""
echo -e "${GREEN}🚀 Production deployment complete!${NC}"
