from collections.abc import Mapping


def _value(data: Mapping, key: str, default: str = "нет данных") -> str:
    value = data.get(key)
    if value in (None, "", []):
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or default
    return str(value)


def build_consultation_audit_prompt(company_data: Mapping, extra_data: Mapping | None = None) -> str:
    extra_data = extra_data or {}
    return f"""
Ты senior digital-стратег агентства ШАРиК digital. Подготовь профессиональный,
продающий, но спокойный AI-аудит digital-присутствия стоматологической клиники.

Цель аудита: помочь менеджеру провести консультацию с владельцем/управляющим клиники,
показать, где теряются заявки, доверие и повторные касания, и предложить понятный
roadmap улучшений без грубого давления.

Контекст клиента:
- ID: {_value(company_data, "id")}
- Клиника: {_value(company_data, "name")}
- Юридическое название: {_value(company_data, "legal_name")}
- Ниша: {_value(company_data, "niche", "стоматология")}
- Город: {_value(company_data, "city")}
- Адрес: {_value(company_data, "address")}
- Телефон: {_value(company_data, "phone")}
- Сайт: {_value(company_data, "website")}
- Карты: {_value(company_data, "maps_url")}
- Соцсети: {_value(company_data, "social_links")}
- Рейтинг: {_value(company_data, "rating")}
- Количество отзывов: {_value(company_data, "reviews_count")}
- Репутация/контекст: {_value(company_data, "reputation_notes")}
- Заметки CRM: {_value(company_data, "crm_notes")}
- Боль клиента: {_value(company_data, "pain")}
- Результат холодного звонка: {_value(company_data, "cold_call_result")}

Дополнительные данные менеджера, ссылки и материалы:
{extra_data or "нет дополнительных данных"}

Что учитывать:
- стоматология продаёт через доверие, карту рядом с пациентом, отзывы, удобную запись и работу администратора;
- важно показать потери заявок на сайте, картах, в соцсетях и при повторном касании;
- рекомендации должны быть реалистичными для малого/среднего бизнеса и low-cost/self-hosted friendly;
- не обещай гарантированный результат и не придумывай факты, если данных нет;
- если данных мало, напиши гипотезы и что проверить на консультации.

Верни ответ строго в markdown с такими заголовками, без дополнительных заголовков:

# Общий вывод

# Аудит сайта

# Аудит карт

# Аудит соцсетей

# Репутация

# Основные проблемы

# Точки роста

# Быстрые улучшения

# План на 7 дней

# План на 30 дней

# План на 90 дней

# Рекомендации по услугам ШАРиК digital

# Следующий шаг

В разделах со списками используй обычные markdown bullets. Пиши конкретно: что сделать,
зачем это влияет на заявки, и как это объяснить владельцу клиники на консультации.
""".strip()
