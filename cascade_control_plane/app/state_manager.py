"""
CASCADE Control Plane - State Manager
Manages change history, ghost changes, rollback points, and validation queue.
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import shutil

from .models import (
    CodeChange, ChangeImpact, GhostChange, ChangeHistoryEntry,
    ValidationStatus, ChangeType
)


class StateManager:
    """Manages the state of changes, history, and rollbacks"""
    
    def __init__(self, data_dir: str = "/tmp/cascade_control_plane"):
        self.data_dir = Path(data_dir)
        self.history_dir = self.data_dir / "history"
        self.ghosts_dir = self.data_dir / "ghosts"
        self.rollback_dir = self.data_dir / "rollbacks"
        self.snapshots_dir = self.data_dir / "snapshots"
        
        # Create directories
        for d in [self.history_dir, self.ghosts_dir, self.rollback_dir, self.snapshots_dir]:
            d.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches
        self.ghosts: Dict[str, GhostChange] = {}
        self.history: List[ChangeHistoryEntry] = []
        self.validation_queue: List[str] = []  # Ghost IDs pending validation
        
        # Load existing history
        self._load_history()
    
    def _load_history(self):
        """Load history from disk"""
        history_file = self.history_dir / "history.json"
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    data = json.load(f)
                    self.history = [ChangeHistoryEntry(**h) for h in data]
            except:
                self.history = []
    
    def _save_history(self):
        """Save history to disk"""
        history_file = self.history_dir / "history.json"
        with open(history_file, 'w') as f:
            json.dump([h.dict() for h in self.history], f, default=str, indent=2)
    
    async def create_ghost(self, changes: List[CodeChange], impact: ChangeImpact) -> GhostChange:
        """Create a ghost change (preview before applying)"""
        ghost = GhostChange(
            changes=changes,
            impact=impact,
            validation_status=ValidationStatus.PENDING
        )
        
        # Store in memory and disk
        self.ghosts[ghost.id] = ghost
        ghost_file = self.ghosts_dir / f"{ghost.id}.json"
        with open(ghost_file, 'w') as f:
            json.dump(ghost.dict(), f, default=str, indent=2)
        
        # Add to validation queue
        self.validation_queue.append(ghost.id)
        
        return ghost
    
    async def get_ghost(self, ghost_id: str) -> Optional[GhostChange]:
        """Get a ghost change by ID"""
        if ghost_id in self.ghosts:
            return self.ghosts[ghost_id]
        
        # Try loading from disk
        ghost_file = self.ghosts_dir / f"{ghost_id}.json"
        if ghost_file.exists():
            with open(ghost_file, 'r') as f:
                data = json.load(f)
                ghost = GhostChange(**data)
                self.ghosts[ghost_id] = ghost
                return ghost
        
        return None
    
    async def validate_ghost(self, ghost_id: str) -> GhostChange:
        """Validate a ghost change"""
        ghost = await self.get_ghost(ghost_id)
        if not ghost:
            raise ValueError(f"Ghost {ghost_id} not found")
        
        # Check if it has blockers
        if ghost.impact and ghost.impact.blockers:
            ghost.validation_status = ValidationStatus.REQUIRES_REVIEW
        else:
            ghost.validation_status = ValidationStatus.APPROVED
        
        # Update on disk
        ghost_file = self.ghosts_dir / f"{ghost_id}.json"
        with open(ghost_file, 'w') as f:
            json.dump(ghost.dict(), f, default=str, indent=2)
        
        # Remove from validation queue
        if ghost_id in self.validation_queue:
            self.validation_queue.remove(ghost_id)
        
        return ghost
    
    async def approve_ghost(self, ghost_id: str, approver: str, reason: str) -> GhostChange:
        """Approve a ghost change that requires review"""
        ghost = await self.get_ghost(ghost_id)
        if not ghost:
            raise ValueError(f"Ghost {ghost_id} not found")
        
        ghost.validation_status = ValidationStatus.APPROVED
        
        # Update on disk
        ghost_file = self.ghosts_dir / f"{ghost_id}.json"
        with open(ghost_file, 'w') as f:
            json.dump(ghost.dict(), f, default=str, indent=2)
        
        return ghost
    
    async def apply_ghost(self, ghost_id: str) -> ChangeHistoryEntry:
        """Apply a ghost change to the actual codebase"""
        ghost = await self.get_ghost(ghost_id)
        if not ghost:
            raise ValueError(f"Ghost {ghost_id} not found")
        
        if ghost.validation_status != ValidationStatus.APPROVED:
            raise ValueError(f"Ghost {ghost_id} is not approved")
        
        # Create rollback point before applying
        rollback_id = await self._create_rollback_point(ghost)
        ghost.rollback_point = rollback_id
        
        # Apply each change
        for change in ghost.changes:
            await self._apply_change(change)
        
        ghost.applied_at = datetime.utcnow()
        
        # Create history entry
        history_entry = ChangeHistoryEntry(
            ghost_id=ghost_id,
            changes=ghost.changes,
            impact=ghost.impact,
            rollback_available=True
        )
        
        self.history.append(history_entry)
        self._save_history()
        
        # Clean up ghost
        del self.ghosts[ghost_id]
        ghost_file = self.ghosts_dir / f"{ghost_id}.json"
        if ghost_file.exists():
            ghost_file.unlink()
        
        return history_entry
    
    async def _apply_change(self, change: CodeChange):
        """Apply a single change to the filesystem"""
        file_path = Path(change.file_path)
        
        if change.change_type == ChangeType.CREATE:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, 'w') as f:
                f.write(change.new_content or "")
        
        elif change.change_type == ChangeType.MODIFY:
            if change.new_content:
                with open(file_path, 'w') as f:
                    f.write(change.new_content)
        
        elif change.change_type == ChangeType.DELETE:
            if file_path.exists():
                file_path.unlink()
        
        elif change.change_type == ChangeType.RENAME:
            if change.new_content and file_path.exists():
                new_path = Path(change.new_content)
                shutil.move(str(file_path), str(new_path))
    
    async def _create_rollback_point(self, ghost: GhostChange) -> str:
        """Create a rollback point before applying changes"""
        rollback_id = f"rollback_{ghost.id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        rollback_path = self.rollback_dir / rollback_id
        rollback_path.mkdir(parents=True, exist_ok=True)
        
        # Save original content of all affected files
        for change in ghost.changes:
            file_path = Path(change.file_path)
            if file_path.exists():
                # Create relative path structure
                rel_path = file_path.name
                backup_path = rollback_path / rel_path
                shutil.copy2(str(file_path), str(backup_path))
        
        # Save rollback metadata
        metadata = {
            "ghost_id": ghost.id,
            "created_at": datetime.utcnow().isoformat(),
            "changes": [c.dict() for c in ghost.changes]
        }
        with open(rollback_path / "metadata.json", 'w') as f:
            json.dump(metadata, f, default=str, indent=2)
        
        return rollback_id
    
    async def rollback(self, history_id: str, reason: str) -> bool:
        """Rollback to a previous state"""
        # Find the history entry
        entry = next((h for h in self.history if h.id == history_id), None)
        if not entry:
            raise ValueError(f"History entry {history_id} not found")
        
        if not entry.rollback_available:
            raise ValueError(f"Rollback not available for {history_id}")
        
        # Find the rollback point
        rollback_dirs = list(self.rollback_dir.glob(f"rollback_{entry.ghost_id}_*"))
        if not rollback_dirs:
            raise ValueError(f"Rollback data not found for {history_id}")
        
        rollback_path = rollback_dirs[0]
        
        # Load metadata
        with open(rollback_path / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        # Restore original files
        for change_data in metadata["changes"]:
            change = CodeChange(**change_data)
            file_path = Path(change.file_path)
            backup_path = rollback_path / file_path.name
            
            if backup_path.exists():
                shutil.copy2(str(backup_path), str(file_path))
            elif change.change_type == ChangeType.CREATE:
                # File was created, so delete it
                if file_path.exists():
                    file_path.unlink()
        
        # Mark rollback as used
        entry.rollback_available = False
        self._save_history()
        
        return True
    
    async def get_history(self, limit: int = 50) -> List[ChangeHistoryEntry]:
        """Get recent change history"""
        return self.history[-limit:]
    
    async def get_pending_validations(self) -> List[GhostChange]:
        """Get all ghosts pending validation"""
        pending = []
        for ghost_id in self.validation_queue:
            ghost = await self.get_ghost(ghost_id)
            if ghost:
                pending.append(ghost)
        return pending
    
    async def create_snapshot(self, name: str, paths: List[str]) -> str:
        """Create a named snapshot of specific paths"""
        snapshot_id = f"snapshot_{name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        snapshot_path = self.snapshots_dir / snapshot_id
        snapshot_path.mkdir(parents=True, exist_ok=True)
        
        for path in paths:
            src = Path(path)
            if src.exists():
                if src.is_dir():
                    shutil.copytree(str(src), str(snapshot_path / src.name))
                else:
                    shutil.copy2(str(src), str(snapshot_path / src.name))
        
        # Save metadata
        metadata = {
            "name": name,
            "created_at": datetime.utcnow().isoformat(),
            "paths": paths
        }
        with open(snapshot_path / "metadata.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        return snapshot_id
    
    async def list_snapshots(self) -> List[Dict[str, Any]]:
        """List all available snapshots"""
        snapshots = []
        for snapshot_dir in self.snapshots_dir.iterdir():
            if snapshot_dir.is_dir():
                metadata_file = snapshot_dir / "metadata.json"
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        metadata["id"] = snapshot_dir.name
                        snapshots.append(metadata)
        return sorted(snapshots, key=lambda x: x.get("created_at", ""), reverse=True)
