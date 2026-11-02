"""
config.py
---------
Configuração centralizada via .env (python-dotenv).
Carrega uma única vez no startup e expõe `settings` para todo o projeto.
"""
from pathlib import Path
from dotenv import load_dotenv
import os

# Carrega .env da raiz do projeto (onde está este arquivo)
load_dotenv(Path(__file__).parent / ".env")


class Settings:
    # ─────────────────────────────────────────────
    # LM Studio / LLM
    # ─────────────────────────────────────────────
    LM_STUDIO_URL: str = os.getenv(
        "LM_STUDIO_URL", "http://localhost:1234/v1/chat/completions"
    )
    LM_STUDIO_MODELS_URL: str = os.getenv(
        "LM_STUDIO_MODELS_URL", "http://localhost:1234/v1/models"
    )
    MODELO_VISAO: str = os.getenv("MODELO_VISAO", "qwen2.5-vl-3b-instruct")
    MODELO_CHAT: str = os.getenv("MODELO_CHAT", "qwen2.5-vl-3b-instruct")
    TEMPERATURA: float = float(os.getenv("TEMPERATURA", "0.1"))
    MAX_TOKENS_VISAO: int = int(os.getenv("MAX_TOKENS_VISAO", "2048"))
    MAX_TOKENS_CHAT: int = int(os.getenv("MAX_TOKENS_CHAT", "1024"))

    # ─────────────────────────────────────────────
    # Tesseract (opcional - None = auto-detect via PATH)
    # ─────────────────────────────────────────────
    TESSERACT_CMD: str | None = os.getenv("TESSERACT_CMD")

    # ─────────────────────────────────────────────
    # Dados / Planilha
    # ─────────────────────────────────────────────
    CAMINHO_PLANILHA: str = os.getenv("CAMINHO_PLANILHA", "notas_fiscais.xlsx")

    # ─────────────────────────────────────────────
    # Interface Streamlit
    # ─────────────────────────────────────────────
    STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    STREAMLIT_THEME: str = os.getenv("STREAMLIT_THEME", "light")


# Instância singleton
settings = Settings()