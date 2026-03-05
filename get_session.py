"""
Запусти этот скрипт ОДИН РАЗ локально, чтобы получить SESSION_STRING
для Railway. После этого bot.py можно деплоить без телефона рядом.

pip install telethon
python get_session.py
"""
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID   = input("API_ID: ").strip()
API_HASH = input("API_HASH: ").strip()
PHONE    = input("Номер телефона (+992...): ").strip()

async def main():
    async with TelegramClient(StringSession(), int(API_ID), API_HASH) as client:
        await client.start(phone=lambda: PHONE)
        session_string = client.session.save()
        print("\n" + "="*60)
        print("SESSION_STRING (скопируй в Railway):")
        print(session_string)
        print("="*60)

asyncio.run(main())
