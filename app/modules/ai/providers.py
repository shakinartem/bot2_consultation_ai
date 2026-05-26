from __future__ import annotations

from abc import ABC, abstractmethod
import logging

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


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
            logger.warning("OpenRouter provider failed: %s", exc)
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
            logger.warning("Ollama provider failed: %s", exc)
            raise AIProviderError(f"Ollama error: {exc}") from exc


class FallbackProvider(AIProvider):
    async def generate(self, prompt: str) -> str:
        return """# Контекст продаж
Клиника уже дошла до этапа консультации, значит интерес к улучшению digital-воронки подтвержден. При этом часть решений еще нужно уточнить вместе с владельцем или управляющим.

# Что важно проговорить на консультации
- Как сейчас клиника получает заявки и где именно теряет часть обращений.
- Кто отвечает за обработку звонков, сообщений и повторные касания.
- Какие услуги приоритетны по марже и загрузке.
- Какие каналы уже работают, а какие вызывают сомнения.

# Общий вывод
Клиника уже имеет базовые точки контакта, но часть потенциальных пациентов теряется между картами, сайтом, соцсетями и работой администратора. Главная задача консультации — показать, как собрать эти каналы в понятную систему доверия и записи.

# Аудит сайта
- Проверить, видны ли с первого экрана телефон, мессенджеры и запись.
- Разделить ключевые услуги стоматологии по понятным сценариям пациента.
- Добавить сильные элементы доверия: врачи, лицензии, фото, отзывы, диапазоны цен.

# Аудит карт
- Заполнить карточки карт: услуги, фото, режим, цены, ссылки на запись.
- Регулярно отвечать на отзывы и вопросы.
- Проверить локальную видимость по ключевым поисковым сценариям.

# Аудит соцсетей
- Сделать соцсети каналом записи, а не только просмотра.
- Упаковать профиль, офферы и контент вокруг доверия.
- Добавить ссылки и понятный следующий шаг после просмотра контента.

# Репутация
- Вести регулярный сбор и обработку отзывов.
- Использовать лучшие отзывы в других digital-каналах.
- Назначить ответственного за репутацию и ответы.

# Основные проблемы
- Нет прозрачного пути пациента от первого касания до записи.
- Карты и отзывы используются не в полную силу.
- Нет единой системы повторных касаний после первичного интереса.

# Точки роста
- Упаковать высокомаржинальные услуги через отдельные посадочные и карточки услуг.
- Усилить карты как локальный канал привлечения.
- Построить контент и репутацию вокруг доверия к клинике и врачам.

# Быстрые улучшения
- Обновить CTA на сайте и в соцсетях.
- Добавить свежие фото клиники и врачей.
- Собрать первые свежие отзывы по понятному сценарию.
- Проверить скорость ответа администратора на типовые вопросы.

# План на 7 дней
- Собрать доступы, ссылки и текущие материалы.
- Проверить критичные точки записи и доверия.
- Исправить самые заметные контактные и репутационные потери.

# План на 30 дней
- Оформить основные страницы услуг и ключевые точки конверсии.
- Запустить регулярный сбор отзывов и ответы на отзывы.
- Подготовить контент-план доверия и повторных касаний.

# План на 90 дней
- Собрать устойчивую систему: карты, сайт, контент, репутация, процесс обработки лидов.
- Расширить работающие каналы без обещаний неподтвержденного результата.
- Сравнивать динамику заявок, записи и доходимости.

# Рекомендации по услугам ШАРиК digital
- Диагностика и roadmap digital-воронки.
- Упаковка карт и репутации.
- Посадочные страницы под ключевые услуги.
- Контент и повторные касания для прогрева пациентов.

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
