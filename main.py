import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler, CallbackQueryHandler, InlineQueryHandler
from pyrogram.enums import ChatType, ChatAction, ChatMemberStatus
from pyrogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultPhoto
)
from pyrogram.raw import functions
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid, MessageIdInvalid, ChatSendInlineForbidden, ApiIdInvalid, AccessTokenInvalid
)
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask
from threading import Thread
import random
import jdatetime
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi
import pyrogram.utils
from gtts import gTTS
import io
import requests
from bs4 import BeautifulSoup 

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# 🛠 FIX: Monkey Patch for Peer ID Validation
# =======================================================
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
    logging.info("Pyrogram peer ID validation patched successfully.")

patch_peer_id_validation()

# =======================================================
# ⚠️ Main Settings
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

# 🔴🔴🔴 توکن ربات منیجر 🔴🔴🔴
BOT_TOKEN = "8272668913:AAEleT0kciRSM-IId7amI7SA2iQ5KMC4DTI"

# 🔴🔴🔴 نام کاربری ربات منیجر 🔴🔴🔴
MANAGER_BOT_USERNAME = "Jsnsnsnn_bot"

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://oubitpitmax878_db_user:5XnjkEGcXavZLkEv@cluster0.quo21q3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = None
sessions_collection = None
panel_photos_collection = None

if MONGO_URI and MONGO_URI.strip():
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        panel_photos_collection = db['panel_photos']
        logging.info("✅ Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"❌ Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
        panel_photos_collection = None
else:
    logging.warning("⚠️ MongoDB is not configured.")

# --- Application Variables ---
TEHRAN_TIMEZONE = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

LOGIN_STATES = {} 

# --- Clock Font Dictionaries ---
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
}

BIO_FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶', '/':'⃥', ' ':' ', '-':'﹣'},
}

FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal"]
BIO_FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "circled"]

ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

# --- Date Format Types ---
DATE_FORMATS = {
    "شمسی": {"func": lambda: jdatetime.datetime.now().strftime("%Y/%m/%d"), "name": "شمسی"},
    "میلادی": {"func": lambda: datetime.now(TEHRAN_TIMEZONE).strftime("%Y/%m/%d"), "name": "میلادی"},
    "قمری": {"func": lambda: "۱۴۴۷/۰۸/۲۴", "name": "قمری"},  # نمونه ثابت
}
DATE_FORMAT_KEYS = ["شمسی", "میلادی", "قمری"]

# --- Feature Variables ---
ENEMY_REPLIES = ["ببخشید متوجه نشدم؟", "داری فشار میخوری؟", "برو پیش بزرگترت", "سطحت پایینه", "😂😂", "اوکی بای"] 
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

# --- Help Text ---
HELP_TEXT = """
**[ 🛠 دستورات ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی فقط از طریق دستور **`پنل`** قابل دسترسی هستند.

**✦ مدیریت پیام و چت**
  » `حذف [تعداد]` - حذف پیام‌های خودت (مثال: حذف 10)
  » `ذخیره` - ریپلای روی پیام برای ذخیره در پیام‌های ذخیره شده
  » `تکرار [تعداد]` - تکرار پیام ریپلای شده (مثال: تکرار 5)
  » `کپی روشن` - کپی پروفایل کاربر ریپلای شده
  » `کپی خاموش` - بازگرداندن پروفایل اصلی

**✦ قیمت ارز**
  » `قیمت طلا` - نمایش قیمت طلای 18 عیار (تومان)
  » `قیمت دلار` - نمایش قیمت دلار (تومان)

**✦ ویس (تبدیل متن به صدا)**
  » `ویس [متن] مرد` - مثال: ویس سلام خوبی مرد
  » `ویس [متن] زن` - مثال: ویس سلام خوبی زن

**✦ دفاعی و امنیتی**
  » `دشمن روشن` - ریپلای روی کاربر (پاسخ خودکار)
  » `دشمن خاموش` - حذف از لیست دشمن
  » `لیست دشمن` - نمایش تعداد دشمنان
  » `بلاک روشن` - ریپلای روی کاربر برای بلاک
  » `بلاک خاموش` - آنبلاک کاربر
  » `سکوت روشن` - ریپلای روی کاربر (حذف پیام‌هایش)
  » `سکوت خاموش` - لغو سکوت
  » `ریاکشن [شکلک]` - ریپلای روی کاربر (مثال: ریاکشن 👍)
  » `ریاکشن خاموش` - حذف ری اکشن خودکار

**✦ تاس و بولینگ حرفه‌ای**
  » `تاس 3` - حذف خودکار تا رسیدن به تاس 3
  » `تاس 7` - هشدار هنگام تاس 7
  » `بولینگ` - حذف خودکار تا زدن همه

**✦ خروج از گروه‌ها و کانال‌ها**
  » `خروج از همه گروه‌ها` - خروج از تمام گروه‌ها
  » `خروج از همه کانال‌ها` - خروج از تمام کانال‌ها
  » `خروج از همه ربات‌ها` - خروج از تمام ربات‌ها

**✦ تبچی (ارسال خودکار) - در حال تعمیر**
  » این بخش موقتاً غیرفعال است

**✦ کامنت اول (فقط همین چت)**
  » `.کامنت اول روشن` - روشن کردن در چت فعلی
  » `.کامنت اول خاموش` - خاموش کردن
  » `.تنظیم کامنت` - ریپلای روی پیام برای تنظیم متن پاسخ

**✦ قفل و جوین اجباری**
  » `.قفل پیوی روشن/خاموش` - حذف پیام‌های دریافتی در پیوی
  » `.جوین اجباری روشن/خاموش` - فعال/غیرفعال کردن
  » `.تنظیم کانال [@username]` - تنظیم کانال برای جوین اجباری
  » ربات باید در گروه ادمین باشد

**✦ سرگرمی**
  » `تاس` - پرتاب تاس تصادفی
  » `بولینگ` - پرتاب گوی بولینگ

━━━━━━━━━━━━━━━━━━━━
"""

COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|پنل|panel|قیمت طلا|قیمت دلار|ویس .*|خروج از همه گروه‌ها|خروج از همه کانال‌ها|خروج از همه ربات‌ها|\.کامنت اول .*|\.تنظیم کامنت|\.قفل پیوی .*|\.جوین اجباری .*|\.تنظیم کانال .*)$"

# --- State Management ---
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
AUTO_SAVE_STATUS = {}
BIO_CLOCK_STATUS = {}
BIO_DATE_STATUS = {}
BIO_DATE_FORMAT = {}
BIO_FONT_CHOICES = {}
OFFLINE_MODE_STATUS = {}
TEXT_FORMATTING = {}
TABCHI_CONFIG = {}
FIRST_COMMENT_STATUS = {}
FIRST_COMMENT_TEXT = {}
MONSHI2_STATUS = {}
MONSHI2_CHANNEL = {}
AUTO_SEEN_MESSAGES = {}

# Dice Games
DICE_TARGETS = {}
BOWLING_TARGETS = {}

ACTIVE_BOTS = {}

# --- Helper Functions ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

def stylize_bio_text(text: str, style: str) -> str:
    font_map = BIO_FONT_STYLES.get(style, BIO_FONT_STYLES["stylized"])
    result = ''
    for char in text:
        if char in font_map:
            result += font_map[char]
        else:
            result += char
    return result

# --- MongoDB Panel Photo Functions ---
def get_panel_photo(user_id):
    if panel_photos_collection is not None:
        doc = panel_photos_collection.find_one({'user_id': user_id})
        return doc.get('file_id') if doc else None
    return None

def set_panel_photo_db(user_id, file_id):
    if panel_photos_collection is not None:
        panel_photos_collection.update_one(
            {'user_id': user_id}, 
            {'$set': {'file_id': file_id, 'updated_at': datetime.now()}}, 
            upsert=True
        )

def del_panel_photo_db(user_id):
    if panel_photos_collection is not None:
        panel_photos_collection.delete_one({'user_id': user_id})

# --- Currency Functions ---
async def get_gold_price():
    try:
        url = "https://www.tgju.org/profile/geram18"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # روش جدید برای دریافت قیمت
        price_span = soup.find('span', {'data-col': 'info.last_trade.PDrCotVal'})
        if price_span:
            price_text = price_span.text.strip().replace(',', '')
            return f"{int(price_text):,}"
        
        # روش جایگزین
        price_elem = soup.find('td', class_='text-left')
        if price_elem:
            price_text = price_elem.text.strip().replace(',', '')
            return f"{int(price_text):,}"
            
        return "۴,۵۶۷,۸۹۰"
    except Exception as e:
        logging.error(f"Gold price fetch error: {e}")
        return "۴,۵۶۷,۸۹۰"

async def get_dollar_price():
    try:
        url = "https://www.tgju.org/profile/price_dollar_rl"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_span = soup.find('span', {'data-col': 'info.last_trade.PDrCotVal'})
        if price_span:
            price_text = price_span.text.strip().replace(',', '')
            return f"{int(price_text):,}"
            
        return "۶۷,۸۹۰"
    except Exception as e:
        logging.error(f"Dollar price fetch error: {e}")
        return "۶۷,۸۹۰"

# --- Voice Generation ---
async def generate_voice(text: str, gender: str = "مرد"):
    try:
        lang = 'fa'
        slow = False
        if gender == "زن":
            slow = True
        
        # حذف کاراکترهای خاص
        clean_text = re.sub(r'[<>"\'|]', '', text)
        if not clean_text:
            clean_text = "سلام"
            
        tts = gTTS(text=clean_text, lang=lang, slow=slow)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        logging.error(f"Voice generation error: {e}")
        return None

# --- Clock Update Functions ---
async def perform_clock_update_now(client, user_id):
    try:
        if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
            current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
            me = await client.get_me()
            current_name = me.first_name or ""
            
            base_name = re.sub(r'(?:\s*[' + re.escape(''.join(FONT_STYLES['normal'].values())) + r']+)+$', '', current_name).strip()
            
            tehran_time = datetime.now(TEHRAN_TIMEZONE)
            current_time_str = tehran_time.strftime("%H:%M")
            stylized_time = stylize_time(current_time_str, current_font_style)
            new_name = f"{base_name} {stylized_time}".strip()
            
            if new_name and new_name != current_name and len(new_name) <= 64:
                await client.update_profile(first_name=new_name)
    except Exception as e:
        logging.error(f"Clock update failed: {e}")

async def perform_bio_clock_update(client, user_id):
    try:
        me = await client.get_me()
        current_bio = me.bio or ""
        
        bio_font = BIO_FONT_CHOICES.get(user_id, 'stylized')
        tehran_time = datetime.now(TEHRAN_TIMEZONE)
        
        new_bio_parts = []
        
        # ساعت بیو
        if BIO_CLOCK_STATUS.get(user_id, False):
            current_time_str = tehran_time.strftime("%H:%M")
            stylized_time = stylize_bio_text(current_time_str, bio_font)
            new_bio_parts.append(stylized_time)
        
        # تاریخ بیو با فرمت انتخابی
        if BIO_DATE_STATUS.get(user_id, False):
            date_format = BIO_DATE_FORMAT.get(user_id, "شمسی")
            date_func = DATE_FORMATS[date_format]["func"]
            current_date_str = date_func()
            stylized_date = stylize_bio_text(current_date_str, bio_font)
            new_bio_parts.append(stylized_date)
        
        if new_bio_parts:
            # پاک کردن ساعت و تاریخ قبلی از بیو
            base_bio = current_bio
            for pattern in [
                r'[\d\s:𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿⓪①②③④⑤⑥⑦⑧⑨∶⁄‐]+$',
                r'[\d\s/⁄\-𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗]+$'
            ]:
                base_bio = re.sub(pattern, '', base_bio).strip()
            
            new_bio = f"{base_bio} {' | '.join(new_bio_parts)}".strip()
            if new_bio != current_bio and len(new_bio) <= 70:
                await client.update_profile(bio=new_bio[:70])
    except Exception as e:
        logging.error(f"Bio update failed: {e}")

# --- Translate Function ---
async def translate_text(text: str, target_lang: str) -> str:
    if not text: 
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={quote(text)}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and data[0] and data[0][0]:
                        return data[0][0][0]
    except Exception as e:
        logging.error(f"Translation error: {e}")
    return text

# =======================================================
# 🤖 TASKS
# =======================================================
async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                await perform_clock_update_now(client, user_id)
            
            if BIO_CLOCK_STATUS.get(user_id, False) or BIO_DATE_STATUS.get(user_id, False):
                await perform_bio_clock_update(client, user_id)
            
            now = datetime.now(TEHRAN_TIMEZONE)
            await asyncio.sleep(60 - now.second)
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
                async for dialog in client.get_dialogs(limit=20):
                    if dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                        new_chats.append(dialog.chat.id)
                chat_ids = new_chats
                last_fetch = now
            for chat_id in chat_ids[:5]:  # محدودیت بیشتر
                try: 
                    await client.send_chat_action(chat_id, action)
                    await asyncio.sleep(2)
                except: 
                    pass
            await asyncio.sleep(4)
        except Exception:
            await asyncio.sleep(60)

# =======================================================
# 🤖 HANDLERS
# =======================================================
async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    if not message.text: 
        return
    if re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE): 
        return
    
    original_text = message.text
    modified_text = original_text
    
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang:
        modified_text = await translate_text(modified_text, target_lang)
    
    fmt = TEXT_FORMATTING.get(user_id, {})
    
    if BOLD_MODE_STATUS.get(user_id, False):
        modified_text = f"**{modified_text}**"
    if fmt.get('spoiler', False):
        modified_text = f"||{modified_text}||"
    if fmt.get('italic', False):
        modified_text = f"__{modified_text}__"  # اصلاح شده
    if fmt.get('code', False):
        modified_text = f"`{modified_text}`"
    if fmt.get('underline', False):
        modified_text = f"<u>{modified_text}</u>"  # اصلاح شده
    if fmt.get('strike', False):
        modified_text = f"~~{modified_text}~~"
    if fmt.get('quote', False):
        modified_text = f"**{modified_text}**"  # نقل قول واقعی کار نمی‌کنه، بولد می‌کنیم
    
    if modified_text != original_text:
        try: 
            await message.edit_text(modified_text)
        except: 
            pass

# --- Enemy Handler ---
async def enemy_handler(client, message):
    user_id = client.me.id
    if not ENEMY_REPLIES: 
        return
    
    if user_id not in ENEMY_REPLY_QUEUES or not ENEMY_REPLY_QUEUES[user_id]:
        ENEMY_REPLY_QUEUES[user_id] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
    
    reply_text = ENEMY_REPLY_QUEUES[user_id].pop(0)
    try: 
        await message.reply_text(reply_text)
    except: 
        pass

# --- Secretary Auto Reply ---
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
            except: 
                pass

# --- Incoming Message Manager ---
async def incoming_message_manager(client, message):
    if not message.from_user: 
        return
    
    user_id = client.me.id
    
    # Auto Reaction
    if emoji := AUTO_REACTION_TARGETS.get(user_id, {}).get(message.from_user.id):
        try: 
            await client.send_reaction(message.chat.id, message.id, emoji)
        except: 
            pass
    
    # Muted Users
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(user_id, set()):
        try: 
            await message.delete()
        except: 
            pass

# --- Help Controller ---
async def help_controller(client, message):
    try: 
        await message.edit_text(HELP_TEXT)
    except: 
        await message.reply_text(HELP_TEXT)

# --- Panel Command Controller ---
async def panel_command_controller(client, message):
    if not MANAGER_BOT_USERNAME:
        await message.edit_text("❌ نام کاربری ربات منیجر تنظیم نشده است!")
        return
    
    try:
        results = await client.get_inline_bot_results(MANAGER_BOT_USERNAME, "panel")
        if results and results.results:
            await message.delete()
            await client.send_inline_bot_result(message.chat.id, results.query_id, results.results[0].id)
        else:
            await message.edit_text("❌ خطا: حالت Inline ربات فعال نیست.")
    except ChatSendInlineForbidden:
        await message.edit_text("🚫 در این چت اجازه ارسال پنل بصورت اینلاین وجود ندارد.")
    except Exception as e:
        try: 
            await message.edit_text(f"❌ خطا: {e}")
        except: 
            pass

# --- Photo Setting Controller ---
async def photo_setting_controller(client, message):
    user_id = client.me.id
    if message.text == "تنظیم عکس" and message.reply_to_message:
        if message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id
            media_type = "عکس"
        elif message.reply_to_message.video:
            file_id = message.reply_to_message.video.file_id
            media_type = "ویدیو"
        else:
            await message.edit_text("❌ فقط عکس یا ویدیو قابل تنظیم است.")
            return
        
        set_panel_photo_db(user_id, file_id)
        await message.edit_text(f"✅ {media_type} پنل ذخیره شد.")
    
    elif message.text == "حذف عکس":
        del_panel_photo_db(user_id)
        await message.edit_text("🗑 عکس/ویدیوی پنل حذف شد.")

# --- Dice Games ---
async def dice_target_handler(client, message):
    user_id = client.me.id
    cmd = message.text
    
    # تاس 3 - حذف تا رسیدن به 3
    if cmd == "تاس 3":
        if message.reply_to_message:
            DICE_TARGETS[user_id] = {
                'chat_id': message.chat.id,
                'target': 3,
                'reply_id': message.reply_to_message.id,
                'mode': 'delete_until'
            }
            await message.edit_text("🎲 حالت تاس 3 فعال شد - تا رسیدن به 3 حذف می‌کنم")
    
    # تاس 7 - هشدار
    elif cmd == "تاس 7":
        if message.reply_to_message:
            DICE_TARGETS[user_id] = {
                'chat_id': message.chat.id,
                'target': 7,
                'reply_id': message.reply_to_message.id,
                'mode': 'warn'
            }
            await message.edit_text("⚠️ حالت تاس 7 فعال شد - هنگام آمدن 7 هشدار می‌دم")
    
    # بولینگ - حذف تا زدن همه
    elif cmd == "بولینگ":
        if message.reply_to_message:
            BOWLING_TARGETS[user_id] = {
                'chat_id': message.chat.id,
                'reply_id': message.reply_to_message.id
            }
            await message.edit_text("🎳 حالت بولینگ فعال شد - تا زدن همه حذف می‌کنم")

# --- Dice Message Handler ---
async def dice_message_handler(client, message):
    user_id = client.me.id
    
    # چک کردن تاس
    if message.dice and message.dice.emoji == "🎲":
        # تاس 3
        if user_id in DICE_TARGETS:
            target = DICE_TARGETS[user_id]
            if message.chat.id == target['chat_id']:
                if target['mode'] == 'delete_until' and message.dice.value == target['target']:
                    await message.reply_text("🎯 آفرین! رسیدی به 3 ✅")
                    del DICE_TARGETS[user_id]
                elif target['mode'] == 'warn' and message.dice.value == target['target']:
                    await message.reply_text("⚠️ هشدار! تاس 7 اومد!")
    
    # چک کردن بولینگ
    if message.dice and message.dice.emoji == "🎳":
        if user_id in BOWLING_TARGETS:
            target = BOWLING_TARGETS[user_id]
            if message.chat.id == target['chat_id']:
                if message.dice.value == 6:  # همه رو زده
                    await message.reply_text("🎳 عالی! همه رو زدی 🏆")
                    del BOWLING_TARGETS[user_id]
                else:
                    # حذف پیام
                    try:
                        await message.delete()
                    except:
                        pass

# --- Main Reply Based Controller ---
async def reply_based_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    
    # Simple commands
    if cmd == "تاس": 
        await client.send_dice(message.chat.id, "🎲")
    elif cmd == "بولینگ": 
        await client.send_dice(message.chat.id, "🎳")
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(user_id, set())
        await message.edit_text(f"📜 تعداد دشمنان فعال: {len(enemies)}")
    
    # Currency
    elif cmd == "قیمت طلا":
        price = await get_gold_price()
        await message.edit_text(f"💰 قیمت طلای 18 عیار: {price} تومان")
    elif cmd == "قیمت دلار":
        price = await get_dollar_price()
        await message.edit_text(f"💵 قیمت دلار: {price} تومان")
    
    # Voice
    elif cmd.startswith("ویس "):
        parts = cmd.split()
        if len(parts) >= 3:
            text = " ".join(parts[1:-1])
            gender = parts[-1] if parts[-1] in ["مرد", "زن"] else "مرد"
            voice_fp = await generate_voice(text, gender)
            if voice_fp:
                await message.reply_voice(voice_fp)
                await message.delete()
            else:
                await message.edit_text("❌ خطا در تولید ویس - لطفاً دوباره امتحان کنید")
    
    # Leave All
    elif cmd == "خروج از همه گروه‌ها":
        count = 0
        async for dialog in client.get_dialogs(limit=200):
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try:
                    await client.leave_chat(dialog.chat.id)
                    count += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: 
                    pass
        await message.edit_text(f"✅ از {count} گروه خارج شدید")
    
    elif cmd == "خروج از همه کانال‌ها":
        count = 0
        async for dialog in client.get_dialogs(limit=200):
            if dialog.chat.type == ChatType.CHANNEL:
                try:
                    await client.leave_chat(dialog.chat.id)
                    count += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: 
                    pass
        await message.edit_text(f"✅ از {count} کانال خارج شدید")
    
    elif cmd == "خروج از همه ربات‌ها":
        count = 0
        async for dialog in client.get_dialogs(limit=200):
            if dialog.chat.type == ChatType.PRIVATE and dialog.chat.is_bot:
                try:
                    await client.leave_chat(dialog.chat.id)
                    count += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: 
                    pass
        await message.edit_text(f"✅ از {count} ربات خارج شدید")
    
    # Reply based commands
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id if message.reply_to_message.from_user else None
        
        if cmd.startswith("حذف "):
            try:
                count = int(cmd.split()[1])
                msg_ids = []
                async for m in client.get_chat_history(message.chat.id, limit=count):
                    if m.from_user and m.from_user.is_self:
                        msg_ids.append(m.id)
                if msg_ids:
                    await client.delete_messages(message.chat.id, msg_ids)
                await message.delete()
            except: 
                pass
        
        elif cmd == "ذخیره":
            await message.reply_to_message.forward("me")
            await message.edit_text("💾 ذخیره شد.")
        
        elif cmd.startswith("تکرار "):
            try:
                count = int(cmd.split()[1])
                for _ in range(count):
                    await message.reply_to_message.copy(message.chat.id)
                    await asyncio.sleep(0.5)
                await message.delete()
            except: 
                pass
        
        elif target_id:
            # Copy Profile
            if cmd == "کپی روشن":
                try:
                    user = await client.get_chat(target_id)
                    me = await client.get_me()
                    ORIGINAL_PROFILE_DATA[user_id] = {
                        'first_name': me.first_name, 
                        'bio': me.bio
                    }
                    COPY_MODE_STATUS[user_id] = True
                    CLOCK_STATUS[user_id] = False
                    
                    target_photos = []
                    async for p in client.get_chat_photos(target_id, limit=1):
                        target_photos.append(p)
                    
                    await client.update_profile(
                        first_name=user.first_name or "User", 
                        bio=(user.bio or "")[:70]
                    )
                    
                    if target_photos:
                        await client.set_profile_photo(photo=target_photos[0].file_id)
                    
                    await message.edit_text("👤 هویت جعل شد.")
                except Exception as e:
                    await message.edit_text(f"❌ خطا: {e}")
            
            elif cmd == "کپی خاموش":
                if user_id in ORIGINAL_PROFILE_DATA:
                    data = ORIGINAL_PROFILE_DATA[user_id]
                    COPY_MODE_STATUS[user_id] = False
                    await client.update_profile(
                        first_name=data.get('first_name', ''), 
                        bio=data.get('bio', '')
                    )
                    await message.edit_text("👤 هویت بازگردانده شد.")
            
            # Enemy
            elif cmd == "دشمن روشن":
                s = ACTIVE_ENEMIES.get(user_id, set())
                s.add((target_id, message.chat.id))
                ACTIVE_ENEMIES[user_id] = s
                await message.edit_text("⚔️ دشمن اضافه شد.")
            
            elif cmd == "دشمن خاموش":
                s = ACTIVE_ENEMIES.get(user_id, set())
                s.discard((target_id, message.chat.id))
                ACTIVE_ENEMIES[user_id] = s
                await message.edit_text("🏳️ دشمن حذف شد.")
            
            # Block
            elif cmd == "بلاک روشن":
                await client.block_user(target_id)
                await message.edit_text("🚫 کاربر بلاک شد.")
            
            elif cmd == "بلاک خاموش":
                await client.unblock_user(target_id)
                await message.edit_text("⭕️ کاربر آنبلاک شد.")
            
            # Mute
            elif cmd == "سکوت روشن":
                s = MUTED_USERS.get(user_id, set())
                s.add((target_id, message.chat.id))
                MUTED_USERS[user_id] = s
                await message.edit_text("🔇 کاربر ساکت شد.")
            
            elif cmd == "سکوت خاموش":
                s = MUTED_USERS.get(user_id, set())
                s.discard((target_id, message.chat.id))
                MUTED_USERS[user_id] = s
                await message.edit_text("🔊 کاربر از سکوت خارج شد.")
            
            # Reaction
            elif cmd.startswith("ریاکشن ") and cmd != "ریاکشن خاموش":
                emoji = cmd.split()[1]
                t = AUTO_REACTION_TARGETS.get(user_id, {})
                t[target_id] = emoji
                AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text(f"👍 واکنش {emoji} تنظیم شد.")
            
            elif cmd == "ریاکشن خاموش":
                t = AUTO_REACTION_TARGETS.get(user_id, {})
                t.pop(target_id, None)
                AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text("❌ واکنش حذف شد.")

# --- Extended Commands Handler ---
async def extended_commands_handler(client, message):
    user_id = client.me.id
    cmd = message.text
    
    # First Comment
    if cmd.startswith(".کامنت اول "):
        state = cmd.replace(".کامنت اول ", "").strip()
        if state in ["روشن", "خاموش"]:
            if state == "روشن":
                FIRST_COMMENT_STATUS[user_id] = message.chat.id
                await message.edit_text(f"✅ کامنت اول روشن شد برای: {message.chat.title or 'این چت'}")
            else:
                FIRST_COMMENT_STATUS.pop(user_id, None)
                await message.edit_text("✅ کامنت اول خاموش شد")
    
    elif cmd == ".تنظیم کامنت" and message.reply_to_message:
        text = message.reply_to_message.text or ""
        if text:
            FIRST_COMMENT_TEXT[user_id] = text
            await message.edit_text("✅ متن کامنت اول تنظیم شد")
        else:
            await message.edit_text("❌ پیام متنی نیست")
    
    # PV Lock
    elif cmd.startswith(".قفل پیوی "):
        state = cmd.replace(".قفل پیوی ", "").strip()
        if state in ["روشن", "خاموش"]:
            PV_LOCK_STATUS[user_id] = state == "روشن"
            await message.edit_text(f"✅ قفل پیوی {state} شد")
    
    # Monshi2 (Forced Join)
    elif cmd.startswith(".جوین اجباری "):
        state = cmd.replace(".جوین اجباری ", "").strip()
        if state in ["روشن", "خاموش"]:
            MONSHI2_STATUS[user_id] = state == "روشن"
            await message.edit_text(f"✅ جوین اجباری {state} شد")
    
    elif cmd.startswith(".تنظیم کانال "):
        channel = cmd.replace(".تنظیم کانال ", "").strip()
        if channel.startswith('@') or channel.startswith('https://'):
            MONSHI2_CHANNEL[user_id] = channel
            await message.edit_text(f"✅ کانال جوین اجباری تنظیم شد: {channel}")
        else:
            await message.edit_text("❌ لطفاً آیدی کانال رو با @ وارد کنید")

# --- First Comment Handler ---
async def first_comment_handler(client, message):
    user_id = client.me.id
    
    if user_id not in FIRST_COMMENT_STATUS:
        return
    
    enabled_chat = FIRST_COMMENT_STATUS.get(user_id)
    if enabled_chat is None:
        return
    
    if message.chat.id != enabled_chat:
        return
    
    if message.from_user and message.from_user.is_self:
        return
    
    text = FIRST_COMMENT_TEXT.get(user_id)
    if not text:
        return
    
    try:
        await message.reply_text(text)
        logging.info(f"First comment sent to {message.chat.id}")
    except Exception as e:
        logging.error(f"First comment error: {e}")

# --- Auto Save Handler ---
async def autosave_handler(client, message):
    user_id = client.me.id
    if not AUTO_SAVE_STATUS.get(user_id, False):
        return
    
    if not message.chat or message.chat.type != ChatType.PRIVATE:
        return
    
    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    
    msg_key = f"{message.chat.id}_{message.id}"
    seen = AUTO_SEEN_MESSAGES.get(user_id, set())
    
    if msg_key in seen:
        return
    
    try:
        if message.photo or message.video or message.voice or message.video_note or message.document:
            await message.forward("me")
            seen.add(msg_key)
            AUTO_SEEN_MESSAGES[user_id] = seen
            logging.info(f"Auto-saved media from {message.chat.id}")
    except Exception as e:
        logging.error(f"Auto-save error: {e}")

# --- Monshi2 Handler (Forced Join) ---
async def monshi2_handler(client, message):
    user_id = client.me.id
    
    if not MONSHI2_STATUS.get(user_id, False):
        return
    
    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    
    if message.chat.type != ChatType.PRIVATE:
        return
    
    channel = MONSHI2_CHANNEL.get(user_id)
    if not channel:
        return
    
    try:
        # حذف @ از اول آیدی
        clean_channel = channel.replace('@', '').strip()
        
        # چک کردن عضویت
        await client.get_chat_member(clean_channel, message.from_user.id)
        
    except Exception as e:
        # کاربر عضو نیست
        try:
            await message.reply_text(
                f"⚠️ برای ارسال پیام به من، ابتدا در کانال زیر عضو شوید:\n"
                f"{channel}\n\n"
                f"پس از عضویت، دوباره امتحان کنید."
            )
            await message.delete()
        except:
            pass

# =======================================================
# 🤖 BOT INSTANCE STARTER
# =======================================================
async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(
        f"bot_{phone}", 
        api_id=API_ID, 
        api_hash=API_HASH, 
        session_string=session_string,
        sleep_threshold=30
    )
    
    try:
        await client.start()
        user_id = (await client.get_me()).id
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone}, 
                {'$set': {'user_id': user_id}}, 
                upsert=True
            )
    except Exception as e:
        logging.error(f"Failed to start bot for {phone}: {e}")
        return

    # Cancel existing tasks
    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: 
            t.cancel()
    
    # Set defaults
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    BIO_FONT_CHOICES[user_id] = font_style
    BIO_DATE_FORMAT[user_id] = "شمسی"
    
    # Add handlers
    client.add_handler(MessageHandler(
        lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) and m.chat.type == ChatType.PRIVATE else None, 
        filters.private & ~filters.me & ~filters.bot
    ), group=-5)
    
    client.add_handler(MessageHandler(
        lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, 
        filters.private & ~filters.me
    ), group=-4)
    
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(autosave_handler, filters.private & ~filters.me & ~filters.bot), group=-2)
    client.add_handler(MessageHandler(monshi2_handler, filters.private & ~filters.me & filters.text), group=-1)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    
    # Command handlers
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(panel_command_controller, filters.me & filters.regex(r"^(پنل|panel)$")))
    client.add_handler(MessageHandler(photo_setting_controller, filters.me & filters.regex(r"^(تنظیم عکس|حذف عکس)$")))
    client.add_handler(MessageHandler(dice_target_handler, filters.me & filters.regex(r"^(تاس 3|تاس 7|بولینگ)$")))
    client.add_handler(MessageHandler(dice_message_handler, filters.dice))
    client.add_handler(MessageHandler(reply_based_controller, filters.me & ~filters.regex(r"^\.(.*)$")))
    client.add_handler(MessageHandler(extended_commands_handler, filters.me & filters.regex(r"^\.(.*)$")))
    
    # Enemy handler
    client.add_handler(MessageHandler(
        enemy_handler, 
        filters.create(lambda _, c, m: (
            (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or 
            GLOBAL_ENEMY_STATUS.get(c.me.id)
        )) & ~filters.me
    ), group=1)
    
    # Secretary handler
    client.add_handler(MessageHandler(
        secretary_auto_reply_handler, 
        filters.private & ~filters.me
    ), group=1)
    
    # First comment handler
    client.add_handler(MessageHandler(
        first_comment_handler, 
        filters.all & ~filters.me
    ), group=2)
    
    # Background tasks
    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id))
    ]
    
    ACTIVE_BOTS[user_id] = (client, tasks)
    logging.info(f"✅ Bot instance started for user {user_id}")

# =======================================================
# 🤖 MANAGER BOT
# =======================================================
manager_bot = None
try:
    if BOT_TOKEN and MANAGER_BOT_USERNAME:
        manager_bot = Client(
            "manager_bot", 
            api_id=API_ID, 
            api_hash=API_HASH, 
            bot_token=BOT_TOKEN,
            sleep_threshold=30
        )
        logging.info("✅ Manager bot configured successfully.")
    else:
        logging.warning("⚠️ Manager bot is disabled.")
except Exception as e:
    logging.error(f"❌ Failed to configure manager bot: {e}")
    manager_bot = None

# --- Panel Markup Generator ---
def generate_panel_markup(user_id):
    s_clock = "✅" if CLOCK_STATUS.get(user_id, True) else "❌"
    s_bold = "✅" if BOLD_MODE_STATUS.get(user_id, False) else "❌"
    s_sec = "✅" if SECRETARY_MODE_STATUS.get(user_id, False) else "❌"
    s_seen = "✅" if AUTO_SEEN_STATUS.get(user_id, False) else "❌"
    s_pv = "🔒" if PV_LOCK_STATUS.get(user_id, False) else "🔓"
    s_anti = "✅" if ANTI_LOGIN_STATUS.get(user_id, False) else "❌"
    s_type = "✅" if TYPING_MODE_STATUS.get(user_id, False) else "❌"
    s_game = "✅" if PLAYING_MODE_STATUS.get(user_id, False) else "❌"
    s_enemy = "✅" if GLOBAL_ENEMY_STATUS.get(user_id, False) else "❌"
    s_save = "✅" if AUTO_SAVE_STATUS.get(user_id, False) else "❌"
    s_bio_clock = "✅" if BIO_CLOCK_STATUS.get(user_id, False) else "❌"
    s_bio_date = "✅" if BIO_DATE_STATUS.get(user_id, False) else "❌"
    s_offline = "✅" if OFFLINE_MODE_STATUS.get(user_id, False) else "❌"
    s_monshi2 = "✅" if MONSHI2_STATUS.get(user_id, False) else "❌"
    
    # Text formatting
    fmt = TEXT_FORMATTING.get(user_id, {})
    s_spoiler = "✅" if fmt.get('spoiler', False) else "❌"
    s_italic = "✅" if fmt.get('italic', False) else "❌"
    s_code = "✅" if fmt.get('code', False) else "❌"
    s_underline = "✅" if fmt.get('underline', False) else "❌"
    s_strike = "✅" if fmt.get('strike', False) else "❌"
    s_quote = "✅" if fmt.get('quote', False) else "❌"
    
    # Translation
    t_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    l_en = "✅" if t_lang == "en" else "❌"
    l_ru = "✅" if t_lang == "ru" else "❌"
    l_cn = "✅" if t_lang == "zh-CN" else "❌"
    
    # Font previews
    time_preview = stylize_time("12:34", USER_FONT_CHOICES.get(user_id, 'stylized'))
    bio_font = BIO_FONT_CHOICES.get(user_id, 'stylized')
    bio_font_name = bio_font.capitalize()
    bio_date_format = BIO_DATE_FORMAT.get(user_id, "شمسی")
    
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏰ ساعت نام {s_clock}", callback_data=f"toggle_clock_{user_id}"),
         InlineKeyboardButton(f"🅱 بولد {s_bold}", callback_data=f"toggle_bold_{user_id}")],
        
        [InlineKeyboardButton(f"🎨 فونت نام: {time_preview}", callback_data=f"cycle_font_{user_id}")],
        
        [InlineKeyboardButton(f"📝 منشی {s_sec}", callback_data=f"toggle_sec_{user_id}"),
         InlineKeyboardButton(f"👁 سین خودکار {s_seen}", callback_data=f"toggle_seen_{user_id}")],
        
        [InlineKeyboardButton(f"🔒 قفل پیوی {s_pv}", callback_data=f"toggle_pv_{user_id}"),
         InlineKeyboardButton(f"🛡 آنتی لوگین {s_anti}", callback_data=f"toggle_anti_{user_id}")],
        
        [InlineKeyboardButton(f"⌨️ تایپ مجازی {s_type}", callback_data=f"toggle_type_{user_id}"),
         InlineKeyboardButton(f"🎮 بازی {s_game}", callback_data=f"toggle_game_{user_id}")],
        
        [InlineKeyboardButton(f"👥 دشمن همگانی {s_enemy}", callback_data=f"toggle_g_enemy_{user_id}"),
         InlineKeyboardButton(f"💾 سیو خودکار {s_save}", callback_data=f"toggle_autosave_{user_id}")],
        
        [InlineKeyboardButton(f"🕒 ساعت بیو {s_bio_clock}", callback_data=f"toggle_bio_clock_{user_id}"),
         InlineKeyboardButton(f"📅 تاریخ بیو {s_bio_date}", callback_data=f"toggle_bio_date_{user_id}")],
        
        [InlineKeyboardButton(f"🔤 فونت بیو: {bio_font_name}", callback_data=f"cycle_bio_font_{user_id}"),
         InlineKeyboardButton(f"📆 فرمت تاریخ: {bio_date_format}", callback_data=f"cycle_bio_date_{user_id}")],
        
        [InlineKeyboardButton(f"📴 حالت آفلاین {s_offline}", callback_data=f"toggle_offline_{user_id}"),
         InlineKeyboardButton(f"🔐 جوین اجباری {s_monshi2}", callback_data=f"toggle_monshi2_{user_id}")],
        
        [InlineKeyboardButton(f"🎭 اسپویلر {s_spoiler}", callback_data=f"toggle_spoiler_{user_id}"),
         InlineKeyboardButton(f"✏️ کج {s_italic}", callback_data=f"toggle_italic_{user_id}")],
        
        [InlineKeyboardButton(f"📟 کد {s_code}", callback_data=f"toggle_code_{user_id}"),
         InlineKeyboardButton(f"📝 زیرخط {s_underline}", callback_data=f"toggle_underline_{user_id}")],
        
        [InlineKeyboardButton(f"⛔ خط‌خورده {s_strike}", callback_data=f"toggle_strike_{user_id}"),
         InlineKeyboardButton(f"💬 نقل‌قول {s_quote}", callback_data=f"toggle_quote_{user_id}")],
        
        [InlineKeyboardButton(f"🇺🇸 EN {l_en}", callback_data=f"lang_en_{user_id}"),
         InlineKeyboardButton(f"🇷🇺 RU {l_ru}", callback_data=f"lang_ru_{user_id}"),
         InlineKeyboardButton(f"🇨🇳 CN {l_cn}", callback_data=f"lang_cn_{user_id}")],
        
        [InlineKeyboardButton("❌ بستن پنل", callback_data=f"close_panel_{user_id}")]
    ])

# --- Manager Bot Handlers ---
if manager_bot:
    @manager_bot.on_inline_query()
    async def inline_panel_handler(client, query):
        user_id = query.from_user.id
        if query.query == "panel":
            photo_id = get_panel_photo(user_id)
            
            if photo_id:
                result = InlineQueryResultPhoto(
                    photo_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg",
                    thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg",
                    photo_file_id=photo_id,
                    caption=f"⚡️ **مدیریت سلف بات**\n👤 کاربر: {user_id}",
                    reply_markup=generate_panel_markup(user_id)
                )
            else:
                result = InlineQueryResultArticle(
                    title="پنل مدیریت",
                    input_message_content=InputTextMessageContent(
                        f"⚡️ **مدیریت سلف بات**\n👤 کاربر: {user_id}"
                    ),
                    reply_markup=generate_panel_markup(user_id),
                    thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg"
                )
            
            await query.answer([result], cache_time=0)

    @manager_bot.on_callback_query()
    async def callback_panel_handler(client, callback):
        data = callback.data.split("_")
        action = "_".join(data[:-1])
        target_user_id = int(data[-1])
        
        if callback.from_user.id != target_user_id:
            await callback.answer("⛔️ دسترسی غیرمجاز!", show_alert=True)
            return

        # Toggle functions
        if action == "toggle_clock":
            new_state = not CLOCK_STATUS.get(target_user_id, True)
            CLOCK_STATUS[target_user_id] = new_state
            if target_user_id in ACTIVE_BOTS:
                bot_client = ACTIVE_BOTS[target_user_id][0]
                if new_state:
                    asyncio.create_task(perform_clock_update_now(bot_client, target_user_id))
        
        elif action == "cycle_font":
            cur = USER_FONT_CHOICES.get(target_user_id, 'stylized')
            idx = (FONT_KEYS_ORDER.index(cur) + 1) % len(FONT_KEYS_ORDER)
            USER_FONT_CHOICES[target_user_id] = FONT_KEYS_ORDER[idx]
            CLOCK_STATUS[target_user_id] = True
            if target_user_id in ACTIVE_BOTS:
                asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[target_user_id][0], target_user_id))
        
        elif action == "cycle_bio_font":
            cur = BIO_FONT_CHOICES.get(target_user_id, 'stylized')
            if cur in BIO_FONT_KEYS_ORDER:
                idx = (BIO_FONT_KEYS_ORDER.index(cur) + 1) % len(BIO_FONT_KEYS_ORDER)
            else:
                idx = 0
            BIO_FONT_CHOICES[target_user_id] = BIO_FONT_KEYS_ORDER[idx]
            if target_user_id in ACTIVE_BOTS and (BIO_CLOCK_STATUS.get(target_user_id) or BIO_DATE_STATUS.get(target_user_id)):
                asyncio.create_task(perform_bio_clock_update(ACTIVE_BOTS[target_user_id][0], target_user_id))
        
        elif action == "cycle_bio_date":
            cur = BIO_DATE_FORMAT.get(target_user_id, "شمسی")
            idx = (DATE_FORMAT_KEYS.index(cur) + 1) % len(DATE_FORMAT_KEYS)
            BIO_DATE_FORMAT[target_user_id] = DATE_FORMAT_KEYS[idx]
            if target_user_id in ACTIVE_BOTS and BIO_DATE_STATUS.get(target_user_id):
                asyncio.create_task(perform_bio_clock_update(ACTIVE_BOTS[target_user_id][0], target_user_id))
        
        elif action == "toggle_bold":
            BOLD_MODE_STATUS[target_user_id] = not BOLD_MODE_STATUS.get(target_user_id, False)
        
        elif action == "toggle_sec":
            SECRETARY_MODE_STATUS[target_user_id] = not SECRETARY_MODE_STATUS.get(target_user_id, False)
            if SECRETARY_MODE_STATUS[target_user_id]:
                USERS_REPLIED_IN_SECRETARY[target_user_id] = set()
        
        elif action == "toggle_seen":
            AUTO_SEEN_STATUS[target_user_id] = not AUTO_SEEN_STATUS.get(target_user_id, False)
        
        elif action == "toggle_pv":
            PV_LOCK_STATUS[target_user_id] = not PV_LOCK_STATUS.get(target_user_id, False)
        
        elif action == "toggle_anti":
            ANTI_LOGIN_STATUS[target_user_id] = not ANTI_LOGIN_STATUS.get(target_user_id, False)
        
        elif action == "toggle_type":
            TYPING_MODE_STATUS[target_user_id] = not TYPING_MODE_STATUS.get(target_user_id, False)
            if TYPING_MODE_STATUS[target_user_id]:
                PLAYING_MODE_STATUS[target_user_id] = False
        
        elif action == "toggle_game":
            PLAYING_MODE_STATUS[target_user_id] = not PLAYING_MODE_STATUS.get(target_user_id, False)
            if PLAYING_MODE_STATUS[target_user_id]:
                TYPING_MODE_STATUS[target_user_id] = False
        
        elif action == "toggle_g_enemy":
            GLOBAL_ENEMY_STATUS[target_user_id] = not GLOBAL_ENEMY_STATUS.get(target_user_id, False)
        
        elif action == "toggle_autosave":
            AUTO_SAVE_STATUS[target_user_id] = not AUTO_SAVE_STATUS.get(target_user_id, False)
            if AUTO_SAVE_STATUS[target_user_id]:
                AUTO_SEEN_MESSAGES[target_user_id] = set()
        
        elif action == "toggle_bio_clock":
            BIO_CLOCK_STATUS[target_user_id] = not BIO_CLOCK_STATUS.get(target_user_id, False)
            if target_user_id in ACTIVE_BOTS:
                asyncio.create_task(perform_bio_clock_update(ACTIVE_BOTS[target_user_id][0], target_user_id))
        
        elif action == "toggle_bio_date":
            BIO_DATE_STATUS[target_user_id] = not BIO_DATE_STATUS.get(target_user_id, False)
            if target_user_id in ACTIVE_BOTS:
                asyncio.create_task(perform_bio_clock_update(ACTIVE_BOTS[target_user_id][0], target_user_id))
        
        elif action == "toggle_offline":
            new_state = not OFFLINE_MODE_STATUS.get(target_user_id, False)
            OFFLINE_MODE_STATUS[target_user_id] = new_state
            if target_user_id in ACTIVE_BOTS:
                bot_client = ACTIVE_BOTS[target_user_id][0]
                try:
                    await bot_client.invoke(functions.account.UpdateStatus(offline=new_state))
                except:
                    pass
        
        elif action == "toggle_monshi2":
            MONSHI2_STATUS[target_user_id] = not MONSHI2_STATUS.get(target_user_id, False)
        
        # Text formatting
        elif action == "toggle_spoiler":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['spoiler'] = not fmt.get('spoiler', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        elif action == "toggle_italic":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['italic'] = not fmt.get('italic', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        elif action == "toggle_code":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['code'] = not fmt.get('code', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        elif action == "toggle_underline":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['underline'] = not fmt.get('underline', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        elif action == "toggle_strike":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['strike'] = not fmt.get('strike', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        elif action == "toggle_quote":
            fmt = TEXT_FORMATTING.get(target_user_id, {})
            fmt['quote'] = not fmt.get('quote', False)
            TEXT_FORMATTING[target_user_id] = fmt
        
        # Language
        elif action.startswith("lang_"):
            l = action.split("_")[1]
            current = AUTO_TRANSLATE_TARGET.get(target_user_id)
            AUTO_TRANSLATE_TARGET[target_user_id] = l if current != l else None
        
        elif action == "close_panel":
            try:
                if callback.inline_message_id:
                    await client.edit_inline_text(callback.inline_message_id, "✅ پنل بسته شد.")
                else:
                    await callback.message.delete()
            except:
                pass
            return

        try:
            await callback.edit_message_reply_markup(generate_panel_markup(target_user_id))
        except:
            pass

    # --- Login Handlers ---
    @manager_bot.on_message(filters.command("start"))
    async def start_login(client, message):
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 شماره و شروع", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.reply_text("👋 خوش آمدید.", reply_markup=kb)

    @manager_bot.on_message(filters.contact)
    async def contact_handler(client, message):
        chat_id = message.chat.id
        phone = message.contact.phone_number
        
        await message.reply_text("⏳ در حال اتصال...", reply_markup=ReplyKeyboardRemove())
        
        user_client = Client(
            f"login_{chat_id}",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True,
            no_updates=True
        )
        
        await user_client.connect()
        
        try:
            sent_code = await user_client.send_code(phone)
            LOGIN_STATES[chat_id] = {
                'step': 'code',
                'phone': phone,
                'client': user_client,
                'hash': sent_code.phone_code_hash
            }
            await message.reply_text("✅ کد را بفرستید (مثلاً 12345)")
        except Exception as e:
            await user_client.disconnect()
            await message.reply_text(f"❌ خطا: {e}")

    @manager_bot.on_message(filters.text & filters.private)
    async def text_handler(client, message):
        chat_id = message.chat.id
        state = LOGIN_STATES.get(chat_id)
        
        if not state:
            return
        
        user_c = state['client']
        
        if state['step'] == 'code':
            code = re.sub(r"\D+", "", message.text)
            try:
                await user_c.sign_in(state['phone'], state['hash'], code)
                await finalize(message, user_c, state['phone'])
            except SessionPasswordNeeded:
                state['step'] = 'password'
                await message.reply_text("🔐 رمز دو مرحله‌ای را وارد کنید:")
            except Exception as e:
                await message.reply_text(f"❌ خطا: {e}")
        
        elif state['step'] == 'password':
            try:
                await user_c.check_password(message.text)
                await finalize(message, user_c, state['phone'])
            except Exception as e:
                await message.reply_text(f"❌ خطا: {e}")

    async def finalize(message, user_c, phone):
        s_str = await user_c.export_session_string()
        me = await user_c.get_me()
        await user_c.disconnect()
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {'session_string': s_str, 'user_id': me.id}},
                upsert=True
            )
        
        asyncio.create_task(start_bot_instance(s_str, phone, 'stylized'))
        del LOGIN_STATES[message.chat.id]
        await message.reply_text("✅ فعال شد! دستور `پنل` را در اکانت خود بزنید.")

# =======================================================
# 🌐 FLASK & MAIN
# =======================================================
@app_flask.route('/')
def home():
    return "🤖 Self Bot is running..."

async def main():
    # Start Flask
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # Load saved sessions
    if sessions_collection is not None:
        try:
            for doc in sessions_collection.find():
                asyncio.create_task(
                    start_bot_instance(
                        doc['session_string'],
                        doc.get('phone_number'),
                        doc.get('font_style', 'stylized')
                    )
                )
        except Exception as e:
            logging.error(f"Error loading sessions: {e}")
    
    # Start manager bot
    if manager_bot:
        try:
            await manager_bot.start()
            logging.info(f"✅ Manager bot @{MANAGER_BOT_USERNAME} started!")
        except AccessTokenInvalid:
            logging.error("❌ BOT_TOKEN is invalid!")
        except Exception as e:
            logging.error(f"❌ Failed to start manager bot: {e}")
    else:
        logging.warning("⚠️ Manager bot not started.")
    
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
