"""Shared Agent Memory Module"""
from typing import Dict, Any, Optional
from datetime import datetime
import json

class AgentMemory:
    """Shared agent memory implementation"""
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.memory: Dict[str, Any] = {}
        self.created_at = datetime.now()
    
    def store(self, key: str, value: Any) -> None:
        """Store value in memory"""
        self.memory[key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    def retrieve(self, key: str) -> Optional[Any]:
        """Retrieve value from memory"""
        if key in self.memory:
            return self.memory[key]["value"]
        return None
    
    def get_all(self) -> Dict[str, Any]:
        """Get all memory"""
        return {k: v["value"] for k, v in self.memory.items()}
    
    def clear(self) -> None:
        """Clear memory"""
        self.memory.clear()
    
    def save_to_file(self, filepath: str) -> None:
        """Save memory to file"""
        with open(filepath, 'w') as f:
            json.dump(self.memory, f, indent=2)
    
    def load_from_file(self, filepath: str) -> None:
        """Load memory from file"""
        try:
            with open(filepath, 'r') as f:
                self.memory = json.load(f)
        except FileNotFoundError:
            pass
