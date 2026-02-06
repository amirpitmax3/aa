import asyncio
import logging
import os
import re
import secrets
import contextlib
from threading import Thread
import time
from flask import Flask
from urllib.parse import quote
import aiohttp
import random
import html
import traceback
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton,
                      InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove)
from telegram.constants import ParseMode
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ConversationHandler, filters, ContextTypes, CallbackQueryHandler,
                          ApplicationHandlerStop, TypeHandler)
import telegram.error

from pyrogram import Client, filters as py_filters
from pyrogram.handlers import MessageHandler as PyMessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.raw import functions
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid,
    PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ChatSendInlineForbidden
)
import pyrogram.utils

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

def patch_peer_id_validation():
    original_get_peer_type = pyrogram.utils.get_peer_type
    def patched_get_peer_type(peer_id: int) -> str:
        try:
            return original_get_peer_type(peer_id)
        except ValueError:
            if str(peer_id).startswith("-100"):
                return "channel"
            raise
    pyrogram.utils.get_peer_type = patched_get_peer_type

patch_peer_id_validation()

# 🔴 تنظیمات اصلی وارد شده
BOT_TOKEN = "8340821170:AAGrJSp-fqDituAOTq7N3CTt0YBZKnfFJ3k"
OWNER_ID = 7423552124
MONGO_URI = "mongodb+srv://amirpitmax1_db_user:DvkIhwWzUfBT4L5j@cluster0.kdvbr3p.mongodb.net/?appName=Cluster0"
DB_NAME = "telegram_bot_data"

API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")

try:
    mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
    db = mongo_client[DB_NAME]
    mongo_client.server_info()
    logging.info("✅ Connected to MongoDB successfully.")
except Exception as e:
    logging.error(f"❌ Failed to connect to MongoDB: {e}")
    db = None

GLOBAL_USERS = {}
GLOBAL_SETTINGS = {}
GLOBAL_TRANSACTIONS = {}
GLOBAL_BETS = {}
GLOBAL_CHANNELS = {}
ACTIVE_BOTS = {} 
LOGIN_TEMP_DATA = {} 

TX_ID_COUNTER = 1
BET_ID_COUNTER = 1

FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'７','8':'۸','9':'۹',':':'：'},
    "filled":       {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':':'},
    "sans":         {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "inverted":     {'0':'0','1':'Ɩ','2':'ᄅ','3':'Ɛ','4':'ㄣ','5':'ϛ','6':'9','7':'ㄥ','8':'8','9':'6',':':':'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth", "filled", "sans", "inverted"]
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
SECRETARY_MODE_STATUS = {}
USERS_REPLIED_IN_SECRETARY = {}
MUTED_USERS = {}
USER_FONT_CHOICES = {}
CLOCK_STATUS = {}
BOLD_MODE_STATUS = {}
AUTO_SEEN_STATUS = {}
AUTO_REACTION_TARGETS = {}
AUTO_TRANSLATE_TARGET = {}
ANTI_LOGIN_STATUS = {}
COPY_MODE_STATUS = {}
ORIGINAL_PROFILE_DATA = {}
GLOBAL_ENEMY_STATUS = {}
TYPING_MODE_STATUS = {}
PLAYING_MODE_STATUS = {}
PV_LOCK_STATUS = {}

ENEMY_REPLIES = ["ببخشید متوجه نشدم؟", "داری فشار میخوری؟", "برو پیش بزرگترت", "سطحت پایینه", "😂😂", "اوکی بای"] 
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

HELP_TEXT = """
**[ 🛠 𝐃𝐀𝐑𝐊𝐒𝐄𝐋𝐅 𝐓𝐎𝐎𝐋𝐒 ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی (ساعت، فونت، منشی و...) فقط از طریق دستور **`پنل`** قابل دسترسی هستند.

**✦ 𝐂𝐡𝐚𝐭 𝐌𝐚𝐧𝐚𝐠𝐞𝐫**
  » `حذف [تعداد]` 
  » `ذخیره` (ریپلای روی پیام)
  » `تکرار [تعداد]` (ریپلای روی پیام)
  » `کپی روشن` | `کپی خاموش` (ریپلای روی کاربر)

**✦ 𝐒𝐞𝐜𝐮𝐫𝐢𝐭𝐲**
  » `دشمن روشن` | `خاموش` (ریپلای روی کاربر)
  » `لیست دشمن`
  » `بلاک روشن` | `بلاک خاموش` (ریپلای روی کاربر)
  » `سکوت روشن` | `سکوت خاموش` (ریپلای روی کاربر)
  » `ریاکشن [شکلک]` | `خاموش` (ریپلای روی کاربر)

**✦ 𝐅𝐮𝐧**
  » `تاس` | `تاس [عدد]`
  » `بولینگ`
━━━━━━━━━━━━━━━━━━━━
"""
COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|پنل|panel)$"


def init_memory_db():
    global TX_ID_COUNTER, BET_ID_COUNTER
    logging.info("Initializing database (Loading from MongoDB)...")
    
    if db is not None:
        try:
            for doc in db.settings.find():
                GLOBAL_SETTINGS[doc['_id']] = doc['value']
        except Exception as e: logging.error(f"Error loading settings: {e}")

        try:
            for doc in db.users.find():
                user_id = int(doc['user_id'])
                GLOBAL_USERS[user_id] = doc
        except Exception as e: logging.error(f"Error loading users: {e}")

        try:
            max_tx_id = 0
            for doc in db.transactions.find():
                tx_id = int(doc['tx_id'])
                GLOBAL_TRANSACTIONS[tx_id] = doc
                if tx_id > max_tx_id: max_tx_id = tx_id
            TX_ID_COUNTER = max_tx_id + 1
        except Exception as e: logging.error(f"Error loading transactions: {e}")

        try:
            max_bet_id = 0
            for doc in db.bets.find():
                bet_id = int(doc['bet_id'])
                GLOBAL_BETS[bet_id] = doc
                if bet_id > max_bet_id: max_bet_id = bet_id
            BET_ID_COUNTER = max_bet_id + 1
        except Exception as e: logging.error(f"Error loading bets: {e}")

        try:
            for doc in db.channels.find():
                GLOBAL_CHANNELS[doc['channel_username']] = doc
        except Exception as e: logging.error(f"Error loading channels: {e}")

    default_settings = {
        'credit_price': '1000',
        'initial_balance': '10',
        'referral_reward': '5',
        'bet_tax_rate': '2',
        'card_number': 'هنوز تنظیم نشده',
        'card_holder': 'هنوز تنظیم نشده',
        'bet_photo_file_id': 'None',
        'panel_photo_file_id': 'None', 
        'forced_channel_lock': 'false',
        'self_hourly_cost': '1',
        'self_min_balance': '10'
    }
    
    for key, value in default_settings.items():
        if key not in GLOBAL_SETTINGS:
            GLOBAL_SETTINGS[key] = value
    
    logging.info(f"Database loaded. Users: {len(GLOBAL_USERS)}")

def background_db_sync():
    while True:
        if db is None:
            time.sleep(20)
            continue
        try:
            for user_id, data in list(GLOBAL_USERS.items()):
                db.users.replace_one({'user_id': user_id}, data, upsert=True)
            for key, value in list(GLOBAL_SETTINGS.items()):
                db.settings.replace_one({'_id': key}, {'value': value}, upsert=True)
            for tx_id, data in list(GLOBAL_TRANSACTIONS.items()):
                db.transactions.replace_one({'tx_id': tx_id}, data, upsert=True)
            for bet_id, data in list(GLOBAL_BETS.items()):
                db.bets.replace_one({'bet_id': bet_id}, data, upsert=True)
            for ch_username, data in list(GLOBAL_CHANNELS.items()):
                db.channels.replace_one({'channel_username': ch_username}, data, upsert=True)
        except Exception as e:
            logging.error(f"Error in DB Sync loop: {e}")
        time.sleep(10)

def save_user_immediate(user_id):
    if db is None or user_id not in GLOBAL_USERS: return
    try:
        db.users.replace_one({'user_id': user_id}, GLOBAL_USERS[user_id], upsert=True)
    except Exception as e: logging.error(f"Immediate save failed for {user_id}: {e}")

async def get_setting_async(name):
    return GLOBAL_SETTINGS.get(name)

async def set_setting_async(name, value):
    GLOBAL_SETTINGS[name] = str(value)
    if db is not None:
        try:
            db.settings.replace_one({'_id': name}, {'value': str(value)}, upsert=True)
        except: pass

async def get_user_async(user_id):
    user_doc = None
    if user_id in GLOBAL_USERS:
        user_doc = GLOBAL_USERS[user_id]
        if 'vip_balance' not in user_doc: user_doc['vip_balance'] = 0
    else:
        try:
            initial_balance_val = int(GLOBAL_SETTINGS.get('initial_balance', '10'))
        except: initial_balance_val = 10

        is_owner = (user_id == OWNER_ID)
        balance_on_create = 1000000000 if is_owner else initial_balance_val

        new_user_doc = {
            'user_id': user_id,
            'balance': balance_on_create,
            'vip_balance': 0,
            'is_admin': is_owner,
            'is_owner': is_owner,
            'referred_by': None,
            'is_moderator': False,
            'username': None,
            'first_name': None 
        }
        GLOBAL_USERS[user_id] = new_user_doc
        user_doc = new_user_doc
        if db is not None:
            try: db.users.replace_one({'user_id': user_id}, new_user_doc, upsert=True)
            except: pass
    
    if user_id == OWNER_ID:
        if not user_doc.get('is_owner') or not user_doc.get('is_admin'):
            user_doc['is_owner'] = True; user_doc['is_admin'] = True; save_user_immediate(user_id)
    elif user_doc.get('is_owner') and user_id != OWNER_ID:
        user_doc['is_owner'] = False; user_doc['is_admin'] = False; user_doc['is_moderator'] = False; user_doc['balance'] = 0
        save_user_immediate(user_id)
    return user_doc

def get_user_display_name(user):
    if user.id in GLOBAL_USERS:
        GLOBAL_USERS[user.id]['username'] = user.username
        GLOBAL_USERS[user.id]['first_name'] = user.first_name
    if user.username: return f"@{user.username}"
    return html.escape(user.first_name + (f" {user.last_name}" if user.last_name else ""))

def get_session_from_db(user_id):
    if db is None: return None
    return db.sessions.find_one({'user_id': user_id})

def save_session_to_db(user_id, phone, session_string):
    if db is None: return
    db.sessions.replace_one(
        {'user_id': user_id}, 
        {'user_id': user_id, 'phone_number': phone, 'session_string': session_string, 'font_style': 'stylized'},
        upsert=True
    )

def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def translate_text(text: str, target_lang: str) -> str:
    if not text: return ""
    encoded_text = quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0][0][0]
    except: pass
    return text

async def perform_clock_update_now(client, user_id):
    try:
        if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
            current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
            me = await client.get_me()
            current_name = me.first_name
            base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()
            
            tehran_time = datetime.now(TEHRAN_TIMEZONE)
            current_time_str = tehran_time.strftime("%H:%M")
            stylized_time = stylize_time(current_time_str, current_font_style)
            new_name = f"{base_name} {stylized_time}"
            
            if new_name != current_name:
                await client.update_profile(first_name=new_name)
    except Exception as e:
        logging.error(f"Immediate clock update failed for {user_id}: {e}")

async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                await perform_clock_update_now(client, user_id)
            now = datetime.now(TEHRAN_TIMEZONE)
            await asyncio.sleep(60 - now.second + 0.1)
        except Exception:
            await asyncio.sleep(60)

async def anti_login_task(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False):
                auths = await client.invoke(functions.account.GetAuthorizations())
                current_hash = next((a.hash for a in auths.authorizations if a.current), None)
                if current_hash:
                    for auth in auths.authorizations:
                        if auth.hash != current_hash:
                            await client.invoke(functions.account.ResetAuthorization(hash=auth.hash))
                            await client.send_message("me", f"🚨 نشست غیرمجاز حذف شد: {auth.device_model}")
            await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(120)

async def status_action_task(client: Client, user_id: int):
    chat_ids = []
    last_fetch = 0
    while user_id in ACTIVE_BOTS:
        try:
            typing = TYPING_MODE_STATUS.get(user_id, False)
            playing = PLAYING_MODE_STATUS.get(user_id, False)
            if not typing and not playing:
                await asyncio.sleep(2)
                continue
            action = ChatAction.TYPING if typing else ChatAction.PLAYING
            now = time.time()
            if not chat_ids or (now - last_fetch > 300):
                new_chats = []
                async for dialog in client.get_dialogs(limit=30):
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chats.append(dialog.chat.id)
                chat_ids = new_chats
                last_fetch = now
            for chat_id in chat_ids:
                try: await client.send_chat_action(chat_id, action)
                except: pass
            await asyncio.sleep(4)
        except Exception:
            await asyncio.sleep(60)

async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    if not message.text or re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE): return
    original_text = message.text
    modified_text = original_text
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang: modified_text = await translate_text(modified_text, target_lang)
    if BOLD_MODE_STATUS.get(user_id, False):
        if not modified_text.startswith(('`', '**', '__', '~~', '||')): modified_text = f"**{modified_text}**"
    if modified_text != original_text:
        try: await message.edit_text(modified_text)
        except: pass

async def enemy_handler(client, message):
    user_id = client.me.id
    if not ENEMY_REPLIES: return 
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try: await message.reply_text(reply_text)
    except: pass

async def secretary_auto_reply_handler(client, message):
    owner_id = client.me.id
    if message.from_user and SECRETARY_MODE_STATUS.get(owner_id, False):
        target_id = message.from_user.id
        replied = USERS_REPLIED_IN_SECRETARY.get(owner_id, set())
        if target_id not in replied:
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied.add(target_id)
                USERS_REPLIED_IN_SECRETARY[owner_id] = replied
            except: pass

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    if emoji := AUTO_REACTION_TARGETS.get(user_id, {}).get(message.from_user.id):
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except: pass
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(user_id, set()):
        try: await message.delete()
        except: pass

async def help_controller(client, message):
    try: await message.edit_text(HELP_TEXT)
    except: await message.reply_text(HELP_TEXT)

async def panel_command_controller(client, message):
    photo_id = GLOBAL_SETTINGS.get('panel_photo_file_id')
    user_id = client.me.id
    caption_text = f"⚡️ **کنترل پنل کاربری**\n👤 کاربر: `{user_id}`\n\nوضعیت: ✅ فعال"
    try:
        if photo_id and photo_id != 'None':
            await message.delete()
            await client.send_photo(message.chat.id, photo_id, caption=caption_text)
        else:
            await message.edit_text(caption_text)
    except Exception as e:
        await message.reply_text(f"❌ خطا: {e}")

async def reply_based_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    if cmd == "تاس": await client.send_dice(message.chat.id, "🎲")
    elif cmd == "بولینگ": await client.send_dice(message.chat.id, "🎳")
    elif cmd.startswith("تاس "): 
        try: await client.send_dice(message.chat.id, "🎲", reply_to_message_id=message.reply_to_message_id)
        except: pass
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(user_id, set())
        await message.edit_text(f"📜 تعداد دشمنان فعال: {len(enemies)}")
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id if message.reply_to_message.from_user else None
        if cmd.startswith("حذف "):
            try:
                count = int(cmd.split()[1])
                msg_ids = [m.id async for m in client.get_chat_history(message.chat.id, limit=count) if m.from_user and m.from_user.is_self]
                if msg_ids: await client.delete_messages(message.chat.id, msg_ids)
                await message.delete()
            except: pass
        elif cmd == "ذخیره":
            await message.reply_to_message.forward("me")
            await message.edit_text("💾 ذخیره شد.")
        elif cmd.startswith("تکرار "):
            try:
                count = int(cmd.split()[1])
                for _ in range(count): await message.reply_to_message.copy(message.chat.id)
                await message.delete()
            except: pass
        elif target_id:
            if cmd == "کپی روشن":
                user = await client.get_chat(target_id)
                me = await client.get_me()
                ORIGINAL_PROFILE_DATA[user_id] = {'first_name': me.first_name, 'bio': me.bio}
                COPY_MODE_STATUS[user_id] = True
                CLOCK_STATUS[user_id] = False
                target_photos = [p async for p in client.get_chat_photos(target_id, limit=1)]
                await client.update_profile(first_name=user.first_name, bio=(user.bio or "")[:70])
                if target_photos: await client.set_profile_photo(photo=target_photos[0].file_id)
                await message.edit_text("👤 هویت جعل شد.")
            elif cmd == "کپی خاموش":
                if user_id in ORIGINAL_PROFILE_DATA:
                    data = ORIGINAL_PROFILE_DATA[user_id]
                    COPY_MODE_STATUS[user_id] = False
                    await client.update_profile(first_name=data.get('first_name'), bio=data.get('bio'))
                    await message.edit_text("👤 هویت بازگردانده شد.")
            elif cmd == "دشمن روشن":
                s = ACTIVE_ENEMIES.get(user_id, set()); s.add((target_id, message.chat.id)); ACTIVE_ENEMIES[user_id] = s
                await message.edit_text("⚔️ دشمن اضافه شد.")
            elif cmd == "دشمن خاموش":
                s = ACTIVE_ENEMIES.get(user_id, set()); s.discard((target_id, message.chat.id)); ACTIVE_ENEMIES[user_id] = s
                await message.edit_text("🏳️ دشمن حذف شد.")
            elif cmd == "بلاک روشن": await client.block_user(target_id); await message.edit_text("🚫 کاربر بلاک شد.")
            elif cmd == "بلاک خاموش": await client.unblock_user(target_id); await message.edit_text("⭕️ کاربر آنبلاک شد.")
            elif cmd == "سکوت روشن":
                s = MUTED_USERS.get(user_id, set()); s.add((target_id, message.chat.id)); MUTED_USERS[user_id] = s
                await message.edit_text("🔇 کاربر ساکت شد.")
            elif cmd == "سکوت خاموش":
                s = MUTED_USERS.get(user_id, set()); s.discard((target_id, message.chat.id)); MUTED_USERS[user_id] = s
                await message.edit_text("🔊 کاربر از سکوت خارج شد.")
            elif cmd.startswith("ریاکشن ") and cmd != "ریاکشن خاموش":
                emoji = cmd.split()[1]
                t = AUTO_REACTION_TARGETS.get(user_id, {}); t[target_id] = emoji; AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text(f"👍 واکنش {emoji} تنظیم شد.")
            elif cmd == "ریاکشن خاموش":
                t = AUTO_REACTION_TARGETS.get(user_id, {}); t.pop(target_id, None); AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text("❌ واکنش حذف شد.")

async def start_bot_instance(session_string: str, phone: str, font_style: str, user_id_tg: int, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
    try:
        await client.start()
        me = await client.get_me()
        user_id = me.id 
        if user_id_tg != 0 and user_id != user_id_tg:
             logging.warning(f"Mismatch user ID for phone {phone}")
    except Exception as e:
        logging.error(f"Failed to start self-bot for {phone}: {e}")
        return

    if user_id in ACTIVE_BOTS:
        try:
            await ACTIVE_BOTS[user_id][0].stop()
            for t in ACTIVE_BOTS[user_id][1]: t.cancel()
        except: pass
    
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    
    client.add_handler(PyMessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, py_filters.private & ~py_filters.me & ~py_filters.bot), group=-5)
    client.add_handler(PyMessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, py_filters.private & ~py_filters.me), group=-4)
    client.add_handler(PyMessageHandler(incoming_message_manager, py_filters.all & ~py_filters.me), group=-3)
    client.add_handler(PyMessageHandler(outgoing_message_modifier, py_filters.text & py_filters.me & ~py_filters.reply), group=-1)
    client.add_handler(PyMessageHandler(help_controller, py_filters.me & py_filters.regex("^راهنما$")))
    client.add_handler(PyMessageHandler(panel_command_controller, py_filters.me & py_filters.regex(r"^(پنل|panel)$")))
    client.add_handler(PyMessageHandler(reply_based_controller, py_filters.me)) 
    client.add_handler(PyMessageHandler(enemy_handler, py_filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~py_filters.me), group=1)
    client.add_handler(PyMessageHandler(secretary_auto_reply_handler, py_filters.private & ~py_filters.me), group=1)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)
    logging.info(f"Self-bot started for user {user_id}")


web_app = Flask(__name__)
@web_app.route('/')
def health_check(): return "Bot is running with merged features.", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

(ADMIN_MENU, AWAIT_ADMIN_REPLY,
 AWAIT_DEPOSIT_AMOUNT, AWAIT_DEPOSIT_RECEIPT,
 AWAIT_SUPPORT_MESSAGE, AWAIT_ADMIN_SUPPORT_REPLY,
 AWAIT_NEW_CHANNEL, AWAIT_BET_PHOTO,
 AWAIT_ADMIN_SET_BALANCE, AWAIT_ADMIN_TAX, AWAIT_ADMIN_CREDIT_PRICE,
 AWAIT_ADMIN_REFERRAL_PRICE, AWAIT_ADMIN_SET_BALANCE_ID,
 AWAIT_MANAGE_USER_ID, AWAIT_MANAGE_USER_ROLE,
 AWAIT_ADMIN_SET_CARD_NUMBER, AWAIT_ADMIN_SET_CARD_HOLDER,
 AWAIT_ADMIN_ADD_BALANCE_ID, AWAIT_ADMIN_ADD_BALANCE_AMOUNT, 
 AWAIT_ADMIN_DEDUCT_BALANCE_ID, AWAIT_ADMIN_DEDUCT_BALANCE_AMOUNT,
 AWAIT_BROADCAST_MESSAGE,
 AWAIT_ADMIN_SELF_COST, AWAIT_ADMIN_SELF_MIN_BALANCE,
 AWAIT_ADMIN_PANEL_PHOTO, 
 SELF_LOGIN_PHONE, SELF_LOGIN_CODE, SELF_LOGIN_PASSWORD
) = range(28)

def get_main_keyboard(user_doc):
    if user_doc.get('is_owner'):
        keyboard = [
            [KeyboardButton("💳 موجودی حساب"), KeyboardButton("👔 پنل مدیریت")],
            [KeyboardButton("🚀 فعال‌سازی سلف‌بات")]
        ]
    else:
        keyboard = [
            [KeyboardButton("💳 موجودی حساب"), KeyboardButton("💎 خرید الماس")],
            [KeyboardButton("🎁 دریافت هدیه"), KeyboardButton("💬 پشتیبانی آنلاین")],
            [KeyboardButton("🚀 فعال‌سازی سلف‌بات")]
        ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("👥 مدیریت کاربران"), KeyboardButton("📊 آمار ربات")],
    [KeyboardButton("💳 تنظیم کارت واریز"), KeyboardButton("👤 تنظیم صاحب کارت")],
    [KeyboardButton("➕ افزایش موجودی"), KeyboardButton("➖ کسر موجودی")],
    [KeyboardButton("💰 تعیین موجودی"), KeyboardButton("💲 قیمت الماس")],
    [KeyboardButton("🎁 پاداش دعوت"), KeyboardButton("📉 درصد مالیات")],
    [KeyboardButton("💎 هزینه سلف"), KeyboardButton("📉 کف موجودی سلف")],
    [KeyboardButton("➕ افزودن کانال"), KeyboardButton("➖ حذف کانال")],
    [KeyboardButton("🔒 قفل: فعال"), KeyboardButton("🔓 قفل: غیرفعال")],
    [KeyboardButton("🖼 تصویر شرط"), KeyboardButton("🗑 حذف تصویر شرط")],
    [KeyboardButton("🖼 تصویر پنل"), KeyboardButton("🗑 حذف تصویر پنل")], 
    [KeyboardButton("📢 ارسال همگانی")],
    [KeyboardButton("🔙 بازگشت")]
], resize_keyboard=True)

bet_group_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("💳 موجودی حساب")],
    [KeyboardButton("100"), KeyboardButton("500")],
    [KeyboardButton("1000"), KeyboardButton("5000")]
], resize_keyboard=True)


async def billing_loop(context: ContextTypes.DEFAULT_TYPE):
    try:
        cost_str = GLOBAL_SETTINGS.get('self_hourly_cost', '1')
        cost = int(cost_str)
        if cost <= 0: return

        active_users = list(ACTIVE_BOTS.keys())
        logging.info(f"Running billing task for {len(active_users)} active self-bots.")

        for user_id in active_users:
            user_doc = await get_user_async(user_id)
            if user_doc['balance'] >= cost:
                user_doc['balance'] -= cost
                save_user_immediate(user_id)
            else:
                client_tuple = ACTIVE_BOTS.pop(user_id, None)
                if client_tuple:
                    try:
                        await client_tuple[0].stop()
                        for task in client_tuple[1]: task.cancel()
                    except: pass
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⚠️ **هشدار:** موجودی الماس شما برای تمدید سلف‌بات کافی نبود و ربات خاموش شد.\n\n"
                             "💎 لطفا حساب خود را شارژ کنید و سپس دکمه **فعال‌سازی سلف** را بزنید تا مجددا فعال شود.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logging.warning(f"Failed to notify user {user_id} about billing: {e}")

    except Exception as e:
        logging.error(f"Error in billing loop: {e}")

async def self_activation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = await get_user_async(user.id)
    
    min_bal_str = GLOBAL_SETTINGS.get('self_min_balance', '10')
    try: min_bal = int(min_bal_str)
    except: min_bal = 10
    
    cost_str = GLOBAL_SETTINGS.get('self_hourly_cost', '1')
    
    if user_doc['balance'] < min_bal:
        await update.message.reply_text(
            f"⛔️ موجودی شما کافی نیست.\n\n"
            f"💎 حداقل موجودی برای فعال‌سازی سلف: {min_bal} الماس\n"
            f"💰 موجودی فعلی شما: {user_doc['balance']} الماس\n\n"
            f"لطفا ابتدا حساب خود را شارژ کنید.",
            reply_markup=get_main_keyboard(user_doc)
        )
        return ConversationHandler.END

    if user.id in ACTIVE_BOTS:
        await update.message.reply_text("✅ سلف‌بات شما هم‌اکنون فعال است.", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END
        
    session_doc = get_session_from_db(user.id)
    if session_doc:
        await update.message.reply_text("🔄 یافتن نشست قبلی... در حال راه‌اندازی مجدد سلف‌بات...", reply_markup=ReplyKeyboardRemove())
        asyncio.create_task(start_bot_instance(session_doc['session_string'], session_doc.get('phone_number'), session_doc.get('font_style', 'stylized'), user.id))
        await asyncio.sleep(2)
        if user.id in ACTIVE_BOTS:
             await update.message.reply_text(f"✅ سلف‌بات شما با موفقیت مجددا فعال شد.\n💎 هزینه: {cost_str} الماس در ساعت.", reply_markup=get_main_keyboard(user_doc))
             return ConversationHandler.END
        else:
             await update.message.reply_text("❌ نشست قبلی نامعتبر شده است. لطفا مجددا وارد شوید.")

    await update.message.reply_text(
        "📱 لطفا شماره موبایل خود را با استفاده از دکمه زیر ارسال کنید:\n"
        "این شماره برای فعال‌سازی سلف‌بات روی اکانت شما استفاده می‌شود.",
        reply_markup=ReplyKeyboardMarkup([[KeyboardButton("📱 ارسال شماره", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    )
    return SELF_LOGIN_PHONE

async def process_self_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not update.message.contact:
        await update.message.reply_text("❌ لطفا از دکمه ارسال شماره استفاده کنید.")
        return SELF_LOGIN_PHONE
    
    phone_number = update.message.contact.phone_number
    await update.message.reply_text("⏳ در حال اتصال به سرور تلگرام... لطفا صبر کنید...", reply_markup=ReplyKeyboardRemove())
    
    client = Client(f"login_{user.id}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    try:
        await client.connect()
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در اتصال: {e}", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

    try:
        sent_code = await client.send_code(phone_number)
        LOGIN_TEMP_DATA[user.id] = {
            'client': client,
            'phone': phone_number,
            'phone_code_hash': sent_code.phone_code_hash
        }
        await update.message.reply_text("✅ کد تایید ارسال شد. لطفا کد را وارد کنید (مثلا: 12345):")
        return SELF_LOGIN_CODE
    except Exception as e:
        await client.disconnect()
        await update.message.reply_text(f"❌ خطا در ارسال کد: {e}\nممکن است شماره اشتباه باشد.", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

async def process_self_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    code = re.sub(r"\D+", "", update.message.text) 
    
    if user.id not in LOGIN_TEMP_DATA:
        await update.message.reply_text("❌ نشست منقضی شد. دوباره تلاش کنید.", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END
        
    data = LOGIN_TEMP_DATA[user.id]
    client: Client = data['client']
    
    try:
        await client.sign_in(data['phone'], data['phone_code_hash'], code)
        return await finalize_login(update, context, client, data['phone'])
    except SessionPasswordNeeded:
        await update.message.reply_text("🔐 اکانت شما دارای رمز دو مرحله‌ای است. لطفا رمز عبور خود را وارد کنید:")
        return SELF_LOGIN_PASSWORD
    except (PhoneCodeInvalid, PhoneCodeExpired):
        await update.message.reply_text("❌ کد وارد شده اشتباه یا منقضی شده است. لطفا مجددا تلاش کنید (/cancel برای لغو).")
        return SELF_LOGIN_CODE
    except Exception as e:
        await client.disconnect()
        del LOGIN_TEMP_DATA[user.id]
        await update.message.reply_text(f"❌ خطا: {e}", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

async def process_self_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    password = update.message.text
    
    if user.id not in LOGIN_TEMP_DATA:
        await update.message.reply_text("❌ نشست منقضی شد.", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END
        
    data = LOGIN_TEMP_DATA[user.id]
    client: Client = data['client']
    
    try:
        await client.check_password(password)
        return await finalize_login(update, context, client, data['phone'])
    except PasswordHashInvalid:
        await update.message.reply_text("❌ رمز عبور اشتباه است. دوباره تلاش کنید:")
        return SELF_LOGIN_PASSWORD
    except Exception as e:
        await client.disconnect()
        del LOGIN_TEMP_DATA[user.id]
        await update.message.reply_text(f"❌ خطا: {e}", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

async def finalize_login(update, context, client, phone):
    user = update.effective_user
    try:
        session_string = await client.export_session_string()
        me = await client.get_me()
        await client.disconnect()
        
        save_session_to_db(user.id, phone, session_string)
        
        asyncio.create_task(start_bot_instance(session_string, phone, 'stylized', user.id))
        
        del LOGIN_TEMP_DATA[user.id]
        user_doc = await get_user_async(user.id)
        cost = GLOBAL_SETTINGS.get('self_hourly_cost', '1')
        
        await update.message.reply_text(
            f"✅ **سلف‌بات با موفقیت فعال شد!**\n\n"
            f"👤 متصل به اکانت: {me.first_name}\n"
            f"💎 هزینه سرویس: هر ساعت {cost} الماس کسر می‌شود.\n"
            f"⚙️ برای دسترسی به تنظیمات سلف، دستور `پنل` را در اکانت خود ارسال کنید.",
            reply_markup=get_main_keyboard(user_doc),
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در نهایی‌سازی: {e}", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = await get_user_async(update.effective_user.id)
    if not user_doc.get('is_owner'):
        await update.message.reply_text("⛔️ عدم دسترسی.")
        return ConversationHandler.END
    await update.message.reply_text("👑 پنل ادمین:", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    context.user_data['admin_choice'] = choice
    
    prompts = {
        "💳 تنظیم کارت واریز": (AWAIT_ADMIN_SET_CARD_NUMBER, "شماره کارت جدید:"),
        "👤 تنظیم صاحب کارت": (AWAIT_ADMIN_SET_CARD_HOLDER, "نام صاحب کارت:"),
        "💰 تعیین موجودی": (AWAIT_ADMIN_SET_BALANCE_ID, "آیدی عددی کاربر:"),
        "➕ افزایش موجودی": (AWAIT_ADMIN_ADD_BALANCE_ID, "آیدی عددی کاربر:"),
        "➖ کسر موجودی": (AWAIT_ADMIN_DEDUCT_BALANCE_ID, "آیدی عددی کاربر:"),
        "💲 قیمت الماس": (AWAIT_ADMIN_CREDIT_PRICE, "قیمت جدید (تومان):"),
        "🎁 پاداش دعوت": (AWAIT_ADMIN_REFERRAL_PRICE, "پاداش جدید (الماس):"),
        "📉 درصد مالیات": (AWAIT_ADMIN_TAX, "درصد مالیات:"),
        "💎 هزینه سلف": (AWAIT_ADMIN_SELF_COST, "هزینه هر ساعت استفاده از سلف (الماس):"),
        "📉 کف موجودی سلف": (AWAIT_ADMIN_SELF_MIN_BALANCE, "حداقل موجودی برای فعال‌سازی سلف (الماس):"),
        "➕ افزودن کانال": (AWAIT_NEW_CHANNEL, "لینک یا یوزرنیم کانال:"),
        "🖼 تصویر شرط": (AWAIT_BET_PHOTO, "عکس را ارسال کنید:"),
        "🖼 تصویر پنل": (AWAIT_ADMIN_PANEL_PHOTO, "عکس مورد نظر برای پنل کاربری را ارسال کنید:"), 
        "👥 مدیریت کاربران": (AWAIT_MANAGE_USER_ID, "آیدی کاربر:")
    }

    if choice in prompts:
        state, msg = prompts[choice]
        await update.message.reply_text(msg, reply_markup=ReplyKeyboardRemove())
        return state
        
    if choice == "📢 ارسال همگانی":
        await update.message.reply_text("پیام خود را بفرستید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_BROADCAST_MESSAGE
        
    if choice == "📊 آمار ربات":
        active_selfs = len(ACTIVE_BOTS)
        await update.message.reply_text(f"👥 کاربران: {len(GLOBAL_USERS)}\n🤖 سلف‌های فعال: {active_selfs}", reply_markup=admin_keyboard)
        return ADMIN_MENU

    if choice == "🗑 حذف تصویر پنل":
        await set_setting_async('panel_photo_file_id', 'None')
        await update.message.reply_text("✅ تصویر پنل با موفقیت حذف شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU

    if choice == "🗑 حذف تصویر شرط":
        await set_setting_async('bet_photo_file_id', 'None')
        await update.message.reply_text("✅ تصویر شرط حذف شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU
    
    if choice == "🔙 بازگشت":
        await update.message.reply_text("منوی اصلی:", reply_markup=get_main_keyboard(await get_user_async(update.effective_user.id)))
        return ConversationHandler.END

    if choice == "🔒 قفل: فعال":
        await set_setting_async('forced_channel_lock', 'true')
        await update.message.reply_text("✅ قفل روشن شد.", reply_markup=admin_keyboard); return ADMIN_MENU
    if choice == "🔓 قفل: غیرفعال":
        await set_setting_async('forced_channel_lock', 'false')
        await update.message.reply_text("❌ قفل خاموش شد.", reply_markup=admin_keyboard); return ADMIN_MENU
    
    await update.message.reply_text("دستور نامعتبر.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_simple_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state_map = {
        AWAIT_ADMIN_SET_CARD_NUMBER: 'card_number',
        AWAIT_ADMIN_SET_CARD_HOLDER: 'card_holder',
        AWAIT_ADMIN_CREDIT_PRICE: 'credit_price',
        AWAIT_ADMIN_REFERRAL_PRICE: 'referral_reward',
        AWAIT_ADMIN_TAX: 'bet_tax_rate'
    }
    return ADMIN_MENU

async def process_admin_panel_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ لطفا عکس ارسال کنید.", reply_markup=admin_keyboard)
        return AWAIT_ADMIN_PANEL_PHOTO
    
    file_id = update.message.photo[-1].file_id
    await set_setting_async('panel_photo_file_id', file_id)
    await update.message.reply_text("✅ تصویر پنل کاربری با موفقیت تنظیم شد.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_manage_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        context.user_data['target_user_id'] = uid
        await update.message.reply_text("نقش جدید (ادمین/مادریتور/کاربر عادی/لغو):")
        return AWAIT_MANAGE_USER_ROLE
    except: return ADMIN_MENU

async def process_manage_user_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text
    uid = context.user_data.get('target_user_id')
    user = await get_user_async(uid)
    if role == "ادمین": user['is_admin'] = True; user['is_moderator'] = False
    elif role == "مادریتور": user['is_admin'] = False; user['is_moderator'] = True
    elif role == "کاربر عادی": user['is_admin'] = False; user['is_moderator'] = False
    save_user_immediate(uid)
    await update.message.reply_text("✅ انجام شد.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    count = 0
    for uid in list(GLOBAL_USERS.keys()):
        try:
            await context.bot.copy_message(uid, msg.chat.id, msg.message_id)
            count += 1
            if count % 20 == 0: await asyncio.sleep(1)
        except: pass
    await update.message.reply_text("✅ ارسال شد.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split('_')
    action = data[0]

    if action == "tx":
        tx_id = int(data[2])
        decision = data[1]
        tx = GLOBAL_TRANSACTIONS.get(tx_id)
        if not tx or tx['status'] != 'pending': 
            await query.answer("نامعتبر."); return
        
        user_doc = await get_user_async(tx['user_id'])
        if decision == "approve":
            tx['status'] = 'approved'
            user_doc['balance'] += tx['amount']
            save_user_immediate(tx['user_id'])
            await context.bot.send_message(tx['user_id'], f"✅ شارژ {tx['amount']} الماس انجام شد.")
            await query.edit_message_caption(caption=query.message.caption + "\n✅ تایید شد.")
        else:
            tx['status'] = 'rejected'
            await context.bot.send_message(tx['user_id'], "❌ درخواست شارژ رد شد.")
            await query.edit_message_caption(caption=query.message.caption + "\n❌ رد شد.")

    elif action == "bet":
        bet_id = int(data[2])
        bet = GLOBAL_BETS.get(bet_id)
        if not bet or bet['status'] != 'pending': 
            await query.answer("شرط فعال نیست."); return
        
        user = query.from_user
        if data[1] == "cancel":
            if user.id == bet['proposer_id']:
                GLOBAL_BETS.pop(bet_id)
                await query.edit_message_caption("❌ لغو شد.")
        elif data[1] == "join":
            if user.id == bet['proposer_id']: 
                await query.answer("نمی‌توانید به شرط خودتان وارد شوید."); return
            
            joiner = await get_user_async(user.id)
            if joiner['balance'] < bet['amount']:
                await query.answer("موجودی ناکافی."); return
            
            proposer = await get_user_async(bet['proposer_id'])
            amount = bet['amount']
            joiner['balance'] -= amount
            proposer['balance'] -= amount
            
            winner = random.choice([joiner, proposer])
            loser = joiner if winner == proposer else proposer
            
            tax_rate = int(GLOBAL_SETTINGS.get('bet_tax_rate', '2'))
            pot = amount * 2
            tax = int(pot * tax_rate / 100)
            prize = pot - tax
            
            winner['balance'] += prize
            owner = await get_user_async(OWNER_ID)
            owner['balance'] += tax
            
            save_user_immediate(joiner['user_id'])
            save_user_immediate(proposer['user_id'])
            GLOBAL_BETS.pop(bet_id)
            
            txt = (
                f"<b>🏆 𝐌𝐀𝐓𝐂𝐇 𝐑𝐄𝐒𝐔𝐋𝐓</b>\n\n"
                f"👤 <b>Winner:</b> {get_user_display_name(winner)}\n"
                f"💀 <b>Loser:</b> {get_user_display_name(loser)}\n\n"
                f"💎 <b>Prize:</b> <code>{prize:,}</code>\n"
                f"📉 <b>Tax:</b> <code>{tax:,}</code>\n\n"
                f"🏴‍☠️ <b>𝐃𝐀𝐑𝐊𝐒𝐄𝐋𝐅</b>"
            )
            try:
                await query.edit_message_caption(txt, parse_mode=ParseMode.HTML)
            except:
                await query.edit_message_text(txt, parse_mode=ParseMode.HTML)

    elif action == "check":
        await query.answer()

async def start_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    amount = int(re.search(r'\d+', msg).group())
    user = await get_user_async(update.effective_user.id)
    if user['balance'] < amount:
        await update.message.reply_text("⛔️ <b>Your balance is insufficient.</b>", parse_mode=ParseMode.HTML)
        return
    
    global BET_ID_COUNTER
    bet_id = BET_ID_COUNTER; BET_ID_COUNTER += 1
    GLOBAL_BETS[bet_id] = {
        'bet_id': bet_id, 'proposer_id': user['user_id'], 'amount': amount, 'status': 'pending'
    }
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚔️ 𝐉𝐎𝐈𝐍", callback_data=f"bet_join_{bet_id}"), 
         InlineKeyboardButton("🚫 𝐂𝐀𝐍𝐂𝐄𝐋", callback_data=f"bet_cancel_{bet_id}")]
    ])
    
    caption = (
        f"<b>⚔️ 𝐍𝐄𝐖 𝐌𝐀𝐓𝐂𝐇 𝐒𝐓𝐀𝐑𝐓𝐄𝐃</b>\n\n"
        f"💎 <b>Amount:</b> <code>{amount:,}</code>\n"
        f"👤 <b>Player:</b> {user['first_name']}\n\n"
        f"🏴‍☠️ <b>𝐃𝐀𝐑𝐊𝐒𝐄𝐋𝐅</b>"
    )

    photo_id = await get_setting_async('bet_photo_file_id')
    if photo_id and photo_id != 'None':
        try:
            await update.message.reply_photo(photo_id, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        except:
             await update.message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(caption, reply_markup=kb, parse_mode=ParseMode.HTML)

async def transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message: return
    amount = int(re.search(r'\d+', update.message.text).group())
    sender = await get_user_async(update.effective_user.id)
    receiver = await get_user_async(update.message.reply_to_message.from_user.id)
    
    if sender['balance'] >= amount:
        sender['balance'] -= amount
        receiver['balance'] += amount
        save_user_immediate(sender['user_id'])
        save_user_immediate(receiver['user_id'])
        await update.message.reply_text(f"✅ {amount} الماس انتقال یافت.")
    else:
        await update.message.reply_text("موجودی ناکافی.")

async def post_init(application: Application):
    init_memory_db()
    
    if db is not None:
        count = 0
        cost = int(GLOBAL_SETTINGS.get('self_hourly_cost', '1'))
        for doc in db.sessions.find():
            user_doc = await get_user_async(doc['user_id'])
            if user_doc['balance'] >= cost:
                asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized'), doc['user_id']))
                count += 1
        logging.info(f"Restored {count} self-bot sessions.")

    application.job_queue.run_repeating(billing_loop, interval=3600, first=60)

def main():
    if not BOT_TOKEN:
        print("🔴 Error: BOT_TOKEN is missing!")
        return

    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    db_thread = Thread(target=background_db_sync, daemon=True)
    db_thread.start()

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex("^💳 موجودی حساب$"), show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 دریافت هدیه$"), get_referral_link))
    
    self_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🚀 فعال‌سازی سلف‌بات$"), self_activation_entry)],
        states={
            SELF_LOGIN_PHONE: [MessageHandler(filters.CONTACT, process_self_phone)],
            SELF_LOGIN_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_self_code)],
            SELF_LOGIN_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_self_password)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    application.add_handler(self_conv)

    admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👔 پنل مدیریت$"), admin_panel_entry)],
        states={
            ADMIN_MENU: [
                MessageHandler(filters.Regex("^(💳 تنظیم کارت واریز|👤 تنظیم صاحب کارت|👥 مدیریت کاربران)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(➕ افزودن کانال|➖ حذف کانال|🖼 تصویر شرط)$"), process_admin_choice),
                MessageHandler(filters.Regex(r"^(💰 تعیین موجودی|➕ افزایش موجودی|➖ کسر موجودی|💲 قیمت الماس|🎁 پاداش دعوت|📉 درصد مالیات)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(💎 هزینه سلف|📉 کف موجودی سلف)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(👁‍🗨 لیست کانال‌های عضویت|📊 آمار ربات|🗑 حذف تصویر شرط)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(🔒 قفل: فعال|🔓 قفل: غیرفعال)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(📢 ارسال همگانی)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(🖼 تصویر پنل|🗑 حذف تصویر پنل)$"), process_admin_choice), 
                MessageHandler(filters.Regex("^🔙 بازگشت$"), process_admin_choice),
            ],
            AWAIT_ADMIN_REPLY: [], 
            AWAIT_ADMIN_SELF_COST: [MessageHandler(filters.TEXT, process_admin_self_cost)],
            AWAIT_ADMIN_SELF_MIN_BALANCE: [MessageHandler(filters.TEXT, process_admin_self_min_balance)],
            AWAIT_ADMIN_PANEL_PHOTO: [MessageHandler(filters.PHOTO, process_admin_panel_photo)], 
            AWAIT_ADMIN_SET_CARD_NUMBER: [MessageHandler(filters.TEXT, lambda u,c: process_admin_choice(u,c))],
            AWAIT_NEW_CHANNEL: [MessageHandler(filters.TEXT, process_admin_choice)],
            AWAIT_BET_PHOTO: [MessageHandler(filters.PHOTO, process_admin_choice)],
            AWAIT_MANAGE_USER_ID: [MessageHandler(filters.TEXT, process_manage_user_id)],
            AWAIT_MANAGE_USER_ROLE: [MessageHandler(filters.TEXT, process_manage_user_role)],
            AWAIT_BROADCAST_MESSAGE: [MessageHandler(filters.ALL, process_admin_broadcast)],
            AWAIT_ADMIN_SET_BALANCE_ID: [MessageHandler(filters.TEXT, process_admin_choice)],
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    )
    application.add_handler(admin_conv)
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💎 خرید الماس$"), deposit_entry)],
        states={AWAIT_DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT, process_deposit_amount)],
                AWAIT_DEPOSIT_RECEIPT: [MessageHandler(filters.PHOTO, process_deposit_receipt)]},
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    ))
    
    application.add_handler(ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💬 پشتیبانی آنلاین$"), support_entry)],
        states={AWAIT_SUPPORT_MESSAGE: [MessageHandler(filters.TEXT, process_support_message)]},
        fallbacks=[CommandHandler('cancel', lambda u,c: ConversationHandler.END)]
    ))

    application.add_handler(MessageHandler(filters.Regex(r'^(شرط|بت) \d+$') & filters.ChatType.GROUPS, start_bet_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(انتقال) \d+$') & filters.ChatType.GROUPS, transfer_handler))
    
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    application.run_polling()

if __name__ == "__main__":
    main()
