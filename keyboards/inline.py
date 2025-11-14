import json

from maxapi.utils.inline_keyboard import InlineKeyboardBuilder
from maxapi.types.attachments.buttons.callback_button import CallbackButton


def main_menu_kb():
    """Главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="Создать новый счёт", payload=json.dumps({"menu": "new_wallet"})))
    builder.row(CallbackButton(text="Мои счета", payload=json.dumps({"menu": "my_wallets"})))
    builder.row(CallbackButton(text="Присоединиться к счёту", payload=json.dumps({"menu": "connect_wallet"})))
    return builder.as_markup()


def wallets_list_kb(wallets: list):
    """Список счетов пользователя."""
    builder = InlineKeyboardBuilder()
    for wallet in wallets:
        payload = json.dumps({"action": "open_wallet", "wallet_id": wallet.id})
        builder.row(CallbackButton(text=f"Счёт #{wallet.id} ({wallet.balance} ₽)", payload=payload))

    builder.row(CallbackButton(text="‹ Назад", payload=json.dumps({"menu": "back_to_main"})))
    return builder.as_markup()


def wallet_menu_kb(wallet_id: int, is_owner: bool):
    """Меню для конкретного счёта."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="📈 Статистика", payload=json.dumps({"action": "stats", "wallet_id": wallet_id})),
        CallbackButton(text="💰 Пополнить", payload=json.dumps({"action": "add_capital", "wallet_id": wallet_id}))
    )
    builder.row(
        CallbackButton(text="💸 Добавить трату", payload=json.dumps({"action": "add_expense", "wallet_id": wallet_id})))
    builder.row(
        CallbackButton(text="💵 Мои пополнения", payload=json.dumps({"action": "my_incomes", "wallet_id": wallet_id})),
        CallbackButton(text="🧾 Мои траты", payload=json.dumps({"action": "my_expenses", "wallet_id": wallet_id}))
    )
    if is_owner:
        builder.row(CallbackButton(text="🗑 Удалить счёт",
                                   payload=json.dumps({"action": "delete_wallet", "wallet_id": wallet_id})))

    builder.row(CallbackButton(text="‹ Назад к счетам", payload=json.dumps({"menu": "my_wallets"})))
    return builder.as_markup()


def confirm_delete_kb(wallet_id: int):
    """Подтверждение удаления."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Да, удалить", payload=json.dumps({"action": "confirm_delete", "wallet_id": wallet_id})))
    builder.row(
        CallbackButton(text="Нет, отмена", payload=json.dumps({"action": "open_wallet", "wallet_id": wallet_id})))
    return builder.as_markup()


def back_to_main_menu_kb():
    """Кнопка "Назад" в главное меню."""
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(text="‹ Главное меню", payload=json.dumps({"menu": "back_to_main"})))
    return builder.as_markup()


def is_shared_expense_kb(wallet_id: int):
    """Выбор: общая трата или личная."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(text="Общая", payload=json.dumps({"shared": True, "wallet_id": wallet_id})),
        CallbackButton(text="Личная", payload=json.dumps({"shared": False, "wallet_id": wallet_id}))
    )
    return builder.as_markup()


def incomes_list_kb(incomes: list, wallet_id: int):
    """Список пополнений пользователя с возможностью удалить."""
    builder = InlineKeyboardBuilder()
    for income in incomes:
        date_str = income.created_at.strftime("%d.%m.%Y %H:%M")
        btn_text = f"🗑 {income.amount} ₽ | {date_str}"
        payload = json.dumps({"action": "delete_income", "income_id": income.id, "wallet_id": wallet_id})
        builder.row(CallbackButton(text=btn_text, payload=payload))

    builder.row(CallbackButton(text="‹ Назад", payload=json.dumps({"action": "open_wallet", "wallet_id": wallet_id})))
    return builder.as_markup()


def expenses_list_kb(expenses: list, wallet_id: int):
    """Список трат пользователя с возможностью удаления."""
    builder = InlineKeyboardBuilder()
    for expense in expenses:
        date_str = expense.created_at.strftime("%d.%m.%Y %H:%M")
        shared_marker = "👥" if expense.is_shared else "👤"
        btn_text = f"🗑 {expense.amount} ₽ | {expense.category} | {shared_marker} | {date_str}"
        payload = json.dumps({"action": "delete_expense", "expense_id": expense.id, "wallet_id": wallet_id})
        builder.row(CallbackButton(text=btn_text, payload=payload))

    builder.row(CallbackButton(text="‹ Назад", payload=json.dumps({"action": "open_wallet", "wallet_id": wallet_id})))
    return builder.as_markup()


def confirm_delete_transaction_kb(transaction_type: str, transaction_id: int, wallet_id: int):
    """Подтверждение удаления транзакции."""
    builder = InlineKeyboardBuilder()
    builder.row(CallbackButton(
        text="Да, удалить",
        payload=json.dumps(
            {"action": f"confirm_delete_{transaction_type}", "id": transaction_id, "wallet_id": wallet_id})
    ))
    builder.row(CallbackButton(
        text="Нет, отмена",
        payload=json.dumps({"action": f"my_{transaction_type}s", "wallet_id": wallet_id})
    ))
    return builder.as_markup()


def membership_request_kb(requester_id, wallet_id):
    """Разрешение/отклонение заявки на присоединение к счёту."""
    builder = InlineKeyboardBuilder()
    builder.row(
        CallbackButton(
            text="✅ Разрешить",
            payload=json.dumps({
                "action": "accept_member",
                "requester_id": requester_id,
                "wallet_id": wallet_id
            })
        ),
        CallbackButton(
            text="❌ Отклонить",
            payload=json.dumps({
                "action": "decline_member",
                "requester_id": requester_id,
                "wallet_id": wallet_id
            })
        )
    )
    return builder.as_markup()
