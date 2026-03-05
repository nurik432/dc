import os
import re
import json
from datetime import date
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession

# ─── Настройки ───────────────────────────────────────────────────────────────
API_ID      = int(os.environ["API_ID"])
API_HASH    = os.environ["API_HASH"]
PHONE       = os.environ.get("PHONE", "")
SOURCE_BOT  = os.environ["SOURCE_BOT"]       # username бота банка (без @)
SESSION     = os.environ.get("SESSION_STRING", "")

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
        return f"📅 **{day}**\n\nПлатежей пока нет."
    total = sum(r["summa"] for r in records)
    lines = [f"📅 **{day}**", f"💰 Итого: **{total:.2f} TJS**", f"📝 Транзакций: {len(records)}", "─" * 24]
    for i, r in enumerate(records, 1):
        lines.append(f"{i}. `{r['time']}`  +**{r['summa']:.2f}** TJS\n    👤 {r['otpravitel']}")
    return "\n".join(lines)

def fmt_history():
    if not db:
        return "📊 **История**\n\nДанных пока нет."
    lines = ["📊 **История по дням**", ""]
    grand = 0
    days = sorted(db.keys(), key=lambda x: (x[6:], x[3:5], x[:2]))
    for day in days:
        records = db[day]
        total = sum(r["summa"] for r in records)
        grand += total
        bar_count = min(10, round(total / 50))
        bar = "█" * bar_count + "░" * (10 - bar_count)
        lines.append(f"📅 `{day}`  {bar}  **{total:.2f}** TJS  ({len(records)} шт)")
    lines += ["", "━" * 24, f"💎 **Всего: {grand:.2f} TJS**"]
    return "\n".join(lines)

# ─── Меню ────────────────────────────────────────────────────────────────────
MENU_BUTTONS = [
    [Button.inline("📅 Сегодня", b"today"), Button.inline("📊 История", b"history")],
    [Button.inline("🔄 Обновить", b"menu")],
]

def menu_text():
    day = date.today().strftime("%d.%m.%y")
    records = db.get(day, [])
    total_today = sum(r["summa"] for r in records)
    grand = sum(sum(r["summa"] for r in v) for v in db.values())
    return (
        f"💳 **Payment Tracker**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 Сегодня ({day}): **{total_today:.2f} TJS**\n"
        f"💰 За всё время: **{grand:.2f} TJS**\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Выбери раздел 👇"
    )

# ─── Клиент ──────────────────────────────────────────────────────────────────
if SESSION:
    client = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
else:
    client = TelegramClient("session", API_ID, API_HASH)

# ─── Новое зачисление от бота банка ──────────────────────────────────────────
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
        f"✅ Новое зачисление!\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💵 +**{payment['summa']:.2f} TJS**  🕐 {payment['time']}\n"
        f"👤 {payment['otpravitel']}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📅 За {day}: **{day_total:.2f} TJS** ({count} платежей)",
        buttons=MENU_BUTTONS,
        parse_mode="markdown"
    )

# ─── /menu ────────────────────────────────────────────────────────────────────
@client.on(events.NewMessage(outgoing=True, pattern=r"^/menu$"))
async def cmd_menu(event):
    me = await client.get_me()
    chat = await event.get_chat()
    if chat.id != me.id:
        return
    await event.delete()
    await client.send_message("me", menu_text(), buttons=MENU_BUTTONS, parse_mode="markdown")

# ─── Кнопки ──────────────────────────────────────────────────────────────────
@client.on(events.CallbackQuery(data=b"today"))
async def cb_today(event):
    await event.answer()
    await event.edit(fmt_today(), buttons=[[Button.inline("🔙 Назад", b"menu")]], parse_mode="markdown")

@client.on(events.CallbackQuery(data=b"history"))
async def cb_history(event):
    await event.answer()
    await event.edit(fmt_history(), buttons=[[Button.inline("🔙 Назад", b"menu")]], parse_mode="markdown")

@client.on(events.CallbackQuery(data=b"menu"))
async def cb_menu(event):
    await event.answer()
    await event.edit(menu_text(), buttons=MENU_BUTTONS, parse_mode="markdown")

# ─── Запуск ───────────────────────────────────────────────────────────────────
print("✅ Бот запущен. Напиши /menu в Избранное для управления.")

with client.start(phone=lambda: PHONE):
    client.run_until_disconnected()
