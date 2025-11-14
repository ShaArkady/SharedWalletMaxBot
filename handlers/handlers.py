import json
import logging
from decimal import Decimal, InvalidOperation
from collections import defaultdict

from maxapi import Dispatcher, F, Bot
from maxapi.types import MessageCreated, Command, Message, MessageCallback, BotStarted
from maxapi.context import MemoryContext
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import pytz

from database.db import async_session_maker
from database.models import User, Wallet, WalletMember, Income, Expense
from keyboards.inline import (
    main_menu_kb, wallets_list_kb, wallet_menu_kb,
    confirm_delete_kb, back_to_main_menu_kb, is_shared_expense_kb,
    incomes_list_kb, expenses_list_kb, confirm_delete_transaction_kb, membership_request_kb
)
from states.forms import WalletForm, TransactionForm

logger = logging.getLogger(__name__)

MOSCOW_TZ = pytz.timezone("Europe/Moscow")


async def show_main_menu(message: Message | None, context: MemoryContext, bot: Bot = None, user_id: int = None):
    """Показывает главное меню и очищает состояние."""
    await context.clear()
    text = "👋 Привет! Я бот для учёта финансов. Выберите действие:"
    payload = main_menu_kb()
    attachments = [payload] if payload else []

    if message is not None:
        await message.edit(text, attachments=attachments)
    else:
        await bot.send_message(user_id=user_id, text=text, attachments=attachments)


async def register_handlers(dp: Dispatcher):
    @dp.bot_started()
    async def on_bot_start(event: BotStarted, context: MemoryContext):
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_created(Command('start'))
    async def cmd_start(event: MessageCreated, context: MemoryContext):
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "back_to_main"))
    async def back_to_main_menu(event: MessageCallback, context: MemoryContext):
        await show_main_menu(message=event.message, context=context)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "cancel_action"), state="*")
    async def cancel_handler(event: MessageCallback, context: MemoryContext):
        if await context.get_state() is None: return
        await context.clear()
        await event.message.edit("Действие отменено.")
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "my_wallets"))
    async def show_user_wallets(event: MessageCallback, context: MemoryContext):
        user_id = event.from_user.user_id
        async with async_session_maker() as session:
            owned_q = select(Wallet).where(Wallet.owner_id == user_id)
            member_q = select(Wallet).join(WalletMember).where(WalletMember.user_id == user_id)
            owned_wallets = (await session.execute(owned_q)).scalars().all()
            member_wallets = (await session.execute(member_q)).scalars().all()
            all_wallets = sorted(list(set(owned_wallets + member_wallets)), key=lambda w: w.id)

        if not all_wallets:
            await event.message.edit("У вас пока нет счетов.", attachments=[back_to_main_menu_kb()])
            return
        await event.message.edit("Выберите счёт для управления:", attachments=[wallets_list_kb(all_wallets)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "open_wallet"))
    async def open_wallet_menu(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        async with async_session_maker() as session:
            wallet = await session.get(Wallet, wallet_id)
        if not wallet:
            await event.message.edit("Ошибка: счёт не найден.", attachments=[back_to_main_menu_kb()])
            return
        is_owner = wallet.owner_id == event.from_user.user_id
        text = f"Управление счётом #{wallet.id} «{wallet.name}»\nБаланс: {wallet.balance} ₽"
        await event.message.edit(text, attachments=[wallet_menu_kb(wallet_id, is_owner)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "new_wallet"))
    async def new_wallet_start(event: MessageCallback, context: MemoryContext):
        await context.set_state(WalletForm.creating_name)
        await event.message.edit("Введите название для нового счёта:", attachments=[back_to_main_menu_kb()])

    @dp.message_created(WalletForm.creating_name)
    async def new_wallet_name_provided(event: MessageCreated, context: MemoryContext):
        wallet_name = event.message.body.text
        if not wallet_name or len(wallet_name) > 100:
            await event.message.answer("Название некорректно, попробуйте ещё раз.",
                                       attachments=[back_to_main_menu_kb()])
            return

        user_id = event.message.sender.user_id
        async with async_session_maker() as session:
            user = await session.get(User, user_id)
            if not user:
                user = User(id=user_id, first_name=getattr(event.message.sender, 'first_name', "User"))
                session.add(user)
            wallet = Wallet(name=wallet_name, owner_id=user_id)
            session.add(wallet)
            await session.commit()
            await event.message.answer(f"✅ Счёт «{wallet.name}» успешно создан! Его ID: `{wallet.id}`")
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "connect_wallet"))
    async def connect_wallet_start(event: MessageCallback, context: MemoryContext):
        await context.set_state(WalletForm.connecting_id)
        await event.message.edit("Пришлите ID счёта для присоединения:", attachments=[back_to_main_menu_kb()])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("menu") == "connect_wallet"))
    async def connect_wallet_start(event: MessageCallback, context: MemoryContext):
        await context.set_state(WalletForm.connecting_id)
        await event.message.edit("Пришлите ID счёта для присоединения:", attachments=[back_to_main_menu_kb()])

    @dp.message_created(WalletForm.connecting_id)
    async def connect_wallet_id_provided(event: MessageCreated, context: MemoryContext):
        try:
            wallet_id = int(event.message.body.text)
        except (ValueError, TypeError):
            await event.message.answer("ID должен быть числом. Попробуйте ещё раз.",
                                       attachments=[back_to_main_menu_kb()])
            return

        user_id = event.message.sender.user_id
        async with async_session_maker() as session:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                await event.message.answer("Счёт с таким ID не найден.", attachments=[back_to_main_menu_kb()])
                return
            if wallet.owner_id == user_id:
                await event.message.answer("👑 Вы владелец этого счёта.", attachments=[back_to_main_menu_kb()])
                return
            existing = await session.execute(
                select(WalletMember).where(WalletMember.wallet_id == wallet_id, WalletMember.user_id == user_id)
            )
            if existing.scalar_one_or_none():
                await event.message.answer("⚠️ Вы уже участник этого счёта.", attachments=[back_to_main_menu_kb()])
                return

        owner_id = wallet.owner_id
        requester_name = event.message.sender.first_name or str(user_id)
        await event.bot.send_message(
            user_id=owner_id,
            text=f"Пользователь {requester_name} хочет присоединиться к вашему счёту «{wallet.name}» (ID: {wallet_id})",
            attachments=[membership_request_kb(user_id, wallet_id)]
        )
        await event.message.answer("Заявка отправлена владельцу счёта. Ожидайте решения.")

        await context.clear()

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "accept_member"))
    async def accept_member(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        requester_id = payload["requester_id"]
        wallet_id = payload["wallet_id"]
        async with async_session_maker() as session:
            existing = await session.execute(
                select(WalletMember).where(WalletMember.wallet_id == wallet_id, WalletMember.user_id == requester_id)
            )
            if existing.scalar_one_or_none():
                await event.message.edit("Пользователь уже добавлен ранее.")
                return
            member = WalletMember(wallet_id=wallet_id, user_id=requester_id)
            session.add(member)
            await session.commit()
        await event.message.edit("Пользователь добавлен!")
        await event.bot.send_message(
            user_id=requester_id,
            text="Ваша заявка на присоединение к счёту принята! Теперь вы участник."
        )

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "decline_member"))
    async def decline_member(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        requester_id = payload["requester_id"]
        wallet_id = payload["wallet_id"]
        await event.message.edit("Заявка отклонена.")
        await event.bot.send_message(
            user_id=requester_id,
            text="Ваша заявка на вступление в счёт отклонена владельцем."
        )

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "stats"))
    async def wallet_stats_handler(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        async with async_session_maker() as session:
            stmt = select(Wallet).where(Wallet.id == wallet_id).options(
                selectinload(Wallet.incomes).selectinload(Income.user),
                selectinload(Wallet.expenses).selectinload(Expense.user),
                selectinload(Wallet.members).selectinload(WalletMember.user),
                selectinload(Wallet.owner)
            )
            wallet = (await session.execute(stmt)).scalar_one_or_none()
            if not wallet:
                await event.message.edit("❌ Счёт не найден.", attachments=[back_to_main_menu_kb()])
                return

            total_income = sum(i.amount for i in wallet.incomes)
            total_expense = sum(e.amount for e in wallet.expenses)
            expenses_by_cat = defaultdict(Decimal)
            for exp in wallet.expenses: expenses_by_cat[exp.category] += exp.amount

            stats_msg = f"📊 **Статистика по счёту «{wallet.name}» (ID: {wallet.id})**\n\n"
            stats_msg += f"🏦 **Текущий баланс:** `{wallet.balance}` ₽\n"
            stats_msg += f"⬆️ **Всего поступлений:** `{total_income}` ₽\n"
            stats_msg += f"⬇️ **Всего трат:** `{total_expense}` ₽\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
            if expenses_by_cat:
                stats_msg += "📁 **Траты по категориям:**\n"
                for cat, amount in sorted(expenses_by_cat.items(), key=lambda i: i[1], reverse=True):
                    perc = (amount / total_expense) * 100 if total_expense else Decimal(0)
                    stats_msg += f"  - `{cat}`: {amount} ₽ ({perc:.1f}%)\n"

            await event.message.edit(stats_msg, attachments=[
                wallet_menu_kb(wallet_id, wallet.owner_id == event.from_user.user_id)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "delete_wallet"))
    async def delete_wallet_confirm(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        await event.message.edit("Вы уверены, что хотите удалить этот счёт?",
                                 attachments=[confirm_delete_kb(payload['wallet_id'])])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "confirm_delete"))
    async def delete_wallet_execute(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        async with async_session_maker() as session:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet or wallet.owner_id != event.from_user.user_id:
                await event.message.edit("❌ Ошибка: счёт не найден или у вас нет прав на удаление.")
                await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)
                return
            await session.delete(wallet)
            await session.commit()
        await event.message.edit(f"✅ Счёт #{wallet_id} удалён.")
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "add_capital"))
    async def add_capital_start(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        await context.update_data(wallet_id=wallet_id)
        await context.set_state(TransactionForm.entering_capital_amount)
        await event.message.edit(f"Введите сумму для пополнения счёта #{wallet_id}:",
                                 attachments=[back_to_main_menu_kb()])

    @dp.message_created(TransactionForm.entering_capital_amount)
    async def add_capital_amount_provided(event: MessageCreated, context: MemoryContext):
        try:
            amount = Decimal(event.message.body.text)
            if amount <= 0: raise ValueError
        except (InvalidOperation, ValueError):
            await event.message.answer("Сумма некорректна. Введите положительное число.",
                                       attachments=[back_to_main_menu_kb()])
            return

        user_data = await context.get_data()
        wallet_id = user_data.get("wallet_id")
        async with async_session_maker() as session:
            wallet = await session.get(Wallet, wallet_id)
            wallet.balance += amount
            income = Income(wallet_id=wallet_id, user_id=event.message.sender.user_id, amount=amount,
                            description="Пополнение баланса")
            session.add(income)
            await session.commit()
            await event.message.answer(f"✅ Счёт #{wallet_id} пополнен на {amount} ₽.\nНовый баланс: {wallet.balance} ₽")
        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "add_expense"))
    async def add_expense_start(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']

        await context.update_data(wallet_id=wallet_id)
        await context.set_state(TransactionForm.entering_expense_category)

        await event.message.edit(
            f"Вы добавляете трату в счёт #{wallet_id}.\n\n"
            "Введите категорию траты (например, 'Продукты', 'Транспорт', 'Развлечения'):",
            attachments=[back_to_main_menu_kb()]
        )

    @dp.message_created(TransactionForm.entering_expense_category)
    async def expense_category_provided(event: MessageCreated, context: MemoryContext):
        category = event.message.body.text
        if not category or len(category) > 100:
            await event.message.answer("Название категории некорректно. Попробуйте снова.",
                                       attachments=[back_to_main_menu_kb()])
            return

        await context.update_data(category=category)
        await context.set_state(TransactionForm.entering_expense_destination)

        await event.message.answer(
            "Отлично. Теперь введите назначение траты (например, 'Поход в Пятёрочку', 'Такси до дома'):",
            attachments=[back_to_main_menu_kb()]
        )

    @dp.message_created(TransactionForm.entering_expense_destination)
    async def expense_destination_provided(event: MessageCreated, context: MemoryContext):
        destination = event.message.body.text
        if not destination or len(destination) > 255:
            await event.message.answer("Название назначения некорректно. Попробуйте снова.",
                                       attachments=[back_to_main_menu_kb()])
            return

        await context.update_data(destination=destination)
        await context.set_state(TransactionForm.entering_expense_amount)

        await event.message.answer(
            "Принято. Теперь введите сумму траты (только число):",
            attachments=[back_to_main_menu_kb()]
        )

    @dp.message_created(TransactionForm.entering_expense_amount)
    async def expense_amount_provided(event: MessageCreated, context: MemoryContext):
        try:
            amount = Decimal(event.message.body.text)
            if amount <= 0: raise ValueError
        except (InvalidOperation, ValueError):
            await event.message.answer("Сумма должна быть положительным числом. Попробуйте снова.",
                                       attachments=[back_to_main_menu_kb()])
            return

        user_data = await context.get_data()
        wallet_id = user_data.get("wallet_id")

        await context.update_data(amount=amount)
        await context.set_state(TransactionForm.choosing_expense_share_type)

        await event.message.answer(
            "Последний шаг. Эта трата общая для всех участников счёта?",
            attachments=[is_shared_expense_kb(wallet_id)]
        )

    @dp.message_callback(TransactionForm.choosing_expense_share_type)
    async def expense_share_type_chosen(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        is_shared = payload.get("shared", False)

        user_data = await context.get_data()
        wallet_id = user_data.get("wallet_id")
        category = user_data.get("category")
        destination = user_data.get("destination")
        amount = Decimal(user_data.get("amount"))

        async with async_session_maker() as session:
            wallet = await session.get(Wallet, wallet_id)
            if not wallet:
                await event.message.edit("❌ Произошла ошибка, счёт не найден.")
                await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)
                return

            wallet.balance -= amount

            expense = Expense(
                wallet_id=wallet_id,
                user_id=event.from_user.user_id,
                category=category,
                destination=destination,
                amount=amount,
                is_shared=is_shared
            )
            session.add(expense)
            await session.commit()

            shared_text = "общая" if is_shared else "личная"
            await event.message.edit(
                f"✅ Трата добавлена!\n\n"
                f"Категория: {category}\n"
                f"Назначение: {destination}\n"
                f"Сумма: {amount} ₽ ({shared_text})\n\n"
                f"Новый баланс счёта: {wallet.balance} ₽"
            )

        await show_main_menu(message=None, user_id=event.from_user.user_id, context=context, bot=event.bot)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "my_incomes"))
    async def show_my_incomes(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        user_id = event.from_user.user_id

        async with async_session_maker() as session:
            stmt = select(Income).where(
                Income.wallet_id == wallet_id,
                Income.user_id == user_id
            ).order_by(Income.created_at.desc())

            incomes = (await session.execute(stmt)).scalars().all()

        if not incomes:
            await event.message.edit(
                "У вас пока нет пополнений в этом счёте.",
                attachments=[wallet_menu_kb(wallet_id, False)]
            )
            return

        total = sum(i.amount for i in incomes)
        text = f"💵 **Ваши пополнения в счёт #{wallet_id}**\n\n"
        text += f"Всего пополнений: {len(incomes)}\n"
        text += f"Общая сумма: {total} ₽\n\n"
        text += "Нажмите на кнопку, чтобы удалить пополнение:"

        await event.message.edit(text, attachments=[incomes_list_kb(incomes, wallet_id)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "delete_income"))
    async def delete_income_confirm(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        income_id = payload['income_id']
        wallet_id = payload['wallet_id']

        async with async_session_maker() as session:
            income = await session.get(Income, income_id)
            if not income:
                await event.message.edit("❌ Пополнение не найдено.")
                return

            utc_time = income.created_at.replace(tzinfo=pytz.utc)
            moscow_time = utc_time.astimezone(MOSCOW_TZ)
            date_str = moscow_time.strftime("%d.%m.%Y %H:%M")
            text = f"Вы уверены, что хотите удалить пополнение?\n\n"
            text += f"Сумма: {income.amount} ₽\n"
            text += f"Дата: {date_str}\n"
            text += f"Описание: {income.description or 'Не указано'}"

        await event.message.edit(text,
                                 attachments=[confirm_delete_transaction_kb("income", income_id, wallet_id)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "confirm_delete_income"))
    async def delete_income_execute(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        income_id = payload['id']
        wallet_id = payload['wallet_id']
        user_id = event.from_user.user_id

        async with async_session_maker() as session:
            income = await session.get(Income, income_id)

            if not income:
                await event.message.edit("❌ Пополнение не найдено.")
                return

            if income.user_id != user_id:
                await event.message.edit("❌ Вы можете удалять только свои пополнения.")
                return

            wallet = await session.get(Wallet, wallet_id)
            wallet.balance -= income.amount

            amount = income.amount
            await session.delete(income)
            await session.commit()

            await event.message.edit(
                f"✅ Пополнение на сумму {amount} ₽ удалено.\n"
                f"Баланс счёта уменьшен на {amount} ₽."
            )

        await show_my_incomes(event, context)

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "my_expenses"))
    async def show_my_expenses(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        wallet_id = payload['wallet_id']
        user_id = event.from_user.user_id

        async with async_session_maker() as session:
            stmt = select(Expense).where(
                Expense.wallet_id == wallet_id,
                Expense.user_id == user_id
            ).order_by(Expense.created_at.desc())

            expenses = (await session.execute(stmt)).scalars().all()

        if not expenses:
            await event.message.edit(
                "У вас пока нет трат в этом счёте.",
                attachments=[wallet_menu_kb(wallet_id, False)]
            )
            return

        total = sum(e.amount for e in expenses)
        text = f"🧾 **Ваши траты в счёте #{wallet_id}**\n\n"
        text += f"Всего трат: {len(expenses)}\n"
        text += f"Общая сумма: {total} ₽\n\n"
        text += "Нажмите на кнопку, чтобы удалить трату:"

        await event.message.edit(text, attachments=[expenses_list_kb(expenses, wallet_id)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "delete_expense"))
    async def delete_expense_confirm(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        expense_id = payload['expense_id']
        wallet_id = payload['wallet_id']

        async with async_session_maker() as session:
            expense = await session.get(Expense, expense_id)
            if not expense:
                await event.message.edit("❌ Трата не найдена.")
                return

            utc_time = expense.created_at.replace(tzinfo=pytz.utc)
            moscow_time = utc_time.astimezone(MOSCOW_TZ)
            date_str = moscow_time.strftime("%d.%m.%Y %H:%M")
            shared_text = "Общая" if expense.is_shared else "Личная"
            text = f"Вы уверены, что хотите удалить трату?\n\n"
            text += f"Категория: {expense.category}\n"
            text += f"Назначение: {expense.destination}\n"
            text += f"Сумма: {expense.amount} ₽\n"
            text += f"Тип: {shared_text}\n"
            text += f"Дата: {date_str}"

        await event.message.edit(text,
                                 attachments=[confirm_delete_transaction_kb("expense", expense_id, wallet_id)])

    @dp.message_callback(F.callback.payload.func(lambda p: json.loads(p).get("action") == "confirm_delete_expense"))
    async def delete_expense_execute(event: MessageCallback, context: MemoryContext):
        payload = json.loads(event.callback.payload)
        expense_id = payload['id']
        wallet_id = payload['wallet_id']
        user_id = event.from_user.user_id

        async with async_session_maker() as session:
            expense = await session.get(Expense, expense_id)

            if not expense:
                await event.message.edit("❌ Трата не найдена.")
                return

            if expense.user_id != user_id:
                await event.message.edit("❌ Вы можете удалять только свои траты.")
                return

            wallet = await session.get(Wallet, wallet_id)
            wallet.balance += expense.amount

            amount = expense.amount
            await session.delete(expense)
            await session.commit()

            await event.message.edit(
                f"✅ Трата на сумму {amount} ₽ удалена.\n"
                f"Баланс счёта восстановлен на {amount} ₽."
            )

        await show_my_expenses(event, context)
