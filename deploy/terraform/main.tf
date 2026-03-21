# =============================================================================
# Resonant Genesis - Terraform Infrastructure (Phase 4.4)
# =============================================================================
# Supports: DigitalOcean, AWS, GCP (select via var.cloud_provider)
#
# Usage:
#   cd deploy/terraform
#   terraform init
#   terraform plan -var="cloud_provider=digitalocean" -var="do_token=xxx"
#   terraform apply
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.30"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
}

# =============================================================================
# Variables
# =============================================================================

variable "cloud_provider" {
  description = "Cloud provider: digitalocean, aws, gcp"
  type        = string
  default     = "digitalocean"
}

variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
  default     = "resonant-genesis"
}

variable "region" {
  description = "Cloud region"
  type        = string
  default     = "nyc1"
}

variable "node_size" {
  description = "Node instance size"
  type        = string
  default     = "s-4vcpu-8gb"
}

variable "node_count" {
  description = "Number of nodes in the default pool"
  type        = number
  default     = 3
}

variable "min_nodes" {
  description = "Minimum nodes for autoscaling"
  type        = number
  default     = 2
}

variable "max_nodes" {
  description = "Maximum nodes for autoscaling"
  type        = number
  default     = 8
}

variable "do_token" {
  description = "DigitalOcean API token"
  type        = string
  sensitive   = true
  default     = ""
}

variable "domain" {
  description = "Primary domain"
  type        = string
  default     = "resonantgenesis.xyz"
}

variable "db_size" {
  description = "Managed database size slug"
  type        = string
  default     = "db-s-2vcpu-4gb"
}

variable "redis_size" {
  description = "Managed Redis size slug"
  type        = string
  default     = "db-s-1vcpu-1gb"
}

# =============================================================================
# DigitalOcean Provider
# =============================================================================

provider "digitalocean" {
  token = var.do_token
}

# =============================================================================
# Kubernetes Cluster
# =============================================================================

resource "digitalocean_kubernetes_cluster" "rg" {
  count   = var.cloud_provider == "digitalocean" ? 1 : 0
  name    = var.cluster_name
  region  = var.region
  version = "1.29.1-do.0"

  node_pool {
    name       = "default-pool"
    size       = var.node_size
    auto_scale = true
    min_nodes  = var.min_nodes
    max_nodes  = var.max_nodes
  }

  tags = ["resonant-genesis", "production"]
}

# =============================================================================
# Managed PostgreSQL
# =============================================================================

resource "digitalocean_database_cluster" "postgres" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  name       = "${var.cluster_name}-db"
  engine     = "pg"
  version    = "16"
  size       = var.db_size
  region     = var.region
  node_count = 1

  tags = ["resonant-genesis"]
}

resource "digitalocean_database_db" "rg_db" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  cluster_id = digitalocean_database_cluster.postgres[0].id
  name       = "resonant_genesis"
}

resource "digitalocean_database_firewall" "postgres_fw" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  cluster_id = digitalocean_database_cluster.postgres[0].id

  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.rg[0].id
  }
}

# =============================================================================
# Managed Redis
# =============================================================================

resource "digitalocean_database_cluster" "redis" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  name       = "${var.cluster_name}-redis"
  engine     = "redis"
  version    = "7"
  size       = var.redis_size
  region     = var.region
  node_count = 1

  tags = ["resonant-genesis"]
}

resource "digitalocean_database_firewall" "redis_fw" {
  count      = var.cloud_provider == "digitalocean" ? 1 : 0
  cluster_id = digitalocean_database_cluster.redis[0].id

  rule {
    type  = "k8s"
    value = digitalocean_kubernetes_cluster.rg[0].id
  }
}

# =============================================================================
# Container Registry
# =============================================================================

resource "digitalocean_container_registry" "rg" {
  count                  = var.cloud_provider == "digitalocean" ? 1 : 0
  name                   = "resonant-genesis"
  subscription_tier_slug = "professional"
  region                 = var.region
}

# =============================================================================
# Domain + DNS
# =============================================================================

resource "digitalocean_domain" "rg" {
  count = var.cloud_provider == "digitalocean" ? 1 : 0
  name  = var.domain
}

# =============================================================================
# Kubernetes Provider (connects to the created cluster)
# =============================================================================

provider "kubernetes" {
  host  = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].endpoint : ""
  token = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].kube_config[0].token : ""
  cluster_ca_certificate = var.cloud_provider == "digitalocean" ? base64decode(
    digitalocean_kubernetes_cluster.rg[0].kube_config[0].cluster_ca_certificate
  ) : ""
}

provider "helm" {
  kubernetes {
    host  = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].endpoint : ""
    token = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].kube_config[0].token : ""
    cluster_ca_certificate = var.cloud_provider == "digitalocean" ? base64decode(
      digitalocean_kubernetes_cluster.rg[0].kube_config[0].cluster_ca_certificate
    ) : ""
  }
}

# =============================================================================
# Helm Release (deploy the platform)
# =============================================================================

resource "helm_release" "resonant_genesis" {
  count            = var.cloud_provider == "digitalocean" ? 1 : 0
  name             = "resonant-genesis"
  chart            = "${path.module}/../helm/genesis2026"
  namespace        = "resonant-genesis"
  create_namespace = true

  set {
    name  = "global.domain"
    value = var.domain
  }

  set {
    name  = "global.database.host"
    value = digitalocean_database_cluster.postgres[0].private_host
  }

  set {
    name  = "global.database.port"
    value = digitalocean_database_cluster.postgres[0].port
  }

  set {
    name  = "global.database.name"
    value = "resonant_genesis"
  }

  set {
    name  = "global.database.user"
    value = digitalocean_database_cluster.postgres[0].user
  }

  set_sensitive {
    name  = "global.database.password"
    value = digitalocean_database_cluster.postgres[0].password
  }

  set {
    name  = "global.redis.host"
    value = digitalocean_database_cluster.redis[0].private_host
  }

  set {
    name  = "global.redis.port"
    value = digitalocean_database_cluster.redis[0].port
  }

  set {
    name  = "global.imageRegistry"
    value = digitalocean_container_registry.rg[0].server_url
  }

  depends_on = [
    digitalocean_kubernetes_cluster.rg,
    digitalocean_database_cluster.postgres,
    digitalocean_database_cluster.redis,
  ]
}

# =============================================================================
# Outputs
# =============================================================================

output "cluster_endpoint" {
  value       = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].endpoint : ""
  description = "Kubernetes API endpoint"
}

output "database_host" {
  value       = var.cloud_provider == "digitalocean" ? digitalocean_database_cluster.postgres[0].private_host : ""
  description = "PostgreSQL private host"
  sensitive   = true
}

output "redis_host" {
  value       = var.cloud_provider == "digitalocean" ? digitalocean_database_cluster.redis[0].private_host : ""
  description = "Redis private host"
  sensitive   = true
}

output "registry_url" {
  value       = var.cloud_provider == "digitalocean" ? digitalocean_container_registry.rg[0].server_url : ""
  description = "Container registry URL"
}

output "kubeconfig" {
  value       = var.cloud_provider == "digitalocean" ? digitalocean_kubernetes_cluster.rg[0].kube_config[0].raw_config : ""
  description = "Raw kubeconfig for kubectl"
  sensitive   = true
}
