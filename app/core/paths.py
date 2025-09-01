# app/core/paths.py
from pathlib import Path
import os

# Permite trocar o diretório base via env var, mas padrão continua "data"
DATA_DIR = Path(os.getenv("DATA_DIR", "data")).resolve()

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def pdf_dir(usuario_id: str, aula_id: str) -> Path:
    """
    Pasta padrão para PDFs: data/pdfs/<usuario_id>/<aula_id>/
    """
    return ensure_dir(DATA_DIR / "pdfs" / usuario_id / aula_id)

def audio_dir(usuario_id: str, aula_id: str) -> Path:
    """
    Pasta padrão para áudios: data/audios/<usuario_id>/<aula_id>/
    """
    return ensure_dir(DATA_DIR / "audios" / usuario_id / aula_id)

def pdf_path(usuario_id: str, aula_id: str, pdf_id: str) -> Path:
    """
    Caminho final do PDF: data/pdfs/<usuario_id>/<aula_id>/<pdf_id>.pdf
    """
    return pdf_dir(usuario_id, aula_id) / f"{pdf_id}.pdf"

def audio_path(usuario_id: str, aula_id: str, pdf_id: str, ext: str = "mp3") -> Path:
    """
    Caminho final do áudio: data/audios/<usuario_id>/<aula_id>/<pdf_id>.<ext>
    """
    return audio_dir(usuario_id, aula_id) / f"{pdf_id}.{ext}"
