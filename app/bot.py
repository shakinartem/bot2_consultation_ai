from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from aiogram.client.default import DefaultBotProperties

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.modules.consultation.models import Consultation
from app.modules.consultation.service import ConsultationService
from app.modules.crm.service import Company, crm_service
from app.modules.documents.generator import generate_consultation_docx
from app.modules.files.storage import company_storage_dir


router = Router()


class ConsultationStates(StatesGroup):
    waiting_company_id = State()
    waiting_note = State()
    waiting_link = State()
    waiting_material = State()


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Клиенты на консультацию"), KeyboardButton(text="Открыть карточку")],
        [KeyboardButton(text="Добавить заметки"), KeyboardButton(text="Добавить ссылки")],
        [KeyboardButton(text="Добавить материалы"), KeyboardButton(text="Сгенерировать аудит")],
        [KeyboardButton(text="Сгенерировать DOCX"), KeyboardButton(text="Указать результат консультации")],
        [KeyboardButton(text="Архив консультаций"), KeyboardButton(text="Настройки AI")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def company_keyboard(companies: list[Company]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=f"{company.name} | {company.city}", callback_data=f"company:{company.id}")]
        for company in companies
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def consultation_keyboard(consultation: Consultation) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Аудит", callback_data=f"audit:{consultation.id}"),
                InlineKeyboardButton(text="DOCX", callback_data=f"docx:{consultation.id}"),
            ],
            [
                InlineKeyboardButton(text="Заметка", callback_data=f"note:{consultation.id}"),
                InlineKeyboardButton(text="Ссылка", callback_data=f"link:{consultation.id}"),
                InlineKeyboardButton(text="Материал", callback_data=f"material:{consultation.id}"),
            ],
            [InlineKeyboardButton(text="Результат", callback_data=f"result_menu:{consultation.id}")],
        ]
    )


def result_keyboard(consultation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отказ", callback_data=f"result:{consultation_id}:refused")],
            [InlineKeyboardButton(text="Думает", callback_data=f"result:{consultation_id}:thinking")],
            [InlineKeyboardButton(text="Договор отправлен", callback_data=f"result:{consultation_id}:contract_sent")],
            [InlineKeyboardButton(text="Договор подписан", callback_data=f"result:{consultation_id}:signed")],
        ]
    )


def is_allowed(user_id: int) -> bool:
    admins = get_settings().admin_id_set
    return not admins or user_id in admins


async def _guard(message: Message) -> bool:
    if message.from_user and is_allowed(message.from_user.id):
        return True
    await message.answer("Доступ ограничен.")
    return False


def _company_card(company: Company, consultation: Consultation) -> str:
    social = ", ".join(company.social_links) or "нет данных"
    return (
        f"<b>{company.name}</b>\n"
        f"ID компании: <code>{company.id}</code>\n"
        f"Консультация: <code>{consultation.id}</code>\n"
        f"Статус консультации: <b>{consultation.status}</b>\n\n"
        f"Ниша: {company.niche}\n"
        f"Город: {company.city}\n"
        f"Сайт: {company.website or 'нет данных'}\n"
        f"Карты: {company.maps_url or 'нет данных'}\n"
        f"Соцсети: {social}\n"
        f"Репутация: {company.reputation_notes or 'нет данных'}"
    )


async def _open_company(message: Message, company_id: int) -> None:
    company = await crm_service.get_company(company_id)
    if company is None:
        await message.answer("Компания не найдена в CRM.")
        return
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get_or_create_for_company(company_id)
        await message.answer(
            _company_card(company, consultation),
            reply_markup=consultation_keyboard(consultation),
        )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer(
        "Consultation AI System для ШАРиК digital готов. Выберите действие.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "Клиенты на консультацию")
async def list_clients(message: Message) -> None:
    if not await _guard(message):
        return
    companies = await crm_service.list_consultation_scheduled()
    if not companies:
        await message.answer("Клиентов со статусом consultation_scheduled пока нет.")
        return
    await message.answer("Клиенты на консультацию:", reply_markup=company_keyboard(companies))


@router.callback_query(F.data.startswith("company:"))
async def open_company_callback(callback: CallbackQuery) -> None:
    if callback.from_user and not is_allowed(callback.from_user.id):
        await callback.answer("Доступ ограничен.", show_alert=True)
        return
    company_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _open_company(callback.message, company_id)


@router.message(F.text == "Открыть карточку")
async def ask_company_id(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    await state.set_state(ConsultationStates.waiting_company_id)
    await message.answer("Введите ID компании из CRM.")


@router.message(ConsultationStates.waiting_company_id)
async def receive_company_id(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Нужен числовой ID компании.")
        return
    await state.clear()
    await _open_company(message, int(message.text.strip()))


@router.message(F.text.in_({"Добавить заметки", "Добавить ссылки", "Добавить материалы"}))
async def ask_target_consultation(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    action_to_state = {
        "Добавить заметки": ConsultationStates.waiting_note,
        "Добавить ссылки": ConsultationStates.waiting_link,
        "Добавить материалы": ConsultationStates.waiting_material,
    }
    await state.set_state(action_to_state[message.text])
    await message.answer("Отправьте ID консультации и текст/материал. Пример: 12 заметка по клиенту")


@router.callback_query(F.data.startswith("note:"))
async def note_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(consultation_id=int(callback.data.split(":")[1]))
    await state.set_state(ConsultationStates.waiting_note)
    await callback.answer()
    await callback.message.answer("Отправьте текст заметки.")


@router.callback_query(F.data.startswith("link:"))
async def link_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(consultation_id=int(callback.data.split(":")[1]))
    await state.set_state(ConsultationStates.waiting_link)
    await callback.answer()
    await callback.message.answer("Отправьте ссылку или список ссылок.")


@router.callback_query(F.data.startswith("material:"))
async def material_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(consultation_id=int(callback.data.split(":")[1]))
    await state.set_state(ConsultationStates.waiting_material)
    await callback.answer()
    await callback.message.answer("Отправьте документ, фото или текстовое описание материала.")


async def _resolve_consultation_id(message: Message, state: FSMContext) -> tuple[int | None, str]:
    data = await state.get_data()
    text = message.text or message.caption or ""
    if data.get("consultation_id"):
        return int(data["consultation_id"]), text
    if not text:
        return None, ""
    parts = text.strip().split(maxsplit=1)
    if not parts or not parts[0].isdigit():
        return None, text
    return int(parts[0]), parts[1] if len(parts) > 1 else ""


@router.message(ConsultationStates.waiting_note)
async def receive_note(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    consultation_id, content = await _resolve_consultation_id(message, state)
    if not consultation_id or not content:
        await message.answer("Нужен ID консультации и текст заметки.")
        return
    async with AsyncSessionLocal() as session:
        await ConsultationService(session).add_note(consultation_id, content)
    await state.clear()
    await message.answer("Заметка сохранена.")


@router.message(ConsultationStates.waiting_link)
async def receive_link(message: Message, state: FSMContext) -> None:
    if not await _guard(message):
        return
    consultation_id, content = await _resolve_consultation_id(message, state)
    if not consultation_id or not content:
        await message.answer("Нужен ID консультации и ссылка.")
        return
    async with AsyncSessionLocal() as session:
        await ConsultationService(session).add_attachment(consultation_id, content, "link")
    await state.clear()
    await message.answer("Ссылка сохранена.")


@router.message(ConsultationStates.waiting_material)
async def receive_material(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await _guard(message):
        return
    consultation_id, content = await _resolve_consultation_id(message, state)
    if not consultation_id:
        await message.answer("Нужен ID консультации. Если открыли через карточку, просто отправьте материал.")
        return

    file_path = content
    attachment_type = "text"
    if message.document:
        attachment_type = "document"
    elif message.photo:
        attachment_type = "photo"

    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(consultation_id)
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return
        if message.document:
            file = await bot.get_file(message.document.file_id)
            target_dir = company_storage_dir(consultation.company_id)
            file_path = str(target_dir / message.document.file_name)
            await bot.download_file(file.file_path, destination=file_path)
        elif message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            target_dir = company_storage_dir(consultation.company_id)
            file_path = str(target_dir / f"photo_{message.photo[-1].file_unique_id}.jpg")
            await bot.download_file(file.file_path, destination=file_path)
        await service.add_attachment(consultation_id, file_path, attachment_type)
    await state.clear()
    await message.answer("Материал сохранен.")


@router.message(F.text == "Сгенерировать аудит")
async def ask_audit_id(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer("Откройте карточку клиента и нажмите кнопку Аудит, либо отправьте: /audit ID_консультации")


@router.message(F.text.startswith("/audit"))
async def audit_command(message: Message) -> None:
    if not await _guard(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /audit ID_консультации")
        return
    await _generate_audit(message, int(parts[1]))


@router.callback_query(F.data.startswith("audit:"))
async def audit_callback(callback: CallbackQuery) -> None:
    await callback.answer("Генерирую аудит...")
    await _generate_audit(callback.message, int(callback.data.split(":")[1]))


async def _generate_audit(message: Message, consultation_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation, audit_text = await service.generate_audit(consultation_id)
        preview = audit_text[:3500]
        await message.answer(
            f"Аудит сохранен для консультации <code>{consultation.id}</code>.\n\n{preview}"
        )


@router.message(F.text == "Сгенерировать DOCX")
async def ask_docx_id(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer("Откройте карточку клиента и нажмите DOCX, либо отправьте: /docx ID_консультации")


@router.message(F.text.startswith("/docx"))
async def docx_command(message: Message) -> None:
    if not await _guard(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /docx ID_консультации")
        return
    await _generate_docx(message, int(parts[1]))


@router.callback_query(F.data.startswith("docx:"))
async def docx_callback(callback: CallbackQuery) -> None:
    await callback.answer("Генерирую DOCX...")
    await _generate_docx(callback.message, int(callback.data.split(":")[1]))


async def _generate_docx(message: Message, consultation_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(consultation_id)
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return
        company = await crm_service.get_company(consultation.company_id)
        if company is None:
            await message.answer("Компания не найдена в CRM.")
            return
        path = await generate_consultation_docx(session, consultation, company)
    await message.answer_document(FSInputFile(Path(path)), caption="DOCX консультации готов.")


@router.message(F.text == "Указать результат консультации")
async def ask_result_id(message: Message) -> None:
    if not await _guard(message):
        return
    await message.answer("Откройте карточку и нажмите Результат, либо отправьте: /result ID_консультации")


@router.message(F.text.startswith("/result"))
async def result_command(message: Message) -> None:
    if not await _guard(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /result ID_консультации")
        return
    await message.answer("Выберите результат консультации:", reply_markup=result_keyboard(int(parts[1])))


@router.callback_query(F.data.startswith("result_menu:"))
async def result_menu_callback(callback: CallbackQuery) -> None:
    consultation_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer("Выберите результат консультации:", reply_markup=result_keyboard(consultation_id))


@router.callback_query(F.data.startswith("result:"))
async def set_result_callback(callback: CallbackQuery) -> None:
    _, consultation_id, result = callback.data.split(":")
    async with AsyncSessionLocal() as session:
        consultation = await ConsultationService(session).set_result(int(consultation_id), result)
    await callback.answer("Результат сохранен.")
    suffix = ""
    if result == "signed":
        suffix = "\nСтатус компании обновлен на client. Следующий слой: передача в production bot."
    await callback.message.answer(f"Статус консультации: <b>{consultation.status}</b>{suffix}")


@router.message(F.text == "Архив консультаций")
async def archive(message: Message) -> None:
    if not await _guard(message):
        return
    async with AsyncSessionLocal() as session:
        consultations = await ConsultationService(session).list_archive()
    if not consultations:
        await message.answer("Архив пока пуст.")
        return
    lines = [
        f"#{item.id} | company_{item.company_id} | {item.status} | {item.document_path or 'без DOCX'}"
        for item in consultations
    ]
    await message.answer("\n".join(lines))


@router.message(F.text == "Настройки AI")
async def ai_settings(message: Message) -> None:
    if not await _guard(message):
        return
    settings = get_settings()
    await message.answer(
        "Текущие настройки AI:\n"
        f"AI_PROVIDER=<code>{settings.ai_provider}</code>\n"
        f"OPENROUTER_MODEL=<code>{settings.openrouter_model}</code>\n"
        f"OLLAMA_BASE_URL=<code>{settings.ollama_base_url}</code>\n"
        f"OLLAMA_MODEL=<code>{settings.ollama_model}</code>"
    )


async def start_bot() -> None:
    settings = get_settings()
    if not settings.bot_token:
        return
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)
