from dataclasses import asdict
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.consultation.models import Consultation
from app.modules.crm.service import Company
from app.modules.files.storage import docs_storage_dir


BRAND_BLUE = RGBColor(28, 66, 146)
BRAND_RED = RGBColor(226, 58, 46)


def _set_run_style(run, size: int = 11, bold: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.bold = bold
    if color is not None:
        run.font.color.rgb = color


def _add_title(document: Document, text: str, size: int = 18, color: RGBColor = BRAND_BLUE) -> None:
    paragraph = document.add_paragraph()
    run = paragraph.add_run(text)
    _set_run_style(run, size=size, bold=True, color=color)
    paragraph.paragraph_format.space_after = Pt(8)


def _add_body(document: Document, text: str | None) -> None:
    if not text:
        text = "Нет данных. Нужно уточнить на консультации."
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        paragraph = document.add_paragraph()
        run = paragraph.add_run(line)
        _set_run_style(run)
        paragraph.paragraph_format.space_after = Pt(4)


def _add_section(document: Document, title: str, text: str | None) -> None:
    _add_title(document, title, size=14)
    _add_body(document, text)


def _add_cover(document: Document, company: Company) -> None:
    for section in document.sections:
        section.top_margin = Inches(0.7)
        section.bottom_margin = Inches(0.7)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    brand = document.add_paragraph()
    brand.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = brand.add_run("ШАРиК digital")
    _set_run_style(run, size=28, bold=True, color=BRAND_RED)

    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle.add_run("Аудит и точки роста")
    _set_run_style(run, size=22, bold=True, color=BRAND_BLUE)

    target = document.add_paragraph()
    target.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = target.add_run(company.name)
    _set_run_style(run, size=16, bold=True)

    document.add_paragraph()
    lead = document.add_paragraph()
    lead.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = lead.add_run("Подготовлено для консультации по росту заявок и упаковке digital-точек контакта")
    _set_run_style(run, size=11)
    document.add_page_break()


def _company_info(company: Company) -> str:
    data = asdict(company)
    social = ", ".join(data.get("social_links") or []) or "нет данных"
    return (
        f"Компания: {company.name}\n"
        f"Ниша: {company.niche}\n"
        f"Город: {company.city}\n"
        f"Сайт: {company.website or 'нет данных'}\n"
        f"Карты: {company.maps_url or 'нет данных'}\n"
        f"Соцсети: {social}\n"
        f"Репутация/контекст: {company.reputation_notes or 'нет данных'}"
    )


async def generate_consultation_docx(
    session: AsyncSession,
    consultation: Consultation,
    company: Company,
) -> Path:
    document = Document()
    _add_cover(document, company)

    _add_section(document, "Информация о клиенте", _company_info(company))
    _add_section(document, "Краткий вывод", consultation.growth_points)
    _add_section(document, "Сайт", consultation.website_audit)
    _add_section(document, "Карты", consultation.maps_audit)
    _add_section(document, "Соцсети", consultation.social_audit)
    _add_section(document, "Репутация", consultation.reputation_audit)
    _add_section(document, "Точки роста", consultation.growth_points)
    _add_section(document, "План на 7 дней", consultation.roadmap_7_days)
    _add_section(document, "План на 30 дней", consultation.roadmap_30_days)
    _add_section(document, "План на 90 дней", consultation.roadmap_90_days)
    _add_section(document, "Рекомендации", consultation.recommendations)
    _add_section(
        document,
        "Следующий шаг",
        "Согласовать приоритеты на консультации, выбрать первый пакет работ и зафиксировать ответственного менеджера.",
    )

    output_path = docs_storage_dir() / f"consultation_company_{company.id}_{consultation.id}.docx"
    document.save(output_path)
    consultation.document_path = str(output_path)
    await session.commit()
    await session.refresh(consultation)
    return output_path
