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
from typing import Optional, List, Dict, Any
from loguru import logger

from app.config import settings

# Try to import google.generativeai
try:
    import google.generativeai as genai

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("google-generativeai not installed")


class GeminiService:
    """
    Google Gemini LLM service with flexible authentication.

    Supports:
    - API key authentication (GEMINI_API_KEY in .env)
    - Google Cloud ADC (Application Default Credentials)
    - Google Code Assist authentication
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        """
        Initialize Gemini service.

        Args:
            model_name: Model to use (default: gemini-2.0-flash)
        """
        if not GENAI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. Run: pip install google-generativeai"
            )

        self.model_name = model_name
        self._client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Gemini client with available authentication."""

        # Method 1: Try API key first
        api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self._client = genai.GenerativeModel(self.model_name)
                logger.info(f"Gemini initialized with API key: {self.model_name}")
                return
            except Exception as e:
                logger.warning(f"Failed to initialize with API key: {e}")

        # Method 2: Try Google Cloud ADC (for Google Code Assist)
        try:
            # This works with Google Code Assist / gcloud auth
            import google.auth

            credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/generative-language.tuning"]
            )
            genai.configure(
                credentials=credentials,
                project=project or settings.GEMINI_PROJECT_ID,
            )
            self._client = genai.GenerativeModel(self.model_name)
            logger.info(f"Gemini initialized with ADC, project: {project}")
            return
        except Exception as e:
            logger.warning(f"Failed to initialize with ADC: {e}")

        # Method 3: Try vertex AI (Google Cloud)
        try:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(
                project=settings.GEMINI_PROJECT_ID,
                location="us-central1",
            )
            self._client = GenerativeModel(self.model_name)
            logger.info("Gemini initialized with Vertex AI")
            return
        except Exception as e:
            logger.warning(f"Failed to initialize with Vertex AI: {e}")

        # If we get here, no auth method worked
        raise ValueError(
            "Failed to initialize Gemini. Please ensure either:\n"
            "1. GEMINI_API_KEY is set in .env, OR\n"
            "2. Run 'gcloud auth application-default login' for ADC, OR\n"
            "3. Google Code Assist is properly configured"
        )

    async def generate(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate text from Gemini.

        Args:
            prompt: Input prompt
            temperature: Creativity (0.0-1.0)
            max_tokens: Max response tokens

        Returns:
            Generated text response
        """
        if not self._client:
            raise RuntimeError("Gemini client not initialized")

        try:
            response = self._client.generate_content(
                prompt,
                generation_config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise

    async def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
    ) -> str:
        """
        Generate response in a chat context.

        Args:
            messages: List of {"role": "user"|"model", "content": "..."}
            temperature: Creativity

        Returns:
            Model response
        """
        if not self._client:
            raise RuntimeError("Gemini client not initialized")

        try:
            # Start chat session
            chat = self._client.start_chat(
                history=[
                    {"role": m["role"], "parts": [m["content"]]} for m in messages[:-1]
                ]
            )

            # Send last message
            response = chat.send_message(
                messages[-1]["content"], generation_config={"temperature": temperature}
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini chat failed: {e}")
            raise

    async def analyze_betting_scenario(
        self,
        game_info: Dict[str, Any],
        odds_data: Dict[str, Any],
    ) -> str:
        """
        Analyze a betting scenario using Gemini.

        Args:
            game_info: Game details (teams, spread, etc.)
            odds_data: Current odds and line movement

        Returns:
            Analysis text from Gemini
        """
        prompt = f"""
You are a professional sports bettor analyzing a game.

Game Information:
- Home Team: {game_info.get("home", "N/A")}
- Away Team: {game_info.get("away", "N/A")}
- Spread: {game_info.get("spread", "N/A")}
- Conference: {game_info.get("conference", "N/A")}

Odds Data:
- Pinnacle Odds: Home {odds_data.get("pinnacle_home", "N/A")}, Away {odds_data.get("pinnacle_away", "N/A")}
- Retail Odds: Home {odds_data.get("retail_home", "N/A")}, Away {odds_data.get("retail_away", "N/A")}
- Public Tickets: {odds_data.get("home_ticket_pct", "N/A")}% on home
- Sharp Money: {odds_data.get("sharp_signals", "None")}

Provide a brief analysis of whether there's value on either side.
Consider: Reverse Line Movement, sharp money signals, and the spread relative to the odds.
"""
        return await self.generate(prompt, temperature=0.3)

    @property
    def is_available(self) -> bool:
        """Check if Gemini is properly configured."""
        return self._client is not None


# Convenience function for quick usage
async def quick_generate(prompt: str) -> str:
    """Quick generate without initializing service."""
    service = GeminiService()
    return await service.generate(prompt)
