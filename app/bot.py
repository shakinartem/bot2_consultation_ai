from __future__ import annotations

import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
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

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.modules.consultation.models import Consultation
from app.modules.consultation.service import ConsultationService
from app.modules.crm.service import CRMAdapterError, Company, crm_service
from app.modules.documents.generator import generate_consultation_docx
from app.modules.documents.pdf import export_pdf_if_available
from app.modules.files.storage import company_storage_dir, safe_filename


router = Router()
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
logger = logging.getLogger(__name__)


class ConsultationStates(StatesGroup):
    waiting_company_id = State()
    waiting_note = State()
    waiting_links = State()
    waiting_material = State()
    waiting_result_notes = State()


def main_menu() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📋 Клиенты на консультацию"), KeyboardButton(text="🔎 Открыть карточку")],
        [KeyboardButton(text="🧠 Сгенерировать аудит"), KeyboardButton(text="📄 Сгенерировать документ")],
        [KeyboardButton(text="✅ Указать результат консультации"), KeyboardButton(text="🗂 Архив консультаций")],
        [KeyboardButton(text="⚙️ Настройки AI"), KeyboardButton(text="❓ Помощь")],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def is_admin(user_id: int) -> bool:
    admins = get_settings().admin_id_set
    return not admins or user_id in admins


def is_allowed(user_id: int) -> bool:
    return is_admin(user_id)


async def guard_message(message: Message) -> bool:
    if message.from_user and is_allowed(message.from_user.id):
        return True
    await message.answer("Доступ ограничен. Укажите ваш Telegram ID в ADMIN_IDS.")
    return False


async def guard_callback(callback: CallbackQuery) -> bool:
    if callback.from_user and is_allowed(callback.from_user.id):
        return True
    await callback.answer("Доступ ограничен.", show_alert=True)
    return False


def company_list_keyboard(companies: list[Company]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"Открыть карточку · {company.name}", callback_data=f"company:{company.id}")]
            for company in companies
        ]
    )


def card_keyboard(consultation: Consultation) -> InlineKeyboardMarkup:
    cid = consultation.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Добавить заметку", callback_data=f"note:{cid}"),
                InlineKeyboardButton(text="🔗 Добавить ссылки", callback_data=f"links:{cid}"),
            ],
            [
                InlineKeyboardButton(text="📎 Добавить материалы", callback_data=f"material:{cid}"),
                InlineKeyboardButton(text="🧠 Сгенерировать аудит", callback_data=f"audit:{cid}"),
            ],
            [
                InlineKeyboardButton(text="💼 Сформировать предложение", callback_data=f"proposal:{cid}"),
                InlineKeyboardButton(text="📄 Сгенерировать DOCX", callback_data=f"docx:{cid}"),
            ],
            [InlineKeyboardButton(text="✅ Итог консультации", callback_data=f"result_menu:{cid}")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back:list")],
        ]
    )


def result_keyboard(consultation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отказ", callback_data=f"result:{consultation_id}:refused")],
            [InlineKeyboardButton(text="🤔 Думает", callback_data=f"result:{consultation_id}:thinking")],
            [InlineKeyboardButton(text="📩 Договор отправлен", callback_data=f"result:{consultation_id}:contract_sent")],
            [InlineKeyboardButton(text="✅ Договор подписан / стал клиентом", callback_data=f"result:{consultation_id}:signed")],
        ]
    )


def _fmt(value: object | None) -> str:
    return str(value) if value not in (None, "", []) else "нет данных"


def company_short(company: Company) -> str:
    return (
        f"<b>{company.name}</b>\n"
        f"Город: {_fmt(company.city)}\n"
        f"Сайт: {_fmt(company.website)}\n"
        f"Карты: {_fmt(company.maps_url)}\n"
        f"Телефон: {_fmt(company.phone)}\n"
        f"Заметка: {_fmt(company.crm_notes)}"
    )


def company_card(company: Company, consultation: Consultation) -> str:
    social = ", ".join(company.social_links) or "нет данных"
    rating = "нет данных"
    if company.rating is not None or company.reviews_count is not None:
        rating = f"{_fmt(company.rating)} / отзывов: {_fmt(company.reviews_count)}"
    return (
        f"<b>{company.name}</b>\n"
        f"Юр. название: {_fmt(company.legal_name)}\n"
        f"Город: {_fmt(company.city)}\n"
        f"Адрес: {_fmt(company.address)}\n"
        f"Телефон: {_fmt(company.phone)}\n"
        f"Сайт: {_fmt(company.website)}\n"
        f"Карты: {_fmt(company.maps_url)}\n"
        f"Соцсети: {social}\n"
        f"Рейтинг: {rating}\n"
        f"Заметки CRM: {_fmt(company.crm_notes)}\n"
        f"Боль клиента: {_fmt(company.pain)}\n"
        f"Статус CRM: <b>{company.status}</b>\n"
        f"Активная консультация: <code>{consultation.id}</code> · <b>{consultation.status}</b>"
    )


async def send_company_card(message: Message, company_id: int) -> None:
    try:
        company = await crm_service.get_company(company_id)
    except CRMAdapterError as exc:
        await message.answer(f"CRM недоступна: {exc}")
        return
    if company is None:
        await message.answer("Компания не найдена в CRM.")
        return
    async with AsyncSessionLocal() as session:
        consultation = await ConsultationService(session).get_or_create_for_company(company_id)
        await message.answer(company_card(company, consultation), reply_markup=card_keyboard(consultation))


async def send_consultation_clients(message: Message) -> None:
    try:
        companies = await crm_service.list_consultation_scheduled()
    except CRMAdapterError as exc:
        await message.answer(f"CRM недоступна: {exc}")
        return
    if not companies:
        await message.answer("Пока нет клиентов, готовых к консультации.")
        return
    text = "\n\n".join(company_short(company) for company in companies)
    await message.answer(text, reply_markup=company_list_keyboard(companies))


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if not await guard_message(message):
        return
    await message.answer(
        "БОТ 2 · SHARiK digital Consultation AI готов к консультациям.",
        reply_markup=main_menu(),
    )


@router.message(F.text == "❓ Помощь")
async def help_message(message: Message) -> None:
    if not await guard_message(message):
        return
    await message.answer(
        "Сценарий MVP:\n"
        "1. Откройте клиентов на консультацию.\n"
        "2. Выберите клинику и проверьте карточку.\n"
        "3. Добавьте заметки, ссылки и материалы.\n"
        "4. Сгенерируйте аудит.\n"
        "5. Сформируйте предложение.\n"
        "6. Сгенерируйте DOCX.\n"
        "7. Зафиксируйте итог консультации.\n\n"
        "Команды:\n"
        "/audit ID\n"
        "/proposal ID\n"
        "/docx ID\n"
        "/result ID"
    )


@router.message(F.text == "📋 Клиенты на консультацию")
async def list_clients(message: Message) -> None:
    if not await guard_message(message):
        return
    await send_consultation_clients(message)


@router.callback_query(F.data == "back:list")
async def back_to_list(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    await callback.answer()
    await send_consultation_clients(callback.message)


@router.callback_query(F.data.startswith("company:"))
async def open_company_callback(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    await callback.answer()
    await send_company_card(callback.message, int(callback.data.split(":")[1]))


@router.message(F.text == "🔎 Открыть карточку")
async def ask_company_id(message: Message, state: FSMContext) -> None:
    if not await guard_message(message):
        return
    await state.set_state(ConsultationStates.waiting_company_id)
    await message.answer("Введите ID компании из CRM.")


@router.message(ConsultationStates.waiting_company_id)
async def receive_company_id(message: Message, state: FSMContext) -> None:
    if not await guard_message(message):
        return
    if not message.text or not message.text.strip().isdigit():
        await message.answer("Нужен числовой ID компании.")
        return
    await state.clear()
    await send_company_card(message, int(message.text.strip()))


@router.callback_query(F.data.startswith("note:"))
async def note_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not await guard_callback(callback):
        return
    consultation_id = int(callback.data.split(":")[1])
    await state.update_data(consultation_id=consultation_id)
    await state.set_state(ConsultationStates.waiting_note)
    await callback.answer()
    await callback.message.answer("Отправьте текст заметки.")


@router.message(ConsultationStates.waiting_note)
async def receive_note(message: Message, state: FSMContext) -> None:
    if not await guard_message(message):
        return
    data = await state.get_data()
    consultation_id = data.get("consultation_id")
    if not consultation_id or not message.text:
        await message.answer("Нужен текст заметки.")
        return
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(int(consultation_id))
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return
        await service.add_note(int(consultation_id), message.text.strip())
    await state.clear()
    await message.answer("Заметка сохранена.")
    await send_company_card(message, consultation.company_id)


@router.callback_query(F.data.startswith("links:"))
async def links_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not await guard_callback(callback):
        return
    await state.update_data(consultation_id=int(callback.data.split(":")[1]))
    await state.set_state(ConsultationStates.waiting_links)
    await callback.answer()
    await callback.message.answer("Вставьте ссылки одним сообщением: сайт, Яндекс.Карты, 2ГИС, VK, Instagram, Telegram, WhatsApp или другие.")


@router.message(ConsultationStates.waiting_links)
async def receive_links(message: Message, state: FSMContext) -> None:
    if not await guard_message(message):
        return
    data = await state.get_data()
    consultation_id = data.get("consultation_id")
    if not consultation_id or not message.text:
        await message.answer("Нужны ссылки одним сообщением.")
        return
    links = [line.strip() for line in message.text.replace(",", "\n").splitlines() if line.strip()]
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(int(consultation_id))
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return
        await service.add_note(int(consultation_id), "Ссылки менеджера:\n" + "\n".join(links))
        for link in links:
            await service.add_attachment(int(consultation_id), link, "link")
    await state.clear()
    await message.answer("Ссылки сохранены.")
    await send_company_card(message, consultation.company_id)


@router.callback_query(F.data.startswith("material:"))
async def material_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not await guard_callback(callback):
        return
    await state.update_data(consultation_id=int(callback.data.split(":")[1]))
    await state.set_state(ConsultationStates.waiting_material)
    await callback.answer()
    await callback.message.answer("Отправьте документ или изображение до 15 МБ.")


@router.message(ConsultationStates.waiting_material)
async def receive_material(message: Message, state: FSMContext, bot: Bot) -> None:
    if not await guard_message(message):
        return
    data = await state.get_data()
    consultation_id = data.get("consultation_id")
    if not consultation_id:
        await message.answer("Консультация не выбрана.")
        return

    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(int(consultation_id))
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return

        file_path = ""
        attachment_type = "text"
        if message.document:
            if message.document.file_size and message.document.file_size > MAX_UPLOAD_BYTES:
                await message.answer("Файл больше 15 МБ. Для MVP загрузите меньший файл.")
                return
            file = await bot.get_file(message.document.file_id)
            target = company_storage_dir(consultation.company_id) / safe_filename(message.document.file_name or "document")
            await bot.download_file(file.file_path, destination=str(target))
            file_path = str(target)
            attachment_type = "document"
        elif message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            target = company_storage_dir(consultation.company_id) / safe_filename(f"photo_{message.photo[-1].file_unique_id}.jpg")
            await bot.download_file(file.file_path, destination=str(target))
            file_path = str(target)
            attachment_type = "photo"
        elif message.text:
            file_path = message.text.strip()
            attachment_type = "text"
        else:
            await message.answer("Поддерживаются документы, изображения или текстовое описание.")
            return

        await service.add_attachment(int(consultation_id), file_path, attachment_type)
    await state.clear()
    await message.answer("Материал сохранен.")
    await send_company_card(message, consultation.company_id)


async def generate_audit_message(message: Message, consultation_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        try:
            consultation, audit_text = await service.generate_audit(consultation_id)
        except (ValueError, CRMAdapterError) as exc:
            await message.answer(f"Не удалось сгенерировать аудит: {exc}")
            return
    await message.answer(f"Аудит сохранен для консультации <code>{consultation.id}</code>.\n\n{audit_text[:3500]}")


@router.callback_query(F.data.startswith("audit:"))
async def audit_callback(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    await callback.answer("Генерирую аудит...")
    await generate_audit_message(callback.message, int(callback.data.split(":")[1]))


@router.message(F.text == "🧠 Сгенерировать аудит")
async def ask_audit_id(message: Message) -> None:
    if not await guard_message(message):
        return
    await message.answer("Откройте карточку и нажмите “Сгенерировать аудит”, либо отправьте /audit ID_консультации.")


@router.message(F.text.startswith("/audit"))
async def audit_command(message: Message) -> None:
    if not await guard_message(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /audit ID_консультации")
        return
    await generate_audit_message(message, int(parts[1]))


async def generate_docx_message(message: Message, consultation_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation = await service.get(consultation_id)
        if consultation is None:
            await message.answer("Консультация не найдена.")
            return
        try:
            company = await crm_service.get_company(consultation.company_id)
        except CRMAdapterError as exc:
            await message.answer(f"CRM недоступна: {exc}")
            return
        if company is None:
            await message.answer("Компания не найдена в CRM.")
            return
        path = await generate_consultation_docx(session, consultation, company)
        pdf_result = export_pdf_if_available(Path(path))
        if pdf_result.path:
            consultation.pdf_path = str(pdf_result.path)
            await session.commit()

    await message.answer_document(FSInputFile(Path(path)), caption="DOCX консультации готов.")
    if pdf_result.path:
        await message.answer_document(FSInputFile(pdf_result.path), caption="PDF консультации готов.")
    else:
        await message.answer(pdf_result.message)


async def generate_proposal_message(message: Message, consultation_id: int) -> None:
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        try:
            consultation, proposal_text = await service.generate_proposal(consultation_id)
        except (ValueError, CRMAdapterError) as exc:
            await message.answer(f"Не удалось сформировать предложение: {exc}")
            return
    preview = proposal_text[:3500]
    await message.answer(
        f"Предложение сохранено для консультации <code>{consultation.id}</code>.\n\n{preview}"
    )


@router.callback_query(F.data.startswith("proposal:"))
async def proposal_callback(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    await callback.answer("Формирую предложение...")
    await generate_proposal_message(callback.message, int(callback.data.split(":")[1]))


@router.callback_query(F.data.startswith("docx:"))
async def docx_callback(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    await callback.answer("Генерирую документ...")
    await generate_docx_message(callback.message, int(callback.data.split(":")[1]))


@router.message(F.text == "📄 Сгенерировать документ")
async def ask_docx_id(message: Message) -> None:
    if not await guard_message(message):
        return
    await message.answer("Откройте карточку и нажмите “Сгенерировать DOCX”, либо отправьте /docx ID_консультации.")


@router.message(F.text.startswith("/docx"))
async def docx_command(message: Message) -> None:
    if not await guard_message(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /docx ID_консультации")
        return
    await generate_docx_message(message, int(parts[1]))


@router.message(F.text.startswith("/proposal"))
async def proposal_command(message: Message) -> None:
    if not await guard_message(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /proposal ID_консультации")
        return
    await generate_proposal_message(message, int(parts[1]))


@router.callback_query(F.data.startswith("result_menu:"))
async def result_menu_callback(callback: CallbackQuery) -> None:
    if not await guard_callback(callback):
        return
    consultation_id = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.answer("Выберите итог консультации:", reply_markup=result_keyboard(consultation_id))


@router.callback_query(F.data.startswith("result:"))
async def set_result_callback(callback: CallbackQuery, state: FSMContext) -> None:
    if not await guard_callback(callback):
        return
    _, consultation_id, result = callback.data.split(":")
    await state.update_data(consultation_id=int(consultation_id), result=result)
    await state.set_state(ConsultationStates.waiting_result_notes)
    await callback.answer()
    await callback.message.answer("Добавьте короткое резюме итога консультации одним сообщением.")


@router.message(ConsultationStates.waiting_result_notes)
async def receive_result_notes(message: Message, state: FSMContext) -> None:
    if not await guard_message(message):
        return
    data = await state.get_data()
    consultation_id = int(data["consultation_id"])
    result = data["result"]
    async with AsyncSessionLocal() as session:
        service = ConsultationService(session)
        consultation, warning = await service.set_result(consultation_id, result, message.text or result)
    await state.clear()
    suffix = ""
    if result == "signed":
        suffix = "\nСтатус компании обновлен на client. Клиент готов к передаче в production bot."
    if warning:
        suffix += f"\n\n⚠️ {warning}"
    await message.answer(f"Итог сохранен. Статус консультации: <b>{consultation.status}</b>{suffix}")


@router.message(F.text == "✅ Указать результат консультации")
async def ask_result_id(message: Message) -> None:
    if not await guard_message(message):
        return
    await message.answer("Откройте карточку и нажмите “Итог консультации”, либо отправьте /result ID_консультации.")


@router.message(F.text.startswith("/result"))
async def result_command(message: Message) -> None:
    if not await guard_message(message):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /result ID_консультации")
        return
    await message.answer("Выберите итог консультации:", reply_markup=result_keyboard(int(parts[1])))


@router.message(F.text == "🗂 Архив консультаций")
async def archive(message: Message) -> None:
    if not await guard_message(message):
        return
    async with AsyncSessionLocal() as session:
        consultations = await ConsultationService(session).list_archive()
    if not consultations:
        await message.answer("Архив пока пуст.")
        return
    lines = [
        f"#{item.id} · company_{item.company_id} · {item.status} · {item.document_path or 'без DOCX'}"
        for item in consultations
    ]
    await message.answer("\n".join(lines))


@router.message(F.text == "⚙️ Настройки AI")
async def ai_settings(message: Message) -> None:
    if not await guard_message(message):
        return
    settings = get_settings()
    await message.answer(
        "Текущие настройки:\n"
        f"AI_PROVIDER=<code>{settings.ai_provider}</code>\n"
        f"OPENROUTER_MODEL=<code>{settings.openrouter_model}</code>\n"
        f"OLLAMA_BASE_URL=<code>{settings.ollama_base_url}</code>\n"
        f"OLLAMA_MODEL=<code>{settings.ollama_model}</code>\n"
        f"CRM_ADAPTER=<code>{settings.crm_adapter}</code>\n"
        f"PDF_EXPORT_ENABLED=<code>{settings.pdf_export_enabled}</code>\n"
        f"PDF_EXPORT_PROVIDER=<code>{settings.pdf_export_provider}</code>"
    )


async def start_bot() -> None:
    settings = get_settings()
    if not settings.bot_token:
        logger.info("Telegram bot disabled: BOT_TOKEN is empty")
        return
    logger.info("Initializing Telegram bot")
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    try:
        await dispatcher.start_polling(bot)
    except Exception:
        logger.exception("Telegram polling failed")
        raise
