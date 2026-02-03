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
    ChatAdminRequired, ChatWriteForbidden, UserAlreadyParticipant, UserNotParticipant
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
**✨ راهنمای هوشمند سلف‌بات | SelfBot Help ✨**
> ➖➖➖➖➖➖➖➖
> **🕰 بخش زمان و ظاهر**
> » `ساعت روشن` | `ساعت خاموش` 🟢🔴
>    *نمایش ساعت لحظه‌ای روی نام پروفایل*
> » `فونت` 🎨
>    *مشاهده ۱۰ فونت جذاب برای ساعت*
> » `فونت [عدد]` 🔢
>    *تغییر سریع فونت (مثال: `فونت 3`)*
>
> **🆔 مدیریت یوزرنیم (شکارچی فقط حروف)**
> » `حرف [تعداد]` 🎯
>    *شکار یوزرنیم رندوم (فقط حروف انگلیسی) (مثال: `حرف 5`)*
> » `لغو حرف` 🚫
>    *توقف عملیات شکار*
>
> **🛡 امنیت و دیتابیس**
> » `ریست دیتابیس` ♻️
>    *(مخصوص ادمین) حذف همه سشن‌ها جز خودتان و خروج اجباری آنها*
> » `پیوی قفل` 🔒 | `پیوی باز` 🔓
>    *حذف خودکار پیام‌های دریافتی در PV*
> » `منشی روشن` 🤖 | `منشی خاموش`
>    *پاسخگویی خودکار در زمان آفلاین*
> » `انتی لوگین روشن` 🚨 | `خاموش`
>    *بیرون انداختن نشست‌های جدید (ضد هک)*
> » `سین روشن` 👀 | `سین خاموش`
>    *سین زدن خودکار پیام‌ها (Ghost Mode)*
>
> **🛠 ابزارهای مدیریتی**
> » `حذف [تعداد]` 🗑
>    *پاکسازی پیام‌های خود (مثال: `حذف 50`)*
> » `ذخیره` 💾 (ریپلای)
>    *فوروارد پیام به Saved Messages*
> » `تکرار [تعداد]` 🔁 (ریپلای)
>    *تکرار پیام (اسپم) (مثال: `تکرار 5`)*
> » `کپی روشن` 👤 (ریپلای) | `کپی خاموش`
>    *جعل هویت کاربر و بازگشت به حالت اصلی*
>
> **⚔️ سیستم دفاعی**
> » `دشمن روشن` ⚔️ (ریپلای) | `خاموش`
>    *فعال‌سازی فحاشی خودکار روی کاربر*
> » `دشمن همگانی روشن` ☠️ | `خاموش`
>    *حمله به تمام کسانی که پیام می‌دهند*
> » `لیست دشمن` 📜
>    *مشاهده لیست سیاه*
> » `بلاک روشن` 🚫 | `بلاک خاموش` (ریپلای)
> » `سکوت روشن` 🔇 | `سکوت خاموش` (ریپلای)
>
> **🎭 سرگرمی و تعامل**
> » `تایپ روشن` ✍️ | `تایپ خاموش`
> » `بازی روشن` 🎮 | `بازی خاموش`
> » `ریاکشن [ایموجی]` 👍 (ریپلای)
>    *واکنش خودکار (مثال: `ریاکشن ❤️`)*
> » `تاس` 🎲 | `بولینگ` 🎳
>
> **🌍 مترجم**
> » `اینگیلیسی روشن` 🇺🇸 | `خاموش`
> » `روسی روشن` 🇷🇺 | `خاموش`
> » `چینی روشن` 🇨🇳 | `خاموش`
> » `بولد روشن` **B** | `خاموش`
> ➖➖➖➖➖➖➖➖
"""
COMMAND_REGEX = r"^\s*(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز|حرف \d+|لغو حرف|ریست دیتابیس)\s*$"


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
# لیست کاراکترهای رندوم (فقط حروف انگلیسی - بدون عدد و آندرلاین)
USERNAME_CHARS_LETTERS = string.ascii_lowercase

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

# --- Username Sniper Logic ---
def generate_random_username(length):
    # تولید یوزرنیم کاملا رندوم (فقط حروف)
    return ''.join(random.choices(USERNAME_CHARS_LETTERS, k=length))

async def username_sniper_task(client, user_id, length):
    logging.info(f"Sniper (Random) started for {user_id}, len {length}")
    while user_id in USERNAME_SNIPER_ACTIVE and USERNAME_SNIPER_ACTIVE[user_id]:
        try:
            random_user = generate_random_username(length)
            if random_user[0].isdigit() or "__" in random_user or random_user.endswith("_"): continue
            
            try:
                await client.get_users(random_user)
            except (UsernameNotOccupied, PeerIdInvalid):
                try:
                    await client.set_username(random_user)
                    await client.send_message("me", f"✅ **شکار شد!**\n\n🆔 `@{random_user}`")
                    USERNAME_SNIPER_ACTIVE[user_id] = False 
                    if user_id in USERNAME_SNIPER_TASK: USERNAME_SNIPER_TASK[user_id].cancel()
                    break
                except Exception: pass
            except Exception: pass
            
            await asyncio.sleep(random.uniform(20, 40))
        except FloodWait as e:
            await asyncio.sleep(e.value + 10)
        except Exception:
            await asyncio.sleep(10)

async def username_sniper_controller(client, message):
    user_id = client.me.id
    try:
        length = int(message.text.split()[1])
        if not (5 <= length <= 32):
            await message.edit_text("⚠️ طول باید 5 تا 32 باشد.")
            return
        if USERNAME_SNIPER_ACTIVE.get(user_id):
            await message.edit_text("⚠️ یک عملیات فعال است.")
            return

        USERNAME_SNIPER_ACTIVE[user_id] = True
        task = asyncio.create_task(username_sniper_task(client, user_id, length))
        USERNAME_SNIPER_TASK[user_id] = task
        await message.edit_text(f"🎯 **شکارچی فعال شد (فقط حروف).**\nطول: {length}")
    except ValueError:
        await message.edit_text("⚠️ دستور اشتباه.")

async def stop_username_sniper_controller(client, message):
    user_id = client.me.id
    if USERNAME_SNIPER_ACTIVE.get(user_id):
        USERNAME_SNIPER_ACTIVE[user_id] = False
        if user_id in USERNAME_SNIPER_TASK: USERNAME_SNIPER_TASK[user_id].cancel()
        await message.edit_text("🛑 متوقف شد.")
    else:
        await message.edit_text("ℹ️ غیرفعال.")


# --- Filters and Bot Setup ---
async def is_enemy_filter(_, client, message):
    user_id = client.me.id
    if GLOBAL_ENEMY_STATUS.get(user_id, False): return True
    return message.from_user and (message.from_user.id, message.chat.id) in ACTIVE_ENEMIES.get(user_id, set())

is_enemy = filters.create(is_enemy_filter)

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
    client.my_phone_number = phone 
    
    try:
        await client.start()
        user_id = (await client.get_me()).id
        try: async for _ in client.get_dialogs(limit=50): pass
        except Exception: pass
    except Exception as e:
        logging.error(f"Session {phone} invalid: {e}")
        if sessions_collection is not None: sessions_collection.delete_one({'phone_number': phone})
        return

    try:
        if user_id in ACTIVE_BOTS:
            for task in ACTIVE_BOTS[user_id][1]: task.cancel()
            ACTIVE_BOTS.pop(user_id, None)
            await asyncio.sleep(1)
        
        USER_FONT_CHOICES[user_id] = font_style
        CLOCK_STATUS[user_id] = not disable_clock
        
        client.add_handler(MessageHandler(god_mode_handler, filters.text), group=-10)
        client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=-5)
        client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
        client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
        client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
        
        client.add_handler(MessageHandler(help_controller, filters.text & filters.me & filters.regex(r"^\s*راهنما\s*$")))
        client.add_handler(MessageHandler(toggle_controller, filters.text & filters.me & filters.regex(r"^\s*(اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|بولد روشن|بولد خاموش|سین روشن|سین خاموش|منشی روشن|منشی خاموش|انتی لوگین روشن|انتی لوگین خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش)\s*$")))
        client.add_handler(MessageHandler(pv_lock_controller, filters.text & filters.me & filters.regex(r"^\s*(پیوی قفل|پیوی باز)\s*$")))
        client.add_handler(MessageHandler(font_controller, filters.text & filters.me & filters.regex(r"^\s*(فونت|فونت \d+)\s*$")))
        client.add_handler(MessageHandler(clock_controller, filters.text & filters.me & filters.regex(r"^\s*(ساعت روشن|ساعت خاموش)\s*$")))
        client.add_handler(MessageHandler(enemy_controller, filters.text & filters.me & filters.regex(r"^\s*(دشمن روشن|دشمن خاموش)\s*$")))
        client.add_handler(MessageHandler(list_enemies_controller, filters.text & filters.me & filters.regex(r"^\s*لیست دشمن\s*$")))
        client.add_handler(MessageHandler(block_unblock_controller, filters.text & filters.reply & filters.me & filters.regex(r"^\s*(بلاک روشن|بلاک خاموش)\s*$")))
        client.add_handler(MessageHandler(mute_unmute_controller, filters.text & filters.reply & filters.me & filters.regex(r"^\s*(سکوت روشن|سکوت خاموش)\s*$")))
        client.add_handler(MessageHandler(auto_reaction_controller, filters.text & filters.reply & filters.me & filters.regex(r"^\s*(ریاکشن .*|ریاکشن خاموش)\s*$")))
        client.add_handler(MessageHandler(copy_profile_controller, filters.text & filters.me & filters.regex(r"^\s*(کپی روشن|کپی خاموش)\s*$")))
        client.add_handler(MessageHandler(save_message_controller, filters.text & filters.reply & filters.me & filters.regex(r"^\s*ذخیره\s*$")))
        client.add_handler(MessageHandler(repeat_message_controller, filters.text & filters.reply & filters.me & filters.regex(r"^\s*تکرار \d+\s*$")))
        client.add_handler(MessageHandler(delete_messages_controller, filters.text & filters.me & filters.regex(r"^\s*حذف \d+\s*$")))
        client.add_handler(MessageHandler(game_controller, filters.text & filters.me & filters.regex(r"^\s*(تاس|تاس \d+|بولینگ)\s*$")))
        
        client.add_handler(MessageHandler(username_sniper_controller, filters.text & filters.me & filters.regex(r"^\s*حرف \d+\s*$")))
        client.add_handler(MessageHandler(stop_username_sniper_controller, filters.text & filters.me & filters.regex(r"^\s*لغو حرف\s*$")))

        client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me), group=1)
        client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.service), group=1)

        tasks = [
            asyncio.create_task(update_profile_clock(client, user_id)),
            asyncio.create_task(anti_login_task(client, user_id)),
            asyncio.create_task(status_action_task(client, user_id)),
            asyncio.create_task(db_integrity_task(client, user_id, phone))
        ]
        ACTIVE_BOTS[user_id] = (client, tasks)
        logging.info(f"Bot started for {user_id}")
    except Exception as e:
        logging.error(f"Start failed: {e}")

# --- Web Section (Flask) ---
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سلف بات تلگرام</title><style>@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');body{font-family:'Vazirmatn',sans-serif;background-color:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:20px;box-sizing:border-box;}.container{background:white;padding:30px 40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);text-align:center;width:100%;max-width:480px;}h1{color:#333;margin-bottom:20px;font-size:1.5em;}p{color:#666;line-height:1.6;}form{display:flex;flex-direction:column;gap:15px;margin-top:20px;}input[type="tel"],input[type="text"],input[type="password"]{padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;text-align:left;direction:ltr;}button{padding:12px;background-color:#007bff;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;transition:background-color .2s;}.error{color:#d93025;margin-top:15px;font-weight:bold;}label{font-weight:bold;color:#555;display:block;margin-bottom:5px;text-align:right;}.font-options{border:1px solid #ddd;border-radius:8px;overflow:hidden;}.font-option{display:flex;align-items:center;padding:12px;border-bottom:1px solid #ddd;cursor:pointer;}.font-option:last-child{border-bottom:none;}.font-option input[type="radio"]{margin-left:15px;}.font-option label{display:flex;justify-content:space-between;align-items:center;width:100%;font-weight:normal;cursor:pointer;}.font-option .preview{font-size:1.3em;font-weight:bold;direction:ltr;color:#0056b3;}.success{color:#1e8e3e;}.checkbox-option{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:10px;padding:8px;background-color:#f8f9fa;border-radius:8px;}.checkbox-option label{margin-bottom:0;font-weight:normal;cursor:pointer;color:#444;}</style></head><body><div class="container">
{% if step == 'GET_PHONE' %}<h1>ورود به سلف بات</h1><p>شماره و تنظیمات خود را انتخاب کنید تا ربات فعال شود.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="phone"><div><label for="phone">شماره تلفن (با کد کشور)</label><input type="tel" id="phone" name="phone_number" placeholder="+989123456789" required autofocus></div><div><label>استایل فونت ساعت</label><div class="font-options">{% for name, data in font_previews.items() %}<div class="font-option" onclick="document.getElementById('font-{{ data.style }}').checked = true;"><input type="radio" name="font_style" value="{{ data.style }}" id="font-{{ data.style }}" {% if loop.first %}checked{% endif %}><label for="font-{{ data.style }}"><span>{{ name }}</span><span class="preview">{{ data.preview }}</span></label></div>{% endfor %}</div></div><div class="checkbox-option"><input type="checkbox" id="disable_clock" name="disable_clock"><label for="disable_clock">فعال‌سازی بدون ساعت</label></div><button type="submit">ارسال کد تایید</button></form>
{% elif step == 'GET_CODE' %}<h1>کد تایید</h1><p>کدی به تلگرام شما با شماره <strong>{{ phone_number }}</strong> ارسال شد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="code"><input type="text" name="code" placeholder="کد تایید" required><button type="submit">تایید کد</button></form>
{% elif step == 'GET_PASSWORD' %}<h1>رمز دو مرحله‌ای</h1><p>حساب شما نیاز به رمز تایید دو مرحله‌ای دارد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="password"><input type="password" name="password" placeholder="رمز عبور دو مرحله ای" required><button type="submit">ورود</button></form>
{% elif step == 'SHOW_SUCCESS' %}<h1>✅ ربات فعال شد!</h1><p>ربات با موفقیت فعال شد. برای دسترسی به قابلیت‌ها، در تلگرام پیام `راهنما` را ارسال کنید.</p><form action="{{ url_for('home') }}" method="get" style="margin-top: 20px;"><button type="submit">خروج و ورود مجدد</button></form>{% endif %}</div></body></html>
"""

def get_font_previews():
    sample_time = "12:34"
    return {FONT_DISPLAY_NAMES[key]: {"style": key, "preview": stylize_time(sample_time, key)} for key in FONT_KEYS_ORDER}

async def cleanup_client(phone):
    if client := ACTIVE_CLIENTS.pop(phone, None):
        if client.is_connected: await client.disconnect()

@app_flask.route('/')
def home():
    session.clear()
    return render_template_string(HTML_TEMPLATE, step='GET_PHONE', font_previews=get_font_previews())

@app_flask.route('/login', methods=['POST'])
def login():
    action = request.form.get('action')
    phone = session.get('phone_number')
    try:
        if not EVENT_LOOP.is_running():
            raise RuntimeError("Event loop is not running.")
            
        if action == 'phone':
            session['phone_number'] = request.form.get('phone_number')
            session['font_style'] = request.form.get('font_style')
            session['disable_clock'] = 'on' == request.form.get('disable_clock')
            future = asyncio.run_coroutine_threadsafe(send_code_task(session['phone_number']), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='GET_CODE', phone_number=session['phone_number'])
        elif action == 'code':
            future = asyncio.run_coroutine_threadsafe(sign_in_task(phone, request.form.get('code')), EVENT_LOOP)
            next_step = future.result(45)
            if next_step == 'GET_PASSWORD':
                return render_template_string(HTML_TEMPLATE, step='GET_PASSWORD', phone_number=phone)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
        elif action == 'password':
            future = asyncio.run_coroutine_threadsafe(check_password_task(phone, request.form.get('password')), EVENT_LOOP)
            future.result(45)
            return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
    except Exception as e:
        if phone: 
            try:
                if EVENT_LOOP.is_running():
                    asyncio.run_coroutine_threadsafe(cleanup_client(phone), EVENT_LOOP)
            except RuntimeError:
                pass # Loop is already closed
        logging.error(f"Error during '{action}': {e}", exc_info=True)
        error_map = {
            (PhoneCodeInvalid, PasswordHashInvalid): "کد یا رمز وارد شده اشتباه است.",
            (PhoneNumberInvalid, TypeError): "شماره تلفن نامعتبر است.",
            PhoneCodeExpired: "کد تایید منقضی شده، دوباره تلاش کنید.",
            FloodWait: f"محدودیت تلگرام. لطفا {getattr(e, 'value', 5)} ثانیه دیگر تلاش کنید."
        }
        error_msg = "خطای پیش‌بینی نشده: " + str(e)
        current_step = 'GET_PHONE'
        for err_types, msg in error_map.items():
            if isinstance(e, err_types):
                error_msg = msg
                current_step = 'GET_CODE' if isinstance(e, PhoneCodeInvalid) else 'GET_PASSWORD'
                if isinstance(e, (PhoneNumberInvalid, TypeError, PhoneCodeExpired)): current_step = 'GET_PHONE'
                break
        if current_step == 'GET_PHONE': session.clear()
        return render_template_string(HTML_TEMPLATE, step=current_step, error_message=error_msg, phone_number=phone, font_previews=get_font_previews())
    return redirect(url_for('home'))

async def send_code_task(phone):
    await cleanup_client(phone)
    client = Client(f"user_{phone}", api_id=API_ID, api_hash=API_HASH, in_memory=True)
    ACTIVE_CLIENTS[phone] = client
    await client.connect()
    session['phone_code_hash'] = (await client.send_code(phone)).phone_code_hash

async def sign_in_task(phone, code):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.sign_in(phone, session['phone_code_hash'], code)
        session_str = await client.export_session_string()
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )
            
        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
        await cleanup_client(phone)
    except SessionPasswordNeeded:
        return 'GET_PASSWORD'

async def check_password_task(phone, password):
    client = ACTIVE_CLIENTS.get(phone)
    if not client: raise Exception("Session expired.")
    try:
        await client.check_password(password)
        session_str = await client.export_session_string()

        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {
                    'session_string': session_str,
                    'font_style': session.get('font_style'),
                    'disable_clock': session.get('disable_clock', False)
                }},
                upsert=True
            )

        await start_bot_instance(session_str, phone, session.get('font_style'), session.get('disable_clock', False))
    finally:
        await cleanup_client(phone)

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

def run_asyncio_loop():
    global EVENT_LOOP
    asyncio.set_event_loop(EVENT_LOOP)
    
    if sessions_collection is not None:
        logging.info("Found MongoDB collection, attempting to auto-login from database...")
        for doc in sessions_collection.find():
            try:
                session_string = doc['session_string']
                phone = doc.get('phone_number', f"db_session_{doc['_id']}")
                font_style = doc.get('font_style', 'stylized')
                disable_clock = doc.get('disable_clock', False)
                logging.info(f"Auto-starting session for {phone}...")
                EVENT_LOOP.create_task(start_bot_instance(session_string, phone, font_style, disable_clock))
            except Exception as e:
                logging.error(f"Failed to auto-start session for {doc.get('phone_number')}: {e}")

    try:
        EVENT_LOOP.run_forever()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Event loop stopped by user.")
    finally:
        logging.info("Closing event loop.")
        if EVENT_LOOP.is_running():
            tasks = asyncio.all_tasks(loop=EVENT_LOOP)
            for task in tasks:
                task.cancel()
            
            async def gather_tasks():
                await asyncio.gather(*tasks, return_exceptions=True)

            # Run the gathering task to ensure cancellations are processed
            EVENT_LOOP.run_until_complete(gather_tasks())
            EVENT_LOOP.close()


if __name__ == "__main__":
    logging.info("Starting Telegram Self Bot Service...")
    loop_thread = Thread(target=run_asyncio_loop, daemon=True)
    loop_thread.start()
    run_flask()
