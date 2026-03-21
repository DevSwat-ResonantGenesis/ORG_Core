"""
SECRET MANAGEMENT
=================

Centralized secret management for Resonant Genesis.
Supports multiple backends: Environment, AWS Secrets Manager, HashiCorp Vault.

Production Usage:
- Set SECRET_BACKEND=aws or SECRET_BACKEND=vault
- Configure appropriate credentials
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from functools import lru_cache
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class SecretBackend(ABC):
    """Abstract base for secret backends."""
    
    @abstractmethod
    def get_secret(self, key: str) -> Optional[str]:
        """Get a secret by key."""
        pass
    
    @abstractmethod
    def get_secrets(self, prefix: str) -> Dict[str, str]:
        """Get all secrets with a prefix."""
        pass


class EnvSecretBackend(SecretBackend):
    """Environment variable backend (default for dev)."""
    
    def get_secret(self, key: str) -> Optional[str]:
        return os.getenv(key)
    
    def get_secrets(self, prefix: str) -> Dict[str, str]:
        return {
            k: v for k, v in os.environ.items()
            if k.startswith(prefix)
        }


class AWSSecretsBackend(SecretBackend):
    """AWS Secrets Manager backend."""
    
    def __init__(self, region: str = None):
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._client = None
        self._cache: Dict[str, str] = {}
    
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "secretsmanager",
                    region_name=self.region,
                )
            except ImportError:
                logger.error("boto3 not installed. Run: pip install boto3")
                raise
        return self._client
    
    def get_secret(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]
        
        try:
            response = self.client.get_secret_value(SecretId=key)
            secret = response.get("SecretString")
            
            # Try to parse as JSON
            try:
                data = json.loads(secret)
                if isinstance(data, dict):
                    # Cache all values from JSON
                    for k, v in data.items():
                        self._cache[k] = str(v)
                    return self._cache.get(key, secret)
            except json.JSONDecodeError:
                pass
            
            self._cache[key] = secret
            return secret
            
        except Exception as e:
            logger.error(f"Failed to get secret {key}: {e}")
            return None
    
    def get_secrets(self, prefix: str) -> Dict[str, str]:
        try:
            # List all secrets with prefix
            paginator = self.client.get_paginator("list_secrets")
            secrets = {}
            
            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    name = secret.get("Name", "")
                    if name.startswith(prefix):
                        value = self.get_secret(name)
                        if value:
                            secrets[name] = value
            
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets with prefix {prefix}: {e}")
            return {}


class VaultSecretBackend(SecretBackend):
    """HashiCorp Vault backend."""
    
    def __init__(self, url: str = None, token: str = None):
        self.url = url or os.getenv("VAULT_ADDR", "http://vault:8200")
        self.token = token or os.getenv("VAULT_TOKEN")
        self._client = None
        self._cache: Dict[str, str] = {}
    
    @property
    def client(self):
        if self._client is None:
            try:
                import hvac
                self._client = hvac.Client(url=self.url, token=self.token)
                
                if not self._client.is_authenticated():
                    raise ValueError("Vault authentication failed")
                    
            except ImportError:
                logger.error("hvac not installed. Run: pip install hvac")
                raise
        return self._client
    
    def get_secret(self, key: str) -> Optional[str]:
        if key in self._cache:
            return self._cache[key]
        
        try:
            # Assuming KV v2 secrets engine at 'secret/'
            path = f"secret/data/{key}"
            response = self.client.secrets.kv.v2.read_secret_version(path=key)
            
            data = response.get("data", {}).get("data", {})
            
            # Cache all values
            for k, v in data.items():
                self._cache[k] = str(v)
            
            return self._cache.get(key) or data.get("value")
            
        except Exception as e:
            logger.error(f"Failed to get secret {key} from Vault: {e}")
            return None
    
    def get_secrets(self, prefix: str) -> Dict[str, str]:
        try:
            # List secrets at path
            response = self.client.secrets.kv.v2.list_secrets(path=prefix)
            keys = response.get("data", {}).get("keys", [])
            
            secrets = {}
            for key in keys:
                full_path = f"{prefix}/{key}".rstrip("/")
                value = self.get_secret(full_path)
                if value:
                    secrets[full_path] = value
            
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets with prefix {prefix}: {e}")
            return {}


class SecretManager:
    """
    Unified secret management interface.
    
    Usage:
        secrets = get_secret_manager()
        db_password = secrets.get("DATABASE_PASSWORD")
        api_key = secrets.get("OPENAI_API_KEY")
    """
    
    def __init__(self, backend: SecretBackend = None):
        if backend:
            self.backend = backend
        else:
            # Auto-detect backend from environment
            backend_type = os.getenv("SECRET_BACKEND", "env").lower()
            
            if backend_type == "aws":
                self.backend = AWSSecretsBackend()
            elif backend_type == "vault":
                self.backend = VaultSecretBackend()
            else:
                self.backend = EnvSecretBackend()
        
        logger.info(f"Secret manager initialized with {type(self.backend).__name__}")
    
    def get(self, key: str, default: str = None) -> Optional[str]:
        """Get a secret value."""
        value = self.backend.get_secret(key)
        return value if value is not None else default
    
    def get_required(self, key: str) -> str:
        """Get a required secret, raise if missing."""
        value = self.backend.get_secret(key)
        if value is None:
            raise ValueError(f"Required secret '{key}' not found")
        return value
    
    def get_all(self, prefix: str = "") -> Dict[str, str]:
        """Get all secrets with optional prefix."""
        return self.backend.get_secrets(prefix)
    
    def get_database_url(self, service: str) -> str:
        """Get database URL for a service."""
        # Try service-specific first
        url = self.get(f"{service.upper()}_DATABASE_URL")
        if url:
            return url
        
        # Fall back to constructing from parts
        host = self.get(f"{service.upper()}_DB_HOST", f"{service}_db")
        port = self.get(f"{service.upper()}_DB_PORT", "5432")
        user = self.get(f"{service.upper()}_DB_USER", f"{service}_user")
        password = self.get(f"{service.upper()}_DB_PASS", f"{service}_pass")
        database = self.get(f"{service.upper()}_DB_NAME", f"{service}_db")
        
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    def get_redis_url(self, db: int = 0) -> str:
        """Get Redis URL."""
        host = self.get("REDIS_HOST", "redis")
        port = self.get("REDIS_PORT", "6379")
        password = self.get("REDIS_PASSWORD", "")
        
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        return f"redis://{host}:{port}/{db}"
    
    def get_api_keys(self) -> Dict[str, str]:
        """Get all LLM API keys."""
        return {
            "openai": self.get("OPENAI_API_KEY", ""),
            "anthropic": self.get("ANTHROPIC_API_KEY", ""),
            "google": self.get("GOOGLE_API_KEY", ""),
            "groq": self.get("GROQ_API_KEY", ""),
        }


# Singleton instance
_manager: Optional[SecretManager] = None


@lru_cache(maxsize=1)
def get_secret_manager() -> SecretManager:
    """Get or create the secret manager singleton."""
    global _manager
    if _manager is None:
        _manager = SecretManager()
    return _manager


# Convenience functions
def get_secret(key: str, default: str = None) -> Optional[str]:
    """Get a secret value."""
    return get_secret_manager().get(key, default)


def get_required_secret(key: str) -> str:
    """Get a required secret."""
    return get_secret_manager().get_required(key)
