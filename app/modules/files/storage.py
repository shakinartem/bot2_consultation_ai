from pathlib import Path

from app.config import get_settings


def storage_root() -> Path:
    return get_settings().storage_path


def ensure_storage_layout() -> None:
    root = storage_root()
    for relative in ("consultations", "docs", "clients"):
        (root / relative).mkdir(parents=True, exist_ok=True)


def company_storage_dir(company_id: int) -> Path:
    path = storage_root() / "clients" / f"company_{company_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def docs_storage_dir() -> Path:
    path = storage_root() / "docs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def consultations_storage_dir() -> Path:
    path = storage_root() / "consultations"
    path.mkdir(parents=True, exist_ok=True)
    return path
