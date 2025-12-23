# agents/llm_factory.py
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from config.agent_config import get_agent_config, AgentConfig


def build_llm(config: AgentConfig | None = None):
    """
    Devuelve un LLM de chat según el provider configurado.
    - provider == "openai"  -> ChatOpenAI
    - provider == "gemini"  -> ChatGoogleGenerativeAI
    """
    if config is None:
        config = get_agent_config()

    if config.provider == "openai":
        # OpenAI
        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            temperature=config.temperature,
        )

    if config.provider == "gemini":
        # Google / Gemini
        return ChatGoogleGenerativeAI(
            model=config.model,
            google_api_key=config.api_key,
            temperature=config.temperature,
        )

    raise ValueError(f"Unknown provider: {config.provider}")
