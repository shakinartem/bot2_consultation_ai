from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings, get_settings


CONSULTATION_READY_STATUS = "consultation_scheduled"


class CRMAdapterError(RuntimeError):
    """Raised when an external CRM adapter cannot complete a request."""


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
        social_links = data.get("social_links") or data.get("socials") or []
        if isinstance(social_links, str):
            social_links = [item.strip() for item in social_links.split(",") if item.strip()]
        return cls(
            id=int(data["id"]),
            name=data.get("name") or data.get("company_name") or f"Company {data['id']}",
            status=data.get("status") or CONSULTATION_READY_STATUS,
            niche=data.get("niche") or "dentistry",
            city=data.get("city") or "",
            legal_name=data.get("legal_name"),
            address=data.get("address"),
            phone=data.get("phone"),
            website=data.get("website"),
            maps_url=data.get("maps_url"),
            social_links=list(social_links),
            rating=float(data["rating"]) if data.get("rating") not in (None, "") else None,
            reviews_count=int(data["reviews_count"]) if data.get("reviews_count") not in (None, "") else None,
            reputation_notes=data.get("reputation_notes"),
            crm_notes=data.get("crm_notes") or data.get("notes"),
            pain=data.get("pain"),
            cold_call_result=data.get("cold_call_result"),
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


class MockCRMAdapter(CRMAdapter):
    def __init__(self) -> None:
        self._companies: dict[int, Company] = {
            101: Company(
                id=101,
                name="Стоматология Улыбка",
                legal_name='ООО "Улыбка"',
                status=CONSULTATION_READY_STATUS,
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
                status=CONSULTATION_READY_STATUS,
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
        return [
            company
            for company in self._companies.values()
            if company.status == CONSULTATION_READY_STATUS
        ]

    async def get_company(self, company_id: int) -> Company | None:
        return self._companies.get(company_id)

    async def update_company_status(self, company_id: int, status: str) -> None:
        company = self._companies.get(company_id)
        if company is not None:
            company.status = status

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
                "type": type,
                "result": result,
                "notes": notes,
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
        self.tasks.append(
            {
                "company_id": company_id,
                "title": title,
                "due_at": due_at.isoformat() if due_at else None,
                "notes": notes,
            }
        )


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
                response.raise_for_status()
                if response.content:
                    return response.json()
                return None
        except (httpx.HTTPError, ValueError) as exc:
            raise CRMAdapterError(f"CRM API недоступна или вернула ошибку: {exc}") from exc

    async def list_consultation_scheduled(self) -> list[Company]:
        data = await self._request("GET", "/api/companies", params={"status": CONSULTATION_READY_STATUS})
        items = data.get("items", data) if isinstance(data, dict) else data
        return [Company.from_mapping(item) for item in items or []]

    async def get_company(self, company_id: int) -> Company | None:
        try:
            data = await self._request("GET", f"/api/companies/{company_id}")
        except CRMAdapterError:
            raise
        if not data:
            return None
        return Company.from_mapping(data)

    async def update_company_status(self, company_id: int, status: str) -> None:
        await self._request("PATCH", f"/api/companies/{company_id}/status", json={"status": status})

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
            json={"type": type, "result": result, "notes": notes},
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
            f"/api/companies/{company_id}/tasks",
            json={"title": title, "due_at": due_at.isoformat() if due_at else None, "notes": notes},
        )


class SharedSQLiteCRMAdapter(CRMAdapter):
    """Best-effort adapter for a future shared SQLite database from BOT 1.

    It assumes a simple `companies` table. If the database/table is missing, it
    returns empty results instead of breaking BOT 2.
    """

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
                        "SELECT id, name, legal_name, status, niche, city, address, phone, "
                        "website, maps_url, social_links, rating, reviews_count, "
                        "reputation_notes, notes AS crm_notes, pain, cold_call_result "
                        f"FROM companies {where}"
                    ),
                    params,
                )
                return [Company.from_mapping(dict(row._mapping)) for row in result]
        except Exception:
            return []

    async def list_consultation_scheduled(self) -> list[Company]:
        return await self._fetch_companies("WHERE status = :status", {"status": CONSULTATION_READY_STATUS})

    async def get_company(self, company_id: int) -> Company | None:
        companies = await self._fetch_companies("WHERE id = :company_id", {"company_id": company_id})
        return companies[0] if companies else None

    async def update_company_status(self, company_id: int, status: str) -> None:
        if not self._sqlite_path_exists():
            return
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text("UPDATE companies SET status = :status WHERE id = :company_id"),
                    {"company_id": company_id, "status": status},
                )
        except Exception:
            return

    async def add_interaction(
        self,
        company_id: int,
        type: str,
        result: str,
        notes: str | None = None,
    ) -> None:
        if not self._sqlite_path_exists():
            return
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO interactions (company_id, type, result, notes, created_at) "
                        "VALUES (:company_id, :type, :result, :notes, CURRENT_TIMESTAMP)"
                    ),
                    {"company_id": company_id, "type": type, "result": result, "notes": notes},
                )
        except Exception:
            return

    async def create_task(
        self,
        company_id: int,
        title: str,
        due_at: datetime | None = None,
        notes: str | None = None,
    ) -> None:
        if not self._sqlite_path_exists():
            return
        try:
            async with self.engine.begin() as conn:
                await conn.execute(
                    text(
                        "INSERT INTO tasks (company_id, title, due_at, notes, created_at) "
                        "VALUES (:company_id, :title, :due_at, :notes, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "company_id": company_id,
                        "title": title,
                        "due_at": due_at.isoformat() if due_at else None,
                        "notes": notes,
                    },
                )
        except Exception:
            return


def get_crm_adapter(settings: Settings | None = None) -> CRMAdapter:
    settings = settings or get_settings()
    adapter = settings.crm_adapter.lower()
    if adapter in {"mock", "in_memory", "memory"}:
        return MockCRMAdapter()
    if adapter == "http_api":
        return HTTPCRMAdapter(settings)
    if adapter == "sqlite_shared":
        return SharedSQLiteCRMAdapter(settings)
    return MockCRMAdapter()


crm_service = get_crm_adapter()
