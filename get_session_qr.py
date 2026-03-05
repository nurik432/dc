"""
Авторизация через QR-код — без SMS и кода.
Запусти скрипт, отсканируй QR с телефона и получи SESSION_STRING.

pip install telethon qrcode[pil] pillow
python get_session_qr.py
"""
import asyncio
import qrcode
import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError

API_ID   = input("API_ID: ").strip()
API_HASH = input("API_HASH: ").strip()

async def main():
    client = TelegramClient(StringSession(), int(API_ID), API_HASH)
    await client.connect()

    print("\n⏳ Генерирую QR-код...\n")

    qr_login = await client.qr_login()

    def display_qr(url):
        # Показать QR в терминале
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        print(f"\nИли ссылка напрямую:\n{url}\n")

    display_qr(qr_login.url)
    print("📱 Открой Telegram на телефоне:")
    print("   Настройки → Устройства → Подключить устройство → Сканировать QR\n")
    print("⏳ Жду сканирования (60 сек)...\n")

    try:
        # Ждём пока пользователь отсканирует
        await qr_login.wait(timeout=60)
    except SessionPasswordNeededError:
        # Если включена двухфакторная аутентификация
        password = input("🔐 Введи пароль двухфакторной аутентификации: ")
        await client.sign_in(password=password)
    except Exception as e:
        print(f"Ошибка: {e}")
        print("Попробуй запустить скрипт заново.")
        await client.disconnect()
        return

    me = await client.get_me()
    session_string = client.session.save()

    print(f"\n✅ Успешно! Привет, {me.first_name}!\n")
    print("=" * 60)
    print("SESSION_STRING (скопируй в Railway → Variables):")
    print()
    print(session_string)
    print()
    print("=" * 60)

    # Сохранить в файл на случай если потеряешь
    with open("session_string.txt", "w") as f:
        f.write(session_string)
    print("\n💾 Также сохранено в файл session_string.txt")

    await client.disconnect()

asyncio.run(main())
