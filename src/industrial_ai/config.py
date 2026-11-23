from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    erp_url: str = "http://localhost:8080"
    erp_user: str = "Administrator"
    erp_password: str = "admin"
    erp_api_key: str = ""
    erp_api_secret: str = ""
    ollama_host: str = "http://localhost:11434"
    llm_provider: str = "ollama"  # "ollama" or "groq"
    llm_model: str = "qwen2.5:0.5b"
    groq_api_key: str = ""
    llamacpp_base_url: str = "http://localhost:8081/v1"
    embed_model: str = "nomic-embed-text"
    docs_dir: Path = ROOT / "data" / "docs"
    chroma_dir: Path = ROOT / ".chroma"
    rag_collection: str = "industrial_docs"
    recursion_limit: int = 14

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        e = os.environ.get
        return cls(
            erp_url=e("ERP_URL", cls.erp_url),
            erp_user=e("ERP_USER", cls.erp_user),
            erp_password=e("ERP_PASSWORD", cls.erp_password),
            erp_api_key=e("ERP_API_KEY", ""),
            erp_api_secret=e("ERP_API_SECRET", ""),
            ollama_host=e("OLLAMA_HOST", cls.ollama_host),
            llm_provider=e("LLM_PROVIDER", cls.llm_provider).lower(),
            llm_model=e("LLM_MODEL", cls.llm_model),
            groq_api_key=e("GROQ_API_KEY", ""),
            llamacpp_base_url=e("LLAMACPP_BASE_URL", cls.llamacpp_base_url),
            embed_model=e("EMBED_MODEL", cls.embed_model),
            docs_dir=Path(e("DOCS_DIR", str(cls.docs_dir))),
            chroma_dir=Path(e("CHROMA_DIR", str(cls.chroma_dir))),
        )
