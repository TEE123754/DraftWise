from app.ai.gemini import GeminiClient
from app.ai.morpheus import MorpheusClient


def create_provider(settings):
    if settings.ai_provider == "morpheus":
        return MorpheusClient(settings) if settings.morpheus_api_key else None
    return GeminiClient(settings) if settings.gemini_api_key else None
