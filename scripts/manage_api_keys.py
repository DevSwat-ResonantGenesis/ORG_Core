#!/usr/bin/env python3
"""
API Key Management Script for Creator Dashboard
===============================================

This script allows easy management of API keys for the Resonant platform.
It can be used to update, rotate, and validate API keys.

Usage:
    python scripts/manage_api_keys.py --list
    python scripts/manage_api_keys.py --update tavily YOUR_NEW_KEY
    python scripts/manage_api_keys.py --validate tavily
    python scripts/manage_api_keys.py --rotate tavily
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

class APIKeyManager:
    """Manages API keys for the Resonant platform."""
    
    def __init__(self):
        self.env_file = project_root / ".env.websearch"
        self.docker_compose_file = project_root / "docker-compose.yml"
        self.keys = self._load_keys()
    
    def _load_keys(self) -> Dict[str, str]:
        """Load API keys from environment file."""
        keys = {}
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        keys[key] = value
        return keys
    
    def list_keys(self) -> None:
        """List all configured API keys."""
        print("🔑 Configured API Keys:")
        print("=" * 50)
        
        # Web Search Keys
        search_keys = [
            ("Tavily API", "TAVILY_API_KEY"),
            ("Tavily Backup", "TAVILY_API_KEY_BACKUP"), 
            ("Tavily Dev", "TAVILY_API_KEY_DEV"),
            ("SerpAPI", "SERPAPI_KEY"),
        ]
        
        for name, key in search_keys:
            value = self.keys.get(key, "Not configured")
            masked = self._mask_key(value) if value != "Not configured" else value
            print(f"{name:15} : {masked}")
        
        print("\n💡 To update keys:")
        print("   python scripts/manage_api_keys.py --update <service> <new_key>")
        print("   python scripts/manage_api_keys.py --rotate tavily")
    
    def _mask_key(self, key: str) -> str:
        """Mask API key for security."""
        if len(key) <= 8:
            return "*" * len(key)
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
    
    def update_key(self, service: str, new_key: str) -> bool:
        """Update an API key."""
        service = service.lower()
        
        # Map service names to environment variables
        service_map = {
            'tavily': 'TAVILY_API_KEY',
            'tavily_backup': 'TAVILY_API_KEY_BACKUP',
            'tavily_dev': 'TAVILY_API_KEY_DEV',
            'serpapi': 'SERPAPI_KEY',
        }
        
        env_var = service_map.get(service)
        if not env_var:
            print(f"❌ Unknown service: {service}")
            print(f"Available services: {', '.join(service_map.keys())}")
            return False
        
        # Update in .env.websearch
        self._update_env_file(env_var, new_key)
        
        # Update in docker-compose.yml
        self._update_docker_compose(env_var, new_key)
        
        print(f"✅ Updated {service} API key: {self._mask_key(new_key)}")
        return True
    
    def _update_env_file(self, env_var: str, new_key: str) -> None:
        """Update API key in .env.websearch file."""
        lines = []
        if self.env_file.exists():
            with open(self.env_file, 'r') as f:
                lines = f.readlines()
        
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{env_var}="):
                lines[i] = f"{env_var}={new_key}\n"
                updated = True
                break
        
        if not updated:
            lines.append(f"{env_var}={new_key}\n")
        
        with open(self.env_file, 'w') as f:
            f.writelines(lines)
    
    def _update_docker_compose(self, env_var: str, new_key: str) -> None:
        """Update API key in docker-compose.yml."""
        if not self.docker_compose_file.exists():
            return
        
        with open(self.docker_compose_file, 'r') as f:
            content = f.read()
        
        # Update the environment variable
        old_pattern = f'{env_var}: "${{{env_var}:-[^"]*}}"'
        new_pattern = f'{env_var}: "${{{env_var}:-{new_key}}}"'
        
        import re
        content = re.sub(old_pattern, new_pattern, content)
        
        with open(self.docker_compose_file, 'w') as f:
            f.write(content)
    
    def validate_key(self, service: str) -> bool:
        """Validate an API key by testing the service."""
        service = service.lower()
        
        if service == 'tavily':
            return self._validate_tavily()
        elif service == 'serpapi':
            return self._validate_serpapi()
        else:
            print(f"❌ Validation not implemented for: {service}")
            return False
    
    def _validate_tavily(self) -> bool:
        """Validate Tavily API key."""
        import httpx
        import asyncio
        
        api_key = self.keys.get('TAVILY_API_KEY')
        if not api_key or api_key == "Not configured":
            print("❌ Tavily API key not configured")
            return False
        
        async def test():
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.post(
                        "https://api.tavily.com/search",
                        json={
                            "api_key": api_key,
                            "query": "test query",
                            "max_results": 1,
                        }
                    )
                    if response.status_code == 200:
                        data = response.json()
                        if "results" in data:
                            print("✅ Tavily API key is valid")
                            return True
                    print(f"❌ Tavily API key invalid: {response.status_code}")
                    return False
            except Exception as e:
                print(f"❌ Tavily validation failed: {e}")
                return False
        
        return asyncio.run(test())
    
    def rotate_key(self, service: str) -> bool:
        """Rotate to backup API key."""
        if service.lower() == 'tavily':
            backup_key = self.keys.get('TAVILY_API_KEY_BACKUP')
            dev_key = self.keys.get('TAVILY_API_KEY_DEV')
            
            if backup_key and backup_key != "Not configured":
                print("🔄 Rotating to backup Tavily key...")
                return self.update_key('tavily', backup_key)
            elif dev_key and dev_key != "Not configured":
                print("🔄 Rotating to dev Tavily key...")
                return self.update_key('tavily', dev_key)
            else:
                print("❌ No backup keys available for rotation")
                return False
        else:
            print(f"❌ Rotation not implemented for: {service}")
            return False

def main():
    parser = argparse.ArgumentParser(description="Manage API keys for Resonant platform")
    parser.add_argument('--list', action='store_true', help='List all API keys')
    parser.add_argument('--update', nargs=2, metavar=('SERVICE', 'KEY'), help='Update API key')
    parser.add_argument('--validate', metavar='SERVICE', help='Validate API key')
    parser.add_argument('--rotate', metavar='SERVICE', help='Rotate API key')
    
    args = parser.parse_args()
    
    manager = APIKeyManager()
    
    if args.list:
        manager.list_keys()
    elif args.update:
        service, key = args.update
        manager.update_key(service, key)
    elif args.validate:
        manager.validate_key(args.validate)
    elif args.rotate:
        manager.rotate_key(args.rotate)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
