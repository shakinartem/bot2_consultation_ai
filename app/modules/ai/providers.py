from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str) -> str:
        raise NotImplementedError


class OpenRouterProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, prompt: str) -> str:
        if not self.settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is empty")

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


class OllamaProvider(AIProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def generate(self, prompt: str) -> str:
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


class FallbackProvider(AIProvider):
    async def generate(self, prompt: str) -> str:
        return (
            "1. Общий вывод\n"
            "Клиент готов к консультации: есть базовые точки контакта, но нужно собрать "
            "их в понятную воронку и усилить доверие.\n\n"
            "2. Аудит сайта\n"
            "- Проверить наличие быстрых CTA: запись, звонок, мессенджер.\n"
            "- Уточнить, есть ли отдельные страницы под ключевые услуги.\n"
            "- Добавить блоки доверия: кейсы, отзывы, команда, гарантии.\n\n"
            "3. Аудит карт\n"
            "- Заполнить карточки на Яндекс/2ГИС/Google максимально полно.\n"
            "- Добавить свежие фото, услуги, цены и ответы на отзывы.\n"
            "- Отследить позиции по коммерческим запросам в районе.\n\n"
            "4. Аудит соцсетей\n"
            "- Сделать понятную шапку профиля и закрепы.\n"
            "- Публиковать экспертный, продающий и репутационный контент.\n"
            "- Вести пользователя к записи, а не только к просмотрам.\n\n"
            "5. Репутация\n"
            "- Наладить регулярный сбор отзывов после оказания услуги.\n"
            "- Отвечать на негатив быстро и публично.\n"
            "- Использовать отзывы на сайте и в соцсетях.\n\n"
            "6. Основные проблемы\n"
            "- Нет единой системы привлечения и прогрева.\n"
            "- Недостаточно измеримости заявок.\n"
            "- Слабая упаковка преимуществ.\n\n"
            "7. Точки роста\n"
            "- Упаковка оффера под целевые сегменты.\n"
            "- Карты как быстрый источник теплых заявок.\n"
            "- Контент, который закрывает страхи и возражения.\n\n"
            "8. Быстрые улучшения\n"
            "- Добавить кнопки записи во все каналы.\n"
            "- Собрать 10-15 свежих отзывов.\n"
            "- Обновить фото и описание услуг на картах.\n\n"
            "9. План на 7 дней\n"
            "- Собрать доступы и аналитику.\n"
            "- Проверить сайт, карты, соцсети и репутацию.\n"
            "- Исправить критичные CTA и контакты.\n\n"
            "10. План на 30 дней\n"
            "- Запустить регулярный контент и сбор отзывов.\n"
            "- Подготовить посадочные страницы/разделы услуг.\n"
            "- Настроить учет заявок из каналов.\n\n"
            "11. План на 90 дней\n"
            "- Выстроить устойчивую рекламную и контентную систему.\n"
            "- Масштабировать лучшие офферы.\n"
            "- Сравнить динамику заявок, стоимости лида и конверсий.\n\n"
            "12. Рекомендации по услугам\n"
            "- Аудит и упаковка точек контакта.\n"
            "- Ведение карт и репутации.\n"
            "- Контент-маркетинг и performance-реклама."
        )


def get_ai_provider(settings: Settings | None = None) -> AIProvider:
    settings = settings or get_settings()
    provider = settings.ai_provider.lower()
    if provider == "openrouter":
        return OpenRouterProvider(settings)
    if provider == "ollama":
        return OllamaProvider(settings)
    return FallbackProvider()
