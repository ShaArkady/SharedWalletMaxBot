from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics

def generate_pdf(wallet, incomes, expenses, filename: str):
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

    c.save()
