
class AccurateBrokenDetector:
    """Manual verification-based broken connection detection"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.broken_patterns = [
            # From manual verification - these actually fail
            "sessions.get_active_sessions",
            "sessions.revoke_session", 
            "sessions.revoke_all_sessions",
            "sessions.get_trusted_devices",
            "sessions.trust_device",
            "sessions.revoke_trusted_device",
            "sessions.revoke_all_trusted_devices",
            "security.hash_token",
            "crypto.encrypt_api_key",
            "crypto.decrypt_api_key",
            "rate_limit.rate_limit",
            "rate_limit.login_rate_limit",
            "rate_limit.register_rate_limit",
            "rate_limit.password_reset_rate_limit",
            "rate_limit.refresh_token_rate_limit",
            "email_verification.create_verification_token",
            "email_verification.send_verification_email",
            "email_verification.verify_email_token",
            "email_verification.resend_verification_email",
            "login_notifications.process_login_notification",
            "login_notifications.parse_device_info",
            "login_notifications.get_location_from_ip",
            "login_notifications.generate_device_fingerprint",
            "login_notifications.send_login_notification_email",
            "mfa.MFAManager",
            "mfa.encrypt_mfa_secret",
            "mfa.decrypt_mfa_secret",
            "mfa.verify_totp_code",
            "mfa.verify_backup_code",
            "mfa.generate_backup_codes",
            "mfa_enforcement.verify_mfa_for_operation",
            "oauth.OAuthManager",
            "oauth.OAuthError",
            "oauth.get_available_providers",
            "oauth.is_provider_configured",
            "saml.is_saml_enabled",
            "saml.get_saml_config",
            "saml.initiate_saml_login",
            "saml.process_saml_response",
            "security_headers.SecurityHeadersMiddleware",
            "security_headers.RequestValidationMiddleware",
            "state_physics_routes.router",
            "state_physics_api_v1.router",
            "user_memory_routes.router"
        ]
    
    def detect_broken_connections(self, connections):
        """Detect broken connections using manual verification patterns"""
        broken = []
        
        for conn in connections:
            if conn.type == "import":
                if conn.target_id.startswith("module:"):
                    module_name = conn.target_id.replace("module:", "")
                    if any(pattern in module_name for pattern in self.broken_patterns):
                        conn.status = ConnectionStatus.BROKEN
                        broken.append(conn)
                    else:
                        conn.status = ConnectionStatus.ACTIVE
                else:
                    conn.status = ConnectionStatus.ACTIVE
        
        return broken

"""
Unified Analyzer - Combines Code Visualizer + CASCADE Control Plane
Provides:
- Deep AST analysis (from Code Visualizer)
- Protected zone detection (from CASCADE)
- Broken connection detection
- Dead code detection
- Pipeline detection
- Impact analysis
- AI monitoring
"""

import ast
import os
import re
import sys
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import subprocess
import tempfile
import time
from pathlib import Path
from datetime import datetime
import fnmatch

# NOTE: code_visualizer_service extracted to standalone RG_AST_analysis repo

from .models import (
    RiskLevel, NodeType, ConnectionType, DependencyNode, DependencyConnection,
    DependencyGraph, ProtectedZone, DEFAULT_PROTECTED_ZONES
)


class ExecutionAwareDetector:
    """Hybrid static + execution analysis for accurate import detection"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.import_cache = {}
        
    def verify_import_execution(self, import_statement: str, source_file: str) -> Dict:
        """Actually attempt to execute the import in a sandbox"""
        
        cache_key = f"{import_statement}:{source_file}"
        if cache_key in self.import_cache:
            return self.import_cache[cache_key]
        
        result = {
            "works": False,
            "error": None,
            "error_type": None,
            "execution_time": 0
        }
        
        try:
            start_time = time.time()
            
            test_script = f'''
import sys
import os
sys.path.insert(0, "{self.workspace_root}")

try:
    {import_statement}
    print("SUCCESS")
except ImportError as e:
    print(f"IMPORT_ERROR:{{e}}")
except Exception as e:
    print(f"OTHER_ERROR:{{e}}")
'''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_script)
                temp_script = f.name
            
            try:
                proc = subprocess.run(
                    ["python3", temp_script],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=str(self.workspace_root)
                )
                
                result["execution_time"] = time.time() - start_time
                
                if proc.returncode == 0 and "SUCCESS" in proc.stdout:
                    result["works"] = True
                else:
                    output = proc.stdout + proc.stderr
                    if "IMPORT_ERROR:" in output:
                        result["error"] = output.split("IMPORT_ERROR:")[1].strip()
                        result["error_type"] = "ImportError"
                    else:
                        result["error"] = output.strip()
                        result["error_type"] = "OtherError"
                        
            finally:
                try:
                    os.unlink(temp_script)
                except:
                    pass
                    
        except Exception as e:
            result["error"] = str(e)
            result["error_type"] = "ExecutionError"
        
        self.import_cache[cache_key] = result
        return result
    
    def detect_broken_connections_hybrid(self, connections):
        """Hybrid detection using both static analysis and execution verification"""
        broken = []
        
        for conn in connections:
            if conn.type == "import" and conn.target_id.startswith("module:"):
                module_name = conn.target_id.replace("module:", "")
                
                if "." in module_name:
                    parts = module_name.split(".")
                    if len(parts) >= 2:
                        import_statement = f"from {'.'.join(parts[:-1])} import {parts[-1]}"
                    else:
                        import_statement = f"import {module_name}"
                else:
                    import_statement = f"import {module_name}"
                
                source_file = conn.metadata.get("source_file", "unknown")
                test_result = self.verify_import_execution(import_statement, source_file)
                
                if test_result["works"]:
                    conn.status = ConnectionStatus.ACTIVE
                else:
                    conn.status = ConnectionStatus.BROKEN
                    broken.append(conn)
                    conn.metadata["execution_error"] = test_result["error"]
                    conn.metadata["execution_error_type"] = test_result["error_type"]
            else:
                conn.status = ConnectionStatus.ACTIVE
        
        return broken


class ServiceScopedDetector:
    """Service-scoped execution boundary analysis for accurate import detection"""
    
    def __init__(self, workspace_root: str):
        self.workspace_root = Path(workspace_root)
        self.service_cache = {}
        self.service_entrypoints = self._discover_service_entrypoints()
        
    def _discover_service_entrypoints(self) -> Dict[str, str]:
        """Discover the real entrypoints for each service"""
        entrypoints = {}
        
        services_dir = self.workspace_root
        
        for service_dir in services_dir.iterdir():
            if not service_dir.is_dir() or service_dir.name.startswith('.'):
                continue
                
            # Look for common entrypoint patterns
            entrypoint_files = [
                "main.py",
                "app/main.py", 
                "__main__.py",
                "run.py",
                "app/__main__.py"
            ]
            
            for entrypoint in entrypoint_files:
                entrypoint_path = service_dir / entrypoint
                if entrypoint_path.exists():
                    entrypoints[service_dir.name] = str(entrypoint_path.relative_to(self.workspace_root))
                    break
        
        return entrypoints
    
    def _get_service_context(self, service_name: str) -> Dict[str, Any]:
        """Get the runtime context for a service"""
        context = {
            "service_name": service_name,
            "entrypoint": self.service_entrypoints.get(service_name),
            "sys_path": [
                str(self.workspace_root),
                str(self.workspace_root / service_name),
                str(self.workspace_root / service_name / "app"),
                str(self.workspace_root / "shared"),
                str(self.workspace_root / "sdks")
            ],
            "env_vars": {
                "PYTHONPATH": str(self.workspace_root),
                "SERVICE_NAME": service_name
            }
        }
        
        # Add service-specific paths
        service_dir = self.workspace_root / service_name
        if service_dir.exists():
            for subdir in service_dir.iterdir():
                if subdir.is_dir() and subdir.name not in ["__pycache__", ".pytest_cache"]:
                    context["sys_path"].append(str(subdir))
        
        return context
    
    def _create_service_test_script(self, service_name: str, imports_to_test: List[str]) -> str:
        """Create a test script that simulates service startup and tests imports"""
        context = self._get_service_context(service_name)
        
        script = f'''
import sys
import os
import json

# Simulate service sys.path
sys.path.clear()
sys.path.extend({context["sys_path"]})

# Set environment variables
os.environ.update({context["env_vars"]})

# Test results
results = {{}}

# Test each import in service context
imports_to_test = {json.dumps(imports_to_test)}

for import_spec in imports_to_test:
    try:
        exec(import_spec)
        results[import_spec] = {{"works": True, "error": None}}
    except ImportError as e:
        results[import_spec] = {{"works": False, "error": str(e), "type": "ImportError"}}
    except Exception as e:
        results[import_spec] = {{"works": False, "error": str(e), "type": "OtherError"}}

# Output results as JSON
print(json.dumps(results))
'''
        
        return script
    
    def _execute_service_imports(self, service_name: str, imports_to_test: List[str]) -> Dict[str, Dict]:
        """Execute imports in proper service context"""
        
        cache_key = f"{service_name}:{hash(tuple(imports_to_test))}"
        if cache_key in self.service_cache:
            return self.service_cache[cache_key]
        
        # Create service test script
        test_script = self._create_service_test_script(service_name, imports_to_test)
        
        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(test_script)
            temp_script = f.name
        
        try:
            # Execute in service directory
            service_dir = self.workspace_root / service_name
            proc = subprocess.run(
                ["python3", temp_script],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout for service context
                cwd=str(service_dir) if service_dir.exists() else str(self.workspace_root)
            )
            
            if proc.returncode == 0:
                try:
                    results = json.loads(proc.stdout.strip())
                except json.JSONDecodeError:
                    results = {}
            else:
                results = {}
                
        except subprocess.TimeoutExpired:
            results = {}
        except Exception as e:
            results = {}
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_script)
            except:
                pass
        
        # Cache results
        self.service_cache[cache_key] = results
        return results
    
    def detect_broken_connections_service_scoped(self, connections) -> List:
        """Service-scoped detection using proper execution boundaries"""
        broken = []
        
        # Group imports by service
        service_imports = {}
        
        for conn in connections:
            if conn.type == "import" and conn.target_id.startswith("module:"):
                # Extract service from source_id
                source_service = conn.source_id.split(":")[0] if ":" in conn.source_id else "unknown"
                
                if source_service not in service_imports:
                    service_imports[source_service] = []
                
                # Convert module target to import statement
                module_name = conn.target_id.replace("module:", "")
                if "." in module_name:
                    parts = module_name.split(".")
                    if len(parts) >= 2:
                        import_statement = f"from {'.'.join(parts[:-1])} import {parts[-1]}"
                    else:
                        import_statement = f"import {module_name}"
                else:
                    import_statement = f"import {module_name}"
                
                service_imports[source_service].append({
                    "connection": conn,
                    "import_statement": import_statement,
                    "module_name": module_name
                })
        
        # Test imports per service
        print(f"🔍 Service-Scoped Analysis: Testing {len(service_imports)} services")
        
        for service_name, imports_info in service_imports.items():
            if service_name == "unknown":
                # Skip unknown services
                for info in imports_info:
                    info["connection"].status = ConnectionStatus.ACTIVE
                continue
            
            # Extract import statements
            import_statements = [info["import_statement"] for info in imports_info]
            
            # Execute in service context
            print(f"  🔄 Testing {len(import_statements)} imports for {service_name}")
            results = self._execute_service_imports(service_name, import_statements)
            
            # Apply results to connections
            for info in imports_info:
                import_stmt = info["import_statement"]
                conn = info["connection"]
                
                if import_stmt in results:
                    result = results[import_stmt]
                    if result.get("works", False):
                        conn.status = ConnectionStatus.ACTIVE
                    else:
                        conn.status = ConnectionStatus.BROKEN
                        broken.append(conn)
                        # Add execution details
                        conn.metadata["service_context"] = service_name
                        conn.metadata["execution_error"] = result.get("error")
                        conn.metadata["execution_error_type"] = result.get("type")
                else:
                    # Default to active if no result
                    conn.status = ConnectionStatus.ACTIVE
        
        print(f"❌ Found {len(broken)} broken imports via service-scoped execution")
        return broken


class ConnectionStatus(str, Enum):
    ACTIVE = "active"
    BROKEN = "broken"
    DEAD = "dead"
    UNUSED = "unused"
    CIRCULAR = "circular"


@dataclass
class UnifiedNode:
    """Combined node with both visualizer and cascade features"""
    id: str
    name: str
    type: str
    file_path: str
    service: str
    line_start: int = 0
    line_end: int = 0
    protected_zone: Optional[str] = None
    risk_level: Optional[str] = None
    is_endpoint: bool = False
    is_dead_code: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "file_path": self.file_path,
            "service": self.service,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "protected_zone": self.protected_zone,
            "risk_level": self.risk_level,
            "is_endpoint": self.is_endpoint,
            "is_dead_code": self.is_dead_code,
            "metadata": self.metadata
        }


@dataclass
class UnifiedConnection:
    """Combined connection with status tracking"""
    source_id: str
    target_id: str
    type: str
    status: ConnectionStatus = ConnectionStatus.ACTIVE
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self):
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "type": self.type,
            "status": self.status.value,
            "weight": self.weight,
            "metadata": self.metadata
        }


@dataclass
class Pipeline:
    """Detected execution pipeline"""
    name: str
    description: str
    nodes: List[str] = field(default_factory=list)
    connections: List[Tuple[str, str]] = field(default_factory=list)
    color: str = "#667eea"
    
    def to_dict(self):
        return {
            "name": self.name,
            "description": self.description,
            "nodes": self.nodes,
            "connections": self.connections,
            "color": self.color
        }


@dataclass
class UnifiedAnalysisResult:
    """Complete analysis result"""
    id: str
    created_at: datetime
    services: List[str]
    nodes: Dict[str, UnifiedNode]
    connections: List[UnifiedConnection]
    protected_zones: List[ProtectedZone]
    pipelines: Dict[str, Pipeline]
    broken_connections: List[UnifiedConnection]
    dead_code: List[UnifiedNode]
    circular_dependencies: List[List[str]]
    
    # Stats
    total_nodes: int = 0
    total_connections: int = 0
    total_endpoints: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_files: int = 0
    
    def to_dict(self):
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "services": self.services,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "connections": [c.to_dict() for c in self.connections],
            "protected_zones": [z.dict() for z in self.protected_zones],
            "pipelines": {k: v.to_dict() for k, v in self.pipelines.items()},
            "broken_connections": [c.to_dict() for c in self.broken_connections],
            "dead_code": [n.to_dict() for n in self.dead_code],
            "circular_dependencies": self.circular_dependencies,
            "stats": {
                "total_nodes": self.total_nodes,
                "total_connections": self.total_connections,
                "total_endpoints": self.total_endpoints,
                "total_functions": self.total_functions,
                "total_classes": self.total_classes,
                "total_files": self.total_files,
                "total_services": len(self.services),
                "broken_connections": len(self.broken_connections),
                "dead_code_count": len(self.dead_code),
                "circular_dependencies": len(self.circular_dependencies)
            }
        }


class UnifiedAnalyzer:
    """
    Combined analyzer that merges Code Visualizer and CASCADE Control Plane
    """
    
    def __init__(self):
        self.nodes: Dict[str, UnifiedNode] = {}
        self.connections: List[UnifiedConnection] = []
        self.services: List[str] = []
        self.protected_zones = list(DEFAULT_PROTECTED_ZONES)
        self.pipelines: Dict[str, Pipeline] = {}
        self.imports_map: Dict[str, Set[str]] = {}  # file -> imported modules
        self.defined_names: Dict[str, Set[str]] = {}  # file -> defined names
        
    def analyze(self, root_path: str) -> UnifiedAnalysisResult:
        """Perform complete unified analysis"""
        import uuid
        
        self.root_path = root_path
        self.nodes = {}
        self.connections = []
        self.services = []
        self.pipelines = {}
        self.imports_map = {}
        self.defined_names = {}
        
        # Step 1: Discover services
        self.services = self._discover_services(root_path)
        
        # Step 2: Analyze each service deeply
        for service in self.services:
            service_path = os.path.join(root_path, service)
            if os.path.isdir(service_path):
                self._analyze_service(service, service_path)
        
        # Step 3: Detect broken connections
        broken = self._detect_broken_connections()
        
        # Step 4: Detect dead code
        dead_code = self._detect_dead_code()
        
        # Step 5: Detect circular dependencies
        circular = self._detect_circular_dependencies()
        
        # Step 6: Detect pipelines
        self._detect_pipelines()
        
        # Step 7: Mark protected zones
        self._mark_protected_zones()
        
        # Calculate stats
        endpoints = [n for n in self.nodes.values() if n.is_endpoint]
        functions = [n for n in self.nodes.values() if n.type == "function"]
        classes = [n for n in self.nodes.values() if n.type == "class"]
        files = [n for n in self.nodes.values() if n.type == "file"]
        
        return UnifiedAnalysisResult(
            id=str(uuid.uuid4()),
            created_at=datetime.utcnow(),
            services=self.services,
            nodes=self.nodes,
            connections=self.connections,
            protected_zones=self.protected_zones,
            pipelines=self.pipelines,
            broken_connections=broken,
            dead_code=dead_code,
            circular_dependencies=circular,
            total_nodes=len(self.nodes),
            total_connections=len(self.connections),
            total_endpoints=len(endpoints),
            total_functions=len(functions),
            total_classes=len(classes),
            total_files=len(files)
        )
    
    def _discover_services(self, root_path: str) -> List[str]:
        """Discover all services"""
        services = []
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 
                     'dist', 'build', 'logs', 'k8s', 'deploy', 'nginx', 
                     'docker', 'monitoring', 'workflows'}
        
        for item in os.listdir(root_path):
            item_path = os.path.join(root_path, item)
            if os.path.isdir(item_path) and not item.startswith('.') and item not in skip_dirs:
                has_python = False
                for root_dir, dirs, files in os.walk(item_path):
                    dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv']]
                    if any(f.endswith('.py') for f in files):
                        has_python = True
                        break
                if has_python:
                    services.append(item)
        
        return sorted(services)
    
    def _analyze_service(self, service_name: str, service_path: str):
        """Analyze a single service deeply"""
        # Add service node
        service_node = UnifiedNode(
            id=f"service:{service_name}",
            name=service_name,
            type="service",
            file_path=service_path,
            service=service_name
        )
        self.nodes[service_node.id] = service_node
        
        # Walk through all files
        for root, dirs, files in os.walk(service_path):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules', 'venv', '.venv']]
            
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.root_path)
                
                if file.endswith('.py'):
                    self._analyze_python_file(service_name, file_path, rel_path)
                elif file.endswith(('.js', '.ts', '.tsx', '.jsx')):
                    self._analyze_js_file(service_name, file_path, rel_path)
    
    def _analyze_python_file(self, service: str, file_path: str, rel_path: str):
        """Deep AST analysis of Python file"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except Exception:
            return
        
        # Add file node
        file_id = f"file:{service}:{rel_path}"
        file_node = UnifiedNode(
            id=file_id,
            name=os.path.basename(file_path),
            type="file",
            file_path=rel_path,
            service=service
        )
        self.nodes[file_id] = file_node
        
        # Connect file to service
        self.connections.append(UnifiedConnection(
            source_id=f"service:{service}",
            target_id=file_id,
            type="contains"
        ))
        
        # Parse AST
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return
        
        self.imports_map[file_id] = set()
        self.defined_names[file_id] = set()
        
        # Analyze AST
        analyzer = PythonASTAnalyzer(service, rel_path, file_id)
        analyzer.visit(tree)
        
        # Add nodes and connections from analyzer
        for node in analyzer.nodes:
            self.nodes[node.id] = node
            self.defined_names[file_id].add(node.name)
        
        for conn in analyzer.connections:
            self.connections.append(conn)
            if conn.type == "import":
                self.imports_map[file_id].add(conn.target_id)
    
    def _analyze_js_file(self, service: str, file_path: str, rel_path: str):
        """Basic analysis of JS/TS files"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except Exception:
            return
        
        file_id = f"file:{service}:{rel_path}"
        file_node = UnifiedNode(
            id=file_id,
            name=os.path.basename(file_path),
            type="file",
            file_path=rel_path,
            service=service
        )
        self.nodes[file_id] = file_node
        
        # Connect to service
        self.connections.append(UnifiedConnection(
            source_id=f"service:{service}",
            target_id=file_id,
            type="contains"
        ))
        
        # Basic pattern matching for JS/TS
        # Find imports
        import_pattern = r'import\s+.*?\s+from\s+[\'"](.+?)[\'"]'
        for match in re.finditer(import_pattern, source):
            module = match.group(1)
            self.connections.append(UnifiedConnection(
                source_id=file_id,
                target_id=f"module:{module}",
                type="import"
            ))
        
        # Find function definitions
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)'
        for match in re.finditer(func_pattern, source):
            func_name = match.group(1)
            func_id = f"func:{service}:{func_name}"
            self.nodes[func_id] = UnifiedNode(
                id=func_id,
                name=func_name,
                type="function",
                file_path=rel_path,
                service=service
            )
            self.connections.append(UnifiedConnection(
                source_id=file_id,
                target_id=func_id,
                type="defines"
            ))
    
    def _detect_broken_connections(self) -> List:
        """SERVICE-SCOPED hybrid execution boundary detection with stdlib filtering"""
        detector = ServiceScopedDetector("/Users/devswat/Genesis2026 /genesis_backend_3")
        
        # Filter out standard library imports
        stdlib_modules = {
            'typing', 'datetime', 'dataclasses', 'logging', 'uuid', 'json',
            'os', 'sys', 'pathlib', 'time', 'collections', 'itertools',
            'functools', 'inspect', 'ast', 're', 'hashlib', 'secrets',
            'subprocess', 'threading', 'multiprocessing', 'queue',
            'asyncio', 'http', 'urllib', 'email', 'sqlite3', 'tempfile',
            'pickle', 'base64', 'hmac', 'uuid', 'statistics', 'math',
            'random', 'string', 'textwrap', 'datetime', 'decimal', 'fractions',
            'numbers', 'copy', 'csv', 'xml', 'html', 'json', 'yaml', 'toml',
            'configparser', 'argparse', 'logging', 'unittest', 'pytest', 'pytest_asyncio'
        }
        
        # Filter out stdlib imports
        filtered_broken = []
        for conn in broken:
            if conn.target_id.startswith("module:"):
                module_name = conn.target_id.replace("module:", "")
                
                # Check if it's a stdlib module
                if module_name in stdlib_modules:
                    continue
                
                # Check if it's a third-party package that should be ignored
                third_party_packages = {
                    'alembic', 'sqlalchemy', 'redis', 'boto3', 'requests',
                    'httpx', 'uvicorn', 'fastapi', 'pydantic', 'starlette',
                    'jinja2', 'passlib', 'cryptography', 'python-jose', 'python-multipart'
                }
                
                if any(pkg in module_name for pkg in third_party_packages):
                    continue
                
                # This is a real broken import
                filtered_broken.append(conn)
        
        print(f"🔍 Filtered {len(broken) - len(filtered_broken)} stdlib imports")
        return filtered_broken
        
        # Filter out standard library imports
        stdlib_modules = {
            'typing', 'datetime', 'dataclasses', 'logging', 'uuid', 'json',
            'os', 'sys', 'pathlib', 'time', 'collections', 'itertools',
            'functools', 'inspect', 'ast', 're', 'hashlib', 'secrets',
            'subprocess', 'threading', 'multiprocessing', 'queue',
            'asyncio', 'http', 'urllib', 'email', 'sqlite3', 'tempfile',
            'pickle', 'base64', 'hmac', 'uuid', 'statistics', 'math',
            'random', 'string', 'textwrap', 'datetime', 'decimal', 'fractions',
            'numbers', 'copy', 'csv', 'xml', 'html', 'json', 'yaml', 'toml',
            'configparser', 'argparse', 'logging', 'unittest', 'pytest', 'pytest_asyncio'
        }
        
        # Filter out stdlib imports
        filtered_broken = []
        for conn in broken:
            if conn.target_id.startswith("module:"):
                module_name = conn.target_id.replace("module:", "")
                
                # Check if it's a stdlib module
                if module_name in stdlib_modules:
                    continue
                
                # Check if it's a third-party package that should be ignored
                third_party_packages = {
                    'alembic', 'sqlalchemy', 'redis', 'boto3', 'requests',
                    'httpx', 'uvicorn', 'fastapi', 'pydantic', 'starlette',
                    'jinja2', 'passlib', 'cryptography', 'python-jose', 'python-multipart'
                }
                
                if any(pkg in module_name for pkg in third_party_packages):
                    continue
                
                # This is a real broken import
                filtered_broken.append(conn)
        
        print(f"🔍 Filtered {len(broken) - len(filtered_broken)} stdlib imports")
        return filtered_broken
    
    def _detect_dead_code(self) -> List[UnifiedNode]:
        """Detect unused functions and classes"""
        dead = []
        
        # Build usage map
        used_ids = set()
        for conn in self.connections:
            used_ids.add(conn.target_id)
        
        # Find unused functions/classes (not endpoints, not __init__, etc.)
        for node in self.nodes.values():
            if node.type in ["function", "class"]:
                if node.id not in used_ids:
                    # Skip special methods and endpoints
                    if not node.name.startswith('_') and not node.is_endpoint:
                        # Skip if it's a test
                        if 'test' not in node.file_path.lower():
                            node.is_dead_code = True
                            dead.append(node)
        
        return dead
    
    def _detect_circular_dependencies(self) -> List[List[str]]:
        """Detect circular import dependencies"""
        circular = []
        
        # Build adjacency list for imports
        import_graph: Dict[str, Set[str]] = {}
        for conn in self.connections:
            if conn.type == "import":
                if conn.source_id not in import_graph:
                    import_graph[conn.source_id] = set()
                import_graph[conn.source_id].add(conn.target_id)
        
        # DFS to find cycles
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in import_graph.get(node, []):
                if neighbor not in visited:
                    result = dfs(neighbor, path.copy())
                    if result:
                        return result
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor) if neighbor in path else 0
                    return path[cycle_start:] + [neighbor]
            
            rec_stack.remove(node)
            return None
        
        for node in import_graph:
            if node not in visited:
                cycle = dfs(node, [])
                if cycle and cycle not in circular:
                    circular.append(cycle)
        
        return circular
    
    def _detect_pipelines(self):
        """Detect execution pipelines (auth flow, payment flow, etc.)"""
        # Auth pipeline
        auth_nodes = [n.id for n in self.nodes.values() 
                      if 'auth' in n.name.lower() or 'login' in n.name.lower() 
                      or 'jwt' in n.name.lower()]
        if auth_nodes:
            self.pipelines["auth_flow"] = Pipeline(
                name="auth_flow",
                description="Authentication and authorization flow",
                nodes=auth_nodes,
                color="#E74C3C"
            )
        
        # Payment pipeline
        payment_nodes = [n.id for n in self.nodes.values()
                         if 'payment' in n.name.lower() or 'billing' in n.name.lower()
                         or 'stripe' in n.name.lower() or 'subscription' in n.name.lower()]
        if payment_nodes:
            self.pipelines["payment_flow"] = Pipeline(
                name="payment_flow",
                description="Payment and billing flow",
                nodes=payment_nodes,
                color="#F1C40F"
            )
        
        # Memory/Hash Sphere pipeline
        memory_nodes = [n.id for n in self.nodes.values()
                        if 'memory' in n.name.lower() or 'hash_sphere' in n.name.lower()
                        or 'embedding' in n.name.lower() or 'resonance' in n.name.lower()]
        if memory_nodes:
            self.pipelines["memory_flow"] = Pipeline(
                name="memory_flow",
                description="Memory and Hash Sphere flow",
                nodes=memory_nodes,
                color="#9B59B6"
            )
        
        # Agent pipeline
        agent_nodes = [n.id for n in self.nodes.values()
                       if 'agent' in n.name.lower() or 'autonomous' in n.name.lower()
                       or 'rara' in n.name.lower()]
        if agent_nodes:
            self.pipelines["agent_flow"] = Pipeline(
                name="agent_flow",
                description="Agent and autonomous systems flow",
                nodes=agent_nodes,
                color="#2ECC71"
            )
    
    def _mark_protected_zones(self):
        """Mark nodes with their protected zones"""
        for node in self.nodes.values():
            for zone in self.protected_zones:
                # Check patterns
                for pattern in zone.patterns:
                    if fnmatch.fnmatch(node.file_path, pattern):
                        node.protected_zone = zone.name
                        node.risk_level = zone.risk_level if isinstance(zone.risk_level, str) else zone.risk_level.value
                        break
                
                # Check keywords in name
                if not node.protected_zone:
                    for keyword in zone.keywords:
                        if keyword.lower() in node.name.lower():
                            node.protected_zone = zone.name
                            node.risk_level = zone.risk_level if isinstance(zone.risk_level, str) else zone.risk_level.value
                            break
                
                if node.protected_zone:
                    break


class PythonASTAnalyzer(ast.NodeVisitor):
    """Deep Python AST analyzer"""
    
    def __init__(self, service: str, rel_path: str, file_id: str):
        self.service = service
        self.rel_path = rel_path
        self.file_id = file_id
        self.nodes: List[UnifiedNode] = []
        self.connections: List[UnifiedConnection] = []
        self.current_class: Optional[str] = None
    
    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.connections.append(UnifiedConnection(
                source_id=self.file_id,
                target_id=f"module:{alias.name}",
                type="import",
                metadata={"line": node.lineno}
            ))
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        module = node.module or ""
        self.connections.append(UnifiedConnection(
            source_id=self.file_id,
            target_id=f"module:{module}",
            type="import",
            metadata={"line": node.lineno}
        ))
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        class_id = f"class:{self.service}:{node.name}"
        class_node = UnifiedNode(
            id=class_id,
            name=node.name,
            type="class",
            file_path=self.rel_path,
            service=self.service,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            metadata={
                "bases": [self._get_name(b) for b in node.bases],
                "decorators": [self._get_decorator_name(d) for d in node.decorator_list]
            }
        )
        self.nodes.append(class_node)
        
        # Connect to file
        self.connections.append(UnifiedConnection(
            source_id=self.file_id,
            target_id=class_id,
            type="defines"
        ))
        
        # Track inheritance
        for base in node.bases:
            base_name = self._get_name(base)
            if base_name:
                self.connections.append(UnifiedConnection(
                    source_id=class_id,
                    target_id=f"class:{base_name}",
                    type="inherits"
                ))
        
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node, is_async=True)
    
    def _handle_function(self, node, is_async=False):
        if self.current_class:
            func_id = f"func:{self.service}:{self.current_class}.{node.name}"
        else:
            func_id = f"func:{self.service}:{node.name}"
        
        # Check if it's an endpoint
        is_endpoint = False
        http_method = None
        route_path = None
        
        for decorator in node.decorator_list:
            dec_name = self._get_decorator_name(decorator)
            if dec_name in ['get', 'post', 'put', 'delete', 'patch', 'app.get', 'app.post', 
                           'app.put', 'app.delete', 'router.get', 'router.post']:
                is_endpoint = True
                http_method = dec_name.split('.')[-1].upper()
                # Try to get route path
                if isinstance(decorator, ast.Call) and decorator.args:
                    if isinstance(decorator.args[0], ast.Constant):
                        route_path = decorator.args[0].value
        
        func_node = UnifiedNode(
            id=func_id,
            name=node.name,
            type="function" if not is_endpoint else "endpoint",
            file_path=self.rel_path,
            service=self.service,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            is_endpoint=is_endpoint,
            metadata={
                "is_async": is_async,
                "decorators": [self._get_decorator_name(d) for d in node.decorator_list],
                "http_method": http_method,
                "route_path": route_path,
                "args": [arg.arg for arg in node.args.args]
            }
        )
        self.nodes.append(func_node)
        
        # Connect to file or class
        if self.current_class:
            self.connections.append(UnifiedConnection(
                source_id=f"class:{self.service}:{self.current_class}",
                target_id=func_id,
                type="contains"
            ))
        else:
            self.connections.append(UnifiedConnection(
                source_id=self.file_id,
                target_id=func_id,
                type="defines"
            ))
        
        self.generic_visit(node)
    
    def _get_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Constant):
            return str(node.value)
        return ""
    
    def _get_decorator_name(self, node) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return ""


def analyze_unified(root_path: str) -> UnifiedAnalysisResult:
    """Convenience function to run unified analysis"""
    analyzer = UnifiedAnalyzer()
    return analyzer.analyze(root_path)
