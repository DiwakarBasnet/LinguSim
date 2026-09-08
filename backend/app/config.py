from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # AssemblyAI powers both the live voice conversation (Voice Agent API) and
    # the post-session evaluation (LLM Gateway) — there is no mock/offline mode;
    # a working ASSEMBLYAI_API_KEY is required for the app to function.
    assemblyai_api_key: str = ""
    assemblyai_ws_url: str = "wss://agents.assemblyai.com/v1/ws"
    assemblyai_voice_id: str = "ivy"

    llm_gateway_url: str = "https://llm-gateway.assemblyai.com/v1/chat/completions"
    llm_gateway_model: str = "qwen3.5-4b-32k-fast"

    database_url: str = "postgresql+psycopg://speakquest:speakquest@localhost:5544/speakquest"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
