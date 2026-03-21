"""
CASCADE Control Plane - Dependency Graph Engine
Builds and maintains the full dependency graph of the codebase.
"""

import ast
import os
import re
import fnmatch
from pathlib import Path
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime
import networkx as nx

from .models import (
    DependencyNode, DependencyConnection, DependencyGraph,
    NodeType, ConnectionType, ProtectedZone, RiskLevel,
    DEFAULT_PROTECTED_ZONES
)


class DependencyEngine:
    """Builds and queries the dependency graph"""
    
    def __init__(self):
        self.graph: Optional[DependencyGraph] = None
        self.nx_graph: Optional[nx.DiGraph] = None
        self.protected_zones = DEFAULT_PROTECTED_ZONES
        self._service_patterns = {
            "auth_service": ["auth", "jwt", "token", "session"],
            "gateway": ["gateway", "proxy", "middleware", "route"],
            "memory_service": ["memory", "hash_sphere", "embedding", "resonance"],
            "chat_service": ["chat", "message", "conversation", "resonant_chat"],
            "agent_engine_service": ["agent", "autonomous", "daemon", "spawn"],
            "billing_service": ["billing", "stripe", "payment", "subscription"],
            "cognitive_service": ["cognitive", "llm", "inference"],
            "rara_service": ["rara", "physics", "state"],
            "rg_ast_analysis": ["visualizer", "analyzer", "graph"],
            "frontend": ["component", "page", "hook", "context"]
        }
    
    async def build_graph(self, root_path: str) -> DependencyGraph:
        """Build the full dependency graph from a codebase"""
        self.graph = DependencyGraph(
            protected_zones=self.protected_zones
        )
        self.nx_graph = nx.DiGraph()
        
        # Discover services
        services = self._discover_services(root_path)
        self.graph.services = services
        
        # Analyze each service
        for service in services:
            service_path = os.path.join(root_path, service)
            if os.path.isdir(service_path):
                await self._analyze_service(service, service_path)
        
        # Resolve cross-service connections
        self._resolve_connections()
        
        # Mark protected zones
        self._mark_protected_zones()
        
        return self.graph
    
    def _discover_services(self, root_path: str) -> List[str]:
        """Discover all services in the codebase - matches Code Visualizer logic"""
        services = []
        skip_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.venv', 'dist', 'build', 'logs', 'k8s', 'deploy', 'nginx', 'docker', 'monitoring', 'workflows'}
        
        for item in os.listdir(root_path):
            item_path = os.path.join(root_path, item)
            if os.path.isdir(item_path) and not item.startswith('.') and item not in skip_dirs:
                # Check if directory has Python files
                has_python = False
                for root_dir, dirs, files in os.walk(item_path):
                    dirs[:] = [d for d in dirs if d not in ['__pycache__', 'node_modules', '.git', 'venv']]
                    if any(f.endswith('.py') for f in files):
                        has_python = True
                        break
                
                if has_python:
                    services.append(item)
        
        return sorted(services)
    
    async def _analyze_service(self, service_name: str, service_path: str):
        """Analyze a single service"""
        # Add service node
        service_node = DependencyNode(
            id=f"service:{service_name}",
            name=service_name,
            type=NodeType.SERVICE,
            file_path=service_path,
            service=service_name
        )
        self.graph.nodes[service_node.id] = service_node
        self.nx_graph.add_node(service_node.id, **service_node.dict())
        
        # Walk through all Python files
        for root, dirs, files in os.walk(service_path):
            # Skip common non-code directories
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'node_modules', 'venv', '.venv', 'dist', 'build']]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    await self._analyze_python_file(service_name, file_path)
                elif file.endswith(('.ts', '.tsx', '.js', '.jsx')):
                    file_path = os.path.join(root, file)
                    await self._analyze_js_file(service_name, file_path)
    
    async def _analyze_python_file(self, service_name: str, file_path: str):
        """Analyze a Python file using AST"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            return
        
        rel_path = os.path.basename(file_path)
        file_id = f"file:{service_name}:{rel_path}"
        
        # Add file node
        file_node = DependencyNode(
            id=file_id,
            name=rel_path,
            type=NodeType.FILE,
            file_path=file_path,
            service=service_name,
            line_start=1,
            line_end=len(source.splitlines())
        )
        self.graph.nodes[file_id] = file_node
        self.nx_graph.add_node(file_id, **file_node.dict())
        
        # Connect file to service
        conn = DependencyConnection(
            source_id=f"service:{service_name}",
            target_id=file_id,
            type=ConnectionType.IMPORT
        )
        self.graph.connections.append(conn)
        self.nx_graph.add_edge(conn.source_id, conn.target_id)
        
        # Analyze AST
        analyzer = PythonASTAnalyzer(file_path, service_name, file_id)
        nodes, connections = analyzer.analyze(tree)
        
        for node in nodes:
            self.graph.nodes[node.id] = node
            self.nx_graph.add_node(node.id, **node.dict())
        
        for conn in connections:
            self.graph.connections.append(conn)
            self.nx_graph.add_edge(conn.source_id, conn.target_id)
    
    async def _analyze_js_file(self, service_name: str, file_path: str):
        """Analyze a JavaScript/TypeScript file (basic pattern matching)"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
        except:
            return
        
        rel_path = os.path.basename(file_path)
        file_id = f"file:{service_name}:{rel_path}"
        
        # Add file node
        file_node = DependencyNode(
            id=file_id,
            name=rel_path,
            type=NodeType.FILE,
            file_path=file_path,
            service=service_name
        )
        self.graph.nodes[file_id] = file_node
        self.nx_graph.add_node(file_id, **file_node.dict())
        
        # Extract imports
        import_pattern = r"import\s+.*?\s+from\s+['\"](.+?)['\"]"
        for match in re.finditer(import_pattern, source):
            imported = match.group(1)
            conn = DependencyConnection(
                source_id=file_id,
                target_id=f"module:{imported}",
                type=ConnectionType.IMPORT
            )
            self.graph.connections.append(conn)
        
        # Extract API calls
        api_pattern = r"fetch\(['\"](.+?)['\"]|axios\.(get|post|put|delete)\(['\"](.+?)['\"]"
        for match in re.finditer(api_pattern, source):
            url = match.group(1) or match.group(3)
            if url:
                conn = DependencyConnection(
                    source_id=file_id,
                    target_id=f"api:{url}",
                    type=ConnectionType.HTTP
                )
                self.graph.connections.append(conn)
    
    def _resolve_connections(self):
        """Resolve module references to actual files"""
        # Build a map of module names to file nodes
        module_map = {}
        for node_id, node in self.graph.nodes.items():
            if node.type == NodeType.FILE:
                # Extract module name from file path
                module_name = os.path.splitext(os.path.basename(node.file_path))[0]
                module_map[module_name] = node_id
                
                # Also map by service.module
                full_name = f"{node.service}.{module_name}"
                module_map[full_name] = node_id
        
        # Update connections to point to actual files
        for conn in self.graph.connections:
            if conn.target_id.startswith("module:"):
                module_name = conn.target_id.replace("module:", "")
                # Try to find the actual file
                parts = module_name.split(".")
                resolved = False
                
                for i in range(len(parts), 0, -1):
                    partial = ".".join(parts[:i])
                    if partial in module_map:
                        conn.target_id = module_map[partial]
                        resolved = True
                        break
                
                # If not resolved, check for known broken modules
                if not resolved:
                    broken_patterns = [
                        "crypto.encrypt_api_key",
                        "crypto.decrypt_api_key", 
                        "rate_limit.rate_limit",
                        "email_verification.send_verification_email",
                        "login_notifications.process_login_notification",
                        "mfa.MFAManager",
                        "oauth.OAuthManager",
                        "saml.is_saml_enabled",
                        "sessions.get_active_sessions",
                        "security_headers.SecurityHeadersMiddleware"
                    ]
                    
                    if any(pattern in module_name for pattern in broken_patterns):
                        conn.status = ConnectionStatus.BROKEN
    
    def _mark_protected_zones(self):
        """Mark nodes that belong to protected zones"""
        for node_id, node in self.graph.nodes.items():
            for zone in self.protected_zones:
                # Check file path patterns
                for pattern in zone.patterns:
                    if fnmatch.fnmatch(node.file_path, pattern):
                        node.protected_zone = zone.name
                        node.risk_level = zone.risk_level
                        break
                
                # Check keywords in node name
                if not node.protected_zone:
                    for keyword in zone.keywords:
                        if keyword.lower() in node.name.lower():
                            node.protected_zone = zone.name
                            node.risk_level = zone.risk_level
                            break
    
    def get_affected_nodes(self, node_id: str, depth: int = 3) -> Set[str]:
        """Get all nodes affected by a change to the given node"""
        if not self.nx_graph or node_id not in self.nx_graph:
            return set()
        
        affected = set()
        
        # Get all nodes that depend on this node (predecessors in reverse dependency)
        # and all nodes this node depends on (successors)
        try:
            # Nodes that import/call this node
            predecessors = nx.ancestors(self.nx_graph, node_id)
            affected.update(predecessors)
            
            # Nodes this node imports/calls
            successors = nx.descendants(self.nx_graph, node_id)
            affected.update(successors)
            
            # Limit by depth using BFS
            if depth > 0:
                bfs_nodes = set()
                for n in nx.bfs_tree(self.nx_graph.to_undirected(), node_id, depth_limit=depth):
                    bfs_nodes.add(n)
                affected = affected.intersection(bfs_nodes)
        except nx.NetworkXError:
            pass
        
        return affected
    
    def get_cascade_path(self, node_id: str) -> List[List[str]]:
        """Get all paths that could cascade from a change"""
        if not self.nx_graph or node_id not in self.nx_graph:
            return []
        
        paths = []
        try:
            # Find all simple paths from this node to any endpoint
            endpoints = [n for n, d in self.graph.nodes.items() 
                        if d.type == NodeType.ENDPOINT]
            
            for endpoint in endpoints[:10]:  # Limit for performance
                try:
                    for path in nx.all_simple_paths(self.nx_graph, node_id, endpoint, cutoff=5):
                        paths.append(path)
                except nx.NetworkXNoPath:
                    pass
        except:
            pass
        
        return paths
    
    def find_node_by_path(self, file_path: str) -> Optional[DependencyNode]:
        """Find a node by its file path"""
        for node in self.graph.nodes.values():
            if node.file_path == file_path or node.file_path.endswith(file_path):
                return node
        return None


class PythonASTAnalyzer(ast.NodeVisitor):
    """AST analyzer for Python files"""
    
    def __init__(self, file_path: str, service_name: str, file_id: str):
        self.file_path = file_path
        self.service_name = service_name
        self.file_id = file_id
        self.nodes: List[DependencyNode] = []
        self.connections: List[DependencyConnection] = []
        self.current_class: Optional[str] = None
    
    def analyze(self, tree: ast.AST) -> Tuple[List[DependencyNode], List[DependencyConnection]]:
        self.visit(tree)
        return self.nodes, self.connections
    
    def visit_ClassDef(self, node: ast.ClassDef):
        class_id = f"class:{self.service_name}:{node.name}"
        class_node = DependencyNode(
            id=class_id,
            name=node.name,
            type=NodeType.CLASS,
            file_path=self.file_path,
            service=self.service_name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno
        )
        self.nodes.append(class_node)
        
        # Connect to file
        self.connections.append(DependencyConnection(
            source_id=self.file_id,
            target_id=class_id,
            type=ConnectionType.IMPORT
        ))
        
        # Check for inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.connections.append(DependencyConnection(
                    source_id=class_id,
                    target_id=f"class:*:{base.id}",
                    type=ConnectionType.INHERIT
                ))
        
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._visit_function(node)
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._visit_function(node)
    
    def _visit_function(self, node):
        prefix = f"{self.current_class}." if self.current_class else ""
        func_id = f"func:{self.service_name}:{prefix}{node.name}"
        
        # Check if it's an API endpoint
        is_endpoint = False
        http_method = None
        route = None
        
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Attribute):
                    method = decorator.func.attr
                    if method in ['get', 'post', 'put', 'delete', 'patch']:
                        is_endpoint = True
                        http_method = method.upper()
                        if decorator.args:
                            if isinstance(decorator.args[0], ast.Constant):
                                route = decorator.args[0].value
            elif isinstance(decorator, ast.Attribute):
                if decorator.attr in ['get', 'post', 'put', 'delete', 'patch']:
                    is_endpoint = True
                    http_method = decorator.attr.upper()
        
        node_type = NodeType.ENDPOINT if is_endpoint else NodeType.FUNCTION
        func_node = DependencyNode(
            id=func_id,
            name=node.name,
            type=node_type,
            file_path=self.file_path,
            service=self.service_name,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            metadata={
                "http_method": http_method,
                "route": route,
                "is_async": isinstance(node, ast.AsyncFunctionDef)
            }
        )
        self.nodes.append(func_node)
        
        # Connect to file or class
        parent_id = f"class:{self.service_name}:{self.current_class}" if self.current_class else self.file_id
        self.connections.append(DependencyConnection(
            source_id=parent_id,
            target_id=func_id,
            type=ConnectionType.IMPORT
        ))
        
        self.generic_visit(node)
    
    def visit_Call(self, node: ast.Call):
        # Detect HTTP calls
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['get', 'post', 'put', 'delete', 'request']:
                # Check if it's httpx or requests
                if isinstance(node.func.value, ast.Name):
                    if node.func.value.id in ['httpx', 'requests', 'client', 'http_client']:
                        if node.args:
                            if isinstance(node.args[0], ast.Constant):
                                url = node.args[0].value
                                self.connections.append(DependencyConnection(
                                    source_id=self.file_id,
                                    target_id=f"api:{url}",
                                    type=ConnectionType.HTTP
                                ))
        
        self.generic_visit(node)
