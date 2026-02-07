import asyncio
import logging
import os
import re
import secrets
import contextlib
from threading import Thread
import time
from urllib.parse import quote
from flask import Flask
import pymongo
from zoneinfo import ZoneInfo
from datetime import datetime, timezone, timedelta
import html
import traceback
import json
import random

# --- Telegram Bot Imports (PTB) ---
from telegram import (Update, ReplyKeyboardMarkup, KeyboardButton,
                      InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove,
                      InlineQueryResultArticle, InputTextMessageContent)
from telegram.constants import ParseMode, ChatAction as PTBChatAction
from telegram.ext import (Application, CommandHandler, MessageHandler,
                          ConversationHandler, filters, ContextTypes, CallbackQueryHandler,
                          ApplicationHandlerStop, TypeHandler, InlineQueryHandler)
import telegram.error

# --- Pyrogram Imports (Self Bot) ---
from pyrogram import Client, filters as pyro_filters, idle
from pyrogram.handlers import MessageHandler as PyroMessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.raw import functions
from pyrogram.errors import (
    SessionPasswordNeeded, PhoneCodeInvalid, PasswordHashInvalid,
    PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ChatSendInlineForbidden
)
import pyrogram.utils

# =======================================================
#  بخش ۱: تنظیمات اولیه و پیکربندی
# =======================================================

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

# --- Monkey Patch for Peer ID Validation (From Self Bot) ---
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

# --- Environment Variables ---
# مقادیر توکن و API ها
BOT_TOKEN = "8594820914:AAHoX2vPxOYUzVNxf7T99IBNQMPOhiLh1RQ" # توکن جدید شما جایگزین شد
API_ID = 28190856      # ای پی آی آیدی پیروگرام
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521" # ای پی آی هش پیروگرام

OWNER_ID = 7423552124 # آیدی عددی مالک

TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")

# --- MongoDB Connection ---
MONGO_URI = "mongodb+srv://amirpitmax1_db_user:DvkIhwWzUfBT4L5j@cluster0.kdvbr3p.mongodb.net/?appName=Cluster0" # آدرس دیتابیس جدید جایگزین شد
DB_NAME = "telegram_bot_data_merged"

mongo_client = None
db = None
sessions_collection = None

try:
    mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = mongo_client[DB_NAME]
    sessions_collection = db['sessions']
    mongo_client.server_info()
    logging.info("✅ Connected to MongoDB successfully.")
except Exception as e:
    logging.error(f"❌ Failed to connect to MongoDB: {e}")
    db = None
    sessions_collection = None 

# --- In-Memory Database ---
GLOBAL_USERS = {}
GLOBAL_SETTINGS = {}
GLOBAL_TRANSACTIONS = {}
GLOBAL_BETS = {}
GLOBAL_CHANNELS = {}

# Active Pyrogram Clients: {user_id: (Client, [Tasks])}
ACTIVE_BOTS = {}

# Login States for Self Bot Activation
LOGIN_STATES = {}

TX_ID_COUNTER = 1
BET_ID_COUNTER = 1
BOT_USERNAME = "" # Will be set on startup

# --- Conversation States ---
(ADMIN_MENU, AWAIT_ADMIN_REPLY,
 AWAIT_ADMIN_SET_CARD_NUMBER, AWAIT_ADMIN_SET_CARD_HOLDER,
 AWAIT_NEW_CHANNEL, AWAIT_BET_PHOTO,
 AWAIT_ADMIN_SET_BALANCE_ID, AWAIT_ADMIN_SET_BALANCE,
 AWAIT_ADMIN_ADD_BALANCE_ID, AWAIT_ADMIN_ADD_BALANCE_AMOUNT,
 AWAIT_ADMIN_DEDUCT_BALANCE_ID, AWAIT_ADMIN_DEDUCT_BALANCE_AMOUNT,
 AWAIT_ADMIN_TAX, AWAIT_ADMIN_CREDIT_PRICE, AWAIT_ADMIN_REFERRAL_PRICE,
 AWAIT_MANAGE_USER_ID, AWAIT_MANAGE_USER_ROLE,
 AWAIT_BROADCAST_MESSAGE,
 AWAIT_SELF_CONTACT, AWAIT_SELF_CODE, AWAIT_SELF_PASSWORD,
 AWAIT_ADMIN_SELF_COST, AWAIT_ADMIN_SELF_MIN, AWAIT_ADMIN_SELF_PHOTO
) = range(24)

# --- Constants from Self Bot ---
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

ENEMY_REPLIES = ["ببخشید متوجه نشدم؟", "داری فشار میخوری؟", "برو پیش بزرگترت", "سطحت پایینه", "😂😂", "اوکی بای"]
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

HELP_TEXT = """
**[ 🛠 دستورات دستی و ریپلای سلف ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی (ساعت، فونت، منشی و...) فقط از طریق دستور **`پنل`** در اکانت خودتان قابل دسترسی هستند.

**✦ مدیریت پیام و چت**
  » `حذف [تعداد]` 
  » `ذخیره` (ریپلای روی پیام)
  » `تکرار [تعداد]` (ریپلای روی پیام)
  » `کپی روشن` | `کپی خاموش` (ریپلای روی کاربر)

**✦ دفاعی و امنیتی**
  » `دشمن روشن` | `خاموش` (ریپلای روی کاربر)
  » `لیست دشمن`
  » `بلاک روشن` | `بلاک خاموش` (ریپلای روی کاربر)
  » `سکوت روشن` | `سکوت خاموش` (ریپلای روی کاربر)
  » `ریاکشن [شکلک]` | `خاموش` (ریپلای روی کاربر)

**✦ سرگرمی**
  » `تاس` | `تاس [عدد]`
  » `بولینگ`

**✦ سایر**
  » `پنل` (نمایش منوی تنظیمات)
━━━━━━━━━━━━━━━━━━━━
"""
COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تنظیم عکس|حذف عکس|پنل|panel)$"

# --- Self Bot State Dictionaries ---
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

# web_app Flask
web_app = Flask(__name__)

@web_app.route('/')
def health_check():
    return "darkself Bot & Manager is running.", 200

# =======================================================
#  بخش ۳: مدیریت دیتابیس
# =======================================================

def init_memory_db():
    global TX_ID_COUNTER, BET_ID_COUNTER
    logging.info("Initializing database...")
    if db is not None:
        try:
            for doc in db.settings.find(): GLOBAL_SETTINGS[doc['_id']] = doc['value']
            for doc in db.users.find():
                u_id = int(doc['user_id'])
                GLOBAL_USERS[u_id] = doc
                # Ensure fields for self bot
                if 'self_active' not in doc: GLOBAL_USERS[u_id]['self_active'] = False
                if 'self_last_payment' not in doc: GLOBAL_USERS[u_id]['self_last_payment'] = 0
            
            max_tx_id = 0
            for doc in db.transactions.find():
                tx_id = int(doc['tx_id'])
                GLOBAL_TRANSACTIONS[tx_id] = doc
                if tx_id > max_tx_id: max_tx_id = tx_id
            TX_ID_COUNTER = max_tx_id + 1
            
            max_bet_id = 0
            for doc in db.bets.find():
                bet_id = int(doc['bet_id'])
                GLOBAL_BETS[bet_id] = doc
                if bet_id > max_bet_id: max_bet_id = bet_id
            BET_ID_COUNTER = max_bet_id + 1
            
            for doc in db.channels.find(): GLOBAL_CHANNELS[doc['channel_username']] = doc

        except Exception as e: logging.error(f"Error init DB: {e}")

    # Defaults including Self Bot settings
    defaults = {
        'credit_price': '1000', 'initial_balance': '10', 'referral_reward': '5',
        'bet_tax_rate': '2', 'card_number': 'تنظیم نشده', 'card_holder': 'تنظیم نشده',
        'bet_photo_file_id': 'None', 'forced_channel_lock': 'false',
        'self_bot_hourly_cost': '1',    # هزینه ساعتی سلف
        'self_bot_min_balance': '10',   # حداقل موجودی برای فعالسازی
        'self_panel_photo': 'None'      # عکس پنل سلف (تنظیم توسط ادمین)
    }
    for k, v in defaults.items():
        if k not in GLOBAL_SETTINGS: GLOBAL_SETTINGS[k] = v

def background_db_sync():
    while True:
        if db is None: time.sleep(20); continue
        try:
            for u_id, data in list(GLOBAL_USERS.items()):
                db.users.replace_one({'user_id': u_id}, data, upsert=True)
            for k, v in list(GLOBAL_SETTINGS.items()):
                db.settings.replace_one({'_id': k}, {'value': v}, upsert=True)
            for tx_id, data in list(GLOBAL_TRANSACTIONS.items()):
                db.transactions.replace_one({'tx_id': tx_id}, data, upsert=True)
            for bet_id, data in list(GLOBAL_BETS.items()):
                db.bets.replace_one({'bet_id': bet_id}, data, upsert=True)
            for ch, data in list(GLOBAL_CHANNELS.items()):
                db.channels.replace_one({'channel_username': ch}, data, upsert=True)
        except Exception as e: logging.error(f"Sync Error: {e}")
        time.sleep(10)

def save_user_immediate(user_id):
    if db is None or user_id not in GLOBAL_USERS: return
    try: db.users.replace_one({'user_id': user_id}, GLOBAL_USERS[user_id], upsert=True)
    except: pass

async def get_setting_async(name): return GLOBAL_SETTINGS.get(name)
async def set_setting_async(name, value):
    GLOBAL_SETTINGS[name] = str(value)
    if db is not None: db.settings.replace_one({'_id': name}, {'value': str(value)}, upsert=True)

async def get_user_async(user_id):
    if user_id in GLOBAL_USERS:
        u = GLOBAL_USERS[user_id]
        if 'vip_balance' not in u: u['vip_balance'] = 0
        if 'self_active' not in u: u['self_active'] = False
        if 'self_last_payment' not in u: u['self_last_payment'] = 0
        return u
    
    # New User
    try: bal = int(GLOBAL_SETTINGS.get('initial_balance', '10'))
    except: bal = 10
    is_owner = (user_id == OWNER_ID)
    start_bal = 1000000000 if is_owner else bal
    
    new_u = {
        'user_id': user_id, 'balance': start_bal, 'vip_balance': 0,
        'is_admin': is_owner, 'is_owner': is_owner, 'referred_by': None,
        'is_moderator': False, 'username': None, 'first_name': None,
        'self_active': False, 'self_last_payment': 0
    }
    GLOBAL_USERS[user_id] = new_u
    if db: db.users.replace_one({'user_id': user_id}, new_u, upsert=True)
    
    if user_id == OWNER_ID and (not new_u.get('is_owner')):
        new_u['is_owner'] = True; new_u['is_admin'] = True; save_user_immediate(user_id)
    return new_u

def get_user_display_name(user):
    if user.id in GLOBAL_USERS:
        GLOBAL_USERS[user.id]['username'] = user.username
        GLOBAL_USERS[user.id]['first_name'] = user.first_name
    return f"@{user.username}" if user.username else html.escape(user.first_name or "User")

# --- Keyboards (Main Bot) ---
def get_main_keyboard(user_doc):
    if user_doc.get('is_owner'):
        return ReplyKeyboardMarkup([
            [KeyboardButton("💰 موجودی"), KeyboardButton("👑 پنل ادمین")],
            [KeyboardButton("🤖 فعال‌سازی سلف")]
        ], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([
            [KeyboardButton("💰 موجودی"), KeyboardButton("💳 افزایش الماس")],
            [KeyboardButton("🎁 الماس رایگان"), KeyboardButton("💬 پشتیبانی")],
            [KeyboardButton("🤖 فعال‌سازی سلف")]
        ], resize_keyboard=True)

admin_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("📊 آمار کلی"), KeyboardButton("💳 تنظیم شماره کارت")],
    [KeyboardButton("👤 تنظیم صاحب کارت"), KeyboardButton("مدیریت کاربر")],
    [KeyboardButton("➕ افزایش الماس کاربر"), KeyboardButton("➖ کسر الماس کاربر")],
    [KeyboardButton("💰 تنظیم الماس (ست)"), KeyboardButton("📈 تنظیم قیمت الماس")],
    [KeyboardButton("⚙️ هزینه سلف (ساعتی)"), KeyboardButton("💎 حداقل موجودی سلف")],
    [KeyboardButton("🖼 تنظیم عکس پنل سلف"), KeyboardButton("🗑 حذف عکس پنل سلف")],
    [KeyboardButton("🎁 تنظیم پاداش دعوت"), KeyboardButton("📉 تنظیم مالیات (۰-۱۰۰)")],
    [KeyboardButton("➕ افزودن کانال عضویت"), KeyboardButton("➖ حذف کانال عضویت")],
    [KeyboardButton("👁‍🗨 لیست کانال‌های عضویت"), KeyboardButton("🔒 قفل عضویت: روشن"), KeyboardButton("🔓 قفل عضویت: خاموش")],
    [KeyboardButton("🖼 تنظیم عکس شرط"), KeyboardButton("🗑 حذف عکس شرط")],
    [KeyboardButton("📢 پیام همگانی")],
    [KeyboardButton("⬅️ بازگشت به منوی اصلی")]
], resize_keyboard=True)

bet_group_keyboard = ReplyKeyboardMarkup([
    [KeyboardButton("موجودی 💰")],
    [KeyboardButton("شرط 100"), KeyboardButton("شرط 500")],
    [KeyboardButton("شرط 1000"), KeyboardButton("شرط 5000")]
], resize_keyboard=True)

# =======================================================
#  بخش ۴: توابع Pyrogram (موتور سلف)
# =======================================================

def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def stop_self_bot_due_to_auth(user_id):
    """Stops the bot due to invalid session and updates DB."""
    logging.warning(f"Stopping self-bot for {user_id} due to invalid session.")
    if user_id in ACTIVE_BOTS:
        client, tasks = ACTIVE_BOTS[user_id]
        del ACTIVE_BOTS[user_id] 
        try: await client.stop() 
        except: pass
        for t in tasks: t.cancel()
    
    if user_id in GLOBAL_USERS:
        GLOBAL_USERS[user_id]['self_active'] = False
        save_user_immediate(user_id)
        
    if sessions_collection is not None:
        try: sessions_collection.delete_one({'user_id': user_id})
        except: pass

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
    except (AuthKeyUnregistered, UserDeactivated):
        await stop_self_bot_due_to_auth(user_id)
    except Exception as e:
        logging.error(f"Immediate clock update failed: {e}")

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

def get_panel_photo(user_id):
    # This now uses ONLY the global setting set by Admin, as requested.
    global_photo = GLOBAL_SETTINGS.get('self_panel_photo')
    if global_photo and global_photo != 'None':
        return global_photo
    return None

# --- Self Bot Background Tasks ---
async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                await perform_clock_update_now(client, user_id)
            now = datetime.now(TEHRAN_TIMEZONE)
            await asyncio.sleep(60 - now.second + 0.1)
        except Exception: await asyncio.sleep(60)

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
        except Exception: await asyncio.sleep(120)

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
        except Exception: await asyncio.sleep(60)

# --- Pyrogram Message Handlers ---
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

# --- Panel Logic (Updated for PTB Integration) ---
def get_self_panel_keyboard_ptb(user_id):
    """Generates the PTB InlineKeyboardMarkup based on user's self-bot settings."""
    s_clock = "✅" if CLOCK_STATUS.get(user_id, True) else "❌"
    s_bold = "✅" if BOLD_MODE_STATUS.get(user_id, False) else "❌"
    s_sec = "✅" if SECRETARY_MODE_STATUS.get(user_id, False) else "❌"
    s_seen = "✅" if AUTO_SEEN_STATUS.get(user_id, False) else "❌"
    s_pv = "🔒" if PV_LOCK_STATUS.get(user_id, False) else "🔓"
    s_anti = "✅" if ANTI_LOGIN_STATUS.get(user_id, False) else "❌"
    s_type = "✅" if TYPING_MODE_STATUS.get(user_id, False) else "❌"
    s_game = "✅" if PLAYING_MODE_STATUS.get(user_id, False) else "❌"
    s_enemy = "✅" if GLOBAL_ENEMY_STATUS.get(user_id, False) else "❌"
    t_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    l_en = "✅" if t_lang == "en" else "❌"
    l_ru = "✅" if t_lang == "ru" else "❌"
    l_cn = "✅" if t_lang == "zh-CN" else "❌"
    
    current_font = USER_FONT_CHOICES.get(user_id, 'stylized')
    preview = stylize_time("12:34", current_font)

    keyboard = [
        [InlineKeyboardButton(f"ساعت {s_clock}", callback_data=f"toggle_clock_{user_id}"),
         InlineKeyboardButton(f"بولد {s_bold}", callback_data=f"toggle_bold_{user_id}")],
        [InlineKeyboardButton(f"تغییر فونت: {preview}", callback_data=f"cycle_font_{user_id}")],
        [InlineKeyboardButton(f"منشی {s_sec}", callback_data=f"toggle_sec_{user_id}"),
         InlineKeyboardButton(f"سین {s_seen}", callback_data=f"toggle_seen_{user_id}")],
        [InlineKeyboardButton(f"پیوی {s_pv}", callback_data=f"toggle_pv_{user_id}"),
         InlineKeyboardButton(f"انتی لوگین {s_anti}", callback_data=f"toggle_anti_{user_id}")],
        [InlineKeyboardButton(f"تایپ {s_type}", callback_data=f"toggle_type_{user_id}"),
         InlineKeyboardButton(f"دشمن همگانی {s_enemy}", callback_data=f"toggle_g_enemy_{user_id}")],
        [InlineKeyboardButton(f"بازی {s_game}", callback_data=f"toggle_game_{user_id}")],
        [InlineKeyboardButton(f"🇺🇸 EN {l_en}", callback_data=f"lang_en_{user_id}"),
         InlineKeyboardButton(f"🇷🇺 RU {l_ru}", callback_data=f"lang_ru_{user_id}"),
         InlineKeyboardButton(f"🇨🇳 CN {l_cn}", callback_data=f"lang_cn_{user_id}")],
        [InlineKeyboardButton("بستن پنل ❌", callback_data=f"close_panel_{user_id}")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Pyrogram Handler - Now calls Main Bot Inline Mode
async def panel_command_controller(client, message):
    try:
        user_id = client.me.id
        if not BOT_USERNAME:
            await message.edit_text("❌ خطا: نام کاربری ربات اصلی یافت نشد.")
            return
            
        results = await client.get_inline_bot_results(BOT_USERNAME, "panel")
        if results and results.results:
            await message.delete()
            await client.send_inline_bot_result(message.chat.id, results.query_id, results.results[0].id)
        else:
            await message.edit_text("❌ خطا در دریافت پنل از ربات اصلی. مطمئن شوید Inline Mode در BotFather روشن است.")
            
    except ChatSendInlineForbidden:
        await message.edit_text("🚫 در این چت اجازه ارسال پنل بصورت اینلاین وجود ندارد.")
    except Exception as e:
        await message.edit_text(f"❌ خطا: {e}\nلطفا ابتدا دستور /start را در ربات اصلی بزنید.")

# Photo Setting Removed from here (as per request) - Now handled in Admin Panel
# Handler for "تنظیم عکس" and "حذف عکس" removed from client.add_handler below.

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

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    try:
        await client.start()
        user_id = (await client.get_me()).id
        if sessions_collection is not None: sessions_collection.update_one({'phone_number': phone}, {'$set': {'user_id': user_id}})
    except Exception as e:
        logging.error(f"Failed to start Pyrogram client for phone {phone}: {e}")
        return

    # Kill existing instance if any
    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: t.cancel()
    
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    
    # Handlers
    client.add_handler(PyroMessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, pyro_filters.private & ~pyro_filters.me & ~pyro_filters.bot), group=-5)
    client.add_handler(PyroMessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, pyro_filters.private & ~pyro_filters.me), group=-4)
    client.add_handler(PyroMessageHandler(incoming_message_manager, pyro_filters.all & ~pyro_filters.me), group=-3)
    client.add_handler(PyroMessageHandler(outgoing_message_modifier, pyro_filters.text & pyro_filters.me & ~pyro_filters.reply), group=-1)
    client.add_handler(PyroMessageHandler(help_controller, pyro_filters.me & pyro_filters.regex("^راهنما$")))
    client.add_handler(PyroMessageHandler(panel_command_controller, pyro_filters.me & pyro_filters.regex(r"^(پنل|panel)$")))
    # Photo setting handlers removed here as requested
    client.add_handler(PyroMessageHandler(reply_based_controller, pyro_filters.me)) 
    client.add_handler(PyroMessageHandler(enemy_handler, pyro_filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~pyro_filters.me), group=1)
    client.add_handler(PyroMessageHandler(secretary_auto_reply_handler, pyro_filters.private & ~pyro_filters.me), group=1)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)
    logging.info(f"Self Bot started for {user_id}")

async def stop_self_bot_due_to_balance(user_id):
    if user_id in ACTIVE_BOTS:
        client, tasks = ACTIVE_BOTS[user_id]
        try:
            me = await client.get_me()
            clean_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
            if clean_name != me.first_name:
                await client.update_profile(first_name=clean_name)
        except: pass
        try: await client.stop()
        except: pass
        for t in tasks: t.cancel()
        del ACTIVE_BOTS[user_id]
    
    if user_id in GLOBAL_USERS:
        GLOBAL_USERS[user_id]['self_active'] = False
        save_user_immediate(user_id)

# =======================================================
#  بخش ۵: سیستم لاگین سلف در ربات اصلی (PTB)
# =======================================================

async def self_bot_activation_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = await get_user_async(user.id)
    
    min_bal = int(await get_setting_async('self_bot_min_balance') or 10)
    hourly_cost = int(await get_setting_async('self_bot_hourly_cost') or 1)
    
    if user_doc['balance'] < min_bal:
        await update.message.reply_text(f"⛔️ موجودی شما کمتر از حد مجاز است.\nحداقل موجودی برای فعال‌سازی سلف: {min_bal} الماس", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END
        
    if user_doc.get('self_active') and user.id in ACTIVE_BOTS:
        await update.message.reply_text("✅ سلف شما هم‌اکنون فعال است.", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END
        
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 ارسال شماره تلفن", request_contact=True)], [KeyboardButton("بازگشت")]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        f"🤖 **فعال‌سازی سلف بات**\n\n"
        f"💎 هزینه ساعتی: {hourly_cost} الماس\n"
        f"⚠️ اگر موجودی شما تمام شود، سلف به طور خودکار خاموش می‌شود.\n\n"
        f"لطفا برای شروع شماره خود را ارسال کنید:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=kb
    )
    return AWAIT_SELF_CONTACT

async def process_self_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.message.text == "بازگشت":
        await cancel_conversation(update, context)
        return ConversationHandler.END

    if not update.message.contact:
        await update.message.reply_text("لطفا از دکمه ارسال شماره استفاده کنید.")
        return AWAIT_SELF_CONTACT
        
    phone = update.message.contact.phone_number
    await update.message.reply_text("⏳ در حال اتصال به سرور تلگرام...", reply_markup=ReplyKeyboardRemove())
    
    temp_client = Client(f"login_temp_{user.id}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
    await temp_client.connect()
    
    try:
        sent_code = await temp_client.send_code(phone)
        context.user_data['login_client'] = temp_client
        context.user_data['login_phone'] = phone
        context.user_data['login_hash'] = sent_code.phone_code_hash
        
        await update.message.reply_text(
            "✅ کد تایید ارسال شد.\n"
            "لطفا کد را به صورت اعداد جدا شده با فاصله یا نقطه ارسال کنید (مثلا: 1 2 3 4 5 یا 1.2.3.4.5) تا توسط تلگرام لینک شناسایی نشود."
        )
        return AWAIT_SELF_CODE
    except Exception as e:
        await temp_client.disconnect()
        await update.message.reply_text(f"❌ خطا در ارسال کد: {e}\nلطفا دوباره تلاش کنید.", reply_markup=get_main_keyboard(await get_user_async(user.id)))
        return ConversationHandler.END

async def process_self_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = re.sub(r"\D+", "", update.message.text)
    temp_client: Client = context.user_data.get('login_client')
    phone = context.user_data.get('login_phone')
    phone_hash = context.user_data.get('login_hash')
    
    try:
        await temp_client.sign_in(phone, phone_hash, code)
        await finalize_login(update, context, temp_client, phone)
        return ConversationHandler.END
    except SessionPasswordNeeded:
        await update.message.reply_text("🔐 اکانت شما رمز دو مرحله‌ای دارد. لطفا آن را وارد کنید:")
        return AWAIT_SELF_PASSWORD
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}\nلطفا مجدد تلاش کنید.")
        await temp_client.disconnect()
        return ConversationHandler.END

async def process_self_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text
    temp_client: Client = context.user_data.get('login_client')
    phone = context.user_data.get('login_phone')
    
    try:
        await temp_client.check_password(password)
        await finalize_login(update, context, temp_client, phone)
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ رمز اشتباه یا خطا: {e}\nدوباره تلاش کنید.")
        return AWAIT_SELF_PASSWORD

async def finalize_login(update: Update, context: ContextTypes.DEFAULT_TYPE, client: Client, phone: str):
    user_id = update.effective_user.id
    session_str = await client.export_session_string()
    me = await client.get_me()
    await client.disconnect()
    
    if sessions_collection is not None:
        sessions_collection.update_one(
            {'phone_number': phone}, 
            {'$set': {'session_string': session_str, 'user_id': me.id, 'real_owner_id': user_id}}, 
            upsert=True
        )
    
    user_doc = await get_user_async(user_id)
    user_doc['self_active'] = True
    user_doc['self_last_payment'] = time.time()
    
    cost = int(await get_setting_async('self_bot_hourly_cost') or 1)
    if user_doc['balance'] >= cost:
        user_doc['balance'] -= cost
        save_user_immediate(user_id)
        msg = f"✅ سلف بات با موفقیت فعال شد!\n💎 {cost} الماس برای ساعت اول کسر شد."
    else:
        msg = "✅ سلف فعال شد اما موجودی برای کسر هزینه کافی نبود. به زودی غیرفعال می‌شود."
    
    asyncio.create_task(start_bot_instance(session_str, phone, 'stylized'))
    await update.message.reply_text(msg, reply_markup=get_main_keyboard(user_doc))


# =======================================================
#  بخش ۶: سیستم بیلیینگ و جاب (Billing Job)
# =======================================================

async def billing_job(context: ContextTypes.DEFAULT_TYPE):
    cost_str = await get_setting_async('self_bot_hourly_cost')
    try: cost = int(cost_str or 1)
    except: cost = 1
    
    now = time.time()
    
    for user_id, user_data in list(GLOBAL_USERS.items()):
        if not user_data.get('self_active'):
            continue
            
        last_pay = user_data.get('self_last_payment', 0)
        
        if now - last_pay >= 3600:
            if user_data['balance'] >= cost:
                user_data['balance'] -= cost
                user_data['self_last_payment'] = now
                save_user_immediate(user_id)
            else:
                await stop_self_bot_due_to_balance(user_id)
                try:
                    kb = ReplyKeyboardMarkup([[KeyboardButton("🔄 تمدید و ادامه سرویس")], [KeyboardButton("💰 موجودی")]], resize_keyboard=True)
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⚠️ **هشدار: موجودی الماس شما به پایان رسید!**\n\nسلف بات شما خاموش شد و تنظیمات (مثل ساعت پروفایل) حذف گردید.\nلطفا حساب خود را شارژ کنید و سپس دکمه تمدید را بزنید.",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=kb
                    )
                except Exception as e:
                    logging.warning(f"Failed to send billing alert to {user_id}: {e}")

async def continue_service_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_doc = await get_user_async(user_id)
    
    min_bal = int(await get_setting_async('self_bot_min_balance') or 10)
    
    if user_doc['balance'] < min_bal:
        await update.message.reply_text(f"❌ موجودی کافی نیست. حداقل {min_bal} الماس لازم است.", reply_markup=get_main_keyboard(user_doc))
        return

    session_doc = sessions_collection.find_one({'real_owner_id': user_id})
    if not session_doc:
        await update.message.reply_text("❌ سشن شما یافت نشد. لطفا مجدد فعال‌سازی را انجام دهید.", reply_markup=get_main_keyboard(user_doc))
        return

    user_doc['self_active'] = True
    user_doc['self_last_payment'] = time.time()
    
    cost = int(await get_setting_async('self_bot_hourly_cost') or 1)
    user_doc['balance'] -= cost
    save_user_immediate(user_id)
    
    asyncio.create_task(start_bot_instance(session_doc['session_string'], session_doc['phone_number'], 'stylized'))
    await update.message.reply_text(f"✅ سرویس مجددا فعال شد.\n💎 {cost} الماس کسر گردید.", reply_markup=get_main_keyboard(user_doc))

# =======================================================
#  بخش ۷: هندلرهای ادمین (Admin Handlers) - PTB
# =======================================================

async def admin_panel_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_doc = await get_user_async(update.effective_user.id)
    if not user_doc.get('is_owner'):
        await update.message.reply_text("⛔️ دسترسی به تنظیمات پنل فقط برای مالک اصلی مجاز است.")
        return ConversationHandler.END
    await update.message.reply_text("👑 به پنل ادمین خوش آمدید:", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_admin_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    choice = update.message.text
    context.user_data['admin_choice'] = choice
    
    prompts = {
        "⚙️ هزینه سلف (ساعتی)": "هزینه هر ساعت استفاده از سلف (به الماس) را وارد کنید:",
        "💎 حداقل موجودی سلف": "حداقل موجودی لازم برای روشن کردن سلف را وارد کنید:",
        "🖼 تنظیم عکس پنل سلف": "لطفا عکس جدید برای پنل سلف را ارسال کنید:",
    }
    
    if choice in prompts:
        await update.message.reply_text(prompts[choice], reply_markup=ReplyKeyboardRemove())
        if choice == "⚙️ هزینه سلف (ساعتی)": return AWAIT_ADMIN_SELF_COST
        if choice == "💎 حداقل موجودی سلف": return AWAIT_ADMIN_SELF_MIN
        if choice == "🖼 تنظیم عکس پنل سلف": return AWAIT_ADMIN_SELF_PHOTO
        
    if choice == "💳 تنظیم شماره کارت":
        await update.message.reply_text("لطفا شماره کارت جدید را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_SET_CARD_NUMBER
    elif choice == "👤 تنظیم صاحب کارت":
        await update.message.reply_text("لطفا نام صاحب حساب جدید را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_SET_CARD_HOLDER
    elif choice == "💰 تنظیم الماس (ست)":
        await update.message.reply_text("ابتدا آیدی عددی کاربر را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_SET_BALANCE_ID
    elif choice == "➕ افزایش الماس کاربر":
        await update.message.reply_text("ابتدا آیدی عددی کاربر را برای افزایش الماس وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_ADD_BALANCE_ID
    elif choice == "➖ کسر الماس کاربر":
        await update.message.reply_text("ابتدا آیدی عددی کاربر را برای کسر الماس وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_DEDUCT_BALANCE_ID
    elif choice == "📉 تنظیم مالیات (۰-۱۰۰)":
        await update.message.reply_text("درصد مالیات (بین ۰ تا ۱۰۰) را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_TAX
    elif choice == "📈 تنظیم قیمت الماس":
        await update.message.reply_text("قیمت جدید هر الماس به تومان را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_CREDIT_PRICE
    elif choice == "🎁 تنظیم پاداش دعوت":
        await update.message.reply_text("پاداش هر دعوت موفق به الماس را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_ADMIN_REFERRAL_PRICE
    elif choice == "➕ افزودن کانال عضویت":
        await update.message.reply_text("یوزرنیم کانال/گروه با @ (مثل @channel) یا لینک کامل را ارسال کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_NEW_CHANNEL
    elif choice == "🖼 تنظیم عکس شرط":
        await update.message.reply_text("لطفا عکس مورد نظر برای شرط را ارسال کنید.", reply_markup=ReplyKeyboardRemove())
        return AWAIT_BET_PHOTO
    elif choice == "📢 پیام همگانی":
        await update.message.reply_text("لطفا پیام خود را ارسال کنید (متن، عکس، فایل و...).", reply_markup=ReplyKeyboardRemove())
        return AWAIT_BROADCAST_MESSAGE
    elif choice == "➖ حذف کانال عضویت":
        return await show_channels_for_removal(update, context)
    elif choice == "مدیریت کاربر":
        await update.message.reply_text("آیدی عددی کاربر مورد نظر را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return AWAIT_MANAGE_USER_ID
    elif choice == "🔒 قفل عضویت: روشن":
        await set_setting_async('forced_channel_lock', 'true')
        await update.message.reply_text("✅ قفل عضویت فعال شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "🔓 قفل عضویت: خاموش":
        await set_setting_async('forced_channel_lock', 'false')
        await update.message.reply_text("❌ قفل عضویت غیرفعال شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "👁‍🗨 لیست کانال‌های عضویت":
        channels = list(GLOBAL_CHANNELS.values())
        msg = "لیست کانال‌ها:\n" + "\n".join([f"{c['channel_title']} ({c['channel_username']})" for c in channels]) if channels else "خالی"
        await update.message.reply_text(msg, reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "📊 آمار کلی":
        total_users = len(GLOBAL_USERS)
        pending_tx = sum(1 for tx in GLOBAL_TRANSACTIONS.values() if tx['status'] == 'pending')
        await update.message.reply_text(f"👥 کاربران: {total_users}\n🧾 تراکنش‌های معلق: {pending_tx}", reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "🗑 حذف عکس شرط":
        await set_setting_async('bet_photo_file_id', 'None')
        await update.message.reply_text("✅ عکس حذف شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "🗑 حذف عکس پنل سلف":
        await set_setting_async('self_panel_photo', 'None')
        await update.message.reply_text("✅ عکس پنل سلف حذف شد.", reply_markup=admin_keyboard)
        return ADMIN_MENU
    elif choice == "⬅️ بازگشت به منوی اصلی":
        user_doc = await get_user_async(update.effective_user.id)
        await update.message.reply_text("منوی اصلی:", reply_markup=get_main_keyboard(user_doc))
        return ConversationHandler.END
        
    return AWAIT_ADMIN_REPLY

# Admin Handlers
async def process_admin_self_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text)
        await set_setting_async('self_bot_hourly_cost', val)
        await update.message.reply_text(f"✅ هزینه ساعتی سلف به {val} الماس تغییر کرد.", reply_markup=admin_keyboard)
    except: await update.message.reply_text("❌ عدد نامعتبر.")
    return ADMIN_MENU

async def process_admin_self_min(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text)
        await set_setting_async('self_bot_min_balance', val)
        await update.message.reply_text(f"✅ حداقل موجودی سلف به {val} الماس تغییر کرد.", reply_markup=admin_keyboard)
    except: await update.message.reply_text("❌ عدد نامعتبر.")
    return ADMIN_MENU

async def process_admin_self_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("❌ لطفا یک عکس ارسال کنید.", reply_markup=admin_keyboard)
        return AWAIT_ADMIN_SELF_PHOTO
    file_id = update.message.photo[-1].file_id
    await set_setting_async('self_panel_photo', file_id)
    await update.message.reply_text("✅ عکس پنل سلف با موفقیت تنظیم شد.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def show_channels_for_removal(update, context):
    channels = list(GLOBAL_CHANNELS.values())
    if not channels:
        await update.message.reply_text("هیچ کانالی وجود ندارد.", reply_markup=admin_keyboard); return ADMIN_MENU
    kb = [[InlineKeyboardButton(c['channel_username'], callback_data=f"admin_remove_{c['channel_username']}")] for c in channels]
    kb.append([InlineKeyboardButton("لغو", callback_data="admin_remove_cancel")])
    await update.message.reply_text("انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))
    return ADMIN_MENU

async def process_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ انجام شد.", reply_markup=admin_keyboard)
    return ADMIN_MENU

async def process_admin_set_balance_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text)
        context.user_data['target_user_id_balance'] = uid
        await get_user_async(uid)
        await update.message.reply_text(f"مقدار جدید برای {uid}:")
        return AWAIT_ADMIN_SET_BALANCE
    except: await update.message.reply_text("نامعتبر."); return ADMIN_MENU

async def process_admin_set_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        val = int(update.message.text)
        uid = context.user_data.pop('target_user_id_balance')
        u = await get_user_async(uid)
        u['balance'] = val
        save_user_immediate(uid)
        await update.message.reply_text("✅ انجام شد.", reply_markup=admin_keyboard)
    except: pass
    return ADMIN_MENU

async def process_admin_set_card_number(update, context): await set_setting_async('card_number', update.message.text); await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_set_card_holder(update, context): await set_setting_async('card_holder', update.message.text); await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_new_channel(update, context): 
    ch = update.message.text
    GLOBAL_CHANNELS[ch] = {'channel_username': ch, 'channel_title': ch}
    await update.message.reply_text("✅", reply_markup=admin_keyboard)
    return ADMIN_MENU
async def process_bet_photo(update, context):
    if update.message.photo: await set_setting_async('bet_photo_file_id', update.message.photo[-1].file_id)
    await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_add_balance_id(update, context): context.user_data['tid_add'] = int(update.message.text); await update.message.reply_text("مقدار افزودن:"); return AWAIT_ADMIN_ADD_BALANCE_AMOUNT
async def process_admin_add_balance_amount(update, context):
    uid = context.user_data.pop('tid_add'); amt = int(update.message.text)
    u = await get_user_async(uid); u['balance'] += amt; save_user_immediate(uid)
    await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_deduct_balance_id(update, context): context.user_data['tid_ded'] = int(update.message.text); await update.message.reply_text("مقدار کسر:"); return AWAIT_ADMIN_DEDUCT_BALANCE_AMOUNT
async def process_admin_deduct_balance_amount(update, context):
    uid = context.user_data.pop('tid_ded'); amt = int(update.message.text)
    u = await get_user_async(uid); u['balance'] -= amt; save_user_immediate(uid)
    await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_tax(update, context): await set_setting_async('bet_tax_rate', update.message.text); await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_credit_price(update, context): await set_setting_async('credit_price', update.message.text); await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_referral_price(update, context): await set_setting_async('referral_reward', update.message.text); await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_manage_user_id(update, context): context.user_data['tid_man'] = int(update.message.text); await update.message.reply_text("نقش (ادمین/مادریتور/کاربر عادی):"); return AWAIT_MANAGE_USER_ROLE
async def process_manage_user_role(update, context): 
    uid = context.user_data.pop('tid_man'); role = update.message.text
    u = await get_user_async(uid)
    if role == "ادمین": u['is_admin']=True; u['is_moderator']=False
    elif role == "مادریتور": u['is_admin']=False; u['is_moderator']=True
    else: u['is_admin']=False; u['is_moderator']=False
    save_user_immediate(uid)
    await update.message.reply_text("✅", reply_markup=admin_keyboard); return ADMIN_MENU
async def process_admin_broadcast(update, context):
    await update.message.reply_text("پیام ارسال شد.", reply_markup=admin_keyboard); return ADMIN_MENU

# --- Common Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_doc = await get_user_async(user.id)
    
    if update.effective_chat.type != 'private':
        await update.message.reply_text("👋 ربات شرط‌بندی فعال است.", reply_markup=bet_group_keyboard)
        return
        
    await update.message.reply_text("👋 به خدمات مجازی darkself خوش آمدید.", reply_markup=get_main_keyboard(user_doc))

async def show_balance(update, context):
    u = await get_user_async(update.effective_user.id)
    await update.message.reply_text(f"💰 موجودی: {u['balance']} الماس")

async def get_referral_link(update, context):
    link = f"https://t.me/{(await context.bot.get_me()).username}?start={update.effective_user.id}"
    await update.message.reply_text(f"لینک دعوت: {link}")

async def cancel_conversation(update, context):
    u = await get_user_async(update.effective_user.id)
    await update.message.reply_text("لغو شد.", reply_markup=get_main_keyboard(u))
    return ConversationHandler.END

# --- Callback & Inline Handlers ---
async def inline_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline query for panel."""
    query = update.inline_query.query
    if query == "panel":
        user_id = update.effective_user.id
        photo_id = get_panel_photo(user_id)
        markup = get_self_panel_keyboard_ptb(user_id)
        
        results = [
            InlineQueryResultArticle(
                id=str(secrets.randbelow(99999)),
                title="پنل تنظیمات سلف",
                input_message_content=InputTextMessageContent(f"⚡️ **مدیریت پیشرفته سلف بات**\n👤 کاربر: {user_id}\n\nوضعیت اتصال: ✅ برقرار", parse_mode=ParseMode.MARKDOWN),
                reply_markup=markup,
                thumbnail_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg"
            )
        ]
        await update.inline_query.answer(results, cache_time=0)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    # --- Self Bot Callbacks (Ported from Pyrogram) ---
    if data.startswith("toggle_") or data.startswith("cycle_") or data.startswith("lang_") or data.startswith("close_"):
        if str(user_id) not in data: # Security check: Ensure user clicks their own panel
             await query.answer("⛔️ این پنل متعلق به شما نیست!", show_alert=True)
             return

        if data.startswith("toggle_clock"):
            CLOCK_STATUS[user_id] = not CLOCK_STATUS.get(user_id, True)
            if user_id in ACTIVE_BOTS and CLOCK_STATUS[user_id]:
                 asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[user_id][0], user_id))
        
        elif data.startswith("cycle_font"):
            cur = USER_FONT_CHOICES.get(user_id, 'stylized')
            idx = (FONT_KEYS_ORDER.index(cur) + 1) % len(FONT_KEYS_ORDER)
            USER_FONT_CHOICES[user_id] = FONT_KEYS_ORDER[idx]
            CLOCK_STATUS[user_id] = True
            if user_id in ACTIVE_BOTS:
                 asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[user_id][0], user_id))

        elif data.startswith("toggle_bold"): BOLD_MODE_STATUS[user_id] = not BOLD_MODE_STATUS.get(user_id, False)
        elif data.startswith("toggle_sec"): SECRETARY_MODE_STATUS[user_id] = not SECRETARY_MODE_STATUS.get(user_id, False)
        elif data.startswith("toggle_seen"): AUTO_SEEN_STATUS[user_id] = not AUTO_SEEN_STATUS.get(user_id, False)
        elif data.startswith("toggle_pv"): PV_LOCK_STATUS[user_id] = not PV_LOCK_STATUS.get(user_id, False)
        elif data.startswith("toggle_anti"): ANTI_LOGIN_STATUS[user_id] = not ANTI_LOGIN_STATUS.get(user_id, False)
        elif data.startswith("toggle_type"):
            TYPING_MODE_STATUS[user_id] = not TYPING_MODE_STATUS.get(user_id, False)
            if TYPING_MODE_STATUS[user_id]: PLAYING_MODE_STATUS[user_id] = False
        elif data.startswith("toggle_game"):
            PLAYING_MODE_STATUS[user_id] = not PLAYING_MODE_STATUS.get(user_id, False)
            if PLAYING_MODE_STATUS[user_id]: TYPING_MODE_STATUS[user_id] = False
        elif data.startswith("toggle_g_enemy"): GLOBAL_ENEMY_STATUS[user_id] = not GLOBAL_ENEMY_STATUS.get(user_id, False)
        elif data.startswith("lang_"):
            l = data.split("_")[1]
            AUTO_TRANSLATE_TARGET[user_id] = l if AUTO_TRANSLATE_TARGET.get(user_id) != l else None
        
        elif data.startswith("close_panel"):
            await query.message.delete()
            return

        # Refresh Panel
        try:
            await query.edit_message_reply_markup(reply_markup=get_self_panel_keyboard_ptb(user_id))
        except: pass
        return

    # --- Other Callbacks ---
    if data == "check_join_membership":
        await query.message.delete()
        return

    if data.startswith("admin_remove_"):
        ch = data.replace("admin_remove_", "")
        if ch in GLOBAL_CHANNELS: del GLOBAL_CHANNELS[ch]
        await query.edit_message_text(f"حذف شد: {ch}")
        return

    if data.startswith("bet_"):
        bet_id = int(data.split('_')[2])
        if 'join' in data:
            await query.edit_message_text("✅ شما به شرط پیوستید! (darkself)")
        elif 'cancel' in data:
            await query.edit_message_text("❌ شرط لغو شد.")
        return

async def start_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BET_ID_COUNTER
    if not update.message: return
    
    amount = 100
    try:
        match = re.search(r'(\d+)', update.message.text)
        if match: amount = int(match.group(1))
    except: pass
    
    text = (
        f"♦️ — شرط جدید (ID: {BET_ID_COUNTER}) — ♦️\n"
        f"| 💰 | تعداد الماس : {amount:,}\n"
        f"| 👤 | سازنده : {get_user_display_name(update.effective_user)}\n"
        f"♦️ — خدمات مجازی darkself — ♦️"
    )
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ پیوستن", callback_data=f"bet_join_{BET_ID_COUNTER}"),
         InlineKeyboardButton("❌ لغو شرط", callback_data=f"bet_cancel_{BET_ID_COUNTER}")]
    ])
    
    BET_ID_COUNTER += 1
    await update.message.reply_text(text, reply_markup=kb)

async def group_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    sender = update.effective_user
    target_user = sender
    reply_to_message = update.message.reply_to_message
    if reply_to_message and reply_to_message.from_user:
        sender_doc = await get_user_async(sender.id)
        if sender_doc.get('is_admin') or sender_doc.get('is_moderator') or sender_doc.get('is_owner'):
            target_user = reply_to_message.from_user
    target_user_doc = await get_user_async(target_user.id)
    price_str = await get_setting_async('credit_price')
    try: price = int(price_str or 1000)
    except: price = 1000
    toman_value = target_user_doc['balance'] * price
    target_display_name = get_user_display_name(target_user)
    text = (f"👤 کاربر: {target_display_name}\n💰 موجودی الماس: {target_user_doc['balance']:,}\n💳 معادل تخمینی: {toman_value:,.0f} تومان")
    await update.message.reply_text(text)

async def transfer_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message or not update.message.reply_to_message.from_user:
        await update.message.reply_text("⚠️ برای انتقال باید روی پیام کاربر مورد نظر ریپلای کنید.")
        return
    sender = update.effective_user
    receiver = update.message.reply_to_message.from_user
    try:
        match = re.search(r'(\d+)', update.message.text)
        if not match: return
        amount = int(match.group(1))
        if amount <= 0: await update.message.reply_text("تعداد الماس انتقال باید مثبت باشد."); return
    except: await update.message.reply_text("خطا در خواندن تعداد."); return 
    try:
        sender_doc = await get_user_async(sender.id)
        if sender.id == receiver.id: await update.message.reply_text("انتقال به خود امکان‌پذیر نیست."); return
        if sender_doc['balance'] < amount: await update.message.reply_text("موجودی الماس شما کافی نیست."); return
        receiver_doc = await get_user_async(receiver.id)
        sender_doc['balance'] -= amount
        receiver_doc['balance'] += amount
        save_user_immediate(sender.id)
        save_user_immediate(receiver.id)
        sender_display_name = get_user_display_name(sender)
        receiver_display_name = get_user_display_name(receiver)
        text = (f"✅ انتقال موفق ✅\n\n👤 از: {sender_display_name}\n👥 به: {receiver_display_name}\n💰 تعداد: {amount:,} الماس")
        await update.message.reply_text(text)
    except Exception as e: logging.error(f"Error during transfer: {e}"); await update.message.reply_text("خطایی در هنگام انتقال رخ داد.")

async def show_bet_keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("منوی شرط:", reply_markup=bet_group_keyboard)

async def deduct_balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.reply_to_message: return
    admin_user = update.effective_user
    admin_doc = await get_user_async(admin_user.id)
    if not (admin_doc.get('is_admin') or admin_doc.get('is_moderator') or admin_doc.get('is_owner')): return
    target_user = update.message.reply_to_message.from_user
    if target_user.id == admin_user.id: await update.message.reply_text("شما نمی‌توانید از خودتان الماس کسر کنید."); return
    if target_user.id == OWNER_ID: await update.message.reply_text("شما نمی‌توانید از مالک اصلی الماس کسر کنید."); return
    match = re.search(r'(\d+)', update.message.text)
    if not match: await update.message.reply_text("لطفا مقدار عددی برای کسر را مشخص کنید."); return
    try:
        amount_to_deduct = int(match.group(1))
        if amount_to_deduct <= 0: await update.message.reply_text("مقدار کسر باید یک عدد مثبت باشد."); return
    except: await update.message.reply_text("مقدار وارد شده نامعتبر است."); return
    target_doc = await get_user_async(target_user.id)
    if target_doc.get('balance', 0) < amount_to_deduct: await update.message.reply_text(f"کاربر موجودی کافی ندارد."); return
    target_doc['balance'] -= amount_to_deduct
    save_user_immediate(target_user.id)
    admin_display_name = get_user_display_name(admin_user)
    tehran_time = datetime.now(TEHRAN_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
    receipt_text = (f"❌ {amount_to_deduct:,} الماس کسر شد.\n🧾 رسید:\n📤 ادمین: {admin_display_name}\n📥 کاربر: {get_user_display_name(target_user)}\n⏰ {tehran_time}")
    await update.message.reply_text(receipt_text)

# =======================================================
#  بخش ۸: اجرای اصلی
# =======================================================

async def post_init(application: Application):
    global BOT_USERNAME
    init_memory_db()
    
    # Store Bot Username for Inline Query
    try:
        me = await application.bot.get_me()
        BOT_USERNAME = me.username
        logging.info(f"Bot Username: {BOT_USERNAME}")
    except: pass

    # Restore sessions
    if sessions_collection is not None:
        count = 0
        for doc in sessions_collection.find():
            user_id = doc.get('real_owner_id')
            if user_id:
                u = await get_user_async(user_id)
                if u.get('self_active'):
                    asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), 'stylized'))
                    count += 1
        logging.info(f"Restored {count} active self-bots.")

    if application.job_queue:
        application.job_queue.run_repeating(billing_job, interval=60, first=10)
        logging.info("Billing job started.")

def main():
    Thread(target=lambda: web_app.run(host='0.0.0.0', port=10000), daemon=True).start()
    Thread(target=background_db_sync, daemon=True).start()

    from telegram.request import HTTPXRequest
    request = HTTPXRequest(connection_pool_size=8)
    
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .post_init(post_init)
        .build()
    )
    
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.Regex("^💰 موجودی$"), show_balance))
    application.add_handler(MessageHandler(filters.Regex("^🎁 الماس رایگان$"), get_referral_link))
    application.add_handler(MessageHandler(filters.Regex("^🔄 تمدید و ادامه سرویس$"), continue_service_handler))
    
    self_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🤖 فعال‌سازی سلف$"), self_bot_activation_entry)],
        states={
            AWAIT_SELF_CONTACT: [MessageHandler(filters.CONTACT, process_self_contact), MessageHandler(filters.Regex("^بازگشت$"), cancel_conversation)],
            AWAIT_SELF_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_self_code)],
            AWAIT_SELF_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_self_password)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        allow_reentry=True
    )
    application.add_handler(self_conv)

    admin_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👑 پنل ادمین$"), admin_panel_entry)],
        states={
            ADMIN_MENU: [
                MessageHandler(filters.Regex(r"^(⚙️ هزینه سلف \(ساعتی\)|💎 حداقل موجودی سلف)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(🖼 تنظیم عکس پنل سلف|🗑 حذف عکس پنل سلف)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(💳 تنظیم شماره کارت|👤 تنظیم صاحب کارت|مدیریت کاربر)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(➕ افزودن کانال عضویت|➖ حذف کانال عضویت|🖼 تنظیم عکس شرط)$"), process_admin_choice),
                MessageHandler(filters.Regex(r"^(💰 تنظیم الماس \(ست\)|➕ افزایش الماس کاربر|➖ کسر الماس کاربر|📈 تنظیم قیمت الماس|🎁 تنظیم پاداش دعوت|📉 تنظیم مالیات \(۰-۱۰۰\))$"), process_admin_choice),
                MessageHandler(filters.Regex("^(👁‍🗨 لیست کانال‌های عضویت|📊 آمار کلی|🗑 حذف عکس شرط)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(🔒 قفل عضویت: روشن|🔓 قفل عضویت: خاموش)$"), process_admin_choice),
                MessageHandler(filters.Regex("^(📢 پیام همگانی)$"), process_admin_choice),
                MessageHandler(filters.Regex("^⬅️ بازگشت به منوی اصلی$"), process_admin_choice),
            ],
            AWAIT_ADMIN_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_admin_reply)],
            AWAIT_ADMIN_SELF_COST: [MessageHandler(filters.TEXT, process_admin_self_cost)],
            AWAIT_ADMIN_SELF_MIN: [MessageHandler(filters.TEXT, process_admin_self_min)],
            AWAIT_ADMIN_SELF_PHOTO: [MessageHandler(filters.PHOTO, process_admin_self_photo)],
            AWAIT_ADMIN_SET_CARD_NUMBER: [MessageHandler(filters.TEXT, process_admin_set_card_number)],
            AWAIT_ADMIN_SET_CARD_HOLDER: [MessageHandler(filters.TEXT, process_admin_set_card_holder)],
            AWAIT_NEW_CHANNEL: [MessageHandler(filters.TEXT, process_new_channel)],
            AWAIT_BET_PHOTO: [MessageHandler(filters.PHOTO, process_bet_photo)],
            AWAIT_ADMIN_SET_BALANCE_ID: [MessageHandler(filters.TEXT, process_admin_set_balance_id)],
            AWAIT_ADMIN_SET_BALANCE: [MessageHandler(filters.TEXT, process_admin_set_balance)],
            AWAIT_ADMIN_ADD_BALANCE_ID: [MessageHandler(filters.TEXT, process_admin_add_balance_id)],
            AWAIT_ADMIN_ADD_BALANCE_AMOUNT: [MessageHandler(filters.TEXT, process_admin_add_balance_amount)],
            AWAIT_ADMIN_DEDUCT_BALANCE_ID: [MessageHandler(filters.TEXT, process_admin_deduct_balance_id)],
            AWAIT_ADMIN_DEDUCT_BALANCE_AMOUNT: [MessageHandler(filters.TEXT, process_admin_deduct_balance_amount)],
            AWAIT_ADMIN_TAX: [MessageHandler(filters.TEXT, process_admin_tax)],
            AWAIT_ADMIN_CREDIT_PRICE: [MessageHandler(filters.TEXT, process_admin_credit_price)],
            AWAIT_ADMIN_REFERRAL_PRICE: [MessageHandler(filters.TEXT, process_admin_referral_price)],
            AWAIT_MANAGE_USER_ID: [MessageHandler(filters.TEXT, process_manage_user_id)],
            AWAIT_MANAGE_USER_ROLE: [MessageHandler(filters.TEXT, process_manage_user_role)],
            AWAIT_BROADCAST_MESSAGE: [MessageHandler(filters.ALL, process_admin_broadcast)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        allow_reentry=True
    )
    application.add_handler(admin_conv)
    
    # Inline Handler for Panel
    application.add_handler(InlineQueryHandler(inline_query_handler))

    # Group Handlers
    application.add_handler(MessageHandler(filters.Regex(r'^(شرط|بت)$') & filters.ChatType.GROUPS, show_bet_keyboard_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(شرطبندی|شرط) \d+$') & filters.ChatType.GROUPS, start_bet_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(انتقال|transfer)\s+(\d+)$') & filters.REPLY & filters.ChatType.GROUPS, transfer_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^موجودی$') & filters.ChatType.GROUPS, group_balance_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^(کسر اعتبار|کسر) \d+$') & filters.REPLY & filters.ChatType.GROUPS, deduct_balance_handler))
    application.add_handler(MessageHandler(filters.Regex(r'^موجودی 💰$') & filters.ChatType.GROUPS, group_balance_handler))

    application.add_handler(CallbackQueryHandler(callback_query_handler))

    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
