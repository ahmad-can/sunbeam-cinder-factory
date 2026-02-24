"""OpenAI API client for charm generation."""

import json
import logging
from dataclasses import dataclass
from typing import Any

from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from charm_generator.settings import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
    API_TIMEOUT,
    API_RETRY_ATTEMPTS,
)

logger = logging.getLogger(__name__)


@dataclass
class GenerationMetrics:
    """Metrics from a generation call."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


class CharmGeneratorClient:
    """OpenAI client for generating charm files."""
    
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key or OPENAI_API_KEY
        self.model = model or OPENAI_MODEL
        
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        self._client = OpenAI(api_key=self.api_key, timeout=API_TIMEOUT)
    
    def generate_charm_files(
        self,
        system_prompt: str,
        user_prompt: str,
        vendor: str = "",
    ) -> tuple[dict[str, str], GenerationMetrics]:
        """Generate charm files using OpenAI API."""
        metrics = GenerationMetrics()
        
        @retry(
            stop=stop_after_attempt(API_RETRY_ATTEMPTS),
            wait=wait_exponential(multiplier=1, max=30),
            retry=retry_if_exception_type((APIError, APIConnectionError, RateLimitError)),
        )
        def _call_api() -> dict[str, str]:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
                response_format={"type": "json_object"},
            )
            
            if response.usage:
                metrics.prompt_tokens = response.usage.prompt_tokens
                metrics.completion_tokens = response.usage.completion_tokens
                metrics.total_tokens = response.usage.total_tokens
            
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Empty response from API")
            
            return self._parse_response(content)
        
        logger.info(f"Generating charm for: {vendor or 'unknown'}")
        file_map = _call_api()
        logger.info(f"Generated {len(file_map)} files")
        
        return file_map, metrics
    
    def _parse_response(self, content: str) -> dict[str, str]:
        """Parse JSON response from API."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try extracting from markdown code block
            if "```json" in content:
                start = content.find("```json") + 7
                end = content.find("```", start)
                if end > start:
                    data = json.loads(content[start:end])
                else:
                    raise ValueError("Failed to parse JSON response")
            else:
                raise ValueError("Failed to parse JSON response")
        
        if not isinstance(data, dict):
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        
        # Handle nested 'files' key
        if "files" in data and isinstance(data["files"], dict):
            data = data["files"]
        
        # Convert all values to strings
        return {k: str(v) if v is not None else "" for k, v in data.items() if isinstance(k, str)}

