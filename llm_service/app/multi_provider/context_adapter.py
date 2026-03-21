"""
Context Adapter for Multi-Provider LLM Calls
=============================================

Handles provider API differences so context is preserved.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class ContextAdapter:
    """Unified context adapter for all LLM providers."""

    def adapt_for_provider(
        self,
        message: str,
        context: Optional[List[Dict[str, Any]]],
        provider: str,
    ) -> Tuple[str, Any]:
        if not context:
            context = []

        provider_lower = provider.lower()

        if provider_lower in ["claude", "anthropic"]:
            return self._adapt_anthropic(message, context)
        if provider_lower in ["chatgpt", "openai", "groq"]:
            return self._adapt_openai(message, context)
        if provider_lower in ["gemini", "google"]:
            return self._adapt_gemini(message, context)

        logger.warning("Unknown provider %s, using OpenAI format", provider)
        return self._adapt_openai(message, context)

    def _adapt_anthropic(
        self,
        message: str,
        context: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any]]:
        system_messages = []
        conversation_messages = []

        for msg in context:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content = str(msg.get("content", ""))
            if not content:
                continue

            if role == "system":
                system_messages.append(content)
            elif role in ["user", "assistant"]:
                conversation_messages.append({"role": role, "content": content})
            else:
                conversation_messages.append({"role": "user", "content": content})

        conversation_messages.append({"role": "user", "content": message})
        combined_system = "\n\n".join(system_messages) if system_messages else None

        logger.info(
            "[ContextAdapter] Anthropic: %d system, %d conversation",
            len(system_messages),
            len(conversation_messages),
        )

        return message, {"system": combined_system, "messages": conversation_messages}

    def _adapt_openai(
        self,
        message: str,
        context: List[Dict[str, Any]],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        messages = []
        for msg in context:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content = str(msg.get("content", ""))
            if not content:
                continue

            messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})
        logger.info("[ContextAdapter] OpenAI: %d total messages", len(messages))
        return message, messages

    def _adapt_gemini(
        self,
        message: str,
        context: List[Dict[str, Any]],
    ) -> Tuple[str, Dict[str, Any]]:
        system_messages = []
        conversation_messages = []

        for msg in context:
            if not isinstance(msg, dict):
                continue

            role = msg.get("role", "user")
            content = str(msg.get("content", ""))
            if not content:
                continue

            if role == "system":
                system_messages.append(content)
            else:
                gemini_role = "model" if role == "assistant" else "user"
                conversation_messages.append({
                    "role": gemini_role,
                    "parts": [{"text": content}],
                })

        conversation_messages.append({"role": "user", "parts": [{"text": message}]})
        combined_system = "\n\n".join(system_messages) if system_messages else None

        logger.info(
            "[ContextAdapter] Gemini: %d system, %d conversation",
            len(system_messages),
            len(conversation_messages),
        )

        return message, {
            "system_instruction": combined_system,
            "contents": conversation_messages,
        }

    def validate_context(self, context: Optional[List[Dict[str, Any]]]) -> bool:
        if context is None:
            return True
        if not isinstance(context, list):
            logger.error("Context must be a list, got %s", type(context))
            return False
        for i, msg in enumerate(context):
            if not isinstance(msg, dict):
                logger.error("Context message %d must be dict", i)
                return False
            if "role" not in msg:
                logger.error("Context message %d missing role", i)
                return False
            if "content" not in msg:
                logger.error("Context message %d missing content", i)
                return False
        return True

    def get_context_stats(self, context: Optional[List[Dict[str, Any]]]) -> Dict[str, int]:
        if not context:
            return {"system": 0, "user": 0, "assistant": 0, "total": 0}
        stats = {"system": 0, "user": 0, "assistant": 0, "other": 0}
        for msg in context:
            if not isinstance(msg, dict):
                continue
            role = msg.get("role", "unknown")
            if role in stats:
                stats[role] += 1
            else:
                stats["other"] += 1
        stats["total"] = sum(stats.values())
        return stats


context_adapter = ContextAdapter()
