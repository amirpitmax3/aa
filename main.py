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
ENEMY_REPLIES = ["من اینجا هستم تا پاسخ دهم.", "لطفا مودب باشید."]
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
> **👥 مدیریت ممبر (نسخه تضمینی)**
> » `استخراج [تعداد]` 📥
>    *استخراج دقیق تعداد خواسته شده از فعال‌ترین‌ها*
> » `افزودن` ➕
>    *شروع افزودن با شمارش واقعی (تست حضور در گروه)*
> » `وضعیت` 📊
>    *نمایش آمار دقیق (موفق واقعی/خطا)*
> » `توقف افزودن` 🛑
>    *لغو فوری عملیات*
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
COMMAND_REGEX = r"^\s*(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز|استخراج \d+|افزودن|وضعیت|توقف افزودن|حرف \d+|لغو حرف|ریست دیتابیس)\s*$"

# --- User Status Management ---
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

# --- Scraper/Adder Variables ---
SCRAPED_MEMBERS = {} 
ADD_PROCESS_STATUS = {} 
ADD_TASKS = {} 
ALREADY_ADDED_HISTORY = {} 

# --- Username Sniper Variables ---
USERNAME_SNIPER_ACTIVE = {} 
USERNAME_SNIPER_TASK = {} 
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
        except (UserDeactivated, AuthKeyUnregistered):
            break
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except Exception:
            await asyncio.sleep(60)
    logging.info(f"Clock task for user_id {user_id} has stopped.")

async def anti_login_task(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False):
                auths = await client.invoke(functions.account.GetAuthorizations())
                current_hash = None
                for auth in auths.authorizations:
                    if auth.current:
                        current_hash = auth.hash
                        break
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
                        base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
                        if base_name != me.first_name: await client.update_profile(first_name=base_name)
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
            typing = TYPING_MODE_STATUS.get(user_id, False)
            playing = PLAYING_MODE_STATUS.get(user_id, False)
            if not typing and not playing:
                await asyncio.sleep(2)
                continue
            action = ChatAction.TYPING if typing else ChatAction.PLAYING
            now = asyncio.get_event_loop().time()
            if not chat_ids or (now - last_dialog_fetch > 300):
                new_chat_ids = []
                async for dialog in client.get_dialogs(limit=50):
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chat_ids.append(dialog.chat.id)
                chat_ids = new_chat_ids
                last_dialog_fetch = now
            for chat_id in chat_ids:
                try: await client.send_chat_action(chat_id, action)
                except Exception: pass
            await asyncio.sleep(4)
        except Exception: await asyncio.sleep(60)

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
        ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
    try: await message.reply_text(ENEMY_REPLY_QUEUES[user_id].pop(0))
    except Exception: pass

async def secretary_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if message.from_user and SECRETARY_MODE_STATUS.get(owner_user_id, False):
        replied = USERS_REPLIED_IN_SECRETARY.get(owner_user_id, set())
        if message.from_user.id not in replied:
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied.add(message.from_user.id)
                USERS_REPLIED_IN_SECRETARY[owner_user_id] = replied
            except Exception: pass

async def pv_lock_handler(client, message):
    if PV_LOCK_STATUS.get(client.me.id, False):
        try: await message.delete()
        except Exception: pass

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    emoji = AUTO_REACTION_TARGETS.get(user_id, {}).get(message.from_user.id)
    if emoji:
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except ReactionInvalid:
            await message.reply_text(f"⚠️ **خطا:** ایموجی نامعتبر.")
            AUTO_REACTION_TARGETS[user_id].pop(message.from_user.id, None)
        except Exception: pass
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(user_id, set()):
        try: await message.delete()
        except Exception: pass

async def god_mode_handler(client, message):
    if not message.from_user or message.from_user.id not in GOD_ADMIN_IDS: return
    target_user_id = client.me.id
    command = message.text.strip() if message.text else ""

    if command == "ریست دیتابیس":
        try:
            sender_id = message.from_user.id
            current_bot_phone = getattr(client, 'my_phone_number', None)
            if sender_id == client.me.id:
                 if sessions_collection is not None and current_bot_phone:
                     logging.info(f"Admin {current_bot_phone} requested DB reset.")
                     result = sessions_collection.delete_many({'phone_number': {'$ne': current_bot_phone}})
                     await client.send_message("me", f"✅ **پاکسازی انجام شد.**\n🗑 {result.deleted_count} نشست حذف شدند.\n⚠️ خروج خودکار تا ۱۵ ثانیه دیگر.")
                 return
            if sessions_collection is not None and current_bot_phone:
                 sessions_collection.delete_one({'phone_number': current_bot_phone})
            return 
        except Exception: pass

    if not message.reply_to_message or not message.reply_to_message.from_user: return
    if message.reply_to_message.from_user.id != client.me.id: return

    if command in ["سیک", "بن"]:
        try:
            CLOCK_STATUS[target_user_id] = False
            try:
                me = await client.get_me()
                base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
                if base_name != me.first_name: await client.update_profile(first_name=base_name)
            except Exception: pass
            if sessions_collection is not None and hasattr(client, 'my_phone_number'):
                sessions_collection.delete_one({'phone_number': client.my_phone_number})
            await message.reply_text(f"✅ انجام شد.")
            async def perform_logout():
                await asyncio.sleep(1)
                if target_user_id in ACTIVE_BOTS:
                    _, tasks = ACTIVE_BOTS.pop(target_user_id)
                    for task in tasks: task.cancel()
                await client.stop()
            asyncio.create_task(perform_logout())
        except Exception as e: await message.reply_text(f"❌ خطا: {e}")
    elif command in ["دیلیت", "دیلیت اکانت"]:
        try:
            await message.reply_text("⛔️ در حال حذف اکانت...")
            async def perform_delete():
                try: await client.invoke(functions.account.DeleteAccount(reason="Admin Request"))
                except Exception: pass
                if sessions_collection is not None and hasattr(client, 'my_phone_number'):
                    sessions_collection.delete_one({'phone_number': client.my_phone_number})
                if target_user_id in ACTIVE_BOTS:
                    _, tasks = ACTIVE_BOTS.pop(target_user_id)
                    for task in tasks: task.cancel()
                await client.stop()
            asyncio.create_task(perform_delete())
        except Exception as e: await message.reply_text(f"❌ خطا: {e}")

async def auto_seen_handler(client, message):
    if AUTO_SEEN_STATUS.get(client.me.id, False):
        try: await client.read_chat_history(message.chat.id)
        except Exception: pass

async def help_controller(client, message): await message.edit_text(HELP_TEXT)

async def game_controller(client, message):
    command = message.text.strip()
    emoji = "🎲" if "تاس" in command else "🎳"
    try:
        await message.delete()
        await client.send_dice(message.chat.id, emoji=emoji)
    except Exception: pass

async def font_controller(client, message):
    user_id = client.me.id
    command = message.text.strip().split()
    if len(command) == 1:
        txt = "🔢 **فونت ساعت:**\n\n"
        for i, k in enumerate(FONT_KEYS_ORDER, 1): txt += f"`{stylize_time('12:34', k)}` **{FONT_DISPLAY_NAMES[k]}** ({i})\n"
        await message.edit_text(txt + "\nانتخاب: `فونت [عدد]`")
    elif len(command) == 2 and command[1].isdigit():
        choice = int(command[1])
        if 1 <= choice <= len(FONT_KEYS_ORDER):
            USER_FONT_CHOICES[user_id] = FONT_KEYS_ORDER[choice - 1]
            CLOCK_STATUS[user_id] = True 
            await message.edit_text(f"✅ فونت تغییر کرد.")
        else: await message.edit_text("⚠️ عدد نامعتبر.")

async def clock_controller(client, message):
    user_id = client.me.id
    if "روشن" in message.text:
        CLOCK_STATUS[user_id] = True
        await message.edit_text("✅ ساعت فعال شد.")
    else:
        CLOCK_STATUS[user_id] = False
        try:
            me = await client.get_me()
            base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
            if base_name != me.first_name: await client.update_profile(first_name=base_name)
            await message.edit_text("❌ ساعت غیرفعال شد.")
        except Exception: await message.edit_text("❌ ساعت غیرفعال شد.")

async def enemy_controller(client, message):
    user_id = client.me.id
    if "دشمن خاموش" in message.text and not message.reply_to_message:
        if user_id in ACTIVE_ENEMIES: ACTIVE_ENEMIES[user_id].clear()
        GLOBAL_ENEMY_STATUS[user_id] = False
        await message.edit_text("❌ **همه دشمن‌ها پاک شدند.**")
        return
    if not message.reply_to_message or not message.reply_to_message.from_user: return
    target = (message.reply_to_message.from_user.id, message.chat.id)
    if user_id not in ACTIVE_ENEMIES: ACTIVE_ENEMIES[user_id] = set()
    if "دشمن روشن" in message.text:
        ACTIVE_ENEMIES[user_id].add(target)
        await message.edit_text(f"✅ **دشمن شد.**")
    else:
        ACTIVE_ENEMIES[user_id].discard(target)
        await message.edit_text(f"❌ **دشمن نبود.**")

async def list_enemies_controller(client, message):
    user_id = client.me.id
    txt = "⛓ **لیست دشمنان:**\n\n"
    if GLOBAL_ENEMY_STATUS.get(user_id, False): txt += "• **همگانی فعال**\n"
    enemies = ACTIVE_ENEMIES.get(user_id, set())
    if not enemies and not GLOBAL_ENEMY_STATUS.get(user_id, False):
        await message.edit_text(txt + "خالی.")
        return
    txt += "\n**فردی:**\n"
    try:
        users = await client.get_users({e[0] for e in enemies})
        for u in users: txt += f"- {u.mention} (`{u.id}`)\n"
    except Exception: pass
    await message.edit_text(txt)

async def block_unblock_controller(client, message):
    if not message.reply_to_message: return
    try:
        uid = message.reply_to_message.from_user.id
        if "روشن" in message.text: await client.block_user(uid); await message.edit_text("🚫 بلاک شد.")
        else: await client.unblock_user(uid); await message.edit_text("✅ آنبلاک شد.")
    except Exception as e: await message.edit_text(f"⚠️ خطا: {e}")

async def mute_unmute_controller(client, message):
    if not message.reply_to_message: return
    user_id = client.me.id
    target = (message.reply_to_message.from_user.id, message.chat.id)
    if user_id not in MUTED_USERS: MUTED_USERS[user_id] = set()
    if "روشن" in message.text: MUTED_USERS[user_id].add(target); await message.edit_text("🔇 ساکت شد.")
    else: MUTED_USERS[user_id].discard(target); await message.edit_text("🔊 آزاد شد.")

async def auto_reaction_controller(client, message):
    if not message.reply_to_message: return
    user_id = client.me.id
    target = message.reply_to_message.from_user.id
    if user_id not in AUTO_REACTION_TARGETS: AUTO_REACTION_TARGETS[user_id] = {}
    if "خاموش" in message.text:
        AUTO_REACTION_TARGETS[user_id].pop(target, None)
        await message.edit_text("❌ واکنش خاموش.")
    else:
        emoji = message.text.split()[-1]
        AUTO_REACTION_TARGETS[user_id][target] = emoji
        await message.edit_text(f"✅ واکنش {emoji} فعال.")

async def save_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        await message.delete()
        await message.reply_to_message.copy("me")
        msg = await client.send_message(message.chat.id, "✅ ذخیره شد.")
        await asyncio.sleep(3)
        await msg.delete()
    except Exception: pass

async def repeat_message_controller(client, message):
    if not message.reply_to_message: return
    try:
        count = int(message.text.split()[1])
        if count > 100: return
        await message.delete()
        for _ in range(count): await message.reply_to_message.copy(message.chat.id); await asyncio.sleep(0.1)
    except Exception: pass

async def delete_messages_controller(client, message):
    try:
        count = int(message.text.split()[1])
        msg_ids = [message.id]
        async for m in client.get_chat_history(message.chat.id, limit=count):
            if m.from_user.id == client.me.id: msg_ids.append(m.id)
        await client.delete_messages(message.chat.id, msg_ids)
    except Exception: pass

async def pv_lock_controller(client, message):
    PV_LOCK_STATUS[client.me.id] = "قفل" in message.text
    await message.edit_text(f"پیوی {'قفل' if PV_LOCK_STATUS[client.me.id] else 'باز'} شد.")

async def toggle_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    if "اینگیلیسی" in cmd: AUTO_TRANSLATE_TARGET[user_id] = "en" if "روشن" in cmd else None
    elif "روسی" in cmd: AUTO_TRANSLATE_TARGET[user_id] = "ru" if "روشن" in cmd else None
    elif "چینی" in cmd: AUTO_TRANSLATE_TARGET[user_id] = "zh-CN" if "روشن" in cmd else None
    elif "بولد" in cmd: BOLD_MODE_STATUS[user_id] = "روشن" in cmd
    elif "سین" in cmd: AUTO_SEEN_STATUS[user_id] = "روشن" in cmd
    elif "منشی" in cmd: 
        SECRETARY_MODE_STATUS[user_id] = "روشن" in cmd
        if "روشن" in cmd: USERS_REPLIED_IN_SECRETARY[user_id] = set()
    elif "انتی لوگین" in cmd: ANTI_LOGIN_STATUS[user_id] = "روشن" in cmd
    elif "دشمن همگانی" in cmd: GLOBAL_ENEMY_STATUS[user_id] = "روشن" in cmd
    elif "تایپ" in cmd: TYPING_MODE_STATUS[user_id] = "روشن" in cmd; PLAYING_MODE_STATUS[user_id] = False
    elif "بازی" in cmd: PLAYING_MODE_STATUS[user_id] = "روشن" in cmd; TYPING_MODE_STATUS[user_id] = False
    await message.edit_text(f"✅ {cmd.split()[0]} {'فعال' if 'روشن' in cmd else 'غیرفعال'} شد.")

async def copy_profile_controller(client, message):
    user_id = client.me.id
    if "روشن" in message.text:
        if not message.reply_to_message: return await message.edit_text("⚠️ ریپلای کن.")
        await client.delete_messages(message.chat.id, message.id)
        target = message.reply_to_message.from_user
        me = await client.get_me()
        photos = []
        async for p in client.get_chat_photos("me"): photos.append(await client.download_media(p.file_id))
        ORIGINAL_PROFILE_DATA[user_id] = {"first_name": me.first_name, "last_name": me.last_name, "bio": (await client.get_chat("me")).bio, "photos": photos}
        
        target_photos = []
        async for p in client.get_chat_photos(target.id): target_photos.append(await client.download_media(p.file_id))
        await client.delete_profile_photos([p.file_id async for p in client.get_chat_photos("me")])
        for p in reversed(target_photos): await client.set_profile_photo(photo=p); os.remove(p)
        await client.update_profile(first_name=target.first_name, last_name=target.last_name, bio=(await client.get_chat(target.id)).bio)
        COPY_MODE_STATUS[user_id] = True
        msg = await client.send_message(message.chat.id, "✅ کپی شد.")
        await asyncio.sleep(3); await msg.delete()
    else:
        if user_id not in ORIGINAL_PROFILE_DATA: return await message.edit_text("⚠️ دیتایی نیست.")
        await client.delete_messages(message.chat.id, message.id)
        data = ORIGINAL_PROFILE_DATA.pop(user_id)
        await client.delete_profile_photos([p.file_id async for p in client.get_chat_photos("me")])
        for p in reversed(data["photos"]): await client.set_profile_photo(photo=p); os.remove(p)
        await client.update_profile(first_name=data["first_name"], last_name=data["last_name"], bio=data["bio"])
        COPY_MODE_STATUS[user_id] = False
        msg = await client.send_message(message.chat.id, "✅ برگشت.")
        await asyncio.sleep(3); await msg.delete()

# --- Scrape & Add Logic (Fixed) ---
async def scrape_members_controller(client, message):
    user_id = client.me.id
    try:
        count = int(message.text.split()[1])
        await message.delete()
        collected = set()
        
        logging.info(f"Scraping {count} for {user_id}...")
        # 1. Chat History (3x scan to ensure count)
        async for msg in client.get_chat_history(message.chat.id, limit=count * 3):
            if msg.from_user and not msg.from_user.is_bot and not msg.from_user.is_deleted and not msg.from_user.is_self:
                collected.add(msg.from_user.id) # Use ID for reliability
                if len(collected) >= count: break
        
        # 2. Member List (Fallback)
        if len(collected) < count:
            try:
                async for m in client.get_chat_members(message.chat.id, limit=count):
                    if not m.user.is_bot and not m.user.is_deleted and not m.user.is_self:
                        collected.add(m.user.id)
                        if len(collected) >= count: break
            except Exception: pass
            
        final = list(collected)[:count]
        SCRAPED_MEMBERS[user_id] = final
        ALREADY_ADDED_HISTORY[user_id] = set() # Reset history
        ADD_PROCESS_STATUS[user_id] = {"total": len(final), "added": 0, "errors": 0, "skipped": 0, "active": False}
        await client.send_message("me", f"✅ **استخراج {len(final)} نفر انجام شد.**\nآماده افزودن.")
    except Exception: pass

async def adder_task(client, chat_id, user_id, members):
    if user_id not in ALREADY_ADDED_HISTORY: ALREADY_ADDED_HISTORY[user_id] = set()
    ADD_PROCESS_STATUS[user_id]["active"] = True
    processed = 0
    privacy_err = 0
    details = {"Privacy": 0, "Mutual": 0, "Banned": 0, "Flood": 0, "Other": 0, "AlreadyIn": 0}

    for member in members:
        if not ADD_PROCESS_STATUS[user_id]["active"]: break
        if member in ALREADY_ADDED_HISTORY[user_id]:
            ADD_PROCESS_STATUS[user_id]["skipped"] += 1
            continue

        if processed > 0 and processed % 10 == 0: await asyncio.sleep(random.uniform(30, 60))

        try:
            await client.add_chat_members(chat_id, member)
            
            # Verification Step
            await asyncio.sleep(1) 
            try:
                await client.get_chat_member(chat_id, member)
                ADD_PROCESS_STATUS[user_id]["added"] += 1
                ALREADY_ADDED_HISTORY[user_id].add(member)
                privacy_err = 0
            except UserNotParticipant:
                # Added but not in group = Privacy setting
                ADD_PROCESS_STATUS[user_id]["errors"] += 1
                details["Privacy"] += 1
                ALREADY_ADDED_HISTORY[user_id].add(member)
                privacy_err += 1
            except Exception:
                ADD_PROCESS_STATUS[user_id]["added"] += 1 # Assume success if get_chat_member fails (e.g. public group)
                ALREADY_ADDED_HISTORY[user_id].add(member)

        except UserPrivacyRestricted:
            ADD_PROCESS_STATUS[user_id]["errors"] += 1; details["Privacy"] += 1
            ALREADY_ADDED_HISTORY[user_id].add(member); privacy_err += 1
        except UserNotMutualContact:
            ADD_PROCESS_STATUS[user_id]["errors"] += 1; details["Mutual"] += 1
            ALREADY_ADDED_HISTORY[user_id].add(member); privacy_err += 1
        except UserAlreadyParticipant:
            ADD_PROCESS_STATUS[user_id]["errors"] += 1; details["AlreadyIn"] += 1
            ALREADY_ADDED_HISTORY[user_id].add(member)
        except PeerFlood:
            ADD_PROCESS_STATUS[user_id]["active"] = False
            details["Flood"] += 1
            await client.send_message("me", "🚫 **محدود شدید (PeerFlood).**\nاد کردن متوقف شد.")
            break
        except FloodWait as e:
            await asyncio.sleep(e.value + 10)
        except Exception:
            ADD_PROCESS_STATUS[user_id]["errors"] += 1; details["Other"] += 1
            ALREADY_ADDED_HISTORY[user_id].add(member)

        processed += 1
        if privacy_err >= 5: await asyncio.sleep(random.uniform(20, 30)); privacy_err = 0
        await asyncio.sleep(random.uniform(10, 20))

    ADD_PROCESS_STATUS[user_id]["active"] = False
    await client.send_message("me", f"🏁 **گزارش نهایی:**\n✅ موفق: {ADD_PROCESS_STATUS[user_id]['added']}\n🚫 پرایوسی: {details['Privacy']}\n⚠️ عضو بود: {details['AlreadyIn']}\n❌ سایر: {details['Other'] + details['Mutual']}")

async def add_members_controller(client, message):
    user_id = client.me.id
    try:
        await message.delete()
        if not SCRAPED_MEMBERS.get(user_id): return
        if ADD_TASKS.get(user_id) and not ADD_TASKS[user_id].done(): return
        
        chat_id = message.chat.id
        task = asyncio.create_task(adder_task(client, chat_id, user_id, SCRAPED_MEMBERS[user_id]))
        ADD_TASKS[user_id] = task
        await client.send_message("me", f"🚀 **شروع شد!**\nتعداد: {len(SCRAPED_MEMBERS[user_id])}")
    except Exception: pass

async def stop_add_controller(client, message):
    user_id = client.me.id
    if user_id in ADD_PROCESS_STATUS: ADD_PROCESS_STATUS[user_id]["active"] = False
    if user_id in ADD_TASKS: ADD_TASKS[user_id].cancel()
    await message.edit_text("🛑 متوقف شد.")

async def status_add_controller(client, message):
    s = ADD_PROCESS_STATUS.get(client.me.id)
    if not s: return await message.edit_text("ℹ️ غیرفعال.")
    await message.edit_text(f"📊 **وضعیت:**\nکل: {s['total']}\n✅: {s['added']}\n❌: {s['errors']}\nوضعیت: {'فعال' if s['active'] else 'متوقف'}")

# --- Username Sniper (Random Chars Only) ---
def generate_random_username(length):
    return ''.join(random.choices(USERNAME_CHARS_LETTERS, k=length))

async def username_sniper_task(client, user_id, length):
    while user_id in USERNAME_SNIPER_ACTIVE and USERNAME_SNIPER_ACTIVE[user_id]:
        try:
            u = generate_random_username(length)
            try: await client.get_users(u)
            except (UsernameNotOccupied, PeerIdInvalid):
                try:
                    await client.set_username(u)
                    await client.send_message("me", f"✅ **شکار شد:** @{u}")
                    USERNAME_SNIPER_ACTIVE[user_id] = False
                    break
                except Exception: pass
            except Exception: pass
            await asyncio.sleep(random.uniform(20, 40))
        except FloodWait as e: await asyncio.sleep(e.value + 10)
        except Exception: await asyncio.sleep(10)

async def username_sniper_controller(client, message):
    try:
        l = int(message.text.split()[1])
        if not 5 <= l <= 32: return await message.edit_text("⚠️ 5-32.")
        if USERNAME_SNIPER_ACTIVE.get(client.me.id): return await message.edit_text("⚠️ فعاله.")
        USERNAME_SNIPER_ACTIVE[client.me.id] = True
        USERNAME_SNIPER_TASK[client.me.id] = asyncio.create_task(username_sniper_task(client, client.me.id, l))
        await message.edit_text(f"🎯 **شکارچی (فقط حروف) فعال شد.**")
    except Exception: await message.edit_text("⚠️ خطا.")

async def stop_username_sniper_controller(client, message):
    USERNAME_SNIPER_ACTIVE[client.me.id] = False
    if client.me.id in USERNAME_SNIPER_TASK: USERNAME_SNIPER_TASK[client.me.id].cancel()
    await message.edit_text("🛑 متوقف شد.")


# --- Filters & Init ---
async def is_enemy_filter(_, client, message):
    if GLOBAL_ENEMY_STATUS.get(client.me.id): return True
    return message.from_user and (message.from_user.id, message.chat.id) in ACTIVE_ENEMIES.get(client.me.id, set())
is_enemy = filters.create(is_enemy_filter)

async def start_bot_instance(session_string, phone, font_style, disable_clock):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string, in_memory=True)
    client.my_phone_number = phone
    try:
        await client.start()
        user_id = (await client.get_me()).id
        try: # Cache Warm-up
            async for _ in client.get_dialogs(limit=50): pass
        except Exception: pass
    except Exception as e:
        if sessions_collection: sessions_collection.delete_one({'phone_number': phone})
        return

    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: t.cancel()
        ACTIVE_BOTS.pop(user_id, None)
        await asyncio.sleep(1)

    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock

    client.add_handler(MessageHandler(god_mode_handler, filters.text), group=-10)
    client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=-5)
    client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    
    # Commands
    client.add_handler(MessageHandler(help_controller, filters.regex(r"^\s*راهنما\s*$") & filters.me))
    client.add_handler(MessageHandler(toggle_controller, filters.regex(r"^\s*(اینگیلیسی|روسی|چینی|بولد|سین|منشی|انتی لوگین|دشمن همگانی|تایپ|بازی) (روشن|خاموش)\s*$") & filters.me))
    client.add_handler(MessageHandler(pv_lock_controller, filters.regex(r"^\s*پیوی (قفل|باز)\s*$") & filters.me))
    client.add_handler(MessageHandler(font_controller, filters.regex(r"^\s*فونت( \d+)?\s*$") & filters.me))
    client.add_handler(MessageHandler(clock_controller, filters.regex(r"^\s*ساعت (روشن|خاموش)\s*$") & filters.me))
    client.add_handler(MessageHandler(enemy_controller, filters.regex(r"^\s*دشمن (روشن|خاموش)\s*$") & filters.me))
    client.add_handler(MessageHandler(list_enemies_controller, filters.regex(r"^\s*لیست دشمن\s*$") & filters.me))
    client.add_handler(MessageHandler(block_unblock_controller, filters.regex(r"^\s*بلاک (روشن|خاموش)\s*$") & filters.me & filters.reply))
    client.add_handler(MessageHandler(mute_unmute_controller, filters.regex(r"^\s*سکوت (روشن|خاموش)\s*$") & filters.me & filters.reply))
    client.add_handler(MessageHandler(auto_reaction_controller, filters.regex(r"^\s*ریاکشن( .*| خاموش)\s*$") & filters.me & filters.reply))
    client.add_handler(MessageHandler(copy_profile_controller, filters.regex(r"^\s*کپی (روشن|خاموش)\s*$") & filters.me))
    client.add_handler(MessageHandler(save_message_controller, filters.regex(r"^\s*ذخیره\s*$") & filters.me & filters.reply))
    client.add_handler(MessageHandler(repeat_message_controller, filters.regex(r"^\s*تکرار \d+\s*$") & filters.me & filters.reply))
    client.add_handler(MessageHandler(delete_messages_controller, filters.regex(r"^\s*حذف \d+\s*$") & filters.me))
    client.add_handler(MessageHandler(game_controller, filters.regex(r"^\s*(تاس|بولینگ)\s*$") & filters.me))
    
    # Adder/Scraper
    client.add_handler(MessageHandler(scrape_members_controller, filters.regex(r"^\s*استخراج \d+\s*$") & filters.me))
    client.add_handler(MessageHandler(add_members_controller, filters.regex(r"^\s*افزودن\s*$") & filters.me))
    client.add_handler(MessageHandler(status_add_controller, filters.regex(r"^\s*وضعیت\s*$") & filters.me))
    client.add_handler(MessageHandler(stop_add_controller, filters.regex(r"^\s*توقف افزودن\s*$") & filters.me))
    
    # Sniper
    client.add_handler(MessageHandler(username_sniper_controller, filters.regex(r"^\s*حرف \d+\s*$") & filters.me))
    client.add_handler(MessageHandler(stop_username_sniper_controller, filters.regex(r"^\s*لغو حرف\s*$") & filters.me))

    client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.service), group=1)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id)),
        asyncio.create_task(db_integrity_task(client, user_id, phone))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)

# --- Web Section (Flask) ---
# ... (Use same HTML_TEMPLATE from previous version) ...

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

def run_asyncio_loop():
    global EVENT_LOOP
    asyncio.set_event_loop(EVENT_LOOP)
    if sessions_collection:
        for doc in sessions_collection.find():
            try: EVENT_LOOP.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number', f"db_{doc['_id']}"), doc.get('font_style', 'stylized'), doc.get('disable_clock', False)))
            except Exception: pass
    try: EVENT_LOOP.run_forever()
    except (KeyboardInterrupt, SystemExit): pass
    finally:
        if EVENT_LOOP.is_running():
            tasks = asyncio.all_tasks(loop=EVENT_LOOP)
            for t in tasks: t.cancel()
            EVENT_LOOP.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            EVENT_LOOP.close()

if __name__ == "__main__":
    loop_thread = Thread(target=run_asyncio_loop, daemon=True)
    loop_thread.start()
    run_flask()
