import re


AUDIT_SECTIONS = [
    ("# Общий вывод", "overall_conclusion"),
    ("# Аудит сайта", "website_audit"),
    ("# Аудит карт", "maps_audit"),
    ("# Аудит соцсетей", "social_audit"),
    ("# Репутация", "reputation_audit"),
    ("# Основные проблемы", "main_problems"),
    ("# Точки роста", "growth_points"),
    ("# Быстрые улучшения", "quick_improvements"),
    ("# План на 7 дней", "roadmap_7_days"),
    ("# План на 30 дней", "roadmap_30_days"),
    ("# План на 90 дней", "roadmap_90_days"),
    ("# Рекомендации по услугам ШАРиК digital", "recommendations"),
    ("# Следующий шаг", "next_step"),
]


LEGACY_TITLES = {
    "overall_conclusion": ["1. Общий вывод"],
    "website_audit": ["2. Аудит сайта"],
    "maps_audit": ["3. Аудит карт"],
    "social_audit": ["4. Аудит соцсетей"],
    "reputation_audit": ["5. Репутация"],
    "main_problems": ["6. Основные проблемы"],
    "growth_points": ["7. Точки роста"],
    "quick_improvements": ["8. Быстрые улучшения"],
    "roadmap_7_days": ["9. План на 7 дней"],
    "roadmap_30_days": ["10. План на 30 дней"],
    "roadmap_90_days": ["11. План на 90 дней"],
    "recommendations": ["12. Рекомендации по услугам", "12. Рекомендации"],
}


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lstrip("#").strip()).lower()


def parse_markdown_sections(text: str) -> dict[str, str]:
    title_to_field = {_normalize_title(title): field for title, field in AUDIT_SECTIONS}
    result: dict[str, str] = {}
    current_field: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        if current_field and buffer:
            value = "\n".join(buffer).strip()
            if value:
                result[current_field] = value

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            normalized = _normalize_title(stripped)
            if normalized in title_to_field:
                flush()
                current_field = title_to_field[normalized]
                buffer = []
                continue
        if current_field:
            buffer.append(line)
    flush()
    return result


def extract_legacy_section(text: str, title: str) -> str | None:
    start = text.find(title)
    if start == -1:
        return None
    start += len(title)
    next_positions = [
        text.find(f"\n{i}. ", start)
        for i in range(1, 14)
        if text.find(f"\n{i}. ", start) != -1
    ]
    end = min(next_positions) if next_positions else len(text)
    return text[start:end].strip(" \n:-")


def parse_audit_text(text: str) -> dict[str, str | None]:
    parsed = parse_markdown_sections(text)
    data: dict[str, str | None] = {field: parsed.get(field) for _, field in AUDIT_SECTIONS}

    for field, titles in LEGACY_TITLES.items():
        if data.get(field):
            continue
        for title in titles:
            value = extract_legacy_section(text, title)
            if value:
                data[field] = value
                break

    return data
