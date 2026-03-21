# Resonant Genesis - Deployment Guide

## Deployment Options

### 1. Docker Compose (Current Production)
```bash
docker compose -f docker-compose.unified.yml up -d --build
```

### 2. DigitalOcean App Platform
```bash
# See deploy/digitalocean/app.yaml
```

### 3. Kubernetes via Helm (Phase 4.4)
```bash
# Install from local chart
helm install rg ./deploy/helm/resonant-genesis \
  -f my-values.yaml \
  --namespace resonant-genesis \
  --create-namespace

# Upgrade
helm upgrade rg ./deploy/helm/resonant-genesis -f my-values.yaml

# Uninstall
helm uninstall rg -n resonant-genesis
```

### 4. Terraform (Full Infrastructure + Deploy)
```bash
cd deploy/terraform
terraform init
terraform plan -var="do_token=$DO_TOKEN"
terraform apply -var="do_token=$DO_TOKEN"
```

## Required Secrets

Create a Kubernetes secret before deploying:
```bash
kubectl create secret generic rg-env-secrets \
  --from-literal=JWT_SECRET_KEY=<your-jwt-secret> \
  --from-literal=GROQ_API_KEY=<your-groq-key> \
  --from-literal=OPENAI_API_KEY=<your-openai-key> \
  --from-literal=GOOGLE_CLIENT_ID=<your-google-client-id> \
  --from-literal=GOOGLE_CLIENT_SECRET=<your-google-client-secret> \
  -n resonant-genesis

kubectl create secret generic rg-database-credentials \
  --from-literal=password=<db-password> \
  -n resonant-genesis

kubectl create secret generic rg-jwt-secret \
  --from-literal=jwt-secret=<jwt-secret> \
  -n resonant-genesis
```

## Architecture

```
Internet → Ingress/Nginx → Gateway → Internal Services
                                    ├── auth_service
                                    ├── chat_service
                                    ├── llm_service
                                    ├── agent_engine_service
                                    ├── memory_service
                                    ├── workflow_service
                                    ├── billing_service
                                    ├── code_visualizer_service
                                    ├── marketplace_service
                                    └── ... (35 total services)
```
