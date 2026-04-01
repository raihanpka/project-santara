"""Cloud LLM client with rate limiting and exponential backoff.

This module provides the infrastructure adapter for Cloud LLM providers,
implementing robust retry logic and concurrency control as required by
the AGENTS.md architecture guidelines.

Supported providers:
- Google Gemini
- Anthropic Claude
- OpenAI GPT
"""

import asyncio
import json
from abc import abstractmethod
from typing import Any, TypeVar

import anthropic
import google.generativeai as genai
import openai
from pydantic import BaseModel
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import LLMProvider, get_settings
from src.domain.repositories import LLMClient, LLMError, RateLimitError
from src.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class BaseLLMClient(LLMClient):
    """Base class for LLM clients with shared retry and concurrency logic."""

    def __init__(
        self,
        api_key: str,
        model: str,
        max_concurrency: int = 5,
        max_retries: int = 5,
        retry_min_wait: float = 1.0,
        retry_max_wait: float = 60.0,
    ) -> None:
        """Initialize the base LLM client.

        Args:
            api_key: API key for the provider
            model: Model identifier
            max_concurrency: Maximum concurrent requests
            max_retries: Maximum retry attempts
            retry_min_wait: Minimum wait between retries (seconds)
            retry_max_wait: Maximum wait between retries (seconds)
        """
        self._api_key = api_key
        self._model = model
        self._max_retries = max_retries
        self._retry_min_wait = retry_min_wait
        self._retry_max_wait = retry_max_wait
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._request_count = 0
        self._error_count = 0

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name for logging."""
        ...

    def _get_retry_config(self) -> AsyncRetrying:
        """Get tenacity retry configuration."""
        return AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self._retry_min_wait,
                max=self._retry_max_wait,
            ),
            retry=retry_if_exception_type((RateLimitError, asyncio.TimeoutError)),
            reraise=True,
        )

    async def _with_retry(self, coro_func: Any) -> Any:
        """Execute a coroutine with retry logic.

        Args:
            coro_func: Async function to execute

        Returns:
            Result of the coroutine

        Raises:
            LLMError: If all retries fail
        """
        async with self._semaphore:
            self._request_count += 1
            request_id = self._request_count

            logger.debug(
                "llm_request_start",
                provider=self.provider_name,
                model=self._model,
                request_id=request_id,
            )

            try:
                async for attempt in self._get_retry_config():
                    with attempt:
                        result = await coro_func()
                        logger.debug(
                            "llm_request_success",
                            provider=self.provider_name,
                            request_id=request_id,
                            attempt=attempt.retry_state.attempt_number,
                        )
                        return result
            except RetryError as e:
                self._error_count += 1
                logger.error(
                    "llm_request_failed",
                    provider=self.provider_name,
                    request_id=request_id,
                    error=str(e.last_attempt.exception()),
                )
                raise LLMError(
                    f"Request failed after {self._max_retries} attempts",
                    provider=self.provider_name,
                    original_error=e.last_attempt.exception(),
                ) from e

        # This should never be reached, but satisfies type checker
        raise LLMError("Unexpected error", provider=self.provider_name)

    def get_stats(self) -> dict[str, int]:
        """Get client statistics."""
        return {
            "total_requests": self._request_count,
            "total_errors": self._error_count,
        }


# =============================================================================
# Google Gemini Client
# =============================================================================


class GeminiClient(BaseLLMClient):
    """Google Gemini LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        **kwargs: Any,
    ) -> None:
        """Initialize Gemini client."""
        super().__init__(api_key=api_key, model=model, **kwargs)
        genai.configure(api_key=api_key)
        self._client = genai.GenerativeModel(model)

    @property
    def provider_name(self) -> str:
        return "gemini"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using Gemini."""

        async def _generate() -> str:
            try:
                # Combine system prompt and user prompt
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\n{prompt}"

                response = await asyncio.to_thread(
                    self._client.generate_content,
                    full_prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    ),
                )
                return response.text
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    raise RateLimitError(self.provider_name) from e
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Generate structured JSON response using Gemini."""

        async def _generate() -> dict:
            try:
                schema_json = response_schema.model_json_schema() if hasattr(response_schema, "model_json_schema") else {}

                structured_prompt = f"""
{system_prompt or "You are a helpful assistant that outputs JSON."}

Output your response as valid JSON matching this schema:
{json.dumps(schema_json, indent=2)}

User request:
{prompt}

Respond with ONLY valid JSON, no markdown or explanation.
"""
                response = await asyncio.to_thread(
                    self._client.generate_content,
                    structured_prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.3,
                        response_mime_type="application/json",
                    ),
                )
                return json.loads(response.text)
            except json.JSONDecodeError as e:
                raise LLMError(f"Invalid JSON response: {e}", self.provider_name, e) from e
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "quota" in error_str or "rate" in error_str:
                    raise RateLimitError(self.provider_name) from e
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def close(self) -> None:
        """Close the client (no-op for Gemini)."""
        pass


# =============================================================================
# Anthropic Claude Client
# =============================================================================


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        **kwargs: Any,
    ) -> None:
        """Initialize Anthropic client."""
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using Claude."""

        async def _generate() -> str:
            try:
                message = await self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens,
                    system=system_prompt or "You are a helpful assistant.",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                # Extract text from response
                content = message.content[0]
                if hasattr(content, "text"):
                    return content.text
                return str(content)
            except anthropic.RateLimitError as e:
                raise RateLimitError(self.provider_name) from e
            except anthropic.APIError as e:
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Generate structured JSON response using Claude."""

        async def _generate() -> dict:
            try:
                schema_json = response_schema.model_json_schema() if hasattr(response_schema, "model_json_schema") else {}

                system = f"""
{system_prompt or "You are a helpful assistant that outputs JSON."}

You MUST respond with valid JSON matching this schema:
{json.dumps(schema_json, indent=2)}

Output ONLY the JSON object, no markdown formatting or explanation.
"""
                message = await self._client.messages.create(
                    model=self._model,
                    max_tokens=2048,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                content = message.content[0]
                text = content.text if hasattr(content, "text") else str(content)

                # Strip markdown code blocks if present
                text = text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

                return json.loads(text)
            except json.JSONDecodeError as e:
                raise LLMError(f"Invalid JSON response: {e}", self.provider_name, e) from e
            except anthropic.RateLimitError as e:
                raise RateLimitError(self.provider_name) from e
            except anthropic.APIError as e:
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()


# =============================================================================
# OpenAI GPT Client
# =============================================================================


class OpenAIClient(BaseLLMClient):
    """OpenAI GPT LLM client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        **kwargs: Any,
    ) -> None:
        """Initialize OpenAI client."""
        super().__init__(api_key=api_key, model=model, **kwargs)
        self._client = openai.AsyncOpenAI(api_key=api_key)

    @property
    def provider_name(self) -> str:
        return "openai"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using OpenAI."""

        async def _generate() -> str:
            try:
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,  # type: ignore
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""
            except openai.RateLimitError as e:
                raise RateLimitError(self.provider_name) from e
            except openai.APIError as e:
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Generate structured JSON response using OpenAI."""

        async def _generate() -> dict:
            try:
                schema_json = response_schema.model_json_schema() if hasattr(response_schema, "model_json_schema") else {}

                system = f"""
{system_prompt or "You are a helpful assistant that outputs JSON."}

You MUST respond with valid JSON matching this schema:
{json.dumps(schema_json, indent=2)}

Output ONLY the JSON object.
"""
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2048,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                text = response.choices[0].message.content or "{}"
                return json.loads(text)
            except json.JSONDecodeError as e:
                raise LLMError(f"Invalid JSON response: {e}", self.provider_name, e) from e
            except openai.RateLimitError as e:
                raise RateLimitError(self.provider_name) from e
            except openai.APIError as e:
                raise LLMError(str(e), self.provider_name, e) from e

        return await self._with_retry(_generate)

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()


# =============================================================================
# LLM Router (Factory)
# =============================================================================


class LLMRouter:
    """Router that creates and manages LLM clients based on configuration.

    This is the main entry point for LLM interactions, handling provider
    selection based on environment configuration.
    """

    def __init__(self) -> None:
        """Initialize the LLM router."""
        self._client: BaseLLMClient | None = None
        self._settings = get_settings()

    async def get_client(self) -> BaseLLMClient:
        """Get or create the configured LLM client.

        Returns:
            Configured LLM client instance
        """
        if self._client is not None:
            return self._client

        settings = self._settings
        common_kwargs = {
            "api_key": settings.llm_api_key,
            "model": settings.llm_model,
            "max_concurrency": settings.llm_max_concurrency,
            "max_retries": settings.llm_max_retries,
            "retry_min_wait": settings.llm_retry_min_wait,
            "retry_max_wait": settings.llm_retry_max_wait,
        }

        if settings.llm_service == LLMProvider.GEMINI:
            self._client = GeminiClient(**common_kwargs)
        elif settings.llm_service == LLMProvider.ANTHROPIC:
            self._client = AnthropicClient(**common_kwargs)
        elif settings.llm_service == LLMProvider.OPENAI:
            self._client = OpenAIClient(**common_kwargs)
        else:
            raise ValueError(f"Unsupported LLM provider: {settings.llm_service}")

        logger.info(
            "llm_client_created",
            provider=settings.llm_service.value,
            model=settings.llm_model,
            max_concurrency=settings.llm_max_concurrency,
        )

        return self._client

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate text using the configured LLM.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            Generated text
        """
        client = await self.get_client()
        return await client.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def generate_structured(
        self,
        prompt: str,
        response_schema: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Generate structured JSON using the configured LLM.

        Args:
            prompt: User prompt
            response_schema: Pydantic model for response validation
            system_prompt: Optional system prompt

        Returns:
            Parsed JSON response
        """
        client = await self.get_client()
        return await client.generate_structured(
            prompt=prompt,
            response_schema=response_schema,
            system_prompt=system_prompt,
        )

    async def close(self) -> None:
        """Close the LLM client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            logger.info("llm_client_closed")

    def get_stats(self) -> dict[str, Any]:
        """Get router and client statistics."""
        stats: dict[str, Any] = {
            "provider": self._settings.llm_service.value,
            "model": self._settings.llm_model,
        }
        if self._client is not None:
            stats.update(self._client.get_stats())
        return stats


# =============================================================================
# Factory Functions
# =============================================================================


def create_llm_router() -> LLMRouter:
    """Create an LLM router instance."""
    return LLMRouter()


async def create_llm_client() -> BaseLLMClient:
    """Create and return the configured LLM client directly."""
    router = LLMRouter()
    return await router.get_client()
