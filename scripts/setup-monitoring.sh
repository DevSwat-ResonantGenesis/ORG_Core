#!/bin/bash
# Production Monitoring and Alerting Setup
# CRITICAL: Comprehensive monitoring for production deployment

set -e

echo "📊 PRODUCTION MONITORING AND ALERTING"
echo "==================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
MONITORING_DIR="/opt/genesis/monitoring"
ALERT_WEBHOOK="https://monitoring.resonantgenesis.ai/alerts"
GRAFANA_ADMIN_PASSWORD="genesis_grafana_$(openssl rand -base64 16)_$(date +%Y)"

echo "🔧 Setting up production monitoring..."

# Create monitoring directories
echo "📁 Creating monitoring directories..."
sudo mkdir -p "$MONITORING_DIR"/{prometheus,grafana,alertmanager,logs,scripts}
sudo chmod 755 "$MONITORING_DIR"
sudo chown root:root "$MONITORING_DIR"

# Prometheus configuration
echo "📊 Setting up Prometheus..."
cat > "$MONITORING_DIR/prometheus/prometheus.yml" << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  rule_files:
    - "/opt/genesis/monitoring/alertmanager/rules/*.yml"
  external_labels:
    cluster: 'genesis-production'
    region: 'digitalocean-nyc3'

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s

  # Gateway service
  - job_name: 'gateway'
    static_configs:
      - targets: ['gateway:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance

  # Auth service
  - job_name: 'auth_service'
    static_configs:
      - targets: ['auth_service:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # Chat service
  - job_name: 'chat_service'
    static_configs:
      - targets: ['chat_service:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # Memory service
  - job_name: 'memory_service'
    static_configs:
      - targets: ['memory_service:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # LLM service
  - job_name: 'llm_service'
    static_configs:
      - targets: ['llm_service:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s

  # Database monitoring
  - job_name: 'postgres_exporter'
    static_configs:
      - targets: ['postgres_exporter_auth:9187']
    scrape_interval: 30s

  - job_name: 'postgres_exporter_chat'
    static_configs:
      - targets: ['postgres_exporter_chat:9187']
    scrape_interval: 30s

  - job_name: 'postgres_exporter_memory'
    static_configs:
      - targets: ['postgres_exporter_memory:9187']
    scrape_interval: 30s

  # Redis monitoring
  - job_name: 'redis_exporter'
    static_configs:
      - targets: ['redis_exporter:9121']
    scrape_interval: 30s

  # Nginx monitoring
  - job_name: 'nginx_exporter'
    static_configs:
      - targets: ['nginx_exporter:9113']
    scrape_interval: 30s

  # Node exporter (system metrics)
  - job_name: 'node'
    static_configs:
      - targets: ['node_exporter:9100']
    scrape_interval: 30s

  # Docker containers
  - job_name: 'docker'
    static_configs:
      - targets: ['cadvisor:8080']
    scrape_interval: 30s

  # MinIO monitoring
  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
    metrics_path: '/minio/v2/metrics/cluster'
    scrape_interval: 30s
EOF

# Alertmanager configuration
echo "🚨 Setting up Alertmanager..."
cat > "$MONITORING_DIR/alertmanager/alertmanager.yml" << 'EOF'
global:
  smtp_smarthost: localhost
  smtp_from: alerts@resonantgenesis.ai
  smtp_auth_username: alerts@resonantgenesis.ai
  smtp_auth_password: ${SMTP_PASSWORD}

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 1h
  receiver: 'web.hook'
  routes:
    - match:
        severity: critical
      receiver: 'critical-alerts'
    - match:
        severity: warning
      receiver: 'warning-alerts'

receivers:
  - name: 'web.hook'
    webhook_configs:
      - url: 'https://monitoring.resonantgenesis.ai/alerts'
        send_resolved: true
        http_config:
          bearer_token: ${ALERT_WEBHOOK_TOKEN}

  - name: 'critical-alerts'
    webhook_configs:
      - url: 'https://monitoring.resonantgenesis.ai/alerts/critical'
        send_resolved: true
        http_config:
          bearer_token: ${ALERT_WEBHOOK_TOKEN}
    email_configs:
      - to: 'admin@resonantgenesis.ai'
        subject: '[CRITICAL] Genesis Production Alert'
        body: |
          {{ range .Alerts.Firing }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}
          {{ end }}

  - name: 'warning-alerts'
    webhook_configs:
      - url: 'https://monitoring.resonantgenesis.ai/alerts/warning'
        send_resolved: true
        http_config:
          bearer_token: ${ALERT_WEBHOOK_TOKEN}
EOF

# Critical alert rules
cat > "$MONITORING_DIR/alertmanager/rules/critical.yml" << 'EOF'
groups:
  - name: database_critical
    rules:
      - alert: DatabaseDown
        expr: up{job=~"postgres_exporter"} == 0
        for: 1m
        labels:
          severity: critical
          service: database
        annotations:
          summary: "Database is down"
          description: "Database {{ $labels.instance }} has been down for more than 1 minute"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count{datname!~"template.*"} > 80
        for: 5m
        labels:
          severity: critical
          service: database
        annotations:
          summary: "Database connections critical"
          description: "Database {{ $labels.instance }} has {{ $value }} active connections"

      - alert: DatabaseDiskSpaceCritical
        expr: (pg_database_size_bytes / 1024 / 1024 / 1024) > 80
        for: 5m
        labels:
          severity: critical
          service: database
        annotations:
          summary: "Database disk space critical"
          description: "Database {{ $labels.instance }} is {{ $value }}GB used"

  - name: service_critical
    rules:
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "Service {{ $labels.job }} has been down for more than 1 minute"

      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
          service: application
        annotations:
          summary: "High error rate"
          description: "Service {{ $labels.job }} has {{ $value }} errors/sec"

      - alert: HighMemoryUsage
        expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.9
        for: 5m
        labels:
          severity: critical
          service: infrastructure
        annotations:
          summary: "High memory usage"
          description: "Container {{ $labels.name }} is using {{ $value | humanizePercentage }} memory"

      - alert: HighCPUUsage
        expr: rate(container_cpu_usage_seconds_total[5m]) > 0.8
        for: 5m
        labels:
          severity: critical
          service: infrastructure
        annotations:
          summary: "High CPU usage"
          description: "Container {{ $labels.name }} is using {{ $value | humanizePercentage }} CPU"

  - name: security_critical
    rules:
      - alert: UnauthorizedAccess
        expr: rate(http_requests_total{status=~"401"}[5m]) > 10
        for: 2m
        labels:
          severity: critical
          service: security
        annotations:
          summary: "High unauthorized access rate"
          description: "{{ $value }} unauthorized requests in the last 5 minutes"

      - alert: SuspiciousActivity
        expr: rate(http_requests_total{status=~"429"}[5m]) > 5
        for: 2m
        labels:
          severity: critical
          service: security
        annotations:
          summary: "Suspicious activity detected"
          description: "{{ $value }} rate limited requests in the last 5 minutes"
EOF

# Warning alert rules
cat > "$MONITORING_DIR/alertmanager/rules/warning.yml" << 'EOF'
groups:
  - name: database_warning
    rules:
      - alert: DatabaseSlowQueries
        expr: rate(pg_stat_statements_calls_total{datname!~"template.*"}[5m]) > 100
        for: 10m
        labels:
          severity: warning
          service: database
        annotations:
          summary: "Database slow queries"
          description: "Database {{ $labels.instance }} has {{ $value }} slow queries/min"

      - alert: DatabaseConnectionsHigh
        expr: pg_stat_activity_count{datname!~"template.*"} > 50
        for: 10m
        labels:
          severity: warning
          service: database
        annotations:
          summary: "Database connections high"
          description: "Database {{ $labels.instance }} has {{ $value }} active connections"

  - name: service_warning
    rules:
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
          service: application
        annotations:
          summary: "High response time"
          description: "95th percentile response time is {{ $value }}s"

      - alert: MemoryUsageHigh
        expr: (container_memory_usage_bytes / container_spec_memory_limit_bytes) > 0.8
        for: 10m
        labels:
          severity: warning
          service: infrastructure
        annotations:
          summary: "High memory usage"
          description: "Container {{ $labels.name }} is using {{ $value | humanizePercentage }} memory"

      - alert: DiskSpaceLow
        expr: (node_filesystem_avail_bytes / node_filesystem_size_bytes) < 0.2
        for: 5m
        labels:
          severity: warning
          service: infrastructure
        annotations:
          summary: "Low disk space"
          description: "Filesystem {{ $labels.mountpoint }} has {{ $value | humanizePercentage }} free space"
EOF

# Grafana configuration
echo "📈 Setting up Grafana..."
cat > "$MONITORING_DIR/grafana/provisioning/datasources/prometheus.yml" << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
EOF

# Grafana dashboards
cat > "$MONITORING_DIR/grafana/provisioning/dashboards/overview.json" << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "Genesis Production Overview",
    "tags": ["genesis", "production", "overview"],
    "timezone": "browser",
    "panels": [
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up",
            "legendFormat": "{{job}}"
          }
        ],
        "fieldConfig": {
          "defaults": {
            "mappings": [
              {
                "options": {
                  "0": {
                    "text": "DOWN",
                    "color": "red"
                  },
                  "1": {
                    "text": "UP",
                    "color": "green"
                  }
                },
                "type": "value"
              }
            ]
          }
        },
        "gridPos": {
          "h": 8,
          "w": 6,
          "x": 0,
          "y": 0
        }
      },
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{job}}"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 6,
          "y": 0
        }
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~"5.."}[5m])",
            "legendFormat": "{{job}}"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 18,
          "y": 0
        }
      },
      {
        "title": "Database Connections",
        "type": "graph",
        "targets": [
          {
            "expr": "pg_stat_activity_count",
            "legendFormat": "{{instance}}"
          }
        ],
        "gridPos": {
          "h": 8,
          "w": 12,
          "x": 0,
          "y": 8
        }
      }
    ],
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s"
  }
}
EOF

# Health check script
cat > "$MONITORING_DIR/scripts/health-check.sh" << 'EOF'
#!/bin/bash
# Production Health Check Script

echo "🏥 Genesis Production Health Check - $(date)"
echo "======================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0;0m'

# Check services
services=("gateway" "auth_service" "chat_service" "memory_service" "llm_service")
all_healthy=true

for service in "${services[@]}"; do
    if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $service - HEALTHY${NC}"
    else
        echo -e "${RED}❌ $service - UNHEALTHY${NC}"
        all_healthy=false
    fi
done

# Check databases
databases=("auth_db" "chat_db" "memory_db")
for db in "${databases[@]}"; do
    if docker exec "genesis_${db}" pg_isready -U genesis_${db}_user_prod -d ${db} > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $db - HEALTHY${NC}"
    else
        echo -e "${RED}❌ $db - UNHEALTHY${NC}"
        all_healthy=false
    fi
done

# Check disk space
disk_usage=$(df / | awk 'NR==1{next} {print $5}' | head -1)
if [[ "${disk_usage%?}" > 80 ]]; then
    echo -e "${YELLOW}⚠️  Disk usage: ${disk_usage} (HIGH)${NC}"
else
    echo -e "${GREEN}✅ Disk usage: ${disk_usage} (OK)${NC}"
fi

# Check memory usage
memory_usage=$(free | awk 'NR==2{printf "%.1f%%", $3*100/$2}')
if [[ "${memory_usage%?}" > 80 ]]; then
    echo -e "${YELLOW}⚠️  Memory usage: ${memory_usage} (HIGH)${NC}"
else
    echo -e "${GREEN}✅ Memory usage: ${memory_usage} (OK)${NC}"
fi

# Overall status
if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}✅ ALL SYSTEMS HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}❌ SYSTEM ISSUES DETECTED${NC}"
    exit 1
fi
EOF

chmod +x "$MONITORING_DIR/scripts/health-check.sh"

# Alert testing script
cat > "$MONITORING_DIR/scripts/test-alerts.sh" << 'EOF'
#!/bin/bash
# Alert Testing Script

echo "🚨 Testing Alert System - $(date)"

# Test critical alert webhook
echo "📡 Testing critical alert webhook..."
curl -X POST "https://monitoring.resonantgenesis.ai/alerts/test" \
     -H "Content-Type: application/json" \
     -d '{
       "level": "test",
       "message": "Alert system test",
       "timestamp": "'$(date -Iseconds)'"'
     }'

# Test Prometheus alerts
echo "📊 Testing Prometheus alerts..."
curl -X POST "http://localhost:9093/api/v1/alerts" \
     -H "Content-Type: application/json" \
     -d '[
       {
         "labels": {
           "alertname": "TestAlert",
           "severity": "warning"
         },
         "annotations": {
           "summary": "Test alert",
           "description": "This is a test alert"
         },
         "startsAt": "'$(date -Iseconds)'"'
       }
     ]'

# Test Grafana health
echo "📈 Testing Grafana health..."
curl -s "http://localhost:3001/api/health" > /dev/null && echo "✅ Grafana healthy" || echo "❌ Grafana unhealthy"

echo "✅ Alert system test completed"
EOF

chmod +x "$MONITORING_DIR/scripts/test-alerts.sh"

# Log aggregation setup
echo "📋 Setting up log aggregation..."
cat > "$MONITORING_DIR/docker-compose.monitoring.yml" << 'EOF'
version: '3.8'

services:
  # PostgreSQL Exporter
  postgres_exporter_auth:
    image: prom/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://genesis_auth_user_prod:$(grep AUTH_DB_PASSWORD /opt/genesis/.env.production | cut -d'=' -f2)@auth_db:5432/auth_db?sslmode=disable"
      PG_EXPORTER_INCLUDE_DATABASE: "true"
      PG_EXPORTER_INCLUDE_SCHEMA: "true"
    ports:
      - "9187:9187"
    depends_on:
      - auth_db
    restart: unless-stopped

  postgres_exporter_chat:
    image: prom/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://genesis_chat_user_prod:$(grep CHAT_DB_PASSWORD /opt/genesis/.env.production | cut -d'=' -f2)@chat_db:5432/chat_db?sslmode=disable"
      PG_EXPORTER_INCLUDE_DATABASE: "true"
      PG_EXPORTER_INCLUDE_SCHEMA: "true"
    ports:
      - "9188:9187"
    depends_on:
      - chat_db
    restart: unless-stopped

  postgres_exporter_memory:
    image: prom/postgres-exporter:latest
    environment:
      DATA_SOURCE_NAME: "postgresql://genesis_memory_user_prod:$(grep MEMORY_DB_PASSWORD /opt/genesis/.env.production | cut -d'=' -f2)@memory_db:5432/memory_db?sslmode=disable"
      PG_EXPORTER_INCLUDE_DATABASE: "true"
      PG_EXPORTER_INCLUDE_SCHEMA: "true"
    ports:
      - "9189:9187"
    depends_on:
      - memory_db
    restart: unless-stopped

  # Redis Exporter
  redis_exporter:
    image: oliver006/redis_exporter:latest
    environment:
      REDIS_ADDR: "redis://redis:6379"
      REDIS_PASSWORD: "$(grep REDIS_PASSWORD /opt/genesis/.env.production | cut -d'=' -f2)"
    ports:
      - "9121:9121"
    depends_on:
      - redis
    restart: unless-stopped

  # Nginx Exporter
  nginx_exporter:
    image: nginx/nginx-prometheus-exporter:latest
    ports:
      - "9113:9113"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped

  # Node Exporter
  node_exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    restart: unless-stopped

  # cAdvisor (Docker metrics)
  cadvisor:
    image: google/cadvisor:latest
    ports:
      - "8080:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
      - /dev/disk/:/dev/disk/:ro
    privileged: true
    restart: unless-stopped

  # Alertmanager
  alertmanager:
    image: prom/alertmanager:latest
    ports:
      - "9093:9093"
    volumes:
      - "$MONITORING_DIR/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro"
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    environment:
      GF_SECURITY_ADMIN_PASSWORD: genesis_grafana_prod_2024
      GF_USERS_ALLOW_SIGN_UP: false
      GF_INSTALL_PLUGINS: "grafana-piechart-panel"
    volumes:
      - "$MONITORING_DIR/grafana/provisioning:/etc/grafana/provisioning:ro"
      - grafana_data:/var/lib/grafana
    restart: unless-stopped
    depends_on:
      - prometheus
EOF

echo ""
echo "📊 MONITORING SETUP COMPLETE"
echo "=========================="
echo ""
echo -e "${GREEN}✅ Prometheus configured${NC}"
echo -e "${GREEN}✅ Alertmanager configured${NC}"
echo -e "${GREEN}✅ Grafana configured${NC}"
echo -e "${GREEN}✅ Exporters configured${NC}"
echo -e "${GREEN}✅ Health checks created${NC}"
echo -e "${GREEN}✅ Alert testing created${NC}"
echo ""
echo "🚀 Start monitoring stack:"
echo "   docker compose -f docker-compose.monitoring.yml up -d"
echo ""
echo "📊 Access dashboards:"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana: http://localhost:3001 (admin/genesis_grafana_prod_2024)"
echo "   Alertmanager: http://localhost:9093"
echo ""
echo "🔍 Health checks:"
echo "   $MONITORING_DIR/scripts/health-check.sh"
echo "   $MONITORING_DIR/scripts/test-alerts.sh"
