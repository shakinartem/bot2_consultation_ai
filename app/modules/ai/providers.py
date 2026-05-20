from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings


class AIProviderError(RuntimeError):
    pass


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError


class OpenRouterProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, prompt: str) -> str:
        if not self.settings.openrouter_api_key:
            raise AIProviderError("OPENROUTER_API_KEY is empty")

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.settings.openrouter_model,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
            raise AIProviderError(f"OpenRouter error: {exc}") from exc


class OllamaProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, prompt: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    f"{self.settings.ollama_base_url}/api/generate",
                    json={
                        "model": self.settings.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                return response.json()["response"]
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise AIProviderError(f"Ollama error: {exc}") from exc


class FallbackProvider(AIProvider):
    async def generate(self, prompt: str) -> str:
        return """# Общий вывод
Клиника уже имеет базовые точки контакта, но часть потенциальных пациентов теряется между картами, сайтом, соцсетями и работой администратора. Главная задача консультации — показать владельцу, как собрать эти каналы в понятную систему доверия и записи.

# Аудит сайта
- Проверить, видны ли с первого экрана телефон, мессенджер и запись на консультацию.
- Разделить ключевые услуги стоматологии: имплантация, ортодонтия, терапия, гигиена, детский прием.
- Добавить доказательства доверия: врачи, лицензии, фото клиники, кейсы, отзывы и понятные цены/диапазоны.
- Убедиться, что заявки с сайта фиксируются и передаются администратору без ручной потери.

# Аудит карт
- Карточки Яндекс/2ГИС должны быть заполнены: услуги, фото, режим, врачи, цены, ссылки на запись.
- Важно регулярно отвечать на отзывы, особенно на негатив и вопросы о цене/качестве лечения.
- Проверить, по каким запросам клиника видна рядом с конкурентами: "стоматология рядом", "имплантация", "лечение зубов".

# Аудит соцсетей
- Шапка профиля должна быстро объяснять специализацию, район, способ записи и сильное отличие клиники.
- Контент стоит строить вокруг доверия: врачи, разборы страхов пациентов, до/после без нарушений, отзывы, процессы.
- Соцсети должны вести к записи, а не только к просмотрам: кнопки, ссылки, закрепы, понятные офферы.

# Репутация
- Для стоматологии рейтинг и свежесть отзывов напрямую влияют на выбор пациента.
- Нужен регламент: кто просит отзыв, когда просит, как реагирует на негатив, где использует хорошие отзывы.
- Отзывы с карт можно переупаковать в сайт, соцсети и скрипты администраторов.

# Основные проблемы
- Недостаточно прозрачный путь пациента от первого касания до записи.
- Карты и отзывы используются как справочник, а не как источник теплых заявок.
- Нет единой системы повторных касаний после звонка, сообщения или просмотра страницы.

# Точки роста
- Упаковка высокомаржинальных услуг через отдельные посадочные страницы и карточки услуг.
- Усиление карт как главного локального канала привлечения.
- Регулярная работа с репутацией и контентом, который снижает страх перед лечением.

# Быстрые улучшения
- Обновить CTA на сайте и во всех соцсетях: запись, телефон, WhatsApp/Telegram.
- Добавить свежие фото клиники, врачей и кабинетов в карты.
- Собрать первые 10-15 свежих отзывов по понятному сценарию.
- Проверить, как администратор отвечает на типовые вопросы о цене и записи.

# План на 7 дней
- Собрать доступы, ссылки, текущие заявки и данные по звонкам.
- Проверить сайт, карты, соцсети и отзывы по чек-листу.
- Исправить критичные контакты, кнопки записи и устаревшую информацию.

# План на 30 дней
- Оформить карточки услуг и основные посадочные страницы.
- Запустить регулярный сбор отзывов и ответы на отзывы.
- Подготовить контент-план доверия для соцсетей и повторных касаний.
- Ввести учет источников заявок и статусов администраторов.

# План на 90 дней
- Выстроить устойчивую систему: карты, сайт, контент, репутация, реклама, администраторы.
- Масштабировать услуги с лучшей маржинальностью и конверсией.
- Сравнивать динамику заявок, стоимости лида, записи и дошедших пациентов.

# Рекомендации по услугам ШАРиК digital
- Аудит и упаковка digital-точек контакта стоматологии.
- Ведение карт и репутации.
- Посадочные страницы под ключевые стоматологические услуги.
- Контент и повторные касания для прогрева пациентов.
- Настройка учета заявок и консультационная поддержка администраторов.

# Следующий шаг
На консультации согласовать 2-3 приоритетных направления, которые быстрее всего вернут заявки: карты, репутация и путь записи с сайта/соцсетей."""


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    provider = settings.ai_provider.lower()
    if provider == "openrouter":
        return OpenRouterProvider(settings)
    if provider == "ollama":
        return OllamaProvider(settings)
    return FallbackProvider()
