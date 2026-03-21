"""
Multi-AI Routing Service (Agents)
Routes queries to appropriate AI providers with fallback.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import httpx
from openai import OpenAI

from ..config import settings
from .context_adapter import context_adapter

logger = logging.getLogger(__name__)


class MultiAIRouter:
    """Route queries to different AI providers with automatic fallback."""

    @staticmethod
    def _split_api_keys(value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [v.strip() for v in value.split(",") if v.strip()]

    def __init__(self) -> None:
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

        gemini_key_1 = settings.GOOGLE_API_KEY or settings.GEMINI_API_KEY
        gemini_key_2 = settings.GEMINI_API_KEY_2
        self.gemini_api_keys: List[str] = []
        self.gemini_api_keys.extend(self._split_api_keys(gemini_key_1))
        self.gemini_api_keys.extend(self._split_api_keys(gemini_key_2))
        self.gemini_api_key = self.gemini_api_keys[0] if self.gemini_api_keys else None
        self.gemini_key_index = 0
        self.gemini_base_url = "https://generativelanguage.googleapis.com/v1beta"

        groq_key_1 = settings.GROQ_API_KEY
        groq_key_2 = settings.GROQ_API_KEY_2
        self.groq_api_keys: List[str] = []
        self.groq_api_keys.extend(self._split_api_keys(groq_key_1))
        self.groq_api_keys.extend(self._split_api_keys(groq_key_2))
        self.groq_api_key = self.groq_api_keys[0] if self.groq_api_keys else None
        self.groq_key_index = 0
        self.groq_base_url = "https://api.groq.com/openai/v1"

        self.anthropic_api_key = settings.ANTHROPIC_API_KEY
        self._user_api_keys: Dict[str, str] = {}

    def set_user_api_keys(self, keys: Optional[Dict[str, str]]) -> None:
        self._user_api_keys = keys or {}

    def get_available_providers(self) -> List[str]:
        providers = []
        if self._user_api_keys.get("openai") or self.openai_client:
            providers.append("openai")
        if self._user_api_keys.get("anthropic") or self.anthropic_api_key:
            providers.append("anthropic")
        if self._user_api_keys.get("google") or self.gemini_api_keys:
            providers.append("google")
        if self._user_api_keys.get("groq") or self.groq_api_keys:
            providers.append("groq")
        return providers

    def _get_api_key(self, provider: str) -> Optional[str]:
        provider_map = {
            "chatgpt": "openai",
            "gpt": "openai",
            "gemini": "google",
            "claude": "anthropic",
        }
        normalized = provider_map.get(provider.lower(), provider.lower())

        if self._user_api_keys.get(normalized):
            return self._user_api_keys[normalized]

        if normalized == "openai":
            return settings.OPENAI_API_KEY
        if normalized == "anthropic":
            return self.anthropic_api_key
        if normalized == "google":
            return self.gemini_api_key
        if normalized == "groq":
            return self.groq_api_key
        return None

    def route_query(
        self,
        message: str,
        context: Optional[List[Dict]] = None,
        preferred_provider: Optional[str] = None,
        images: Optional[List[Dict]] = None,
    ) -> Dict:
        provider_map = {
            "openai": "chatgpt",
            "chatgpt": "chatgpt",
            "gpt": "chatgpt",
            "gemini": "gemini",
            "google": "gemini",
            "groq": "groq",
            "claude": "claude",
            "anthropic": "claude",
        }
        normalized_provider = provider_map.get(
            preferred_provider.lower() if preferred_provider else "",
            preferred_provider,
        )

        has_openai = self.openai_client or self._user_api_keys.get("openai")
        has_gemini = self.gemini_api_keys or self._user_api_keys.get("google")
        has_groq = self.groq_api_key or self._user_api_keys.get("groq")
        has_anthropic = self.anthropic_api_key or self._user_api_keys.get("anthropic")

        available_providers: List[str] = []
        if normalized_provider:
            if normalized_provider == "chatgpt" and has_openai:
                available_providers.append("chatgpt")
            elif normalized_provider == "gemini" and has_gemini:
                available_providers.append("gemini")
            elif normalized_provider == "groq" and has_groq:
                available_providers.append("groq")
            elif normalized_provider == "claude" and has_anthropic:
                available_providers.append("claude")

        if "groq" not in available_providers and has_groq:
            available_providers.append("groq")
        if "gemini" not in available_providers and has_gemini:
            available_providers.append("gemini")
        if "claude" not in available_providers and has_anthropic:
            available_providers.append("claude")
        if "chatgpt" not in available_providers and has_openai:
            available_providers.append("chatgpt")

        if not normalized_provider:
            auto_provider = self._select_provider(message, context)
            if auto_provider not in available_providers:
                if auto_provider in ["chatgpt", "gemini", "groq", "claude"]:
                    available_providers.insert(0, auto_provider)

        logger.info(
            "Routing query (agents) preferred=%s normalized=%s",
            preferred_provider,
            normalized_provider,
        )
        logger.info(
            "Provider availability: groq=%s gemini=%s claude=%s openai=%s",
            has_groq,
            has_gemini,
            has_anthropic,
            has_openai,
        )
        logger.info("Final provider list: %s", available_providers)

        if images:
            vision_providers = ["chatgpt", "gemini"]
            for vp in reversed(vision_providers):
                if vp in available_providers:
                    available_providers.remove(vp)
                    available_providers.insert(0, vp)

        last_error = None
        attempts: List[Dict[str, str]] = []
        for provider in available_providers:
            try:
                if provider == "chatgpt":
                    result = self._call_chatgpt(message, context, images)
                elif provider == "gemini":
                    result = self._call_gemini(message, context, images)
                elif provider == "groq":
                    result = self._call_groq(message, context)
                elif provider == "claude":
                    result = self._call_anthropic(message, context, images)
                else:
                    continue

                response_text = result.get("response", "")
                metadata = result.get("metadata", {})
                is_error = (
                    (response_text and response_text.startswith("Error calling"))
                    or metadata.get("quota_exceeded", False)
                    or metadata.get("error") is not None
                )

                if is_error:
                    attempts.append(
                        {
                            "provider": provider,
                            "error": str(metadata.get("error") or response_text or "unknown"),
                        }
                    )
                    last_error = result
                    continue

                return result
            except Exception as exc:
                attempts.append(
                    {
                        "provider": provider,
                        "error": f"Error calling {provider}: {exc}",
                    }
                )
                last_error = {
                    "provider": provider,
                    "response": f"Error calling {provider}: {exc}",
                    "metadata": {"error": str(exc)},
                }
                continue

        if last_error:
            preferred_normalized = provider_map.get(
                preferred_provider.lower() if preferred_provider else "",
                preferred_provider.lower() if preferred_provider else None,
            )
            preferred_key = None
            if preferred_normalized:
                reverse_map = {
                    "chatgpt": "chatgpt",
                    "gpt": "chatgpt",
                    "openai": "chatgpt",
                    "gemini": "gemini",
                    "google": "gemini",
                    "groq": "groq",
                    "claude": "claude",
                    "anthropic": "claude",
                }
                preferred_key = reverse_map.get(preferred_normalized, preferred_normalized)

            preferred_attempt = None
            if preferred_key:
                for a in attempts:
                    if a.get("provider") == preferred_key:
                        preferred_attempt = a
                        break

            error_msg = last_error.get("response", "All providers failed")
            if preferred_attempt and preferred_attempt.get("error"):
                error_msg = preferred_attempt["error"]
            return {
                "provider": "resonant-brain",
                "response": "All AI providers are currently unavailable.",
                "metadata": {
                    "error": error_msg,
                    "all_providers_failed": True,
                    "attempts": attempts,
                },
            }

        return {
            "provider": "resonant-brain",
            "response": "No AI providers configured.",
            "metadata": {"note": "No AI providers configured"},
        }

    def _select_provider(self, message: str, context: Optional[List[Dict]] = None) -> str:
        try:
            from ..services.intelligent_router import select_optimal_provider

            available = []
            if self.groq_api_key or self._user_api_keys.get("groq"):
                available.append("groq")
            if self.gemini_api_keys or self._user_api_keys.get("google"):
                available.append("gemini")
            if self.openai_client or self._user_api_keys.get("openai"):
                available.append("chatgpt")
            if self.anthropic_api_key or self._user_api_keys.get("anthropic"):
                available.append("claude")

            if not available:
                return "resonant-brain"

            decision = select_optimal_provider(
                message=message,
                context=context,
                available_providers=available,
                optimize_for="balanced",
            )
            return decision.provider
        except Exception:
            if self.groq_api_key:
                return "groq"
            if self.openai_client:
                return "chatgpt"
            if self.gemini_api_keys:
                return "gemini"
            return "resonant-brain"

    def _call_chatgpt(self, message: str, context: Optional[List[Dict]] = None, images: Optional[List[Dict]] = None) -> Dict:
        api_key = self._get_api_key("openai")
        if not api_key:
            return {
                "provider": "chatgpt",
                "response": "Error calling ChatGPT: API key not configured",
                "metadata": {"error": "API key missing"},
            }

        try:
            client = OpenAI(api_key=api_key)
            messages = []
            if context:
                for msg in context:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        messages.append({
                            "role": msg.get("role", "user"),
                            "content": str(msg.get("content", "")),
                        })

            if images:
                content_parts = [{"type": "text", "text": str(message)}]
                for img in images:
                    if img.get("data"):
                        content_parts.append({
                            "type": "image_url",
                            "image_url": {"url": img["data"]},
                        })
                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": "user", "content": str(message)})

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.5,
                max_tokens=2000,
            )

            return {
                "provider": "chatgpt",
                "response": response.choices[0].message.content,
                "metadata": {
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            }
        except Exception as exc:
            error_str = str(exc).lower()
            is_quota_error = any(x in error_str for x in ["429", "quota", "rate limit", "billing"])
            return {
                "provider": "chatgpt",
                "response": f"Error calling ChatGPT: {exc}",
                "metadata": {"error": str(exc), "quota_exceeded": is_quota_error},
            }

    def _call_anthropic(self, message: str, context: Optional[List[Dict]] = None, images: Optional[List[Dict]] = None) -> Dict:
        api_key = self._get_api_key("anthropic")
        if not api_key:
            return {
                "provider": "claude",
                "response": "Error calling Claude: API key not configured",
                "metadata": {"error": "API key missing"},
            }

        try:
            _, adapted = context_adapter.adapt_for_provider(
                message=message,
                context=context,
                provider="anthropic",
            )

            system_message = adapted.get("system")
            messages = adapted.get("messages", [])

            if images:
                content_parts = []
                for img in images:
                    if img.get("data"):
                        data = img["data"]
                        if "," in data:
                            data = data.split(",")[1]
                        mime_type = img.get("type", "image/png")
                        content_parts.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": data,
                            },
                        })
                content_parts.append({"type": "text", "text": message})
                messages.append({"role": "user", "content": content_parts})
            else:
                messages.append({"role": "user", "content": message})

            payload = {
                "model": settings.ANTHROPIC_MODEL,
                "max_tokens": 2000,
                "messages": messages,
            }
            if system_message:
                payload["system"] = system_message

            with httpx.Client() as client:
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            return {
                "provider": "claude",
                "response": data["content"][0]["text"],
                "metadata": {
                    "model": data.get("model", "claude-3-haiku-20240307"),
                    "usage": data.get("usage", {}),
                },
            }
        except httpx.HTTPStatusError as exc:
            body = ""
            try:
                body = exc.response.text
            except Exception:
                body = ""
            error_detail = f"HTTP {exc.response.status_code}: {body[:500]}"
            error_str = error_detail.lower()
            is_quota_error = any(x in error_str for x in ["429", "quota", "rate limit", "billing"])
            return {
                "provider": "claude",
                "response": f"Error calling Claude: {error_detail}",
                "metadata": {"error": error_detail, "quota_exceeded": is_quota_error},
            }
        except Exception as exc:
            error_str = str(exc).lower()
            is_quota_error = any(x in error_str for x in ["429", "quota", "rate limit", "billing"])
            return {
                "provider": "claude",
                "response": f"Error calling Claude: {exc}",
                "metadata": {"error": str(exc), "quota_exceeded": is_quota_error},
            }

    def _call_groq(self, message: str, context: Optional[List[Dict]] = None) -> Dict:
        user_groq_key = self._user_api_keys.get("groq")
        api_keys_to_try: List[str] = []
        if user_groq_key:
            api_keys_to_try.append(user_groq_key)
        api_keys_to_try.extend(self.groq_api_keys)

        if not api_keys_to_try:
            return {
                "provider": "groq",
                "response": "Error calling Groq: API key not configured",
                "metadata": {"error": "API key missing"},
            }

        last_error = None
        for key_index, api_key in enumerate(api_keys_to_try):
            try:
                messages = []
                if context:
                    for msg in context:
                        if isinstance(msg, dict) and "role" in msg and "content" in msg:
                            role = msg.get("role", "user")
                            if role not in ["user", "assistant", "system"]:
                                role = "user"
                            messages.append({
                                "role": role,
                                "content": str(msg.get("content", "")),
                            })
                messages.append({"role": "user", "content": str(message)})

                with httpx.Client() as client:
                    response = client.post(
                        f"{self.groq_base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "llama-3.3-70b-versatile",
                            "messages": messages,
                            "temperature": 0.5,
                            "max_tokens": 2000,
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                if "choices" not in data or not data["choices"]:
                    if key_index < len(api_keys_to_try) - 1:
                        continue
                    return {
                        "provider": "groq",
                        "response": "Error calling Groq: Invalid response",
                        "metadata": {"error": "Invalid response"},
                    }

                if self.groq_api_keys:
                    self.groq_key_index = (key_index + 1) % len(self.groq_api_keys)

                return {
                    "provider": "groq",
                    "response": data["choices"][0]["message"]["content"],
                    "metadata": {
                        "model": data.get("model", "llama-3.3-70b-versatile"),
                        "usage": data.get("usage", {}),
                    },
                }
            except httpx.HTTPStatusError as exc:
                error_detail = f"HTTP {exc.response.status_code}"
                try:
                    error_data = exc.response.json()
                    if isinstance(error_data, dict) and "error" in error_data:
                        error_detail = str(error_data["error"].get("message", error_data["error"]))
                except Exception:
                    pass

                is_rate_limit = exc.response.status_code == 429 or "rate limit" in error_detail.lower()
                if is_rate_limit and key_index < len(api_keys_to_try) - 1:
                    last_error = error_detail
                    continue
                last_error = error_detail
                if key_index < len(api_keys_to_try) - 1:
                    continue
                return {
                    "provider": "groq",
                    "response": f"Error calling Groq: {error_detail}",
                    "metadata": {"error": error_detail, "rate_limit": is_rate_limit},
                }
            except Exception as exc:
                last_error = str(exc)
                if key_index < len(api_keys_to_try) - 1:
                    continue
                return {
                    "provider": "groq",
                    "response": f"Error calling Groq: {exc}",
                    "metadata": {"error": str(exc)},
                }

        return {
            "provider": "groq",
            "response": f"Error calling Groq: All keys failed. {last_error}",
            "metadata": {"error": last_error, "all_keys_failed": True},
        }

    def _call_gemini(self, message: str, context: Optional[List[Dict]] = None, images: Optional[List[Dict]] = None) -> Dict:
        api_keys_to_try: List[str] = []
        user_google_key = self._user_api_keys.get("google")
        if user_google_key:
            api_keys_to_try.append(user_google_key)
        api_keys_to_try.extend(self.gemini_api_keys)

        if not api_keys_to_try:
            return {
                "provider": "gemini",
                "response": "Error calling Gemini: API key not configured",
                "metadata": {"error": "API key missing"},
            }

        contents = []
        system_messages = []
        if context:
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    system_messages.append(content)
                else:
                    contents.append({
                        "role": "user" if role == "user" else "model",
                        "parts": [{"text": content}],
                    })

        merged_message = message
        if system_messages:
            system_context = "\n\n".join(system_messages)
            merged_message = f"{system_context}\n\n{message}"

        parts = [{"text": merged_message}]
        if images:
            for img in images:
                if img.get("data"):
                    data = img["data"]
                    if "," in data:
                        data = data.split(",")[1]
                    mime_type = img.get("type", "image/png")
                    parts.append({
                        "inline_data": {"mime_type": mime_type, "data": data},
                    })

        contents.append({"role": "user", "parts": parts})

        last_error = None
        for key_index, api_key in enumerate(api_keys_to_try):
            try:
                with httpx.Client() as client:
                    models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]
                    for model_name in models_to_try:
                        try:
                            response = client.post(
                                f"{self.gemini_base_url}/models/{model_name}:generateContent?key={api_key}",
                                json={"contents": contents},
                                timeout=30.0,
                            )
                            response.raise_for_status()
                            data = response.json()

                            if self.gemini_api_keys:
                                self.gemini_key_index = (key_index + 1) % len(self.gemini_api_keys)

                            return {
                                "provider": "gemini",
                                "response": data["candidates"][0]["content"]["parts"][0]["text"],
                                "metadata": {
                                    "model": model_name,
                                    "usage": data.get("usageMetadata", {}),
                                },
                            }
                        except httpx.HTTPStatusError as exc:
                            if exc.response.status_code == 404:
                                continue
                            raise
                        except Exception:
                            continue

                if key_index < len(api_keys_to_try) - 1:
                    continue
                return {
                    "provider": "gemini",
                    "response": "Error calling Gemini: All models failed",
                    "metadata": {"error": "All models failed"},
                }
            except httpx.HTTPStatusError as exc:
                body = ""
                try:
                    body = exc.response.text
                except Exception:
                    body = ""
                last_error = f"HTTP {exc.response.status_code}: {body[:500]}"
                if key_index < len(api_keys_to_try) - 1:
                    continue
                return {
                    "provider": "gemini",
                    "response": f"Error calling Gemini: {last_error}",
                    "metadata": {"error": last_error},
                }
            except Exception as exc:
                last_error = str(exc)
                if key_index < len(api_keys_to_try) - 1:
                    continue
                return {
                    "provider": "gemini",
                    "response": f"Error calling Gemini: {exc}",
                    "metadata": {"error": str(exc)},
                }

        return {
            "provider": "gemini",
            "response": f"Error calling Gemini: All keys failed. {last_error}",
            "metadata": {"error": last_error, "all_keys_failed": True},
        }
