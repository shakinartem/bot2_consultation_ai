from collections.abc import Mapping


def build_consultation_audit_prompt(company_data: Mapping, extra_data: Mapping | None = None) -> str:
    extra_data = extra_data or {}
    return f"""
Ты AI-консультант агентства ШАРиК digital. Подготовь прикладной аудит для консультации
с владельцем бизнеса. Пиши по-русски, конкретно, без воды, с фокусом на рост заявок.

Данные клиента:
- ID: {company_data.get("id")}
- Компания: {company_data.get("name")}
- Ниша: {company_data.get("niche")}
- Город: {company_data.get("city")}
- Сайт: {company_data.get("website") or "нет данных"}
- Карты: {company_data.get("maps_url") or "нет данных"}
- Соцсети: {", ".join(company_data.get("social_links") or []) or "нет данных"}
- Репутация/контекст: {company_data.get("reputation_notes") or "нет данных"}

Дополнительные данные менеджера:
{extra_data or "нет дополнительных данных"}

Верни результат строго в такой структуре с заголовками:
1. Общий вывод
2. Аудит сайта
3. Аудит карт
4. Аудит соцсетей
5. Репутация
6. Основные проблемы
7. Точки роста
8. Быстрые улучшения
9. План на 7 дней
10. План на 30 дней
11. План на 90 дней
12. Рекомендации по услугам

В каждом разделе дай 3-6 практичных пунктов. Если данных мало, явно укажи, что нужно
проверить на консультации, и предложи гипотезы для бизнеса этой ниши.
""".strip()
