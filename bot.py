import os
import re
import json
from datetime import datetime, date
from collections import defaultdict
from telethon import TelegramClient, events
from telethon.tl.types import User

# ─── Настройки из переменных окружения ───────────────────────────────────────
API_ID      = int(os.environ["API_ID"])
API_HASH    = os.environ["API_HASH"]
PHONE       = os.environ["PHONE"]          # +992xxxxxxxxx
SOURCE_BOT  = os.environ["SOURCE_BOT"]    # username бота банка, например: dcnextbot
REPORT_BOT  = os.environ.get("REPORT_BOT", "")   # куда слать отчёты (можно свой @username или другой бот)
SESSION     = os.environ.get("SESSION_STRING", "") # для Railway

# ─── Хранилище платежей (в памяти + файл для persistence) ────────────────────
DATA_FILE = "payments.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

payments_db = load_data()  # {"05.03.26": [{"summa": 18.40, "time": "09:30", "otpravitel": "..."}, ...]}

# ─── Парсер сообщения ─────────────────────────────────────────────────────────
def parse_payment(text):
    summa_match = re.search(r"Summa\s+([\d.]+)\s+TJS", text, re.IGNORECASE)
    data_match  = re.search(r"Data\s+(\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{2})", text, re.IGNORECASE)
    otpr_match  = re.search(r"Otpravitel\s+(.+)", text, re.IGNORECASE)
    kod_match   = re.search(r"Kod\s+(\d+)", text, re.IGNORECASE)

    if not (summa_match and data_match):
        return None

    return {
        "summa":      float(summa_match.group(1)),
        "time":       data_match.group(1),
        "date":       data_match.group(2),
        "otpravitel": otpr_match.group(1).strip() if otpr_match else "—",
        "kod":        kod_match.group(1) if kod_match else "—",
        "raw":        text.strip(),
    }

# ─── Форматирование отчёта ────────────────────────────────────────────────────
def format_daily_report(day=None):
    if day is None:
        day = date.today().strftime("%d.%m.%y")

    records = payments_db.get(day, [])
    if not records:
        return f"📅 {day}\nПлатежей пока нет."

    total = sum(r["summa"] for r in records)
    lines = [f"📅 *{day}* — итого: *{total:.2f} TJS*", ""]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. {r['time']}  +{r['summa']:.2f} TJS  ({r['otpravitel']})")

    return "\n".join(lines)

def format_all_report():
    if not payments_db:
        return "Данных пока нет."
    lines = ["📊 *Все платежи по дням:*", ""]
    grand = 0
    for day in sorted(payments_db.keys()):
        records = payments_db[day]
        total = sum(r["summa"] for r in records)
        grand += total
        lines.append(f"📅 {day}: *{total:.2f} TJS* ({len(records)} платежей)")
    lines += ["", f"💰 *Общий итог: {grand:.2f} TJS*"]
    return "\n".join(lines)

# ─── Клиент ──────────────────────────────────────────────────────────────────
if SESSION:
    from telethon.sessions import StringSession
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
else:
    client = TelegramClient("payment_session", API_ID, API_HASH)

# ─── Обработка входящих сообщений от бота банка ──────────────────────────────
@client.on(events.NewMessage(from_users=SOURCE_BOT))
async def handle_bank_message(event):
    text = event.raw_text
    if "Zachislenie" not in text and "zachislenie" not in text:
        return

    payment = parse_payment(text)
    if not payment:
        return

    day = payment["date"]
    if day not in payments_db:
        payments_db[day] = []

    # Защита от дублей по коду
    existing_kods = {r["kod"] for r in payments_db[day]}
    if payment["kod"] in existing_kods:
        return

    payments_db[day].append(payment)
    save_data(payments_db)

    # Отправить подтверждение себе или в REPORT_BOT
    target = REPORT_BOT or "me"
    day_total = sum(r["summa"] for r in payments_db[day])

    await client.send_message(
        target,
        f"✅ +{payment['summa']:.2f} TJS  [{payment['time']}]\n"
        f"От: {payment['otpravitel']}\n"
        f"📅 За {day}: *{day_total:.2f} TJS* ({len(payments_db[day])} платежей)",
        parse_mode="markdown"
    )

# ─── Команды управления (пишешь себе в Saved Messages) ───────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^/today$"))
async def cmd_today(event):
    if event.is_private and (await event.get_chat()).id != (await client.get_me()).id:
        return
    await event.reply(format_daily_report(), parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^/all$"))
async def cmd_all(event):
    if event.is_private and (await event.get_chat()).id != (await client.get_me()).id:
        return
    await event.reply(format_all_report(), parse_mode="markdown")

@client.on(events.NewMessage(outgoing=True, pattern=r"^/day (.+)$"))
async def cmd_day(event):
    if event.is_private and (await event.get_chat()).id != (await client.get_me()).id:
        return
    day = event.pattern_match.group(1).strip()
    await event.reply(format_daily_report(day), parse_mode="markdown")

# ─── Запуск ───────────────────────────────────────────────────────────────────
print("✅ Userbot запущен. Мониторинг платежей активен.")
print("Команды в Saved Messages: /today  /all  /day DD.MM.YY")

with client.start(phone=lambda: PHONE):
    client.run_until_disconnected()
