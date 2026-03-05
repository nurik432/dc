import os
import re
import json
from datetime import date
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ─── Настройки ───────────────────────────────────────────────────────────────
API_ID     = int(os.environ["API_ID"])
API_HASH   = os.environ["API_HASH"]
PHONE      = os.environ.get("PHONE", "")
SOURCE_BOT = os.environ["SOURCE_BOT"]
SESSION    = os.environ.get("SESSION_STRING", "")

# ─── Хранилище ────────────────────────────────────────────────────────────────
DATA_FILE = "payments.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

db = load_data()

# ─── Парсер ───────────────────────────────────────────────────────────────────
def parse_payment(text):
    s = re.search(r"Summa\s+([\d.]+)\s+TJS", text, re.I)
    d = re.search(r"Data\s+(\d{2}:\d{2})\s+(\d{2}\.\d{2}\.\d{2})", text, re.I)
    o = re.search(r"Otpravitel\s+(.+)", text, re.I)
    k = re.search(r"Kod\s+(\d+)", text, re.I)
    if not (s and d):
        return None
    return {
        "summa":      float(s.group(1)),
        "time":       d.group(1),
        "date":       d.group(2),
        "otpravitel": o.group(1).strip() if o else "—",
        "kod":        k.group(1) if k else "—",
    }

# ─── Форматирование ───────────────────────────────────────────────────────────
def fmt_today():
    day = date.today().strftime("%d.%m.%y")
    records = db.get(day, [])
    if not records:
        return f"📅 {day}\n\nПлатежей пока нет."
    total = sum(r["summa"] for r in records)
    lines = [
        f"📅 {day}",
        f"💰 Итого: {total:.2f} TJS",
        f"📝 Транзакций: {len(records)}",
        "─" * 22,
    ]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. {r['time']}  +{r['summa']:.2f} TJS  👤 {r['otpravitel']}")
    return "\n".join(lines)

def fmt_history():
    if not db:
        return "📊 История\n\nДанных пока нет."
    lines = ["📊 История по дням", ""]
    grand = 0
    days = sorted(db.keys(), key=lambda x: (x[6:], x[3:5], x[:2]))
    for day in days:
        records = db[day]
        total = sum(r["summa"] for r in records)
        grand += total
        lines.append(f"📅 {day}  —  {total:.2f} TJS  ({len(records)} шт)")
    lines += ["", "─" * 22, f"💎 Всего: {grand:.2f} TJS"]
    return "\n".join(lines)

def fmt_help():
    return (
        "📋 Команды:\n\n"
        "/today — платежи за сегодня\n"
        "/all — история по всем дням\n"
        "/day DD.MM.YY — конкретный день\n"
        "/help — это сообщение"
    )

# ─── Клиент ──────────────────────────────────────────────────────────────────
if SESSION:
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)

# ─── Слушаем банковский бот ───────────────────────────────────────────────────
@client.on(events.NewMessage(from_users=SOURCE_BOT))
async def on_payment(event):
    text = event.raw_text
    if "zachislenie" not in text.lower():
        return

    payment = parse_payment(text)
    if not payment:
        return

    day = payment["date"]
    if day not in db:
        db[day] = []

    if payment["kod"] in {r["kod"] for r in db[day]}:
        return

    db[day].append(payment)
    save_data(db)

    day_total = sum(r["summa"] for r in db[day])
    count = len(db[day])

    await client.send_message(
        "me",
        f"✅ +{payment['summa']:.2f} TJS  [{payment['time']}]\n"
        f"👤 {payment['otpravitel']}\n"
        f"📅 За {day}: {day_total:.2f} TJS ({count} платежей)\n\n"
        f"Команды: /today  /all  /help"
    )

# ─── Команды в Избранном ──────────────────────────────────────────────────────
async def is_saved_messages(event):
    me = await client.get_me()
    chat = await event.get_chat()
    return chat.id == me.id

@client.on(events.NewMessage(outgoing=True, pattern=r"^/today$"))
async def cmd_today(event):
    if not await is_saved_messages(event):
        return
    await event.respond(fmt_today())

@client.on(events.NewMessage(outgoing=True, pattern=r"^/all$"))
async def cmd_all(event):
    if not await is_saved_messages(event):
        return
    await event.respond(fmt_history())

@client.on(events.NewMessage(outgoing=True, pattern=r"^/day (.+)$"))
async def cmd_day(event):
    if not await is_saved_messages(event):
        return
    day = event.pattern_match.group(1).strip()
    records = db.get(day, [])
    if not records:
        await event.respond(f"📅 {day}\n\nПлатежей нет.")
        return
    total = sum(r["summa"] for r in records)
    lines = [f"📅 {day}", f"💰 Итого: {total:.2f} TJS", "─" * 22]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. {r['time']}  +{r['summa']:.2f} TJS  👤 {r['otpravitel']}")
    await event.respond("\n".join(lines))

@client.on(events.NewMessage(outgoing=True, pattern=r"^/help$"))
async def cmd_help(event):
    if not await is_saved_messages(event):
        return
    await event.respond(fmt_help())

# ─── Запуск ───────────────────────────────────────────────────────────────────
print("✅ Бот запущен!")
print("Команды в Избранном: /today  /all  /day DD.MM.YY  /help")

with client.start(phone=lambda: PHONE):
    client.run_until_disconnected()
