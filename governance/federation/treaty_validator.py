#!/usr/bin/env python3
"""
Federation Treaty Validator - Validates and enforces cross-droplet treaties.

STATUS: PRODUCTION
CREATED: 2025-12-21
GOVERNANCE: Treaty-based federation with no transitive trust.
"""

import yaml
import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging
import re

logger = logging.getLogger(__name__)

TREATIES_PATH = Path(__file__).parent / "treaties"


class TreatyStatus(Enum):
    """Treaty status."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"


class TrustLevel(Enum):
    """Trust level between parties."""
    NONE = "none"
    MINIMAL = "minimal"
    STANDARD = "standard"
    ELEVATED = "elevated"
    FULL = "full"


@dataclass
class TreatyParty:
    """A party in a federation treaty."""
    dsid: str
    name: str
    grammar_hash: str
    governance_policy_hash: str
    trust_level: TrustLevel
    public_key: Optional[str] = None


@dataclass
class InteractionConstraint:
    """Constraints on an allowed interaction."""
    max_requests_per_minute: Optional[int] = None
    max_requests_per_day: Optional[int] = None
    max_payload_size: Optional[int] = None
    confidence_min: float = 0.7
    readonly: bool = False
    require_approval: bool = False
    allowed_targets: List[str] = field(default_factory=list)
    denied_targets: List[str] = field(default_factory=list)


@dataclass
class AllowedInteraction:
    """An allowed interaction in a treaty."""
    capability: str
    source_dsid: str
    target_dsid: str
    constraints: InteractionConstraint


@dataclass
class Treaty:
    """A federation treaty between two SEDs."""
    treaty_id: str
    parties: List[TreatyParty]
    allowed_interactions: List[AllowedInteraction]
    forbidden: List[str]
    status: TreatyStatus
    created_at: datetime
    expires_at: Optional[datetime] = None
    treaty_hash: str = ""
    hash_sphere_anchor: Optional[str] = None
    auto_revoke_on_violation: bool = True
    violation_count: int = 0
    violation_threshold: int = 3
    
    def __post_init__(self):
        if not self.treaty_hash:
            self.treaty_hash = self._compute_hash()
            
    def _compute_hash(self) -> str:
        content = json.dumps({
            "treaty_id": self.treaty_id,
            "parties": [p.dsid for p in self.parties],
            "allowed_interactions": [
                {"capability": i.capability, "source": i.source_dsid, "target": i.target_dsid}
                for i in self.allowed_interactions
            ],
            "forbidden": self.forbidden
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class RequestValidation:
    """Result of validating a cross-droplet request."""
    allowed: bool
    treaty_id: Optional[str]
    reason: str
    constraints: Optional[InteractionConstraint] = None


class TreatyValidator:
    """
    Validates and enforces federation treaties.
    
    Ensures:
    - No transitive trust
    - Pairwise treaties only
    - Runtime capability enforcement
    """
    
    def __init__(self, treaties_path: Optional[Path] = None):
        self.treaties_path = treaties_path or TREATIES_PATH
        self.treaties: Dict[str, Treaty] = {}
        self.violation_log: List[Dict] = []
        self._load_treaties()
        
    def _load_treaties(self) -> None:
        """Load all treaties from disk."""
        if not self.treaties_path.exists():
            self.treaties_path.mkdir(parents=True, exist_ok=True)
            return
            
        for yaml_file in self.treaties_path.glob("*.yaml"):
            try:
                treaty = self._parse_treaty_file(yaml_file)
                if treaty and treaty.status == TreatyStatus.ACTIVE:
                    self.treaties[treaty.treaty_id] = treaty
                    logger.info(f"Loaded treaty: {treaty.treaty_id}")
            except Exception as e:
                logger.error(f"Failed to load treaty {yaml_file}: {e}")
                
    def _parse_treaty_file(self, path: Path) -> Optional[Treaty]:
        """Parse a treaty YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
            
        treaty_data = data.get("treaty", {})
        parties_data = data.get("parties", [])
        interactions_data = data.get("allowed_interactions", [])
        
        parties = []
        for p in parties_data:
            parties.append(TreatyParty(
                dsid=p["dsid"],
                name=p.get("name", p["dsid"]),
                grammar_hash=p["grammar_hash"],
                governance_policy_hash=p["governance_policy_hash"],
                trust_level=TrustLevel(p.get("trust_level", "minimal")),
                public_key=p.get("public_key")
            ))
            
        interactions = []
        for i in interactions_data:
            direction = i.get("direction", "")
            match = re.match(r"(\S+)\s*→\s*(\S+)", direction)
            if match:
                source, target = match.groups()
            else:
                continue
                
            constraints_data = i.get("constraints", {})
            constraints = InteractionConstraint(
                max_requests_per_minute=constraints_data.get("max_requests_per_minute"),
                max_requests_per_day=constraints_data.get("max_requests_per_day"),
                max_payload_size=constraints_data.get("max_payload_size"),
                confidence_min=constraints_data.get("confidence_min", 0.7),
                readonly=constraints_data.get("readonly", False),
                require_approval=constraints_data.get("require_approval", False),
                allowed_targets=constraints_data.get("allowed_targets", []),
                denied_targets=constraints_data.get("denied_targets", [])
            )
            
            interactions.append(AllowedInteraction(
                capability=i["capability"],
                source_dsid=source,
                target_dsid=target,
                constraints=constraints
            ))
            
        termination = data.get("termination", {})
        
        return Treaty(
            treaty_id=treaty_data["treaty_id"],
            parties=parties,
            allowed_interactions=interactions,
            forbidden=data.get("forbidden", []),
            status=TreatyStatus(treaty_data.get("status", "draft")),
            created_at=datetime.fromisoformat(treaty_data["created_at"]),
            expires_at=datetime.fromisoformat(treaty_data["expires_at"]) if treaty_data.get("expires_at") else None,
            treaty_hash=treaty_data.get("treaty_hash", ""),
            hash_sphere_anchor=treaty_data.get("hash_sphere_anchor"),
            auto_revoke_on_violation=termination.get("auto_revoke_on_violation", True),
            violation_threshold=termination.get("violation_threshold", 3)
        )
        
    def validate_request(
        self,
        source_dsid: str,
        target_dsid: str,
        capability: str,
        context: Dict[str, Any]
    ) -> RequestValidation:
        """
        Validate a cross-droplet request against treaties.
        
        Args:
            source_dsid: Requesting droplet
            target_dsid: Target droplet
            capability: Requested capability
            context: Request context (confidence, payload_size, etc.)
            
        Returns:
            RequestValidation with result and constraints
        """
        # Find applicable treaty
        treaty = self._find_treaty(source_dsid, target_dsid)
        
        if not treaty:
            return RequestValidation(
                allowed=False,
                treaty_id=None,
                reason=f"No active treaty between {source_dsid} and {target_dsid}"
            )
            
        # Check if capability is forbidden
        if self._is_forbidden(capability, treaty.forbidden):
            self._log_violation(treaty, source_dsid, capability, "forbidden_capability")
            return RequestValidation(
                allowed=False,
                treaty_id=treaty.treaty_id,
                reason=f"Capability {capability} is forbidden by treaty"
            )
            
        # Find allowed interaction
        interaction = self._find_interaction(treaty, source_dsid, target_dsid, capability)
        
        if not interaction:
            return RequestValidation(
                allowed=False,
                treaty_id=treaty.treaty_id,
                reason=f"Capability {capability} not allowed in direction {source_dsid} → {target_dsid}"
            )
            
        # Check constraints
        constraint_check = self._check_constraints(interaction.constraints, context)
        if not constraint_check[0]:
            self._log_violation(treaty, source_dsid, capability, constraint_check[1])
            return RequestValidation(
                allowed=False,
                treaty_id=treaty.treaty_id,
                reason=constraint_check[1]
            )
            
        return RequestValidation(
            allowed=True,
            treaty_id=treaty.treaty_id,
            reason="Request allowed by treaty",
            constraints=interaction.constraints
        )
        
    def _find_treaty(self, dsid1: str, dsid2: str) -> Optional[Treaty]:
        """Find active treaty between two DSIDs."""
        for treaty in self.treaties.values():
            if treaty.status != TreatyStatus.ACTIVE:
                continue
            party_dsids = {p.dsid for p in treaty.parties}
            if dsid1 in party_dsids and dsid2 in party_dsids:
                # Check expiration
                if treaty.expires_at and datetime.utcnow() > treaty.expires_at:
                    treaty.status = TreatyStatus.EXPIRED
                    continue
                return treaty
        return None
        
    def _is_forbidden(self, capability: str, forbidden: List[str]) -> bool:
        """Check if capability matches any forbidden pattern."""
        import fnmatch
        for pattern in forbidden:
            if fnmatch.fnmatch(capability, pattern):
                return True
        return False
        
    def _find_interaction(
        self,
        treaty: Treaty,
        source: str,
        target: str,
        capability: str
    ) -> Optional[AllowedInteraction]:
        """Find matching allowed interaction."""
        for interaction in treaty.allowed_interactions:
            if (interaction.source_dsid == source and
                interaction.target_dsid == target and
                self._capability_matches(capability, interaction.capability)):
                return interaction
        return None
        
    def _capability_matches(self, requested: str, allowed: str) -> bool:
        """Check if requested capability matches allowed pattern."""
        import fnmatch
        return fnmatch.fnmatch(requested, allowed)
        
    def _check_constraints(
        self,
        constraints: InteractionConstraint,
        context: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """Check if request meets constraints."""
        # Check confidence
        confidence = context.get("confidence", 0)
        if confidence < constraints.confidence_min:
            return False, f"Confidence {confidence} < required {constraints.confidence_min}"
            
        # Check payload size
        payload_size = context.get("payload_size", 0)
        if constraints.max_payload_size and payload_size > constraints.max_payload_size:
            return False, f"Payload size {payload_size} > max {constraints.max_payload_size}"
            
        # Check readonly
        if constraints.readonly and context.get("is_write", False):
            return False, "Write operation not allowed (readonly constraint)"
            
        # Check target restrictions
        target = context.get("target_path", "")
        if constraints.denied_targets:
            import fnmatch
            for pattern in constraints.denied_targets:
                if fnmatch.fnmatch(target, pattern):
                    return False, f"Target {target} is denied"
                    
        if constraints.allowed_targets:
            import fnmatch
            allowed = any(fnmatch.fnmatch(target, p) for p in constraints.allowed_targets)
            if not allowed:
                return False, f"Target {target} not in allowed list"
                
        return True, "Constraints satisfied"
        
    def _log_violation(
        self,
        treaty: Treaty,
        source_dsid: str,
        capability: str,
        violation_type: str
    ) -> None:
        """Log a treaty violation."""
        treaty.violation_count += 1
        
        entry = {
            "treaty_id": treaty.treaty_id,
            "source_dsid": source_dsid,
            "capability": capability,
            "violation_type": violation_type,
            "timestamp": datetime.utcnow().isoformat(),
            "violation_count": treaty.violation_count
        }
        self.violation_log.append(entry)
        logger.warning(f"TREATY_VIOLATION: {entry}")
        
        # Auto-revoke if threshold exceeded
        if treaty.auto_revoke_on_violation and treaty.violation_count >= treaty.violation_threshold:
            treaty.status = TreatyStatus.REVOKED
            logger.error(f"TREATY_REVOKED: {treaty.treaty_id} due to {treaty.violation_count} violations")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get validator statistics."""
        return {
            "active_treaties": sum(1 for t in self.treaties.values() if t.status == TreatyStatus.ACTIVE),
            "total_treaties": len(self.treaties),
            "total_violations": len(self.violation_log),
            "revoked_treaties": sum(1 for t in self.treaties.values() if t.status == TreatyStatus.REVOKED)
        }


# Global instance
_validator: Optional[TreatyValidator] = None


def get_treaty_validator() -> TreatyValidator:
    """Get or create the global treaty validator."""
    global _validator
    if _validator is None:
        _validator = TreatyValidator()
    return _validator


def validate_request(
    source_dsid: str,
    target_dsid: str,
    capability: str,
    context: Dict[str, Any]
) -> RequestValidation:
    """Convenience function to validate a cross-droplet request."""
    return get_treaty_validator().validate_request(
        source_dsid, target_dsid, capability, context
    )
