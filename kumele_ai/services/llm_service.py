"""
LLM Service - Handles interactions with LLM providers

Supports:
- Local Mistral via TGI (Text Generation Inference)
- OpenRouter API (cloud fallback)
- Auto mode: tries local first, falls back to OpenRouter

Configuration via environment variables:
- LLM_PROVIDER: "local", "openrouter", or "auto" (default)
- LLM_API_URL: URL for local TGI instance
- OPENROUTER_API_KEY: API key for OpenRouter
- OPENROUTER_MODEL: Model to use on OpenRouter
"""
import httpx
import logging
from typing import Optional, List, Dict, Any
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """
    Service for interacting with LLM providers.
    
    Supports local Mistral via TGI and OpenRouter cloud API.
    In "auto" mode, tries local first and falls back to OpenRouter.
    """
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER.lower()
        
        # Local TGI settings
        self.local_url = settings.LLM_API_URL
        self.local_model = settings.LLM_MODEL
        
        # OpenRouter settings
        self.openrouter_url = settings.OPENROUTER_API_URL
        self.openrouter_key = settings.OPENROUTER_API_KEY
        self.openrouter_model = settings.OPENROUTER_MODEL
        self.openrouter_site_url = settings.OPENROUTER_SITE_URL
        self.openrouter_site_name = settings.OPENROUTER_SITE_NAME
        
        self.timeout = 120.0
        
        # Track which provider is currently active
        self._local_available = None  # None = not checked, True/False = checked
        
        logger.info(f"LLM Service initialized with provider: {self.provider}")
    
    async def _generate_local(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate text using local TGI/Mistral"""
        try:
            # Format prompt for Mistral instruction format
            if system_prompt:
                formatted_prompt = f"<s>[INST] {system_prompt}\n\n{prompt} [/INST]"
            else:
                formatted_prompt = f"<s>[INST] {prompt} [/INST]"
            
            payload = {
                "inputs": formatted_prompt,
                "parameters": {
                    "max_new_tokens": max_new_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "do_sample": True,
                    "return_full_text": False
                }
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.local_url}/generate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                self._local_available = True
                return {
                    "success": True,
                    "generated_text": result.get("generated_text", ""),
                    "model": self.local_model,
                    "provider": "local"
                }
                
        except httpx.TimeoutException:
            logger.error("Local LLM request timed out")
            self._local_available = False
            return {
                "success": False,
                "error": "Local LLM request timed out",
                "generated_text": "",
                "provider": "local"
            }
        except Exception as e:
            logger.error(f"Local LLM generation error: {e}")
            self._local_available = False
            return {
                "success": False,
                "error": str(e),
                "generated_text": "",
                "provider": "local"
            }
    
    async def _generate_openrouter(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate text using OpenRouter API"""
        if not self.openrouter_key:
            return {
                "success": False,
                "error": "OpenRouter API key not configured",
                "generated_text": "",
                "provider": "openrouter"
            }
        
        try:
            # Build messages for chat completion format
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.openrouter_model,
                "messages": messages,
                "max_tokens": max_new_tokens,
                "temperature": temperature,
                "top_p": top_p
            }
            
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "HTTP-Referer": self.openrouter_site_url,
                "X-Title": self.openrouter_site_name,
                "Content-Type": "application/json"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.openrouter_url}/chat/completions",
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                
                # Extract text from OpenAI-compatible response
                generated_text = ""
                if "choices" in result and len(result["choices"]) > 0:
                    generated_text = result["choices"][0].get("message", {}).get("content", "")
                
                return {
                    "success": True,
                    "generated_text": generated_text,
                    "model": self.openrouter_model,
                    "provider": "openrouter",
                    "usage": result.get("usage", {})
                }
                
        except httpx.TimeoutException:
            logger.error("OpenRouter request timed out")
            return {
                "success": False,
                "error": "OpenRouter request timed out",
                "generated_text": "",
                "provider": "openrouter"
            }
        except httpx.HTTPStatusError as e:
            error_msg = f"OpenRouter API error: {e.response.status_code}"
            try:
                error_detail = e.response.json()
                error_msg = f"{error_msg} - {error_detail.get('error', {}).get('message', str(e))}"
            except:
                pass
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "generated_text": "",
                "provider": "openrouter"
            }
        except Exception as e:
            logger.error(f"OpenRouter generation error: {e}")
            return {
                "success": False,
                "error": str(e),
                "generated_text": "",
                "provider": "openrouter"
            }
    
    async def generate(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.95,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate text using configured LLM provider.
        
        In "auto" mode:
        1. Try local TGI first
        2. If local fails, fallback to OpenRouter
        
        Args:
            prompt: The user prompt
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter
            system_prompt: Optional system prompt
            
        Returns:
            Dict with success, generated_text, model, provider, and optional error
        """
        if self.provider == "local":
            return await self._generate_local(
                prompt, max_new_tokens, temperature, top_p, system_prompt
            )
        
        elif self.provider == "openrouter":
            return await self._generate_openrouter(
                prompt, max_new_tokens, temperature, top_p, system_prompt
            )
        
        elif self.provider == "auto":
            # Try local first if we haven't determined it's unavailable
            if self._local_available is not False:
                result = await self._generate_local(
                    prompt, max_new_tokens, temperature, top_p, system_prompt
                )
                if result["success"]:
                    return result
                logger.warning("Local LLM failed, falling back to OpenRouter")
            
            # Fallback to OpenRouter
            return await self._generate_openrouter(
                prompt, max_new_tokens, temperature, top_p, system_prompt
            )
        
        else:
            return {
                "success": False,
                "error": f"Unknown LLM provider: {self.provider}",
                "generated_text": "",
                "provider": self.provider
            }
    
    async def generate_chat_response(
        self,
        query: str,
        context: List[str],
        language: str = "en"
    ) -> Dict[str, Any]:
        """Generate a chatbot response with RAG context"""
        system_prompt = """You are a helpful assistant for Kumele, a social platform for hobby enthusiasts.
Answer questions based on the provided context. Be concise and helpful.
If you don't know the answer based on the context, say so honestly."""
        
        context_text = "\n\n".join(context) if context else "No specific context available."
        
        prompt = f"""Context information:
{context_text}

User question: {query}

Please provide a helpful answer based on the context above."""
        
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_new_tokens=512,
            temperature=0.7
        )
    
    async def generate_email_response(
        self,
        email_content: str,
        category: str,
        sentiment: str
    ) -> Dict[str, Any]:
        """Generate a response for a support email"""
        system_prompt = """You are a professional customer support agent for Kumele.
Write a helpful, empathetic, and professional response to the customer's email.
Keep the response concise but address all concerns raised."""
        
        prompt = f"""Customer email (Category: {category}, Sentiment: {sentiment}):
{email_content}

Please write a professional support response:"""
        
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_new_tokens=400,
            temperature=0.5
        )
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of LLM services.
        
        Returns:
            Dict with provider statuses
        """
        health = {
            "provider": self.provider,
            "local": {"configured": bool(self.local_url), "healthy": False},
            "openrouter": {"configured": bool(self.openrouter_key), "healthy": False}
        }
        
        # Check local TGI
        if self.local_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{self.local_url}/health")
                    health["local"]["healthy"] = response.status_code == 200
            except Exception as e:
                logger.debug(f"Local LLM health check failed: {e}")
        
        # Check OpenRouter (just verify API key format)
        if self.openrouter_key:
            # We can't really health-check OpenRouter without making a request
            # Just verify the key looks valid (starts with sk-)
            health["openrouter"]["healthy"] = self.openrouter_key.startswith("sk-")
        
        # Overall status
        if self.provider == "local":
            health["healthy"] = health["local"]["healthy"]
        elif self.provider == "openrouter":
            health["healthy"] = health["openrouter"]["healthy"]
        else:  # auto
            health["healthy"] = health["local"]["healthy"] or health["openrouter"]["healthy"]
        
        return health
    
    def get_active_provider(self) -> str:
        """Get the name of the currently active provider"""
        if self.provider == "auto":
            if self._local_available is True:
                return "local"
            elif self._local_available is False:
                return "openrouter"
            return "auto (not determined)"
        return self.provider


# Singleton instance
llm_service = LLMService()
