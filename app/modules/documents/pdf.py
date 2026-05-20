from __future__ import annotations

import shutil
import subprocess
import logging
from pathlib import Path

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class PDFExportResult:
    def __init__(self, path: Path | None, message: str) -> None:
        self.path = path
        self.message = message


def export_pdf_if_available(docx_path: Path, settings: Settings | None = None) -> PDFExportResult:
    settings = settings or get_settings()
    if not settings.pdf_export_enabled:
        return PDFExportResult(None, "PDF-экспорт отключен в настройках.")
    if settings.pdf_export_provider.lower() != "libreoffice":
        return PDFExportResult(None, "PDF-экспорт не настроен: поддерживается provider=libreoffice.")

    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        logger.warning("PDF export requested but LibreOffice executable was not found")
        return PDFExportResult(None, "LibreOffice не найден. Отправляю DOCX без PDF.")

    output_dir = docx_path.parent
    try:
        subprocess.run(
            [
                executable,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(output_dir),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("PDF export failed for %s: %s", docx_path, exc)
        return PDFExportResult(None, f"PDF-экспорт не удался: {exc}")

    pdf_path = docx_path.with_suffix(".pdf")
    if not pdf_path.exists():
        logger.warning("PDF export finished but output file was not found: %s", pdf_path)
        return PDFExportResult(None, "LibreOffice завершился, но PDF-файл не найден.")
    return PDFExportResult(pdf_path, "PDF успешно создан.")
