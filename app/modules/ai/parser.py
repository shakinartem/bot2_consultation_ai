SECTION_TO_FIELD = {
    "2. Аудит сайта": "website_audit",
    "3. Аудит карт": "maps_audit",
    "4. Аудит соцсетей": "social_audit",
    "5. Репутация": "reputation_audit",
    "7. Точки роста": "growth_points",
    "10. План на 30 дней": "roadmap_30_days",
    "11. План на 90 дней": "roadmap_90_days",
    "12. Рекомендации по услугам": "recommendations",
}


def extract_section(text: str, title: str) -> str | None:
    start = text.find(title)
    if start == -1:
        return None
    start += len(title)
    next_positions = [
        text.find(f"\n{i}. ", start)
        for i in range(1, 13)
        if text.find(f"\n{i}. ", start) != -1
    ]
    end = min(next_positions) if next_positions else len(text)
    return text[start:end].strip(" \n:-")


def parse_audit_text(text: str) -> dict[str, str | None]:
    data = {field: extract_section(text, title) for title, field in SECTION_TO_FIELD.items()}
    data["roadmap_7_days"] = extract_section(text, "9. План на 7 дней")
    if not data.get("growth_points"):
        data["growth_points"] = extract_section(text, "8. Быстрые улучшения")
    return data
