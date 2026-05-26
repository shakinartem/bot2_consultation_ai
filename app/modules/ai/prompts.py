from __future__ import annotations

import json
from collections.abc import Mapping


PROPOSAL_PRICING_DEFAULTS = [
    ("Диагностика / roadmap", "5–10 тыс. ₽"),
    ("Упаковка карт", "около 45 тыс. ₽"),
    ("Авито", "15–20 тыс. ₽"),
    ("Ведение 50 объявлений Авито", "20 тыс. ₽"),
    ("Дополнительное объявление Авито", "500 ₽"),
    ("Соцсети: 30+ постов для одной соцсети", "от 55 тыс. ₽/мес"),
    ("Посадочная с квизом/формой", "от 20 тыс. ₽"),
    ("Лендинг", "от 35 тыс. ₽"),
    ("Лендинг с админкой", "от 60 тыс. ₽"),
    ("Многостраничник", "от 80 тыс. ₽"),
    ("Многостраничник с админкой", "от 115 тыс. ₽"),
    ("Интернет-магазин", "от 150 тыс. ₽"),
    ("CRM", "от 80 тыс. ₽"),
    ("AI-бот", "от 60 тыс. ₽"),
    ("Упоминания на интернет-ресурсах", "от 15 тыс. ₽"),
    ("Комплексное ведение", "150–250 тыс. ₽/мес"),
]


def _value(data: Mapping, key: str, default: str = "нет данных") -> str:
    value = data.get(key)
    if value in (None, "", []):
        return default
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or default
    return str(value)


def _json_block(data: Mapping | None) -> str:
    if not data:
        return "нет данных"
    return json.dumps(data, ensure_ascii=False, indent=2)


def pricing_defaults_text() -> str:
    return "\n".join(f"- {name}: {price}" for name, price in PROPOSAL_PRICING_DEFAULTS)


def build_consultation_audit_prompt(
    company_data: Mapping,
    extra_data: Mapping | None = None,
    crm_context: Mapping | None = None,
) -> str:
    extra_data = extra_data or {}
    crm_context = crm_context or {}
    return f"""
Ты senior digital-стратег агентства ШАРиК digital.
Подготовь осторожный, профессиональный AI-аудит для стоматологической клиники.

Важно:
- не выдумывай факты;
- не пиши точные цифры без данных;
- не обещай гарантированный рост;
- не ссылайся на несуществующие кейсы;
- не пиши, что мы проверили сайт, карты или соцсети вручную, если это не следует из CRM-фактов и заметок менеджера;
- внутреннюю связку из 5 ботов агентства можно упоминать только как внутреннее преимущество агентства, но не как продаваемый продукт.

Подтвержденные данные компании:
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
- Контекст репутации: {_value(company_data, "reputation_notes")}
- Заметки CRM: {_value(company_data, "crm_notes")}
- Боль клиента: {_value(company_data, "pain")}
- Результат холодного звонка: {_value(company_data, "cold_call_result")}

CRM consultation context:
{_json_block(crm_context)}

Заметки и материалы менеджера:
{_json_block(extra_data)}

Собери ответ строго в markdown с разделами:

# Контекст продаж

# Что важно проговорить на консультации

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

Если данных недостаточно, прямо укажи, что нужно уточнить на консультации.
""".strip()


def choose_proposal_defaults(source_text: str) -> tuple[str, str]:
    normalized = source_text.lower()
    if "карты" in normalized or "отзывы" in normalized or "репутац" in normalized:
        return "Упаковка карт и репутации", "около 45 тыс. ₽"
    if "авито" in normalized:
        return "Авито и поток объявлений", "15–20 тыс. ₽ + 500 ₽ за доп. объявление"
    if "crm" in normalized:
        return "CRM и процессы лидов", "от 80 тыс. ₽"
    if "бот" in normalized or "ai" in normalized:
        return "AI-бот и автоматизация", "от 60 тыс. ₽"
    if "сайт" in normalized and "админ" in normalized:
        return "Лендинг с админкой", "от 60 тыс. ₽"
    if "сайт" in normalized or "лендинг" in normalized or "квиз" in normalized:
        return "Лендинг / посадочная", "от 20–35 тыс. ₽"
    if "соц" in normalized or "контент" in normalized:
        return "Соцсети как воронка", "от 55 тыс. ₽/мес"
    return "Диагностика и roadmap + следующий пилот", "5–10 тыс. ₽ за диагностику, далее по согласованному объему"


def build_proposal_prompt(
    company_data: Mapping,
    consultation_data: Mapping,
    crm_context: Mapping | None = None,
    extra_data: Mapping | None = None,
) -> str:
    crm_context = crm_context or {}
    extra_data = extra_data or {}
    return f"""
Ты senior sales strategist агентства ШАРиК digital.
Подготовь предварительное предложение для стоматологической клиники после консультации.

Ограничения:
- используй только бренд ШАРиК digital;
- не упоминай SPG;
- не продавай внутреннюю связку из 5 ботов как готовый продукт;
- цены указывай как предварительный ориентир;
- не обещай гарантированный результат;
- не придумывай кейсы, цифры, подтвержденные боли или техданные, если их нет в CRM и заметках;
- если чего-то не хватает, пиши, что это нужно уточнить перед финальным КП.

Данные компании:
{_json_block(company_data)}

CRM consultation context:
{_json_block(crm_context)}

Текущая консультация и аудит:
{_json_block(consultation_data)}

Дополнительные заметки и материалы:
{_json_block(extra_data)}

Текущий прайс-ориентир ШАРиК digital:
{pricing_defaults_text()}

Верни markdown строго с разделами:

# Краткий вывод

# Главная проблема клиента

# Предлагаемое решение

# Рекомендуемый пакет

# Что входит

# План внедрения

# Бюджетный ориентир

# Что нужно уточнить перед финальным КП

# Следующий шаг
""".strip()


def build_fallback_proposal_text(
    company_data: Mapping,
    consultation_data: Mapping,
    crm_context: Mapping | None = None,
) -> str:
    crm_context = crm_context or {}
    source_text = " ".join(
        str(value or "")
        for value in (
            consultation_data.get("main_problems"),
            consultation_data.get("growth_points"),
            consultation_data.get("recommendations"),
            consultation_data.get("roadmap_30_days"),
            consultation_data.get("sales_context"),
            crm_context.get("sales_summary"),
        )
    )
    package_name, budget = choose_proposal_defaults(source_text)
    company_name = _value(company_data, "name")
    main_problem = consultation_data.get("main_problems") or crm_context.get("sales_summary") or "Нужно уточнить главную точку потери заявок."
    solution = consultation_data.get("recommendations") or consultation_data.get("growth_points") or "Сначала провести диагностику, затем собрать короткий план внедрения."
    next_step = consultation_data.get("next_step") or crm_context.get("recommended_next_step") or "Согласовать следующий созвон и объем пилотных работ."
    return "\n".join(
        [
            "# Краткий вывод",
            f"{company_name} уже готова обсуждать улучшение digital-воронки, но итоговый объем работ лучше подтверждать после сверки процессов записи, сайта и текущих каналов привлечения.",
            "",
            "# Главная проблема клиента",
            str(main_problem),
            "",
            "# Предлагаемое решение",
            str(solution),
            "",
            "# Рекомендуемый пакет",
            package_name,
            "",
            "# Что входит",
            "- Диагностика текущей digital-воронки и точки потери заявок.",
            "- Приоритизация быстрых улучшений на основе консультации и CRM-контекста.",
            "- Подготовка следующего этапа работ без обещаний неподтвержденного результата.",
            "",
            "# План внедрения",
            "- 7 дней: подтвердить текущую ситуацию, собрать материалы, зафиксировать быстрые правки.",
            "- 30 дней: запустить первый согласованный блок улучшений и измерения.",
            "- 90 дней: расширить рабочие каналы и закрепить процесс регулярного follow-up.",
            "",
            "# Бюджетный ориентир",
            f"{budget}. Это предварительный ориентир, финальная стоимость зависит от объема работ и подтвержденных задач.",
            "",
            "# Что нужно уточнить перед финальным КП",
            "- Какие каналы сейчас дают заявки и какие из них приоритетны.",
            "- Кто внутри клиники отвечает за контент, скорость ответа и обработку обращений.",
            "- Какие материалы, доступы и ограничения есть по сайту, картам и CRM.",
            "",
            "# Следующий шаг",
            str(next_step),
        ]
    )
