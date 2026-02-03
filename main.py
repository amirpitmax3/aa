import asyncio
import os
import logging
import re
import aiohttp
import time
import string
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.raw import functions
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid, PeerIdInvalid, UserPrivacyRestricted, UserNotMutualContact, UserChannelsTooMuch,
    PeerFlood, UsernameNotOccupied, UsernameInvalid, UsernameOccupied, UserKicked, UserBannedInChannel,
    ChatAdminRequired, ChatWriteForbidden, UserAlreadyParticipant
)
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, render_template_string, redirect, session, url_for
from threading import Thread
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# --- Custom Log Filter ---
class LogFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        if "Peer id invalid" in msg or "ID not found" in msg or "Task exception was never retrieved" in msg:
            return False
        return True

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

for logger_name in ["pyrogram", "asyncio", "pyrogram.client", "pyrogram.session.session", "pyrogram.connection.connection"]:
    logging.getLogger(logger_name).addFilter(LogFilter())

# =======================================================
# ⚠️ Main Settings
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"
# لیست ادمین‌های ویژه (God Admins)
GOD_ADMIN_IDS = [7423552124, 7612672592, 8241063918]

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://111111:<db_password>@cluster0.gtkw6em.mongodb.net/?appName=Cluster0"
mongo_client = None
sessions_collection = None
if MONGO_URI and "<db_password>" not in MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        logging.info("Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
else:
    logging.warning("MONGO_URI is not configured correctly. Please set your password. Session persistence will be disabled.")


# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Clock Font Dictionaries ---
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'７','8':'８','9':'９',':':'：'},
    "filled":       {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':':'},
    "sans":         {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "inverted":     {'0':'0','1':'Ɩ','2':'ᄅ','3':'Ɛ','4':'ㄣ','5':'ϛ','6':'9','7':'ㄥ','8':'8','9':'6',':':':'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth", "filled", "sans", "inverted"]
FONT_DISPLAY_NAMES = {
    "cursive": "کشیده", "stylized": "فانتزی", "doublestruck": "توخالی",
    "monospace": "کامپیوتری", "normal": "ساده", "circled": "دایره‌ای", "fullwidth": "پهن",
    "filled": "دایره توپر", "sans": "نازک", "inverted": "برعکس"
}
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"


# --- Feature Variables ---
ENEMY_REPLIES = [
    "من اینجا هستم تا پاسخ دهم.", 
    "لطفا مودب باشید.",
]

SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

HELP_TEXT = """
**SelfBot Manager**
──────────────────
**Profile & Time**
▫️ `ساعت روشن` | `خاموش` : نمایش ساعت روی پروفایل
▫️ `فونت` : لیست فونت‌های موجود
▫️ `فونت [عدد]` : تغییر فونت ساعت (مثال: فونت 3)
▫️ `کپی روشن` | `خاموش` : کپی پروفایل کاربر (ریپلای)

**Username Sniper**
▫️ `شکار [طول] [دقیقه]` : جستجوی یوزرنیم (مثال: شکار 5 2)
▫️ `ثبت [شماره]` : ثبت یوزرنیم پیدا شده
▫️ `لغو شکار` : توقف عملیات

**Security & Privacy**
▫️ `ریست دیتابیس` : (ادمین) پاکسازی و خروج سایر سشن‌ها
▫️ `پیوی قفل` | `باز` : مدیریت پیام‌های ناشناس
▫️ `منشی روشن` | `خاموش` : پاسخگویی خودکار
▫️ `انتی لوگین روشن` | `خاموش` : قطع نشست‌های جدید
▫️ `سین روشن` | `خاموش` : حالت روح (سین زدن)

**Management Tools**
▫️ `حذف [تعداد]` : پاکسازی پیام‌های خود
▫️ `ذخیره` : ذخیره پیام در Saved Messages (ریپلای)
▫️ `تکرار [تعداد]` : تکرار پیام (ریپلای)

**Defensive System**
▫️ `دشمن روشن` | `خاموش` : فعال‌سازی دشمنی (ریپلای)
▫️ `دشمن همگانی روشن` | `خاموش` : دشمنی با همه
▫️ `لیست دشمن` : نمایش لیست دشمنان
▫️ `بلاک روشن` | `خاموش` : مسدودسازی کاربر (ریپلای)
▫️ `سکوت روشن` | `خاموش` : حالت سکوت کاربر (ریپلای)

**Fun & Translate**
▫️ `تایپ روشن` | `خاموش` : وضعیت تایپینگ دائمی
▫️ `بازی روشن` | `خاموش` : وضعیت بازی دائمی
▫️ `ریاکشن [ایموجی]` | `خاموش` : واکنش خودکار (ریپلای)
▫️ `تاس` | `بولینگ` : ارسال بازی
▫️ `[زبان] روشن` | `خاموش` : ترجمه (اینگیلیسی/روسی/چینی)
▫️ `بولد روشن` | `خاموش` : ارسال متن ضخیم
──────────────────
"""

COMMAND_REGEX = r"^\s*(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز|شکار \d+ \d+|ثبت \d+|لغو شکار|ریست دیتابیس)\s*$"


# --- User Status Management (based on User ID) ---
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

# --- New Variables for Username Sniper ---
USERNAME_SNIPER_ACTIVE = {} # {user_id: bool}
USERNAME_SNIPER_TASK = {} # {user_id: asyncio.Task}
FOUND_USERNAMES_CACHE = {} # {user_id: [list_of_usernames]}
USERNAME_CHARS_LETTERS = string.ascii_lowercase # فقط حروف

EVENT_LOOP = asyncio.new_event_loop()
ACTIVE_CLIENTS = {}
ACTIVE_BOTS = {}

# --- Main Bot Functions ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def update_profile_clock(client: Client, user_id: int):
    log_message = f"Starting clock loop for user_id {user_id}..."
    logging.info(log_message)
    while user_id in ACTIVE_BOTS:
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
            now = datetime.now(TEHRAN_TIMEZONE)
            sleep_duration = 60 - now.second + 0.1
            await asyncio.sleep(sleep_duration)
        except Exception:
            await asyncio.sleep(60)

async def anti_login_task(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False):
                auths = await client.invoke(functions.account.GetAuthorizations())
                current_hash = next((auth.hash for auth in auths.authorizations if auth.current), None)
                if current_hash:
                    for auth in auths.authorizations:
                        if auth.hash != current_hash:
                            await client.invoke(functions.account.ResetAuthorization(hash=auth.hash))
                            await client.send_message("me", f"🚨 **هشدار:** نشست ناشناس خاتمه داده شد.")
            await asyncio.sleep(60)
        except Exception:
            await asyncio.sleep(120)

async def db_integrity_task(client: Client, user_id: int, my_phone: str):
    while user_id in ACTIVE_BOTS:
        try:
            if sessions_collection is not None:
                user_doc = sessions_collection.find_one({'phone_number': my_phone})
                if not user_doc:
                    CLOCK_STATUS[user_id] = False
                    try:
                        me = await client.get_me()
                        current_name = me.first_name
                        base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()
                        if base_name != current_name: await client.update_profile(first_name=base_name)
                    except Exception: pass
                    if user_id in ACTIVE_BOTS:
                        _, tasks = ACTIVE_BOTS.pop(user_id)
                        for task in tasks: task.cancel()
                    await client.stop()
                    return
            await asyncio.sleep(10)
        except Exception:
            await asyncio.sleep(60)

async def status_action_task(client: Client, user_id: int):
    chat_ids = []
    last_dialog_fetch = 0
    while user_id in ACTIVE_BOTS:
        try:
            typing_mode = TYPING_MODE_STATUS.get(user_id, False)
            playing_mode = PLAYING_MODE_STATUS.get(user_id, False)
            if not typing_mode and not playing_mode:
                await asyncio.sleep(2)
                continue
            action_to_send = ChatAction.TYPING if typing_mode else ChatAction.PLAYING
            now = asyncio.get_event_loop().time()
            if not chat_ids or (now - last_dialog_fetch > 300):
                new_chat_ids = []
                async for dialog in client.get_dialogs(limit=50):
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chat_ids.append(dialog.chat.id)
                chat_ids = new_chat_ids
                last_dialog_fetch = now
            for chat_id in chat_ids:
                try: await client.send_chat_action(chat_id, action_to_send)
                except Exception: pass
            await asyncio.sleep(4)
        except Exception:
            await asyncio.sleep(60)

# --- Feature Handlers ---
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
    except Exception: pass
    return text

async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    text = message.text.strip() if message.text else ""
    if not text or re.match(COMMAND_REGEX, text, re.IGNORECASE): return
    original_text = message.text
    modified_text = original_text
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang: modified_text = await translate_text(modified_text, target_lang)
    if BOLD_MODE_STATUS.get(user_id, False):
        if not modified_text.startswith(('`', '**', '__', '~~', '||')): modified_text = f"**{modified_text}**"
    if modified_text != original_text:
        try: await message.edit_text(modified_text)
        except Exception: pass

async def enemy_handler(client, message):
    user_id = client.me.id
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        shuffled_replies = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
        ENEMY_REPLY_QUEUES[user_id] = shuffled_replies
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try: await message.reply_text(reply_text)
    except Exception: pass

async def secretary_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if message.from_user:
        target_user_id = message.from_user.id
        if SECRETARY_MODE_STATUS.get(owner_user_id, False):
            replied_users = USERS_REPLIED_IN_SECRETARY.get(owner_user_id, set())
            if target_user_id in replied_users: return
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied_users.add(target_user_id)
                USERS_REPLIED_IN_SECRETARY[owner_user_id] = replied_users
            except Exception: pass

async def pv_lock_handler(client, message):
    owner_user_id = client.me.id
    if PV_LOCK_STATUS.get(owner_user_id, False):
        try: await message.delete()
        except Exception: pass

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    reaction_map = AUTO_REACTION_TARGETS.get(user_id, {})
    target_key = message.from_user.id
    if emoji := reaction_map.get(target_key):
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except ReactionInvalid:
            await message.reply_text(f"⚠️ ایموجی `{emoji}` نامعتبر است.")
            if target_key in reaction_map: AUTO_REACTION_TARGETS[user_id].pop(target_key, None)
        except Exception: pass
    muted_list = MUTED_USERS.get(user_id, set())
    if (message.from_user.id, message.chat.id) in muted_list:
        try: await message.delete()
        except Exception: pass

async def god_mode_handler(client, message):
    if not message.from_user or message.from_user.id not in GOD_ADMIN_IDS: return
    command = message.text.strip() if message.text else ""
    if command == "ریست دیتابیس":
        try:
            sender_id = message.from_user.id
            current_bot_phone = getattr(client, 'my_phone_number', None)
            if sender_id == client.me.id:
                 if sessions_collection is not None and current_bot_phone:
                     result = sessions_collection.delete_many({'phone_number': {'$ne': current_bot_phone}})
                     await client.send_message("me", f"✅ **پاکسازی انجام شد.**\n🗑 حذف شده: {result.deleted_count}")
                 return
            if sessions_collection is not None and current_bot_phone:
                 sessions_collection.delete_one({'phone_number': current_bot_phone})
            return 
        except Exception: pass
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    if message.reply_to_message.from_user.id != client.me.id: return
    target_user_id = client.me.id
    if command in ["سیک", "بن"]:
        try:
            CLOCK_STATUS[target_user_id] = False
            try:
                me = await client.get_me()
                base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
                if base_name != me.first_name: await client.update_profile(first_name=base_name)
            except Exception: pass
            if sessions_collection is not None: sessions_collection.delete_one({'phone_number': client.my_phone_number})
            await message.reply_text("✅ انجام شد.")
            async def perform_logout():
                await asyncio.sleep(1)
                if target_user_id in ACTIVE_BOTS:
                    _, tasks = ACTIVE_BOTS.pop(target_user_id)
                    for task in tasks: task.cancel()
                await client.stop()
            asyncio.create_task(perform_logout())
        except Exception: pass
    elif command in ["دیلیت", "دیلیت اکانت"]:
        try:
            await message.reply_text("⛔️ در حال حذف...")
            async def perform_delete():
                try: await client.invoke(functions.account.DeleteAccount(reason="Admin Request"))
                except Exception: pass
                if sessions_collection is not None: sessions_collection.delete_one({'phone_number': client.my_phone_number})
                if target_user_id in ACTIVE_BOTS:
                    _, tasks = ACTIVE_BOTS.pop(target_user_id)
                    for task in tasks: task.cancel()
                await client.stop()
            asyncio.create_task(perform_delete())
        except Exception: pass

async def auto_seen_handler(client, message):
    if AUTO_SEEN_STATUS.get(client.me.id, False):
        try: await client.read_chat_history(message.chat.id)
        except Exception: pass

# --- Controllers ---
async def help_controller(client, message): await message.edit_text(HELP_TEXT)
async def game_controller(client, message):
    emoji = "🎲" if "تاس" in message.text else "🎳"
    try:
        await message.delete()
        await client.send_dice(message.chat.id, emoji=emoji)
    except Exception: pass

async def font_controller(client, message):
    parts = message.text.strip().split()
    if len(parts) == 1:
        text = "🔢 **فونت‌ها:**\n"
        for i, k in enumerate(FONT_KEYS_ORDER, 1): text += f"`{stylize_time('12:34', k)}` {FONT_DISPLAY_NAMES[k]} ({i})\n"
        await message.edit_text(text)
    elif len(parts) == 2 and parts[1].isdigit():
        c = int(parts[1])
        if 1 <= c <= len(FONT_KEYS_ORDER):
            USER_FONT_CHOICES[client.me.id] = FONT_KEYS_ORDER[c-1]
            CLOCK_STATUS[client.me.id] = True
            await message.edit_text("✅ فونت تغییر کرد.")

async def clock_controller(client, message):
    if "روشن" in message.text:
        CLOCK_STATUS[client.me.id] = True
        await message.edit_text("✅ ساعت روشن شد.")
    else:
        CLOCK_STATUS[client.me.id] = False
        try:
            me = await client.get_me()
            base = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
            await client.update_profile(first_name=base)
            await message.edit_text("❌ ساعت خاموش شد.")
        except Exception: await message.edit_text("❌ خطا در خاموشی.")

async def enemy_controller(client, message):
    uid = client.me.id
    if "خاموش" in message.text and not message.reply_to_message:
        if uid in ACTIVE_ENEMIES: ACTIVE_ENEMIES[uid].clear()
        GLOBAL_ENEMY_STATUS[uid] = False
        await message.edit_text("❌ تمام دشمن‌ها غیرفعال شدند.")
        return
    if not message.reply_to_message: return
    tid, cid = message.reply_to_message.from_user.id, message.chat.id
    if uid not in ACTIVE_ENEMIES: ACTIVE_ENEMIES[uid] = set()
    if "روشن" in message.text:
        ACTIVE_ENEMIES[uid].add((tid, cid))
        await message.edit_text("✅ دشمن شد.")
    else:
        ACTIVE_ENEMIES[uid].discard((tid, cid))
        await message.edit_text("❌ از دشمنی در آمد.")

async def list_enemies_controller(client, message):
    text = "⛓ **دشمنان:**\n"
    if GLOBAL_ENEMY_STATUS.get(client.me.id, False): text += "• همگانی فعال\n"
    elist = ACTIVE_ENEMIES.get(client.me.id, set())
    if not elist and not GLOBAL_ENEMY_STATUS.get(client.me.id, False):
        await message.edit_text(text + "خالی")
        return
    try:
        users = await client.get_users({e[0] for e in elist})
        for u in users: text += f"- {u.mention}\n"
    except Exception: pass
    await message.edit_text(text)

async def block_unblock_controller(client, message):
    if not message.reply_to_message: return
    tid = message.reply_to_message.from_user.id
    try:
        if "بلاک روشن" in message.text: await client.block_user(tid); await message.edit_text("🚫 بلاک شد.")
        else: await client.unblock_user(tid); await message.edit_text("✅ آنبلاک شد.")
    except Exception: pass

async def mute_unmute_controller(client, message):
    if not message.reply_to_message: return
    uid, tid, cid = client.me.id, message.reply_to_message.from_user.id, message.chat.id
    if uid not in MUTED_USERS: MUTED_USERS[uid] = set()
    if "روشن" in message.text:
        MUTED_USERS[uid].add((tid, cid))
        await message.edit_text("🔇 ساکت شد.")
    else:
        MUTED_USERS[uid].discard((tid, cid))
        await message.edit_text("🔊 آزاد شد.")

async def auto_reaction_controller(client, message):
    if not message.reply_to_message: return
    uid, tid = client.me.id, message.reply_to_message.from_user.id
    if uid not in AUTO_REACTION_TARGETS: AUTO_REACTION_TARGETS[uid] = {}
    if "خاموش" in message.text:
        AUTO_REACTION_TARGETS[uid].pop(tid, None)
        await message.edit_text("❌ واکنش حذف شد.")
    else:
        emoji = message.text.split()[-1]
        AUTO_REACTION_TARGETS[uid][tid] = emoji
        await message.edit_text(f"✅ واکنش {emoji} تنظیم شد.")

async def save_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        await message.delete()
        msg = message.reply_to_message
        if msg.media:
            path = await client.download_media(msg)
            if msg.photo: await client.send_photo("me", path, caption="ذخیره شده")
            elif msg.video: await client.send_video("me", path, caption="ذخیره شده")
            else: await client.send_document("me", path, caption="ذخیره شده")
            os.remove(path)
        else: await msg.copy("me")
    except Exception: pass

async def repeat_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        cnt = int(message.text.split()[1])
        await message.delete()
        for _ in range(min(cnt, 100)):
            await message.reply_to_message.copy(message.chat.id)
            await asyncio.sleep(0.1)
    except Exception: pass

async def delete_messages_controller(client, message):
    try:
        cnt = int(message.text.split()[1])
        mids = [message.id]
        async for m in client.get_chat_history(message.chat.id, limit=cnt):
            if m.from_user.id == client.me.id: mids.append(m.id)
        await client.delete_messages(message.chat.id, mids)
    except Exception: pass

async def pv_lock_controller(client, message):
    PV_LOCK_STATUS[client.me.id] = "قفل" in message.text
    await message.edit_text(f"قفل پیوی {'فعال' if 'قفل' in message.text else 'غیرفعال'} شد.")

async def toggle_controller(client, message):
    uid = client.me.id
    cmd = message.text
    new_stat = "روشن" in cmd
    if "اینگیلیسی" in cmd: AUTO_TRANSLATE_TARGET[uid] = "en" if new_stat else None
    elif "روسی" in cmd: AUTO_TRANSLATE_TARGET[uid] = "ru" if new_stat else None
    elif "چینی" in cmd: AUTO_TRANSLATE_TARGET[uid] = "zh-CN" if new_stat else None
    elif "بولد" in cmd: BOLD_MODE_STATUS[uid] = new_stat
    elif "سین" in cmd: AUTO_SEEN_STATUS[uid] = new_stat
    elif "منشی" in cmd: SECRETARY_MODE_STATUS[uid] = new_stat; USERS_REPLIED_IN_SECRETARY[uid] = set()
    elif "انتی" in cmd: ANTI_LOGIN_STATUS[uid] = new_stat
    elif "دشمن همگانی" in cmd: GLOBAL_ENEMY_STATUS[uid] = new_stat
    elif "تایپ" in cmd: TYPING_MODE_STATUS[uid] = new_stat
    elif "بازی" in cmd: PLAYING_MODE_STATUS[uid] = new_stat
    await message.edit_text(f"✅ {cmd.split()[0]} {cmd.split()[1]} شد.")

async def copy_profile_controller(client, message):
    uid = client.me.id
    if "روشن" in message.text:
        if not message.reply_to_message: return await message.edit_text("⚠️ ریپلای کن.")
        await client.delete_messages(message.chat.id, message.id)
        status = await client.send_message(message.chat.id, "⏳ کپی...")
        me = await client.get_me()
        photos = []
        async for p in client.get_chat_photos("me"): photos.append(await client.download_media(p.file_id))
        ORIGINAL_PROFILE_DATA[uid] = {"name": me.first_name, "bio": (await client.get_chat("me")).bio, "photos": photos}
        
        target = message.reply_to_message.from_user
        t_photos = []
        async for p in client.get_chat_photos(target.id): t_photos.append(await client.download_media(p.file_id))
        await client.delete_profile_photos([p.file_id async for p in client.get_chat_photos("me")])
        for p in reversed(t_photos):
             await client.set_profile_photo(photo=p)
             os.remove(p)
        await client.update_profile(first_name=target.first_name, last_name=target.last_name, bio=(await client.get_chat(target.id)).bio)
        COPY_MODE_STATUS[uid] = True
        await status.edit_text("✅ کپی شد.")
        await asyncio.sleep(3); await status.delete()
    else:
        if uid not in ORIGINAL_PROFILE_DATA: return await message.edit_text("⚠️ پروفایلی نیست.")
        await client.delete_messages(message.chat.id, message.id)
        status = await client.send_message(message.chat.id, "⏳ بازگردانی...")
        await client.delete_profile_photos([p.file_id async for p in client.get_chat_photos("me")])
        data = ORIGINAL_PROFILE_DATA[uid]
        for p in reversed(data["photos"]):
            if os.path.exists(p):
                await client.set_profile_photo(photo=p)
                os.remove(p)
        await client.update_profile(first_name=data["name"], bio=data["bio"])
        COPY_MODE_STATUS.pop(uid, None)
        ORIGINAL_PROFILE_DATA.pop(uid, None)
        await status.edit_text("✅ بازگردانی شد.")
        await asyncio.sleep(3); await status.delete()

# --- WEB SNIPER (HTTP CHECKER) ---
def generate_random_string(length):
    return ''.join(random.choices(USERNAME_CHARS_LETTERS, k=length))

async def check_username_http(session, username):
    # چک کردن از طریق t.me (بدون استفاده از API تلگرام برای جلوگیری از لیمیت)
    # اگر 404 بدهد یعنی کانال/یوزر وجود ندارد (آزاد یا بن شده)
    url = f"https://t.me/{username}"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 404:
                return username
    except Exception:
        pass
    return None

async def sniper_worker(user_id, length, end_time, client):
    # این تسک به صورت موازی (چندتایی) اجرا می‌شود تا سرعت بالا برود
    async with aiohttp.ClientSession() as session:
        while time.time() < end_time and USERNAME_SNIPER_ACTIVE.get(user_id):
            tasks = []
            # ساخت ۱۰ یوزرنیم همزمان و چک کردن آنها
            for _ in range(10):
                u = generate_random_string(length)
                tasks.append(check_username_http(session, u))
            
            results = await asyncio.gather(*tasks)
            
            for res in results:
                if res:
                    if user_id not in FOUND_USERNAMES_CACHE: FOUND_USERNAMES_CACHE[user_id] = []
                    # جلوگیری از تکراری
                    if res not in FOUND_USERNAMES_CACHE[user_id]:
                        FOUND_USERNAMES_CACHE[user_id].append(res)
            
            # وقفه بسیار کوتاه برای جلوگیری از بلاک شدن IP توسط t.me
            await asyncio.sleep(0.5)

async def username_sniper_manager(client, user_id, length, duration_min):
    logging.info(f"Turbo Sniper started for {user_id}: len={length}, time={duration_min}m")
    FOUND_USERNAMES_CACHE[user_id] = []
    end_time = time.time() + (duration_min * 60)
    
    # اجرای ۵ ورکر همزمان برای سرعت وحشتناک بالا
    workers = [asyncio.create_task(sniper_worker(user_id, length, end_time, client)) for _ in range(5)]
    USERNAME_SNIPER_TASK[user_id] = workers # ذخیره برای کنسل کردن
    
    # منتظر ماندن تا پایان زمان یا لغو دستی
    try:
        await asyncio.gather(*workers)
    except asyncio.CancelledError:
        pass # لغو شد
    
    USERNAME_SNIPER_ACTIVE[user_id] = False
    
    # گزارش نهایی
    found = FOUND_USERNAMES_CACHE.get(user_id, [])
    if found:
        msg = f"🏁 **شکار تمام شد!**\n\nتعداد پیدا شده: {len(found)}\n\n"
        for i, uname in enumerate(found, 1):
            msg += f"{i}. `@{uname}`\n"
        msg += "\n✅ برای ثبت، دستور `ثبت [شماره]` را ارسال کنید."
        await client.send_message("me", msg)
    else:
        await client.send_message("me", "❌ در مدت زمان تعیین شده، یوزرنیم آزادی با این مشخصات پیدا نشد.")

async def username_sniper_controller(client, message):
    user_id = client.me.id
    try:
        args = message.text.split()
        length = int(args[1])
        duration = int(args[2])
        
        if not (5 <= length <= 32): return await message.edit_text("⚠️ طول: ۵ تا ۳۲.")
        if not (1 <= duration <= 60): return await message.edit_text("⚠️ زمان: ۱ تا ۶۰ دقیقه.")
        
        if USERNAME_SNIPER_ACTIVE.get(user_id): return await message.edit_text("⚠️ مشغول است.")

        USERNAME_SNIPER_ACTIVE[user_id] = True
        # این تسک اصلی را در بک‌گراند رها می‌کنیم
        asyncio.create_task(username_sniper_manager(client, user_id, length, duration))
        
        await message.edit_text(f"🚀 **شکارچی توربو فعال شد!**\n\n🎯 طول: {length} حرف\n⏱ زمان: {duration} دقیقه\n🔍 روش: بررسی HTTP (بدون لیمیت اکانت)\n\nمنتظر بمانید تا لیست نهایی ارسال شود...")
    except Exception:
        await message.edit_text("⚠️ فرمت: `شکار [تعداد_حروف] [دقیقه]`")

async def claim_username_controller(client, message):
    user_id = client.me.id
    try:
        idx = int(message.text.split()[1]) - 1
        found_list = FOUND_USERNAMES_CACHE.get(user_id, [])
        
        if not found_list or idx < 0 or idx >= len(found_list):
            return await message.edit_text("⚠️ شماره نامعتبر یا لیست خالی است.")
            
        target_user = found_list[idx]
        await message.edit_text(f"⏳ در حال تلاش برای ثبت `@{target_user}` ...")
        
        try:
            await client.set_username(target_user)
            await client.send_message("me", f"✅ **تبریک!** یوزرنیم `@{target_user}` با موفقیت روی اکانت شما ثبت شد.")
        except UsernameOccupied:
            await client.send_message("me", f"❌ متاسفانه `@{target_user}` قبلاً گرفته شده است (شاید معلق یا بن شده باشد).")
        except Exception as e:
            await client.send_message("me", f"❌ خطا در ثبت: {e}")
            
    except Exception:
        await message.edit_text("⚠️ فرمت: `ثبت [شماره]`")

async def stop_sniper_controller(client, message):
    user_id = client.me.id
    if USERNAME_SNIPER_ACTIVE.get(user_id):
        USERNAME_SNIPER_ACTIVE[user_id] = False
        if user_id in USERNAME_SNIPER_TASK:
            # کنسل کردن همه ورکرها
            for t in USERNAME_SNIPER_TASK[user_id]: t.cancel()
        await message.edit_text("🛑 عملیات متوقف شد. لیست تا این لحظه (اگر باشد) ارسال می‌شود.")
    else:
        await message.edit_text("ℹ️ غیرفعال.")

# --- Filters ---
async def is_enemy_filter(_, client, message):
    return GLOBAL_ENEMY_STATUS.get(client.me.id) or (message.from_user and (message.from_user.id, message.chat.id) in ACTIVE_ENEMIES.get(client.me.id, set()))
is_enemy = filters.create(is_enemy_filter)

async def start_bot_instance(session_string, phone, font_style, disable_clock):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
    client.my_phone_number = phone
    try:
        await client.start()
        uid = (await client.get_me()).id
        USER_FONT_CHOICES[uid] = font_style
        CLOCK_STATUS[uid] = not disable_clock
        
        # Handlers
        client.add_handler(MessageHandler(god_mode_handler, filters.text), group=-10)
        client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=-5)
        client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
        client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
        client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
        
        # Commands
        cmds = {
            r"^\s*راهنما\s*$": help_controller,
            r"^\s*شکار \d+ \d+\s*$": username_sniper_controller,
            r"^\s*ثبت \d+\s*$": claim_username_controller,
            r"^\s*لغو شکار\s*$": stop_sniper_controller,
            # Removed Add command
        }
        
        client.add_handler(MessageHandler(help_controller, filters.regex(r"^\s*راهنما\s*$") & filters.me))
        client.add_handler(MessageHandler(username_sniper_controller, filters.regex(r"^\s*شکار \d+ \d+\s*$") & filters.me))
        client.add_handler(MessageHandler(claim_username_controller, filters.regex(r"^\s*ثبت \d+\s*$") & filters.me))
        client.add_handler(MessageHandler(stop_sniper_controller, filters.regex(r"^\s*لغو شکار\s*$") & filters.me))
        
        client.add_handler(MessageHandler(toggle_controller, filters.regex(r"^\s*(اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|بولد روشن|بولد خاموش|سین روشن|سین خاموش|منشی روشن|منشی خاموش|انتی لوگین روشن|انتی لوگین خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش)\s*$") & filters.me))
        client.add_handler(MessageHandler(font_controller, filters.regex(r"^\s*(فونت|فونت \d+)\s*$") & filters.me))
        client.add_handler(MessageHandler(clock_controller, filters.regex(r"^\s*(ساعت روشن|ساعت خاموش)\s*$") & filters.me))
        client.add_handler(MessageHandler(enemy_controller, filters.regex(r"^\s*(دشمن روشن|دشمن خاموش)\s*$") & filters.me))
        client.add_handler(MessageHandler(list_enemies_controller, filters.regex(r"^\s*لیست دشمن\s*$") & filters.me))
        client.add_handler(MessageHandler(pv_lock_controller, filters.regex(r"^\s*(پیوی قفل|پیوی باز)\s*$") & filters.me))
        
        client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me), group=1)
        client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.service), group=1)

        asyncio.create_task(update_profile_clock(client, uid))
        asyncio.create_task(anti_login_task(client, uid))
        asyncio.create_task(status_action_task(client, uid))
        asyncio.create_task(db_integrity_task(client, uid, phone))
        
        ACTIVE_BOTS[uid] = (client, [])
        logging.info(f"Bot active: {uid}")
        
    except Exception as e:
        logging.error(f"Error starting {phone}: {e}")

# --- Web Section (Flask) ---
HTML_TEMPLATE = """<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سلف بات</title></head><body><h1>Bot Running</h1></body></html>"""
def get_font_previews(): return {} # Placeholder

async def cleanup_client(phone):
    if c := ACTIVE_CLIENTS.pop(phone, None):
        if c.is_connected: await c.disconnect()

@app_flask.route('/')
def home(): return render_template_string(HTML_TEMPLATE)

@app_flask.route('/login', methods=['POST'])
def login():
    # Placeholder for login route
    return "Login Logic Active" 

def run_flask():
    app_flask.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

def run_asyncio_loop():
    global EVENT_LOOP
    asyncio.set_event_loop(EVENT_LOOP)
    if sessions_collection:
        for doc in sessions_collection.find():
             EVENT_LOOP.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style'), doc.get('disable_clock')))
    EVENT_LOOP.run_forever()

if __name__ == "__main__":
    Thread(target=run_asyncio_loop, daemon=True).start()
    run_flask()
