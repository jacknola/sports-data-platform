"""
Gemini LLM Service

Provides Google Gemini integration for the sports betting platform.
Supports both API key and Google Cloud ADC (Application Default Credentials).

Usage:
    from app.services.gemini_service import GeminiService

    gemini = GeminiService()
    response = await gemini.generate("Explain betting odds to me")
"""

import os
import json
from typing import Optional, List, Dict, Any, Type, Union
from loguru import logger
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.config import settings

# Try to import google.generativeai
try:
    import google.generativeai as genai
    from google.generativeai.types import GenerationConfig, SafetySettingDict
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed")


class GeminiService:
    """
    Google Gemini LLM service with best practices:
    - Robust retry logic (exponential backoff)
    - Structured JSON output support
    - System instructions for grounding
    - Multi-auth support (API Key, ADC, Vertex)
    """

    def __init__(
        self, 
        model_name: str = "gemini-2.0-flash",
        system_instruction: Optional[str] = None
    ):
        """
        Initialize Gemini service.

        Args:
            model_name: Model to use (default: gemini-2.0-flash)
            system_instruction: Persona and grounding instructions
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            )

        self.model_name = model_name
        self.system_instruction = system_instruction
        self._model = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Gemini client with available authentication."""
        api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
        
        if api_key:
            genai.configure(api_key=api_key)
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction
            )
            logger.info(f"Gemini initialized with API key: {self.model_name}")
            return

        # Fallback to ADC
        try:
            import google.auth
            credentials, project = google.auth.default()
            genai.configure(credentials=credentials)
            self._model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=self.system_instruction
            )
            logger.info(f"Gemini initialized with ADC, project: {project}")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")
            raise ValueError("No valid Gemini authentication found (API Key or ADC)")

    @retry(
        retry=retry_if_exception_type(Exception), # Broad for demo, refine for production
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        response_schema: Optional[Type[BaseModel]] = None,
    ) -> Union[str, Dict[str, Any]]:
        """
        Generate content with retries and optional structured output.
        """
        if not self._model:
            raise RuntimeError("Gemini model not initialized")

        config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }

        if response_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = response_schema

        try:
            # We use a thread pool for the synchronous SDK call
            import asyncio
            response = await asyncio.to_thread(
                self._model.generate_content,
                prompt,
                generation_config=genai.GenerationConfig(**config)
            )
            
            if response_schema:
                return json.loads(response.text)
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

    async def analyze_betting_scenario(
        self,
        game_info: Dict[str, Any],
        odds_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Structured analysis of a betting scenario.
        """
        class BettingAnalysis(BaseModel):
            value_side: str
            confidence_score: float
            reasoning: str
            sharp_alignment: bool
            risk_factors: List[str]

        prompt = f"""
Analyze this game for betting value:
Game: {game_info.get('away')} @ {game_info.get('home')}
Spread: {game_info.get('spread')}
Sharp Odds: {odds_data.get('pinnacle_home')} / {odds_data.get('pinnacle_away')}
Public Splits: {odds_data.get('home_ticket_pct')}% tickets
Signals: {odds_data.get('sharp_signals')}
"""
        return await self.generate(
            prompt, 
            temperature=0.2, 
            response_schema=BettingAnalysis
        )

    @property
    def is_available(self) -> bool:
        """Check if Gemini is properly configured."""
        return self._client is not None


# Convenience function for quick usage
async def quick_generate(prompt: str) -> str:
    """Quick generate without initializing service."""
    service = GeminiService()
    return await service.generate(prompt)
