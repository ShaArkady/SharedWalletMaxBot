from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics


def calculate_debts(wallet, incomes, expenses, members):
    member_ids = [m.user_id for m in members]
    paid = {uid: 0 for uid in member_ids}
    for inc in incomes:
        paid[inc.user_id] += float(inc.amount)
    spent = {uid: 0 for uid in member_ids}
    for exp in expenses:
        if exp.is_shared:
            share = float(exp.amount) / len(member_ids)
            for uid in member_ids:
                spent[uid] += share
        else:
            spent[exp.user_id] += float(exp.amount)

    balance = {uid: paid[uid] - spent[uid] for uid in member_ids}
    return balance


def debt_report(balance, members_dict):
    creditors = sorted([(uid, amt) for uid, amt in balance.items() if amt > 0], key=lambda x: -x[1])
    debtors = sorted([(uid, amt) for uid, amt in balance.items() if amt < 0], key=lambda x: x[1])
    report = "\nИтоги по счету:\n"
    for uid, amt in balance.items():
        name = members_dict.get(uid, str(uid))
        if amt > 0:
            report += f"{name} (ID: {uid}) — переплатил {amt:.2f} ₽\n"
        elif amt < 0:
            report += f"{name} (ID: {uid}) — должен {-amt:.2f} ₽\n"
        else:
            report += f"{name} (ID: {uid}) — в нуле\n"
    recs = []
    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor_id, debtor_amt = debtors[i]
        creditor_id, creditor_amt = creditors[j]
        pay = min(-debtor_amt, creditor_amt)
        if pay > 0:
            d_name = members_dict.get(debtor_id, str(debtor_id))
            c_name = members_dict.get(creditor_id, str(creditor_id))
            recs.append(f"{d_name} должен {c_name} — {pay:.2f} ₽")
            debtor_amt += pay
            creditor_amt -= pay
            debtors[i] = (debtor_id, debtor_amt)
            creditors[j] = (creditor_id, creditor_amt)
            if abs(debtor_amt) < 0.01:
                i += 1
            if abs(creditor_amt) < 0.01:
                j += 1
        else:
            break
    report += "\nКто кому сколько должен:\n" + "\n".join(recs)
    return report



def generate_pdf(wallet, incomes, expenses, members, filename: str):
    pdfmetrics.registerFont(TTFont('RobotoBold', 'utils/fonts/Roboto-Bold.ttf'))
    pdfmetrics.registerFont(TTFont('Roboto', 'utils/fonts/Roboto-Regular.ttf'))

    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4

    c.setTitle(f"Статистика по кошельку '{wallet.name}'")
    c.setFont("RobotoBold", 18)
    c.drawString(50, height-60, f"Подробная статистика по счёту '{wallet.name}' (ID: {wallet.id})")

    c.setFont("Roboto", 12)
    c.drawString(50, height-90, f"Владелец: {wallet.owner_id}")
    c.drawString(50, height-110, f"Баланс: {wallet.balance} ₽")
    c.drawString(50, height-130, f"Всего поступлений: {sum(i.amount for i in incomes)} ₽")
    c.drawString(50, height-150, f"Всего трат: {sum(e.amount for e in expenses)} ₽")

    c.setFont("RobotoBold", 14)
    c.drawString(50, height-180, "Пополнения:")
    table_data = [["Дата", "Сумма", "Пользователь", "Описание"]]
    for i in incomes:
        table_data.append([
            i.created_at.strftime("%d.%m.%Y %H:%M"),
            f"{i.amount} ₽",
            str(i.user_id),
            i.description or "-"
        ])
    table = Table(table_data, colWidths=[100, 100, 100, 180])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Roboto"),
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Roboto")
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, height-400)

    c.setFont("RobotoBold", 14)
    c.drawString(50, height-440, "Траты:")
    table_data = [["Дата", "Сумма", "Категория", "Назначение", "Пользователь", "Тип"]]
    for e in expenses:
        table_data.append([
            e.created_at.strftime("%d.%m.%Y %H:%M"),
            f"{e.amount} ₽",
            e.category,
            e.destination,
            str(e.user_id),
            "Общая" if e.is_shared else "Личная"
        ])
    table = Table(table_data, colWidths=[90, 70, 80, 130, 80, 60])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Roboto"),
        ("BACKGROUND", (0,0), (-1,0), colors.grey),
        ("GRID", (0,0), (-1,-1), 0.5, colors.black),
        ("FONTNAME", (0,0), (-1,0), "Roboto")
    ]))
    table.wrapOn(c, width, height)
    table.drawOn(c, 50, 50)

    members_dict = {m.user_id: getattr(m.user, 'first_name', str(m.user_id)) for m in members}
    balance = calculate_debts(wallet, incomes, expenses, members)
    report_text = debt_report(balance, members_dict)
    c.setFont("Roboto", 12)
    for idx, line in enumerate(report_text.splitlines()):
        c.drawString(50, height - 480 - idx * 18, line)

    c.save()
