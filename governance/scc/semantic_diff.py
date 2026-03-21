#!/usr/bin/env python3
"""
Semantic Diff Generator - Detects semantic changes between versions.

STATUS: PRODUCTION
CREATED: 2025-12-21
GOVERNANCE: Generates semantic diffs for change control enforcement.
"""

import yaml
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

REGISTRY_PATH = Path(__file__).parent / "registry"


class RiskDelta(Enum):
    """Risk level change."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ChangeType(Enum):
    """Type of semantic change."""
    PATCH = "PATCH"
    MINOR = "MINOR"
    MAJOR = "MAJOR"


@dataclass
class SemanticChange:
    """A single semantic change."""
    field: str
    before: Any
    after: Any
    change_type: ChangeType
    risk_delta: RiskDelta
    requires_grammar_diff: bool


@dataclass
class SemanticDiff:
    """Complete semantic diff for a module."""
    module: str
    semantic_unit: str
    before_version: str
    after_version: str
    changes: List[SemanticChange]
    overall_change_type: ChangeType
    overall_risk_delta: RiskDelta
    requires_approval: bool
    requires_grammar_diff: bool
    generated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    diff_hash: str = ""
    
    def __post_init__(self):
        if not self.diff_hash:
            self.diff_hash = self._compute_hash()
            
    def _compute_hash(self) -> str:
        content = json.dumps({
            "module": self.module,
            "semantic_unit": self.semantic_unit,
            "changes": [asdict(c) for c in self.changes]
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class SemanticDiffGenerator:
    """
    Generates semantic diffs between module versions.
    
    Used by RARA to enforce semantic change control.
    """
    
    def __init__(self, registry_path: Optional[Path] = None):
        self.registry_path = registry_path or REGISTRY_PATH
        self.registry: Dict[str, Dict] = {}
        self._load_registry()
        
    def _load_registry(self) -> None:
        """Load all semantic unit registries."""
        if not self.registry_path.exists():
            logger.warning(f"Registry path not found: {self.registry_path}")
            return
            
        for yaml_file in self.registry_path.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                module_name = data.get("module", {}).get("name", yaml_file.stem)
                self.registry[module_name] = data
                logger.info(f"Loaded semantic registry: {module_name}")
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
                
    def generate_diff(
        self,
        module: str,
        semantic_unit_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any]
    ) -> SemanticDiff:
        """
        Generate semantic diff between two versions of a semantic unit.
        
        Args:
            module: Module name
            semantic_unit_id: Semantic unit ID
            before: Previous semantic unit declaration
            after: New semantic unit declaration
            
        Returns:
            SemanticDiff with all changes and risk assessment
        """
        changes = []
        
        # Compare side effects
        before_effects = set(before.get("side_effects", []))
        after_effects = set(after.get("side_effects", []))
        
        added_effects = after_effects - before_effects
        removed_effects = before_effects - after_effects
        
        if added_effects:
            risk = self._assess_effect_risk(added_effects)
            changes.append(SemanticChange(
                field="side_effects",
                before=list(before_effects),
                after=list(after_effects),
                change_type=ChangeType.MAJOR,
                risk_delta=risk,
                requires_grammar_diff=True
            ))
            
        # Compare forbidden effects
        before_forbidden = set(before.get("forbidden_effects", []))
        after_forbidden = set(after.get("forbidden_effects", []))
        
        removed_forbidden = before_forbidden - after_forbidden
        if removed_forbidden:
            changes.append(SemanticChange(
                field="forbidden_effects",
                before=list(before_forbidden),
                after=list(after_forbidden),
                change_type=ChangeType.MAJOR,
                risk_delta=RiskDelta.CRITICAL,
                requires_grammar_diff=True
            ))
            
        # Compare inputs
        before_inputs = before.get("inputs", [])
        after_inputs = after.get("inputs", [])
        
        if len(after_inputs) > len(before_inputs):
            changes.append(SemanticChange(
                field="inputs",
                before=before_inputs,
                after=after_inputs,
                change_type=ChangeType.MINOR,
                risk_delta=RiskDelta.LOW,
                requires_grammar_diff=False
            ))
            
        # Compare outputs
        before_outputs = before.get("outputs", [])
        after_outputs = after.get("outputs", [])
        
        if self._outputs_expanded(before_outputs, after_outputs):
            changes.append(SemanticChange(
                field="outputs",
                before=before_outputs,
                after=after_outputs,
                change_type=ChangeType.MINOR,
                risk_delta=RiskDelta.LOW,
                requires_grammar_diff=False
            ))
            
        # Compare capability
        before_cap = before.get("capability", "")
        after_cap = after.get("capability", "")
        
        if before_cap != after_cap:
            changes.append(SemanticChange(
                field="capability",
                before=before_cap,
                after=after_cap,
                change_type=ChangeType.MAJOR,
                risk_delta=RiskDelta.HIGH,
                requires_grammar_diff=True
            ))
            
        # Compare confidence required
        before_conf = before.get("confidence_required", 0.7)
        after_conf = after.get("confidence_required", 0.7)
        
        if after_conf < before_conf:
            changes.append(SemanticChange(
                field="confidence_required",
                before=before_conf,
                after=after_conf,
                change_type=ChangeType.MAJOR,
                risk_delta=RiskDelta.MEDIUM,
                requires_grammar_diff=True
            ))
            
        # Determine overall change type and risk
        overall_change = self._determine_overall_change(changes)
        overall_risk = self._determine_overall_risk(changes)
        requires_approval = overall_change in [ChangeType.MINOR, ChangeType.MAJOR]
        requires_grammar = any(c.requires_grammar_diff for c in changes)
        
        return SemanticDiff(
            module=module,
            semantic_unit=semantic_unit_id,
            before_version=before.get("version", "0.0.0"),
            after_version=after.get("version", "0.0.0"),
            changes=changes,
            overall_change_type=overall_change,
            overall_risk_delta=overall_risk,
            requires_approval=requires_approval,
            requires_grammar_diff=requires_grammar
        )
        
    def _assess_effect_risk(self, effects: set) -> RiskDelta:
        """Assess risk level of added side effects."""
        critical_effects = {"filesystem.delete", "network.egress", "agent.spawn"}
        high_effects = {"filesystem.write", "state.mutate", "agent.terminate"}
        medium_effects = {"memory.write", "database.write"}
        
        if effects & critical_effects:
            return RiskDelta.CRITICAL
        if effects & high_effects:
            return RiskDelta.HIGH
        if effects & medium_effects:
            return RiskDelta.MEDIUM
        return RiskDelta.LOW
        
    def _outputs_expanded(self, before: List, after: List) -> bool:
        """Check if outputs have been expanded."""
        if len(after) > len(before):
            return True
        for b, a in zip(before, after):
            if a.get("max_count", 0) > b.get("max_count", 0):
                return True
            if a.get("max_size", 0) > b.get("max_size", 0):
                return True
        return False
        
    def _determine_overall_change(self, changes: List[SemanticChange]) -> ChangeType:
        """Determine overall change type from individual changes."""
        if not changes:
            return ChangeType.PATCH
        if any(c.change_type == ChangeType.MAJOR for c in changes):
            return ChangeType.MAJOR
        if any(c.change_type == ChangeType.MINOR for c in changes):
            return ChangeType.MINOR
        return ChangeType.PATCH
        
    def _determine_overall_risk(self, changes: List[SemanticChange]) -> RiskDelta:
        """Determine overall risk from individual changes."""
        if not changes:
            return RiskDelta.NONE
        risks = [c.risk_delta for c in changes]
        if RiskDelta.CRITICAL in risks:
            return RiskDelta.CRITICAL
        if RiskDelta.HIGH in risks:
            return RiskDelta.HIGH
        if RiskDelta.MEDIUM in risks:
            return RiskDelta.MEDIUM
        if RiskDelta.LOW in risks:
            return RiskDelta.LOW
        return RiskDelta.NONE
        
    def validate_change(
        self,
        diff: SemanticDiff,
        grammar_diff_hash: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Validate a semantic change against SCC rules.
        
        Returns:
            (allowed, reason)
        """
        # Rule: If grammar diff required but not provided, reject
        if diff.requires_grammar_diff and not grammar_diff_hash:
            return False, "Semantic change requires grammar diff but none provided"
            
        # Rule: CRITICAL risk always requires human approval
        if diff.overall_risk_delta == RiskDelta.CRITICAL:
            return False, "CRITICAL risk change requires human approval"
            
        # Rule: MAJOR changes require approval
        if diff.overall_change_type == ChangeType.MAJOR and not grammar_diff_hash:
            return False, "MAJOR semantic change requires grammar update"
            
        return True, "Semantic change validated"
        
    def to_json(self, diff: SemanticDiff) -> str:
        """Convert diff to JSON for storage/transmission."""
        return json.dumps({
            "semantic_unit": diff.semantic_unit,
            "module": diff.module,
            "before_version": diff.before_version,
            "after_version": diff.after_version,
            "changes": [
                {
                    "field": c.field,
                    "before": c.before,
                    "after": c.after,
                    "change_type": c.change_type.value,
                    "risk_delta": c.risk_delta.value,
                    "requires_grammar_diff": c.requires_grammar_diff
                }
                for c in diff.changes
            ],
            "overall_change_type": diff.overall_change_type.value,
            "overall_risk_delta": diff.overall_risk_delta.value,
            "requires_approval": diff.requires_approval,
            "requires_grammar_diff": diff.requires_grammar_diff,
            "generated_at": diff.generated_at,
            "diff_hash": diff.diff_hash
        }, indent=2)


# Global instance
_generator: Optional[SemanticDiffGenerator] = None


def get_semantic_diff_generator() -> SemanticDiffGenerator:
    """Get or create the global semantic diff generator."""
    global _generator
    if _generator is None:
        _generator = SemanticDiffGenerator()
    return _generator


def generate_diff(
    module: str,
    semantic_unit_id: str,
    before: Dict[str, Any],
    after: Dict[str, Any]
) -> SemanticDiff:
    """Convenience function to generate a semantic diff."""
    return get_semantic_diff_generator().generate_diff(
        module, semantic_unit_id, before, after
    )
