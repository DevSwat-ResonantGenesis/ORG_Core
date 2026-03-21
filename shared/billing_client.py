"""
Shared Billing Client for Credit Deduction
All services should use this client to deduct credits from user accounts.

Usage:
    from shared.billing_client import BillingClient
    
    billing = BillingClient()
    
    # Deduct credits
    result = await billing.deduct_credits(
        user_id="user-uuid",
        amount=20,
        reference_type="chat_message",
        reference_id="conversation-uuid",
        description="Chat message in conversation"
    )
    
    # Check balance
    balance = await billing.get_balance(user_id)
"""

import os
import logging
import httpx
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Credit costs from pricing.yaml - SINGLE SOURCE OF TRUTH
CREDIT_COSTS = {
    # Tier 1: Chat/LLM
    "chat": {
        "base_request": 10,
        "input_token": 0.8,
        "output_token": 1.0,
        "message_avg": 20,
        "streaming_overhead": 50,
    },
    # Tier 2: Agents
    "agents": {
        "session_start": 100,
        "step": 500,
        "tool_invocation": 200,
        "web_call": 300,
        "memory_write": 50,
        "goal_completion": 200,
        "team_run": 500,
        "pipeline": 300,
    },
    # Tier 3: Compute/IDE
    "compute": {
        "code_execution_per_ms": 1.0,
        "terminal_per_ms": 1.0,
        "preview_per_ms": 0.5,
        "min_code_execution": 100,
        "min_terminal": 50,
        "min_preview": 200,
        "max_code_execution": 10000,
        "max_terminal": 5000,
        "max_preview": 60000,
    },
    # Tier 4: Workflows
    "workflows": {
        "start": 1000,
        "node": 300,
        "conditional": 200,
        "parallel": 400,
        "step": 20,
        "scheduled_trigger": 10,
        "webhook_trigger": 5,
    },
    # Tier 5: Memory/Storage
    "storage": {
        "embed": 100,
        "retrieve": 50,
        "store": 20,
        "delete": 5,
        "per_mb": 1,
        "per_gb": 1000,
        "memory_write": 2,
        "memory_read": 0,
        "rag_upload": 10,
    },
    # Tier 6: Blockchain Audit
    "blockchain": {
        "audit_entry": 100,
        "verification": 10,
        "compliance_report": 500,
        "smart_contract_deploy": 1000,
    },
    # Tier 7: Hash Sphere
    "hash_sphere": {
        "identity_add": 50,
        "transaction_record": 20,
        "trust_relationship": 10,
        "perturbation_simulation": 100,
    },
    # Tier 8: Code Visualizer
    "code_visualizer": {
        "codebase_analysis": 200,
        "governance_check": 50,
        "graph_export": 20,
    },
    # API Calls
    "api": {
        "get": 1,
        "post": 5,
        "put": 5,
        "delete": 3,
    },
}


class BillingClient:
    """Client for interacting with the billing service."""
    
    def __init__(self, billing_url: Optional[str] = None):
        self.billing_url = billing_url or os.getenv(
            "BILLING_SERVICE_URL", 
            "http://billing_service:8000"
        )
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def deduct_credits(
        self,
        user_id: str,
        amount: int,
        reference_type: str,
        reference_id: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Deduct credits from a user's account.
        
        Args:
            user_id: The user's UUID
            amount: Number of credits to deduct (positive number)
            reference_type: Type of action (e.g., 'chat_message', 'agent_step')
            reference_id: Optional ID of the related resource
            description: Optional human-readable description
            
        Returns:
            Dict with status, new_balance, transaction_id
        """
        if amount <= 0:
            logger.warning(f"Attempted to deduct non-positive amount: {amount}")
            return {"status": "skipped", "reason": "amount must be positive"}
        
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self.billing_url}/billing/credits/deduct",
                json={
                    "amount": amount,
                    "reference_type": reference_type,
                    "reference_id": reference_id,
                    "description": description,
                },
                headers={"x-user-id": user_id},
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(
                    f"Deducted {amount} credits from user {user_id}: "
                    f"{reference_type} - new balance: {data.get('new_balance')}"
                )
                return data
            else:
                logger.error(
                    f"Failed to deduct credits: {response.status_code} - {response.text}"
                )
                return {
                    "status": "error",
                    "error": response.text,
                    "status_code": response.status_code,
                }
                
        except httpx.RequestError as e:
            logger.error(f"Billing service request failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_balance(self, user_id: str) -> Dict[str, Any]:
        """Get a user's credit balance."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.billing_url}/billing/credits/balance/{user_id}",
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"balance": 0, "error": response.text}
                
        except httpx.RequestError as e:
            logger.error(f"Failed to get balance: {e}")
            return {"balance": 0, "error": str(e)}
    
    async def check_sufficient_credits(
        self, 
        user_id: str, 
        required_amount: int
    ) -> bool:
        """Check if user has sufficient credits for an operation."""
        balance_data = await self.get_balance(user_id)
        balance = balance_data.get("balance", 0)
        return balance >= required_amount
    
    # Convenience methods for common operations
    
    async def deduct_chat_message(
        self, 
        user_id: str, 
        conversation_id: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> Dict[str, Any]:
        """Deduct credits for a chat message."""
        # Calculate cost based on tokens or use average
        if input_tokens > 0 or output_tokens > 0:
            cost = int(
                CREDIT_COSTS["chat"]["base_request"] +
                (input_tokens / 1000) * CREDIT_COSTS["chat"]["input_token"] +
                (output_tokens / 1000) * CREDIT_COSTS["chat"]["output_token"]
            )
        else:
            cost = CREDIT_COSTS["chat"]["message_avg"]
        
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type="chat_message",
            reference_id=conversation_id,
            description=f"Chat message in conversation {conversation_id[:8]}...",
        )
    
    async def deduct_agent_session_start(
        self, 
        user_id: str, 
        session_id: str,
    ) -> Dict[str, Any]:
        """Deduct credits for starting an agent session."""
        return await self.deduct_credits(
            user_id=user_id,
            amount=CREDIT_COSTS["agents"]["session_start"],
            reference_type="agent_session_start",
            reference_id=session_id,
            description=f"Agent session started: {session_id[:8]}...",
        )
    
    async def deduct_agent_step(
        self, 
        user_id: str, 
        session_id: str,
        step_number: int,
    ) -> Dict[str, Any]:
        """Deduct credits for an agent step."""
        return await self.deduct_credits(
            user_id=user_id,
            amount=CREDIT_COSTS["agents"]["step"],
            reference_type="agent_step",
            reference_id=session_id,
            description=f"Agent step {step_number} in session {session_id[:8]}...",
        )
    
    async def deduct_agent_tool_invocation(
        self, 
        user_id: str, 
        session_id: str,
        tool_name: str,
    ) -> Dict[str, Any]:
        """Deduct credits for a tool invocation."""
        return await self.deduct_credits(
            user_id=user_id,
            amount=CREDIT_COSTS["agents"]["tool_invocation"],
            reference_type="agent_tool",
            reference_id=session_id,
            description=f"Tool invocation: {tool_name}",
        )
    
    async def deduct_code_execution(
        self, 
        user_id: str, 
        execution_id: str,
        duration_ms: int,
    ) -> Dict[str, Any]:
        """Deduct credits for code execution."""
        cost = max(
            CREDIT_COSTS["compute"]["min_code_execution"],
            min(
                int(duration_ms * CREDIT_COSTS["compute"]["code_execution_per_ms"]),
                CREDIT_COSTS["compute"]["max_code_execution"],
            )
        )
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type="code_execution",
            reference_id=execution_id,
            description=f"Code execution ({duration_ms}ms)",
        )
    
    async def deduct_terminal_session(
        self, 
        user_id: str, 
        session_id: str,
        duration_ms: int,
    ) -> Dict[str, Any]:
        """Deduct credits for terminal session."""
        cost = max(
            CREDIT_COSTS["compute"]["min_terminal"],
            min(
                int(duration_ms * CREDIT_COSTS["compute"]["terminal_per_ms"]),
                CREDIT_COSTS["compute"]["max_terminal"],
            )
        )
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type="terminal_session",
            reference_id=session_id,
            description=f"Terminal session ({duration_ms}ms)",
        )
    
    async def deduct_workflow_run(
        self, 
        user_id: str, 
        workflow_id: str,
        node_count: int,
    ) -> Dict[str, Any]:
        """Deduct credits for a workflow run."""
        cost = (
            CREDIT_COSTS["workflows"]["start"] +
            node_count * CREDIT_COSTS["workflows"]["node"]
        )
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type="workflow_run",
            reference_id=workflow_id,
            description=f"Workflow run with {node_count} nodes",
        )
    
    async def deduct_memory_operation(
        self, 
        user_id: str, 
        operation: str,  # 'embed', 'retrieve', 'store', 'delete'
        reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deduct credits for a memory operation."""
        cost = CREDIT_COSTS["storage"].get(operation, 10)
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type=f"memory_{operation}",
            reference_id=reference_id,
            description=f"Memory operation: {operation}",
        )
    
    async def deduct_rag_upload(
        self, 
        user_id: str, 
        document_id: str,
        size_mb: float = 0,
    ) -> Dict[str, Any]:
        """Deduct credits for RAG document upload."""
        cost = CREDIT_COSTS["storage"]["rag_upload"]
        if size_mb > 0:
            cost += int(size_mb * CREDIT_COSTS["storage"]["per_mb"])
        return await self.deduct_credits(
            user_id=user_id,
            amount=cost,
            reference_type="rag_upload",
            reference_id=document_id,
            description=f"RAG document upload ({size_mb:.1f}MB)",
        )
    
    async def deduct_blockchain_audit(
        self, 
        user_id: str, 
        entry_id: str,
    ) -> Dict[str, Any]:
        """Deduct credits for blockchain audit entry."""
        return await self.deduct_credits(
            user_id=user_id,
            amount=CREDIT_COSTS["blockchain"]["audit_entry"],
            reference_type="blockchain_audit",
            reference_id=entry_id,
            description="Blockchain audit entry",
        )
    
    async def deduct_code_analysis(
        self, 
        user_id: str, 
        analysis_id: str,
    ) -> Dict[str, Any]:
        """Deduct credits for code analysis."""
        return await self.deduct_credits(
            user_id=user_id,
            amount=CREDIT_COSTS["code_visualizer"]["codebase_analysis"],
            reference_type="code_analysis",
            reference_id=analysis_id,
            description="Codebase analysis",
        )


# Singleton instance for easy import
_billing_client: Optional[BillingClient] = None


def get_billing_client() -> BillingClient:
    """Get the singleton billing client instance."""
    global _billing_client
    if _billing_client is None:
        _billing_client = BillingClient()
    return _billing_client
