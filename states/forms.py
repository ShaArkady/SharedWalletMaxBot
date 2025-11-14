from maxapi.context import State, StatesGroup


class WalletForm(StatesGroup):
    creating_name = State()
    connecting_id = State()


class TransactionForm(StatesGroup):
    entering_capital_amount = State()
    entering_expense_category = State()
    entering_expense_destination = State()
    entering_expense_amount = State()
    choosing_expense_share_type = State()
