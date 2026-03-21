"""
CASCADE Control Plane - Change Impact Analyzer
Analyzes the impact of proposed code changes before they are applied.
"""

import fnmatch
from typing import Dict, List, Set, Optional, Any
from datetime import datetime

from .models import (
    CodeChange, ChangeImpact, ChangeType, RiskLevel,
    ProtectedZone, DependencyNode, DependencyGraph,
    DEFAULT_PROTECTED_ZONES
)
from .dependency_engine import DependencyEngine


class ImpactAnalyzer:
    """Analyzes the impact of code changes"""
    
    def __init__(self, dependency_engine: DependencyEngine):
        self.engine = dependency_engine
        self.protected_zones = DEFAULT_PROTECTED_ZONES
    
    async def analyze_change(self, change: CodeChange) -> ChangeImpact:
        """Analyze the full impact of a proposed change"""
        impact = ChangeImpact(change_id=change.id)
        
        # Find the node being changed
        node = self.engine.find_node_by_path(change.file_path)
        
        if node:
            # Get affected nodes
            affected_ids = self.engine.get_affected_nodes(node.id, depth=4)
            impact.affected_nodes = list(affected_ids)
            
            # Get affected services
            services = set()
            for node_id in affected_ids:
                affected_node = self.engine.graph.nodes.get(node_id)
                if affected_node:
                    services.add(affected_node.service)
            impact.affected_services = list(services)
            
            # Calculate cascade depth
            paths = self.engine.get_cascade_path(node.id)
            if paths:
                impact.cascade_depth = max(len(p) for p in paths)
        
        # Check protected zones
        protected = self._check_protected_zones(change)
        impact.protected_zones_affected = [z.name for z in protected]
        
        # Calculate risk level
        impact.risk_level = self._calculate_risk_level(change, protected, impact)
        
        # Calculate impact score
        impact.impact_score = self._calculate_impact_score(impact)
        
        # Generate warnings
        impact.warnings = self._generate_warnings(change, impact)
        
        # Check for blockers
        impact.blockers = self._check_blockers(change, impact)
        
        # Determine if approval is required
        impact.requires_approval = any(z.requires_approval for z in protected)
        
        # Suggest tests
        impact.suggested_tests = self._suggest_tests(change, impact)
        
        # Assess rollback complexity
        impact.rollback_complexity = self._assess_rollback_complexity(change, impact)
        
        return impact
    
    def _check_protected_zones(self, change: CodeChange) -> List[ProtectedZone]:
        """Check which protected zones are affected by the change"""
        affected_zones = []
        
        for zone in self.protected_zones:
            # Check file path patterns
            for pattern in zone.patterns:
                if fnmatch.fnmatch(change.file_path, pattern):
                    affected_zones.append(zone)
                    break
            
            # Check keywords in content
            if zone not in affected_zones and change.new_content:
                for keyword in zone.keywords:
                    if keyword.lower() in change.new_content.lower():
                        affected_zones.append(zone)
                        break
        
        return affected_zones
    
    def _calculate_risk_level(
        self, 
        change: CodeChange, 
        protected_zones: List[ProtectedZone],
        impact: ChangeImpact
    ) -> RiskLevel:
        """Calculate the overall risk level of the change"""
        
        # Start with LOW
        risk = RiskLevel.LOW
        
        # Elevate based on protected zones
        for zone in protected_zones:
            zone_risk = zone.risk_level if isinstance(zone.risk_level, str) else zone.risk_level.value
            if zone_risk == "critical":
                return RiskLevel.CRITICAL
            elif zone_risk == "high" and risk != RiskLevel.CRITICAL:
                risk = RiskLevel.HIGH
            elif zone_risk == "medium" and risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
        
        # Elevate based on change type
        change_type = change.change_type if isinstance(change.change_type, str) else change.change_type.value
        if change_type == "delete":
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
            elif risk == RiskLevel.MEDIUM:
                risk = RiskLevel.HIGH
        
        # Elevate based on cascade depth
        if impact.cascade_depth > 5:
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
        if impact.cascade_depth > 10:
            if risk == RiskLevel.MEDIUM:
                risk = RiskLevel.HIGH
        
        # Elevate based on number of affected services
        if len(impact.affected_services) > 3:
            if risk == RiskLevel.LOW:
                risk = RiskLevel.MEDIUM
        if len(impact.affected_services) > 5:
            if risk == RiskLevel.MEDIUM:
                risk = RiskLevel.HIGH
        
        return risk
    
    def _calculate_impact_score(self, impact: ChangeImpact) -> float:
        """Calculate a 0-100 impact score"""
        score = 0.0
        
        # Base score from affected nodes (max 30)
        node_score = min(30, len(impact.affected_nodes) * 2)
        score += node_score
        
        # Score from affected services (max 20)
        service_score = min(20, len(impact.affected_services) * 5)
        score += service_score
        
        # Score from protected zones (max 30)
        zone_score = 0
        for zone_name in impact.protected_zones_affected:
            zone = next((z for z in self.protected_zones if z.name == zone_name), None)
            if zone:
                if zone.risk_level == RiskLevel.CRITICAL:
                    zone_score += 15
                elif zone.risk_level == RiskLevel.HIGH:
                    zone_score += 10
                elif zone.risk_level == RiskLevel.MEDIUM:
                    zone_score += 5
        score += min(30, zone_score)
        
        # Score from cascade depth (max 20)
        cascade_score = min(20, impact.cascade_depth * 3)
        score += cascade_score
        
        return min(100, score)
    
    def _generate_warnings(self, change: CodeChange, impact: ChangeImpact) -> List[str]:
        """Generate warning messages for the change"""
        warnings = []
        
        # Protected zone warnings
        for zone_name in impact.protected_zones_affected:
            zone = next((z for z in self.protected_zones if z.name == zone_name), None)
            if zone:
                zone_risk_str = zone.risk_level if isinstance(zone.risk_level, str) else zone.risk_level.value
                warnings.append(
                    f"⚠️ PROTECTED ZONE: This change affects the '{zone.name}' zone "
                    f"({zone_risk_str} risk). {zone.description}"
                )
        
        # Cascade warnings
        if impact.cascade_depth > 3:
            warnings.append(
                f"⚠️ CASCADE RISK: This change cascades through {impact.cascade_depth} "
                f"levels of dependencies"
            )
        
        # Multi-service warnings
        if len(impact.affected_services) > 2:
            warnings.append(
                f"⚠️ CROSS-SERVICE: This change affects {len(impact.affected_services)} "
                f"services: {', '.join(impact.affected_services)}"
            )
        
        # Delete warnings
        if change.change_type == ChangeType.DELETE:
            warnings.append(
                "⚠️ DELETION: Deleting code may break dependent components"
            )
        
        # High impact score warning
        if impact.impact_score > 50:
            warnings.append(
                f"⚠️ HIGH IMPACT: Impact score is {impact.impact_score:.1f}/100"
            )
        
        return warnings
    
    def _check_blockers(self, change: CodeChange, impact: ChangeImpact) -> List[str]:
        """Check for issues that should block the change"""
        blockers = []
        
        # Critical zone without approval
        for zone_name in impact.protected_zones_affected:
            zone = next((z for z in self.protected_zones if z.name == zone_name), None)
            if zone and zone.risk_level == RiskLevel.CRITICAL:
                blockers.append(
                    f"🛑 BLOCKER: Change to CRITICAL zone '{zone.name}' requires explicit approval"
                )
        
        # Deleting auth-related code
        if change.change_type == ChangeType.DELETE:
            if 'authentication' in impact.protected_zones_affected:
                blockers.append(
                    "🛑 BLOCKER: Cannot delete authentication code without review"
                )
            if 'payment' in impact.protected_zones_affected:
                blockers.append(
                    "🛑 BLOCKER: Cannot delete payment code without review"
                )
        
        # Too many affected nodes
        if len(impact.affected_nodes) > 50:
            blockers.append(
                f"🛑 BLOCKER: Change affects {len(impact.affected_nodes)} nodes. "
                "Consider breaking into smaller changes."
            )
        
        return blockers
    
    def _suggest_tests(self, change: CodeChange, impact: ChangeImpact) -> List[str]:
        """Suggest tests that should be run after the change"""
        tests = []
        
        # Service-specific tests
        for service in impact.affected_services:
            tests.append(f"Run {service} unit tests")
        
        # Zone-specific tests
        if 'authentication' in impact.protected_zones_affected:
            tests.append("Run authentication integration tests")
            tests.append("Verify JWT token generation and validation")
            tests.append("Test login/logout flow")
        
        if 'payment' in impact.protected_zones_affected:
            tests.append("Run payment integration tests (sandbox mode)")
            tests.append("Verify Stripe webhook handling")
        
        if 'memory' in impact.protected_zones_affected:
            tests.append("Run memory service tests")
            tests.append("Verify Hash Sphere coordinate generation")
            tests.append("Test memory retrieval accuracy")
        
        if 'database' in impact.protected_zones_affected:
            tests.append("Run database migration in test environment first")
            tests.append("Verify data integrity after migration")
        
        # General tests
        if len(impact.affected_services) > 1:
            tests.append("Run cross-service integration tests")
        
        return tests
    
    def _assess_rollback_complexity(self, change: CodeChange, impact: ChangeImpact) -> str:
        """Assess how complex a rollback would be"""
        
        # Simple: single file, no database, low impact
        if (len(impact.affected_services) <= 1 and 
            'database' not in impact.protected_zones_affected and
            impact.impact_score < 30):
            return "simple"
        
        # Complex: database changes, critical zones, high impact
        if ('database' in impact.protected_zones_affected or
            impact.risk_level == RiskLevel.CRITICAL or
            impact.impact_score > 70):
            return "complex"
        
        return "moderate"


class MultiChangeAnalyzer:
    """Analyzes the combined impact of multiple changes"""
    
    def __init__(self, impact_analyzer: ImpactAnalyzer):
        self.analyzer = impact_analyzer
    
    async def analyze_batch(self, changes: List[CodeChange]) -> ChangeImpact:
        """Analyze the combined impact of multiple changes"""
        combined = ChangeImpact(change_id="batch")
        
        all_nodes = set()
        all_services = set()
        all_zones = set()
        max_depth = 0
        all_warnings = []
        all_blockers = []
        all_tests = set()
        
        for change in changes:
            impact = await self.analyzer.analyze_change(change)
            
            all_nodes.update(impact.affected_nodes)
            all_services.update(impact.affected_services)
            all_zones.update(impact.protected_zones_affected)
            max_depth = max(max_depth, impact.cascade_depth)
            all_warnings.extend(impact.warnings)
            all_blockers.extend(impact.blockers)
            all_tests.update(impact.suggested_tests)
        
        combined.affected_nodes = list(all_nodes)
        combined.affected_services = list(all_services)
        combined.protected_zones_affected = list(all_zones)
        combined.cascade_depth = max_depth
        combined.warnings = list(set(all_warnings))
        combined.blockers = list(set(all_blockers))
        combined.suggested_tests = list(all_tests)
        
        # Recalculate risk and score
        combined.risk_level = self._calculate_combined_risk(combined)
        combined.impact_score = self._calculate_combined_score(combined)
        combined.requires_approval = len(all_blockers) > 0
        combined.rollback_complexity = "complex" if len(changes) > 3 else "moderate"
        
        return combined
    
    def _calculate_combined_risk(self, impact: ChangeImpact) -> RiskLevel:
        """Calculate combined risk level"""
        if any(z in ['authentication', 'payment', 'gateway'] for z in impact.protected_zones_affected):
            return RiskLevel.CRITICAL
        if any(z in ['memory', 'database'] for z in impact.protected_zones_affected):
            return RiskLevel.HIGH
        if len(impact.affected_services) > 3:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW
    
    def _calculate_combined_score(self, impact: ChangeImpact) -> float:
        """Calculate combined impact score"""
        score = 0.0
        score += min(40, len(impact.affected_nodes) * 1.5)
        score += min(30, len(impact.affected_services) * 6)
        score += min(30, len(impact.protected_zones_affected) * 10)
        return min(100, score)
