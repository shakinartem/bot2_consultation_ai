from dataclasses import dataclass, field


CONSULTATION_READY_STATUS = "consultation_scheduled"


@dataclass(slots=True)
class Company:
    id: int
    name: str
    status: str
    niche: str
    city: str
    website: str | None = None
    maps_url: str | None = None
    social_links: list[str] = field(default_factory=list)
    reputation_notes: str | None = None


class CRMService:
    """CRM adapter placeholder.

    Replace in-memory data with a real CRM client when bot #1 exposes an API.
    """

    def __init__(self) -> None:
        self._companies: dict[int, Company] = {
            101: Company(
                id=101,
                name="Студия красоты Линия",
                status=CONSULTATION_READY_STATUS,
                niche="beauty",
                city="Саратов",
                website="https://example-beauty.ru",
                maps_url="https://yandex.ru/maps/",
                social_links=["https://vk.com/example_beauty"],
                reputation_notes="Есть отзывы, но ответы нерегулярные.",
            ),
            102: Company(
                id=102,
                name="Стоматология Улыбка",
                status=CONSULTATION_READY_STATUS,
                niche="medical",
                city="Энгельс",
                website=None,
                maps_url="https://2gis.ru/",
                social_links=[],
                reputation_notes="Высокая конкуренция по району.",
            ),
        }

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


crm_service = CRMService()
