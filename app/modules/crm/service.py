from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
import logging
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


DEFAULT_READY_STATUSES = ("consultation_planned", "consultation_scheduled")
PREFERRED_BOT1_READY_STATUS = "consultation_planned"

BOT2_TO_BOT1_STATUS_MAP = {
    "client": "deal_won",
    "signed": "deal_won",
    "contract_sent": "proposal_sent",
    "thinking": "interested",
    "refused": "deal_lost",
}

BOT2_TO_BOT1_INTERACTION_RESULT_MAP = {
    "refused": "rejected",
    "thinking": "interested",
    "contract_sent": "proposal_requested",
    "client": "deal_won",
    "signed": "deal_won",
}

FOLLOW_UP_RULES = {
    "thinking": {"title": "Повторно связаться после консультации", "days": 3},
    "contract_sent": {"title": "Проверить статус договора", "days": 2},
}

BOT1_STATUS_VALUES = {
    "new",
    "research_needed",
    "prepared",
    "call_planned",
    "called",
    "no_answer",
    "interested",
    "consultation_planned",
    "proposal_sent",
    "deal_won",
    "deal_lost",
    "do_not_contact",
}

BOT1_INTERACTION_RESULT_VALUES = {
    "no_answer",
    "rejected",
    "interested",
    "callback_requested",
    "consultation_booked",
    "proposal_requested",
    "deal_won",
    "deal_lost",
    "other",
}


class CRMAdapterError(RuntimeError):
    """Raised when an external CRM adapter cannot complete a request."""


class CRMHTTPError(CRMAdapterError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def parse_ready_statuses(raw: str | None) -> list[str]:
    if raw is None:
        return list(DEFAULT_READY_STATUSES)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or list(DEFAULT_READY_STATUSES)


def get_ready_statuses(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    return parse_ready_statuses(settings.crm_ready_statuses)


def get_primary_ready_status(settings: Settings | None = None) -> str:
    ready_statuses = get_ready_statuses(settings)
    if PREFERRED_BOT1_READY_STATUS in ready_statuses:
        return PREFERRED_BOT1_READY_STATUS
    return ready_statuses[0]


def map_bot2_status_to_bot1(status: str) -> str:
    return BOT2_TO_BOT1_STATUS_MAP.get(status, status)


def map_bot2_interaction_result(result: str) -> str:
    if result in BOT1_INTERACTION_RESULT_VALUES:
        return result
    return BOT2_TO_BOT1_INTERACTION_RESULT_MAP.get(result, "other")


def build_consultation_result_payload(result: str, summary: str, source: str = "bot2") -> dict[str, str]:
    return {"result": result, "summary": summary, "source": source}


def build_bot1_interaction_payload(
    result: str,
    summary: str | None,
    *,
    created_by: str = "bot2",
) -> dict[str, str | None]:
    return {
        "type": "consultation",
        "result": map_bot2_interaction_result(result),
        "summary": summary,
        "created_by": created_by,
    }


def build_bot1_task_payload(
    company_id: int,
    title: str,
    due_at: datetime | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return {
        "company_id": company_id,
        "title": title,
        "description": notes,
        "due_at": due_at.isoformat() if due_at else None,
    }


def get_follow_up_task_payload(result: str, notes: str | None = None) -> dict[str, Any] | None:
    rule = FOLLOW_UP_RULES.get(result)
    if not rule:
        return None
    due_at = datetime.utcnow() + timedelta(days=rule["days"])
    return {"title": rule["title"], "due_at": due_at, "notes": notes}


def _split_links(value: str) -> list[str]:
    normalized = value.replace("\r", "\n").replace(";", "\n").replace(",", "\n")
    return [item.strip() for item in normalized.splitlines() if item.strip()]


def _append_unique(target: list[str], value: str | None) -> None:
    if not value:
        return
    for item in _split_links(value):
        if item not in target:
            target.append(item)


def collect_social_links(data: dict[str, Any]) -> list[str]:
    items: list[str] = []
    raw_social_links = data.get("social_links") or data.get("socials")
    if isinstance(raw_social_links, list):
        for value in raw_social_links:
            if value:
                _append_unique(items, str(value))
    elif isinstance(raw_social_links, str):
        _append_unique(items, raw_social_links)

    for key in ("vk_url", "instagram_url", "telegram_url", "other_socials"):
        _append_unique(items, data.get(key))
    return items


@dataclass(slots=True)
class Company:
    id: int
    name: str
    status: str
    niche: str
    city: str
    legal_name: str | None = None
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    maps_url: str | None = None
    social_links: list[str] = field(default_factory=list)
    rating: float | None = None
    reviews_count: int | None = None
    reputation_notes: str | None = None
    crm_notes: str | None = None
    pain: str | None = None
    cold_call_result: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> Company:
        notes = data.get("crm_notes") or data.get("notes")
        return cls(
            id=int(data["id"]),
            name=data.get("name") or data.get("company_name") or f"Company {data['id']}",
            status=data.get("status") or get_primary_ready_status(),
            niche=data.get("niche") or "dentistry",
            city=data.get("city") or "",
            legal_name=data.get("legal_name"),
            address=data.get("address"),
            phone=data.get("phone"),
            website=data.get("website"),
            maps_url=data.get("maps_url"),
            social_links=collect_social_links(data),
            rating=float(data["rating"]) if data.get("rating") not in (None, "") else None,
            reviews_count=int(data["reviews_count"]) if data.get("reviews_count") not in (None, "") else None,
            reputation_notes=data.get("reputation_notes"),
            crm_notes=notes,
            pain=data.get("pain") or notes,
            cold_call_result=data.get("cold_call_result") or notes,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CRMAdapter(ABC):
    @abstractmethod
    async def list_consultation_scheduled(self) -> list[Company]:
        raise NotImplementedError

    @abstractmethod
    async def get_company(self, company_id: int) -> Company | None:
        raise NotImplementedError

    @abstractmethod
    async def update_company_status(self, company_id: int, status: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        raise NotImplementedError

    async def send_consultation_result(self, company_id: int, result: str, notes: str | None = None) -> None:
        await self.update_company_status(company_id, result)
        await self.add_interaction(company_id, type="consultation", result=result, notes=notes)
        task_payload = get_follow_up_task_payload(result, notes)
        if task_payload:
            await self.create_task(
                company_id,
                title=task_payload["title"],
                due_at=task_payload["due_at"],
                notes=task_payload["notes"],
            )


class MockCRMAdapter(CRMAdapter):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._companies: dict[int, Company] = {
            101: Company(
                id=101,
                name="Стоматология Улыбка",
                legal_name='ООО "Улыбка"',
                status="consultation_scheduled",
                niche="dentistry",
                city="Саратов",
                address="ул. Московская, 12",
                phone="+7 8452 111-222",
                website="https://example-smile.ru",
                maps_url="https://yandex.ru/maps/org/example",
                social_links=["https://vk.com/example_smile", "https://t.me/example_smile"],
                rating=4.4,
                reviews_count=86,
                reputation_notes="Отзывы есть, но клиника редко отвечает на негатив и вопросы пациентов.",
                crm_notes="После холодного звонка владелец попросил показать, где теряются заявки.",
                pain="Мало первичных записей на имплантацию и ортодонтию.",
                cold_call_result="Готовы обсудить карты, сайт и репутацию.",
            ),
            102: Company(
                id=102,
                name="Dental Family",
                legal_name='ООО "Дентал Фэмили"',
                status="consultation_scheduled",
                niche="dentistry",
                city="Энгельс",
                address="пр-т Строителей, 44",
                phone="+7 8453 333-444",
                website=None,
                maps_url="https://2gis.ru/saratov/firm/example",
                social_links=["https://vk.com/dental_family_demo"],
                rating=4.1,
                reviews_count=39,
                reputation_notes="Карточка 2ГИС заполнена неполно, свежих фото мало.",
                crm_notes="Администратор говорит, что звонки есть, но запись нестабильная.",
                pain="Нужно понять, почему пациенты выбирают конкурентов рядом.",
                cold_call_result="Назначена консультация с управляющей.",
            ),
        }
        self.interactions: list[dict[str, Any]] = []
        self.tasks: list[dict[str, Any]] = []

    async def list_consultation_scheduled(self) -> list[Company]:
        ready_statuses = set(get_ready_statuses(self.settings))
        return [
            company
            for company in self._companies.values()
            if company.status in ready_statuses
        ]

    async def get_company(self, company_id: int) -> Company | None:
        return self._companies.get(company_id)

    async def update_company_status(self, company_id: int, status: str) -> None:
        company = self._companies.get(company_id)
        if company is not None:
            company.status = map_bot2_status_to_bot1(status)

    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        self.interactions.append(
            {
                "company_id": company_id,
                **build_bot1_interaction_payload(result, notes),
                "created_at": datetime.utcnow().isoformat(),
            }
        )

    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        self.tasks.append(build_bot1_task_payload(company_id, title, due_at, notes))


class HTTPCRMAdapter(CRMAdapter):
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.base_url = self.settings.crm_api_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.settings.crm_api_token:
            return {}
        return {"Authorization": f"Bearer {self.settings.crm_api_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers(),
                    **kwargs,
                )
        except httpx.HTTPError as exc:
            logger.warning("CRM API request failed: %s %s: %s", method, path, exc)
            raise CRMAdapterError(f"CRM API недоступна или вернула ошибку: {exc}") from exc

        if response.is_error:
            logger.warning("CRM API request failed: %s %s -> %s", method, path, response.status_code)
            raise CRMHTTPError(
                f"CRM API вернула ошибку {response.status_code} для {method} {path}",
                status_code=response.status_code,
            )

        if not response.content:
            return None

        try:
            return response.json()
        except ValueError as exc:
            logger.warning("CRM API returned invalid JSON: %s %s: %s", method, path, exc)
            raise CRMAdapterError(f"CRM API вернула некорректный JSON: {exc}") from exc

    @staticmethod
    def _normalize_items(data: Any) -> list[dict[str, Any]]:
        if isinstance(data, dict):
            items = data.get("items", [])
        else:
            items = data or []
        return [item for item in items if isinstance(item, dict)]

    @staticmethod
    def _should_fallback_to_legacy(exc: CRMAdapterError) -> bool:
        if isinstance(exc, CRMHTTPError):
            return exc.status_code == 404 or exc.status_code >= 500
        return True

    async def list_consultation_scheduled(self) -> list[Company]:
        try:
            data = await self._request("GET", "/api/bot2/consultation-ready")
            return [Company.from_mapping(item) for item in self._normalize_items(data)]
        except CRMAdapterError as exc:
            if not self._should_fallback_to_legacy(exc):
                raise
            logger.info("Falling back to legacy CRM list endpoint after bot2 handoff list failure: %s", exc)

        fallback_status = get_primary_ready_status(self.settings)
        data = await self._request(
            "GET",
            "/api/companies",
            params={"status": fallback_status, "limit": 100},
        )
        return [Company.from_mapping(item) for item in self._normalize_items(data)]

    async def get_company(self, company_id: int) -> Company | None:
        try:
            data = await self._request("GET", f"/api/companies/{company_id}")
        except CRMHTTPError as exc:
            if exc.status_code == 404:
                return None
            raise
        if not data:
            return None
        return Company.from_mapping(data)

    async def update_company_status(self, company_id: int, status: str) -> None:
        await self._request(
            "PATCH",
            f"/api/companies/{company_id}",
            json={"status": map_bot2_status_to_bot1(status)},
        )

    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        await self._request(
            "POST",
            f"/api/companies/{company_id}/interactions",
            json=build_bot1_interaction_payload(result, notes),
        )

    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        await self._request(
            "POST",
            "/api/tasks",
            json=build_bot1_task_payload(company_id, title, due_at, notes),
        )

    async def send_consultation_result(self, company_id: int, result: str, notes: str | None = None) -> None:
        summary = notes or result
        try:
            await self._request(
                "POST",
                f"/api/bot2/companies/{company_id}/consultation-result",
                json=build_consultation_result_payload(result, summary),
            )
            return
        except CRMAdapterError as exc:
            if not self._should_fallback_to_legacy(exc):
                raise
            logger.info("Falling back to legacy CRM consultation result flow: %s", exc)

        await super().send_consultation_result(company_id, result, notes)


class SharedSQLiteCRMAdapter(CRMAdapter):
    """Best-effort adapter for a shared SQLite database from BOT 1."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.database_url = self.settings.crm_shared_database_url
        self.engine = create_async_engine(self.database_url, echo=False)

    def _sqlite_path_exists(self) -> bool:
        if not self.database_url.startswith("sqlite"):
            return True
        raw_path = self.database_url.split(":///", 1)[-1]
        if raw_path.startswith("/") and ":" in raw_path[:4]:
            raw_path = raw_path.lstrip("/")
        if not raw_path or raw_path in (":memory:", "/:memory:"):
            return True
        return Path(raw_path).exists()

    async def _fetch_companies(self, where: str, params: dict[str, Any]) -> list[Company]:
        if not self._sqlite_path_exists():
            return []
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT id, name, legal_name, status, city, region, address, phone, "
                        "website, social_links, maps_url, vk_url, instagram_url, telegram_url, "
                        "other_socials, rating, reviews_count, notes "
                        f"FROM companies {where}"
                    ),
                    params,
                )
                return [Company.from_mapping(dict(row._mapping)) for row in result]
        except Exception as exc:
            logger.warning("Shared SQLite CRM read failed: %s", exc)
            return []

    async def list_consultation_scheduled(self) -> list[Company]:
        statuses = get_ready_statuses(self.settings)
        placeholders = ", ".join(f":status_{index}" for index in range(len(statuses)))
        params = {f"status_{index}": value for index, value in enumerate(statuses)}
        return await self._fetch_companies(f"WHERE status IN ({placeholders})", params)

    async def get_company(self, company_id: int) -> Company | None:
        companies = await self._fetch_companies("WHERE id = :company_id", {"company_id": company_id})
        return companies[0] if companies else None

    async def update_company_status(self, company_id: int, status: str) -> None:
        if not self._sqlite_path_exists():
            raise CRMAdapterError("Shared SQLite CRM database not found")
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text("UPDATE companies SET status = :status WHERE id = :company_id"),
                    {"company_id": company_id, "status": map_bot2_status_to_bot1(status)},
                )
        except Exception as exc:
            logger.warning("Shared SQLite CRM status update failed: %s", exc)
            raise CRMAdapterError(f"Shared SQLite CRM status update failed: {exc}") from exc

    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        if not self._sqlite_path_exists():
            raise CRMAdapterError("Shared SQLite CRM database not found")
        payload = build_bot1_interaction_payload(result, notes)
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO lead_interactions "
                        "(company_id, type, result, summary, created_by, created_at) "
                        "VALUES (:company_id, :type, :result, :summary, :created_by, CURRENT_TIMESTAMP)"
                    ),
                    {"company_id": company_id, **payload},
                )
        except Exception as exc:
            logger.warning("Shared SQLite CRM interaction insert failed: %s", exc)
            raise CRMAdapterError(f"Shared SQLite CRM interaction insert failed: {exc}") from exc

    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        if not self._sqlite_path_exists():
            raise CRMAdapterError("Shared SQLite CRM database not found")
        payload = build_bot1_task_payload(company_id, title, due_at, notes)
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO tasks "
                        "(company_id, title, description, due_at, due_date, status, priority, created_at) "
                        "VALUES (:company_id, :title, :description, :due_at, :due_at, 'open', 'medium', CURRENT_TIMESTAMP)"
                    ),
                    payload,
                )
        except Exception as exc:
            logger.warning("Shared SQLite CRM task insert failed: %s", exc)
            raise CRMAdapterError(f"Shared SQLite CRM task insert failed: {exc}") from exc


def get_crm_adapter(settings: Settings | None = None) -> CRMAdapter:
    settings = settings or get_settings()
    adapter = settings.crm_adapter.lower()
    if adapter in {"mock", "in_memory", "memory"}:
        return MockCRMAdapter(settings)
    if adapter == "http_api":
        return HTTPCRMAdapter(settings)
    if adapter == "sqlite_shared":
        return SharedSQLiteCRMAdapter(settings)
    return MockCRMAdapter(settings)


crm_service = get_crm_adapter()
