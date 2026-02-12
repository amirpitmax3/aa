import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler, CallbackQueryHandler, InlineQueryHandler
from pyrogram.enums import ChatType, ChatAction
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
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask
from threading import Thread
import random
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
# BOT_TOKEN = "8459868829:AAELveuXul1f1TDZ_l3SEniZCaL-fJH7MnU"  # این توکن مشکل داره یا ریپورت شده
BOT_TOKEN = "8272668913:AAEleT0kciRSM-IId7amI7SA2iQ5KMC4DTI"  # یه ربات جدید بساز و توکن جدید بذار اینجا!

# 🔴🔴🔴 نام کاربری ربات منیجر (بدون @) 🔴🔴🔴
MANAGER_BOT_USERNAME = "Jsnsnsnn_bot"  # نام کاربری ربات جدید رو اینجا بذار!

# --- Database Setup (MongoDB) ---
# اگه مونگو نمیخوای استفاده کنی، اینو خالی بذار
MONGO_URI = "mongodb+srv://oubitpitmax878_db_user:5XnjkEGcXavZLkEv@cluster0.quo21q3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"  # موقتاً غیرفعال
mongo_client = None
sessions_collection = None

if MONGO_URI and "<db_password>" not in MONGO_URI and MONGO_URI.strip():
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
    logging.warning("MongoDB is not configured or disabled.")

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
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'۳','4':'۴','5':'۵','6':'۶','7':'۷','8':'۸','9':'۹',':':'：'},
    "filled":       {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':':'},
    "sans":         {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "inverted":     {'0':'0','1':'Ɩ','2':'ᄅ','3':'Ɛ','4':'ㄣ','5':'ϛ','6':'9','7':'ㄥ','8':'8','9':'6',':':':'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth", "filled", "sans", "inverted"]

ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

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
  » `دشمن روشن` - ریپلای روی کاربر (پاسخ خودکار فحش)
  » `دشمن خاموش` - حذف از لیست دشمن
  » `لیست دشمن` - نمایش تعداد دشمنان
  » `بلاک روشن` - ریپلای روی کاربر برای بلاک
  » `بلاک خاموش` - آنبلاک کاربر
  » `سکوت روشن` - ریپلای روی کاربر (حذف پیام‌هایش)
  » `سکوت خاموش` - لغو سکوت
  » `ریاکشن [شکلک]` - ریپلای روی کاربر (مثال: ریاکشن 👍)
  » `ریاکشن خاموش` - حذف ری اکشن خودکار

**✦ خروج از گروه‌ها و کانال‌ها**
  » `خروج از همه گروه‌ها` - خروج از تمام گروه‌ها
  » `خروج از همه کانال‌ها` - خروج از تمام کانال‌ها

**✦ تبچی (ارسال خودکار)**
  » `.تبچی پیوی روشن/خاموش` - روشن/خاموش ارسال خودکار به پیوی‌ها
  » `.تبچی گروه روشن/خاموش` - روشن/خاموش ارسال خودکار به گروه‌ها
  » `.تایمر پیوی [ثانیه]` - فاصله زمانی ارسال به پیوی (مثال: .تایمر پیوی 60)
  » `.تایمر گروه [ثانیه]` - فاصله زمانی ارسال به گروه (مثال: .تایمر گروه 120)
  » `.تنظیم بنر پیوی` - ریپلای روی پیام برای تنظیم متن پیوی
  » `.تنظیم بنر گروه` - ریپلای روی پیام برای تنظیم متن گروه
  » `.ارسال همگانی پیوی` - ریپلای روی پیام برای ارسال فوری به همه پیوی‌ها
  » `.ارسال همگانی گروه` - ریپلای روی پیام برای ارسال فوری به همه گروه‌ها
  » `.لینک گروه` - دریافت لینک دعوت گروه
  » `.پیوستن [لینک]` - عضویت در گروه (مثال: .پیوستن https://t.me/+abc123)
  » `.خروج [لینک]` - خروج از گروه (مثال: .خروج https://t.me/+abc123)

**✦ کامنت اول (فقط همین چت)**
  » `.کامنت اول روشن` - روشن کردن در چت فعلی
  » `.کامنت اول خاموش` - خاموش کردن
  » `.تنظیم کامنت` - ریپلای روی پیام برای تنظیم متن پاسخ

**✦ قفل و جوین اجباری**
  » `.قفل پیوی روشن/خاموش` - حذف پیام‌های دریافتی در پیوی
  » `.جوین اجباری روشن/خاموش` - فعال/غیرفعال کردن
  » `.تنظیم کانال [@username]` - تنظیم کانال برای جوین اجباری (مثال: .تنظیم کانال @MyChannel)

**✦ سرگرمی**
  » `تاس` - پرتاب تاس تصادفی
  » `تاس [عدد]` - پرتاب تاس با ریپلای (مثال: تاس 3)
  » `بولینگ` - پرتاب گوی بولینگ

━━━━━━━━━━━━━━━━━━━━
**📖 راهنمای سریع جوین اجباری:**
1️⃣ برو تو کانالت و یه پیام بفرست
2️⃣ لینک یا آیدی کانال رو بردار (مثلاً @MyChannel)
3️⃣ بفرست: .تنظیم کانال @MyChannel
4️⃣ بفرست: .جوین اجباری روشن
5️⃣ حالا هرکی پیام بده توی پیوی که عضو کانال نباشه، پیامش حذف می‌شه و لینک کانال براش فرستاده می‌شه

⚠️ **نکته:** برای تبچی، حتماً اول بنر رو تنظیم کن بعد روشن کن!
"""

COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|پنل|panel|قیمت طلا|قیمت دلار|ویس .*|خروج از همه گروه‌ها|خروج از همه کانال‌ها|\.تبچی .*|\.تایمر .*|\.تنظیم بنر .*|\.ارسال همگانی .*|\.لینک گروه|\.پیوستن .*|\.خروج .*|\.کامنت اول .*|\.تنظیم کامنت|\.قفل پیوی .*|\.جوین اجباری .*)$"

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
BIO_FONT_CHOICES = {}
OFFLINE_MODE_STATUS = {}
TEXT_FORMATTING = {}
TABCHI_CONFIG = {}
FIRST_COMMENT_STATUS = {}
FIRST_COMMENT_TEXT = {}
MONSHI2_STATUS = {}
MONSHI2_CHANNEL = {}
AUTO_SEEN_MESSAGES = {}
GAME_CHEATS = {} 
CURRENCY_CACHE = {}
CURRENCY_CACHE_TIME = {}

ACTIVE_BOTS = {}

# --- Helpers ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

def stylize_date(date_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    result = ''
    for char in date_str:
        if char in font_map:
            result += font_map[char]
        else:
            result += char
    return result

async def get_gold_price():
    try:
        url = "https://www.tgju.org/profile/geram18"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_elem = soup.find('span', class_='price-value')
        if price_elem:
            return price_elem.text.strip()
        return None
    except Exception as e:
        logging.error(f"Gold price fetch error: {e}")
        return None

async def get_dollar_price():
    try:
        url = "https://www.tgju.org/profile/price_dollar"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_elem = soup.find('span', class_='price-value')
        if price_elem:
            return price_elem.text.strip()
        return None
    except Exception as e:
        logging.error(f"Dollar price fetch error: {e}")
        return None

async def generate_voice(text: str, gender: str = "مرد"):
    try:
        lang = 'fa'
        slow = False
        if gender == "زن":
            slow = True
        tts = gTTS(text=text, lang=lang, slow=slow)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        logging.error(f"Voice generation error: {e}")
        return None

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
        logging.error(f"Immediate clock update failed: {e}")

async def perform_bio_clock_update(client, user_id):
    try:
        me = await client.get_me()
        current_bio = me.bio or ""
        bio_font = BIO_FONT_CHOICES.get(user_id, USER_FONT_CHOICES.get(user_id, 'stylized'))
        tehran_time = datetime.now(TEHRAN_TIMEZONE)
        
        new_bio_parts = []
        
        if BIO_CLOCK_STATUS.get(user_id, False):
            current_time_str = tehran_time.strftime("%H:%M")
            stylized_time = stylize_time(current_time_str, bio_font)
            new_bio_parts.append(stylized_time)
        
        if BIO_DATE_STATUS.get(user_id, False):
            current_date_str = tehran_time.strftime("%Y/%m/%d")
            stylized_date = stylize_date(current_date_str, bio_font)
            new_bio_parts.append(stylized_date)
        
        if new_bio_parts:
            base_bio = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'[:\-/]?' + r')+', '', current_bio).strip()
            new_bio = f"{base_bio} {' | '.join(new_bio_parts)}" if base_bio else ' | '.join(new_bio_parts)
            if new_bio != current_bio and len(new_bio) <= 70:
                await client.update_profile(bio=new_bio[:70])
    except Exception as e:
        logging.error(f"Bio clock update failed: {e}")

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
    if sessions_collection is not None:
        doc = sessions_collection.find_one({'user_id': user_id})
        return doc.get('panel_photo') if doc else None
    return None

def set_panel_photo_db(user_id, file_id):
    if sessions_collection is not None:
        sessions_collection.update_one({'user_id': user_id}, {'$set': {'panel_photo': file_id}}, upsert=True)

def del_panel_photo_db(user_id):
    if sessions_collection is not None:
        sessions_collection.update_one({'user_id': user_id}, {'$unset': {'panel_photo': ""}})

# --- Tasks ---
async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
                await perform_clock_update_now(client, user_id)
            
            if BIO_CLOCK_STATUS.get(user_id, False) or BIO_DATE_STATUS.get(user_id, False):
                await perform_bio_clock_update(client, user_id)
            
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

# --- Handlers ---
async def outgoing_message_modifier(client, message):
    user_id = client.me.id
    if not message.text or re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE): return
    original_text = message.text
    modified_text = original_text
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang: modified_text = await translate_text(modified_text, target_lang)
    
    fmt = TEXT_FORMATTING.get(user_id, {})
    
    if BOLD_MODE_STATUS.get(user_id, False):
        if not modified_text.startswith(('`', '**', '__', '~~', '||')): 
            modified_text = f"**{modified_text}**"
    
    if fmt.get('spoiler', False):
        if not modified_text.startswith('||') and not modified_text.endswith('||'):
            modified_text = f"||{modified_text}||"
    if fmt.get('italic', False):
        if not modified_text.startswith('*') and not modified_text.endswith('*'):
            modified_text = f"*{modified_text}*"
    if fmt.get('code', False):
        if not modified_text.startswith('`') and not modified_text.endswith('`'):
            modified_text = f"`{modified_text}`"
    if fmt.get('underline', False):
        if not modified_text.startswith('__') and not modified_text.endswith('__'):
            modified_text = f"__{modified_text}__"
    if fmt.get('strike', False):
        if not modified_text.startswith('~~') and not modified_text.endswith('~~'):
            modified_text = f"~~{modified_text}~~"
    if fmt.get('quote', False):
        if not modified_text.startswith('>'):
            modified_text = f">{modified_text}"
    
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

# ✅ FIX: Panel Command Controller
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
        await message.edit_text("🚫 در این چت اجازه ارسال پنل بصورت اینلاین وجود ندارد. لطفاً در پیوی یا پیام‌های ذخیره شده تست کنید.")
    except Exception as e:
        try: await message.edit_text(f"❌ خطا در لود پنل: {e}\n\n⚠️ از استارت بودن @{MANAGER_BOT_USERNAME} مطمئن شوید.")
        except: pass

# ✅ FIX: Photo Setting Controller
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
    elif cmd == "قیمت طلا":
        price = await get_gold_price()
        if price:
            await message.edit_text(f"💰 قیمت طلای 18 عیار: {price} تومان")
        else:
            await message.edit_text("❌ خطا در دریافت قیمت طلا")
    elif cmd == "قیمت دلار":
        price = await get_dollar_price()
        if price:
            await message.edit_text(f"💵 قیمت دلار: {price} تومان")
        else:
            await message.edit_text("❌ خطا در دریافت قیمت دلار")
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
                await message.edit_text("❌ خطا در تولید ویس")
    
    # ✅ FIX: Leave All Groups/Channels with limit
    elif cmd == "خروج از همه گروه‌ها":
        count = 0
        limit = 200
        async for dialog in client.get_dialogs(limit=limit):
            if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                try:
                    await client.leave_chat(dialog.chat.id)
                    count += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: pass
        await message.edit_text(f"✅ از {count} گروه خارج شدید (از حداکثر {limit})")
    
    elif cmd == "خروج از همه کانال‌ها":
        count = 0
        limit = 200
        async for dialog in client.get_dialogs(limit=limit):
            if dialog.chat.type == ChatType.CHANNEL:
                try:
                    await client.leave_chat(dialog.chat.id)
                    count += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except: pass
        await message.edit_text(f"✅ از {count} کانال خارج شدید (از حداکثر {limit})")
    
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

async def extended_commands_handler(client, message):
    user_id = client.me.id
    cmd = message.text
    
    if cmd.startswith(".تبچی پیوی "):
        state = cmd.replace(".تبچی پیوی ", "").strip()
        if state in ["روشن", "خاموش"]:
            cfg = TABCHI_CONFIG.get(user_id, {})
            cfg['pv_auto'] = state == "روشن"
            TABCHI_CONFIG[user_id] = cfg
            await message.edit_text(f"✅ تبچی پیوی {state} شد")
    elif cmd.startswith(".تبچی گروه "):
        state = cmd.replace(".تبچی گروه ", "").strip()
        if state in ["روشن", "خاموش"]:
            cfg = TABCHI_CONFIG.get(user_id, {})
            cfg['gp_auto'] = state == "روشن"
            TABCHI_CONFIG[user_id] = cfg
            await message.edit_text(f"✅ تبچی گروه {state} شد")
    elif cmd.startswith(".تایمر پیوی "):
        try:
            seconds = int(cmd.replace(".تایمر پیوی ", "").strip())
            cfg = TABCHI_CONFIG.get(user_id, {})
            cfg['pv_timer'] = seconds
            TABCHI_CONFIG[user_id] = cfg
            await message.edit_text(f"✅ تایمر پیوی: {seconds} ثانیه")
        except: pass
    elif cmd.startswith(".تایمر گروه "):
        try:
            seconds = int(cmd.replace(".تایمر گروه ", "").strip())
            cfg = TABCHI_CONFIG.get(user_id, {})
            cfg['gp_timer'] = seconds
            TABCHI_CONFIG[user_id] = cfg
            await message.edit_text(f"✅ تایمر گروه: {seconds} ثانیه")
        except: pass
    elif cmd == ".تنظیم بنر پیوی" and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        cfg = TABCHI_CONFIG.get(user_id, {})
        cfg['pv_banner'] = text
        TABCHI_CONFIG[user_id] = cfg
        await message.edit_text("✅ بنر پیوی تنظیم شد")
    elif cmd == ".تنظیم بنر گروه" and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        cfg = TABCHI_CONFIG.get(user_id, {})
        cfg['gp_banner'] = text
        TABCHI_CONFIG[user_id] = cfg
        await message.edit_text("✅ بنر گروه تنظیم شد")
    elif cmd == ".ارسال همگانی پیوی":
        if message.reply_to_message:
            count = 0
            async for dialog in client.get_dialogs(limit=100):
                if dialog.chat.type == ChatType.PRIVATE and not dialog.chat.is_bot:
                    try:
                        await message.reply_to_message.copy(dialog.chat.id)
                        count += 1
                        await asyncio.sleep(1)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except: pass
            await message.edit_text(f"✅ به {count} پیوی ارسال شد")
    elif cmd == ".ارسال همگانی گروه":
        if message.reply_to_message:
            count = 0
            async for dialog in client.get_dialogs(limit=100):
                if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    try:
                        await message.reply_to_message.copy(dialog.chat.id)
                        count += 1
                        await asyncio.sleep(1)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except: pass
            await message.edit_text(f"✅ به {count} گروه ارسال شد")
    elif cmd == ".لینک گروه":
        try:
            link = await client.export_chat_invite_link(message.chat.id)
            await message.edit_text(f"🔗 لینک گروه: {link}")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd.startswith(".پیوستن "):
        link = cmd.replace(".پیوستن ", "").strip()
        try:
            await client.join_chat(link)
            await message.edit_text("✅ به گروه پیوستید")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd.startswith(".خروج "):
        link = cmd.replace(".خروج ", "").strip()
        try:
            chat = await client.get_chat(link)
            await client.leave_chat(chat.id)
            await message.edit_text("✅ از گروه خارج شدید")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    
    # ✅ FIX: First Comment - تا وقتی خاموش نکردم کار کنه
    elif cmd.startswith(".کامنت اول "):
        state = cmd.replace(".کامنت اول ", "").strip()
        if state in ["روشن", "خاموش"]:
            if state == "روشن":
                FIRST_COMMENT_STATUS[user_id] = message.chat.id
                await message.edit_text(f"✅ کامنت اول روشن شد برای چت: {message.chat.title or message.chat.id}")
            else:
                FIRST_COMMENT_STATUS.pop(user_id, None)
                await message.edit_text("✅ کامنت اول خاموش شد")
    
    elif cmd == ".تنظیم کامنت" and message.reply_to_message:
        text = message.reply_to_message.text or ""
        FIRST_COMMENT_TEXT[user_id] = text
        await message.edit_text("✅ متن کامنت اول تنظیم شد")
    
    elif cmd.startswith(".قفل پیوی "):
        state = cmd.replace(".قفل پیوی ", "").strip()
        if state in ["روشن", "خاموش"]:
            PV_LOCK_STATUS[user_id] = state == "روشن"
            await message.edit_text(f"✅ قفل پیوی {state} شد")
    elif cmd.startswith(".جوین اجباری "):
        state = cmd.replace(".جوین اجباری ", "").strip()
        if state in ["روشن", "خاموش"]:
            MONSHI2_STATUS[user_id] = state == "روشن"
            await message.edit_text(f"✅ جوین اجباری {state} شد")
    elif cmd.startswith(".تنظیم کانال "):
        channel = cmd.replace(".تنظیم کانال ", "").strip()
        MONSHI2_CHANNEL[user_id] = channel
        await message.edit_text(f"✅ کانال جوین اجباری تنظیم شد: {channel}")

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
        if message.photo or message.video or message.voice or message.video_note:
            await message.forward("me")
            seen.add(msg_key)
            AUTO_SEEN_MESSAGES[user_id] = seen
            logging.info(f"Auto-saved media from {message.chat.id}")
    except Exception as e:
        logging.error(f"Auto-save error: {e}")

async def monshi2_handler(client, message):
    user_id = client.me.id
    if not MONSHI2_STATUS.get(user_id, False):
        return
    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    
    channel = MONSHI2_CHANNEL.get(user_id)
    if not channel:
        return
    
    try:
        await client.get_chat_member(channel, message.from_user.id)
    except Exception:
        await message.reply_text(f"⚠️ برای ارتباط با من ابتدا در کانال زیر عضو شوید:\n{channel}")
        await message.delete()

# ✅ FIX: Tabchi Auto Send Task
async def tabchi_auto_send_task(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            cfg = TABCHI_CONFIG.get(user_id, {})
            
            # Send to PVs
            if cfg.get('pv_auto', False) and cfg.get('pv_banner'):
                pv_timer = cfg.get('pv_timer', 60)
                pv_count = 0
                async for dialog in client.get_dialogs(limit=100):
                    if dialog.chat.type == ChatType.PRIVATE and not dialog.chat.is_bot:
                        try:
                            await client.send_message(dialog.chat.id, cfg['pv_banner'])
                            pv_count += 1
                            await asyncio.sleep(1)
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            pass
                logging.info(f"Tabchi PV: {pv_count} messages sent, waiting {pv_timer}s")
                await asyncio.sleep(pv_timer)
            
            # Send to Groups
            if cfg.get('gp_auto', False) and cfg.get('gp_banner'):
                gp_timer = cfg.get('gp_timer', 60)
                gp_count = 0
                async for dialog in client.get_dialogs(limit=100):
                    if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                        try:
                            await client.send_message(dialog.chat.id, cfg['gp_banner'])
                            gp_count += 1
                            await asyncio.sleep(1)
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            pass
                logging.info(f"Tabchi Group: {gp_count} messages sent, waiting {gp_timer}s")
                await asyncio.sleep(gp_timer)
            
            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Tabchi error: {e}")
            await asyncio.sleep(60)

# ✅ FIX: First Comment Handler - تا وقتی خاموش نکردم کار کنه
async def first_comment_handler(client, message):
    user_id = client.me.id
    
    # اگه کامنت اول خاموشه یا تنظیم نشده
    if user_id not in FIRST_COMMENT_STATUS:
        return
    
    enabled_chat = FIRST_COMMENT_STATUS.get(user_id)
    if enabled_chat is None:
        return
    
    # فقط برای چت مشخص شده
    if message.chat.id != enabled_chat:
        return
    
    # پیام خودم نباشه
    if message.from_user and message.from_user.is_self:
        return
    
    # متن کامنت اول تنظیم شده باشه
    text = FIRST_COMMENT_TEXT.get(user_id)
    if not text:
        return
    
    try:
        await message.reply_text(text)
        logging.info(f"First comment sent to {message.chat.id}")
        # ✅ حذف نشد! فقط لاگ می‌کنیم و ادامه می‌دیم
    except Exception as e:
        logging.error(f"First comment error: {e}")

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    try:
        await client.start()
        user_id = (await client.get_me()).id
        if sessions_collection is not None:
            sessions_collection.update_one({'phone_number': phone}, {'$set': {'user_id': user_id}}, upsert=True)
    except Exception as e:
        logging.error(f"Failed to start bot for {phone}: {e}")
        return

    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: 
            t.cancel()
    
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    
    client.add_handler(MessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) and m.chat.type == ChatType.PRIVATE else None, filters.private & ~filters.me & ~filters.bot), group=-5)
    client.add_handler(MessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(autosave_handler, filters.private & ~filters.me & ~filters.bot & (filters.photo | filters.video | filters.voice | filters.video_note)), group=-2)
    client.add_handler(MessageHandler(monshi2_handler, filters.private & ~filters.me & filters.text), group=-1)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(panel_command_controller, filters.me & filters.regex(r"^(پنل|panel)$")))
    client.add_handler(MessageHandler(photo_setting_controller, filters.me & filters.regex(r"^(تنظیم عکس|حذف عکس)$")))
    client.add_handler(MessageHandler(reply_based_controller, filters.me)) 
    client.add_handler(MessageHandler(extended_commands_handler, filters.me & filters.regex(r"^\.(تبچی|تایمر|تنظیم بنر|تنظیم کانال|ارسال همگانی|لینک گروه|پیوستن|خروج|کامنت اول|تنظیم کامنت|قفل پیوی|جوین اجباری)")))
    client.add_handler(MessageHandler(enemy_handler, filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me), group=1)
    client.add_handler(MessageHandler(first_comment_handler, filters.all & ~filters.me), group=2)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id)),
        asyncio.create_task(tabchi_auto_send_task(client, user_id))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)
    logging.info(f"Bot instance started for user {user_id}")

# =======================================================
# 🤖 MANAGER BOT - فقط اگه توکن و نام کاربری تنظیم شده باشه
# =======================================================
manager_bot = None
if BOT_TOKEN and MANAGER_BOT_USERNAME:
    try:
        manager_bot = Client("manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
        logging.info("Manager bot configured successfully.")
    except Exception as e:
        logging.error(f"Failed to configure manager bot: {e}")
        manager_bot = None
else:
    logging.warning("Manager bot is disabled. Set BOT_TOKEN and MANAGER_BOT_USERNAME to enable.")

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
    s_spoiler = "✅" if TEXT_FORMATTING.get(user_id, {}).get('spoiler', False) else "❌"
    s_italic = "✅" if TEXT_FORMATTING.get(user_id, {}).get('italic', False) else "❌"
    s_code = "✅" if TEXT_FORMATTING.get(user_id, {}).get('code', False) else "❌"
    s_underline = "✅" if TEXT_FORMATTING.get(user_id, {}).get('underline', False) else "❌"
    s_strike = "✅" if TEXT_FORMATTING.get(user_id, {}).get('strike', False) else "❌"
    s_quote = "✅" if TEXT_FORMATTING.get(user_id, {}).get('quote', False) else "❌"
    t_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    l_en, l_ru, l_cn = ("✅" if t_lang == x else "❌" for x in ("en", "ru", "zh-CN"))
    preview = stylize_time("12:34", USER_FONT_CHOICES.get(user_id, 'stylized'))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"ساعت {s_clock}", callback_data=f"toggle_clock_{user_id}"),
         InlineKeyboardButton(f"بولد {s_bold}", callback_data=f"toggle_bold_{user_id}")],
        [InlineKeyboardButton(f"تغییر فونت: {preview}", callback_data=f"cycle_font_{user_id}")],
        [InlineKeyboardButton(f"منشی {s_sec}", callback_data=f"toggle_sec_{user_id}"),
         InlineKeyboardButton(f"سین {s_seen}", callback_data=f"toggle_seen_{user_id}")],
        [InlineKeyboardButton(f"پیوی {s_pv}", callback_data=f"toggle_pv_{user_id}"),
         InlineKeyboardButton(f"انتی لوگین {s_anti}", callback_data=f"toggle_anti_{user_id}")],
        [InlineKeyboardButton(f"تایپ {s_type}", callback_data=f"toggle_type_{user_id}"),
         InlineKeyboardButton(f"دشمن همگانی {s_enemy}", callback_data=f"toggle_g_enemy_{user_id}")],
        [InlineKeyboardButton(f"بازی {s_game}", callback_data=f"toggle_game_{user_id}"),
         InlineKeyboardButton(f"سیو خودکار {s_save}", callback_data=f"toggle_autosave_{user_id}")],
        [InlineKeyboardButton(f"ساعت بیو {s_bio_clock}", callback_data=f"toggle_bio_clock_{user_id}"),
         InlineKeyboardButton(f"تاریخ بیو {s_bio_date}", callback_data=f"toggle_bio_date_{user_id}")],
        [InlineKeyboardButton(f"آفلاین {s_offline}", callback_data=f"toggle_offline_{user_id}"),
         InlineKeyboardButton(f"جوین اجباری {s_monshi2}", callback_data=f"toggle_monshi2_{user_id}")],
        [InlineKeyboardButton(f"اسپویلر {s_spoiler}", callback_data=f"toggle_spoiler_{user_id}"),
         InlineKeyboardButton(f"کج {s_italic}", callback_data=f"toggle_italic_{user_id}")],
        [InlineKeyboardButton(f"کد {s_code}", callback_data=f"toggle_code_{user_id}"),
         InlineKeyboardButton(f"زیرخط {s_underline}", callback_data=f"toggle_underline_{user_id}")],
        [InlineKeyboardButton(f"خط‌خورده {s_strike}", callback_data=f"toggle_strike_{user_id}"),
         InlineKeyboardButton(f"نقل‌قول {s_quote}", callback_data=f"toggle_quote_{user_id}")],
        [InlineKeyboardButton(f"🇺🇸 EN {l_en}", callback_data=f"lang_en_{user_id}"),
         InlineKeyboardButton(f"🇷🇺 RU {l_ru}", callback_data=f"lang_ru_{user_id}"),
         InlineKeyboardButton(f"🇨🇳 CN {l_cn}", callback_data=f"lang_cn_{user_id}")],
        [InlineKeyboardButton("بستن پنل ❌", callback_data=f"close_panel_{user_id}")]
    ])

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
                    caption=f"⚡️ **مدیریت پیشرفته سلف بات**\n👤 کاربر: {user_id}\n\nوضعیت اتصال: ✅ برقرار",
                    reply_markup=generate_panel_markup(user_id)
                )
            else:
                result = InlineQueryResultArticle(
                    title="پنل مدیریت", 
                    input_message_content=InputTextMessageContent(f"⚡️ **مدیریت پیشرفته سلف بات**\n👤 کاربر: {user_id}\n\nوضعیت اتصال: ✅ برقرار"),
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
            await callback.answer("⛔️ دسترسی غیرمجاز!", show_alert=True); return

        if action == "toggle_clock":
            new_state = not CLOCK_STATUS.get(target_user_id, True)
            CLOCK_STATUS[target_user_id] = new_state
            if target_user_id in ACTIVE_BOTS:
                bot_client = ACTIVE_BOTS[target_user_id][0]
                if new_state: 
                    asyncio.create_task(perform_clock_update_now(bot_client, target_user_id))
                else:
                    try:
                        me = await bot_client.get_me()
                        clean_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
                        if clean_name != me.first_name: 
                            await bot_client.update_profile(first_name=clean_name)
                    except: pass
        elif action == "cycle_font":
            cur = USER_FONT_CHOICES.get(target_user_id, 'stylized')
            idx = (FONT_KEYS_ORDER.index(cur) + 1) % len(FONT_KEYS_ORDER)
            USER_FONT_CHOICES[target_user_id] = FONT_KEYS_ORDER[idx]
            CLOCK_STATUS[target_user_id] = True
            BIO_FONT_CHOICES[target_user_id] = FONT_KEYS_ORDER[idx]
            if target_user_id in ACTIVE_BOTS: 
                asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[target_user_id][0], target_user_id))
        elif action == "toggle_bold": 
            BOLD_MODE_STATUS[target_user_id] = not BOLD_MODE_STATUS.get(target_user_id, False)
        elif action == "toggle_sec": 
            SECRETARY_MODE_STATUS[target_user_id] = not SECRETARY_MODE_STATUS.get(target_user_id, False)
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
        elif action == "toggle_bio_clock":
            BIO_CLOCK_STATUS[target_user_id] = not BIO_CLOCK_STATUS.get(target_user_id, False)
            if target_user_id not in BIO_FONT_CHOICES:
                BIO_FONT_CHOICES[target_user_id] = USER_FONT_CHOICES.get(target_user_id, 'stylized')
        elif action == "toggle_bio_date":
            BIO_DATE_STATUS[target_user_id] = not BIO_DATE_STATUS.get(target_user_id, False)
            if target_user_id not in BIO_FONT_CHOICES:
                BIO_FONT_CHOICES[target_user_id] = USER_FONT_CHOICES.get(target_user_id, 'stylized')
        elif action == "toggle_offline":
            new_state = not OFFLINE_MODE_STATUS.get(target_user_id, False)
            OFFLINE_MODE_STATUS[target_user_id] = new_state
            if target_user_id in ACTIVE_BOTS:
                bot_client = ACTIVE_BOTS[target_user_id][0]
                try:
                    await bot_client.invoke(functions.account.UpdateStatus(offline=new_state))
                except Exception as e:
                    logging.error(f"Offline mode update failed: {e}")
        elif action == "toggle_monshi2":
            MONSHI2_STATUS[target_user_id] = not MONSHI2_STATUS.get(target_user_id, False)
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
        elif action.startswith("lang_"):
            l = action.split("_")[1]
            AUTO_TRANSLATE_TARGET[target_user_id] = l if AUTO_TRANSLATE_TARGET.get(target_user_id) != l else None
        elif action == "close_panel":
            try:
                if callback.inline_message_id: 
                    await client.edit_inline_text(callback.inline_message_id, "✅ پنل بسته شد.")
                else: 
                    await callback.message.delete()
            except: pass
            return

        try: 
            await callback.edit_message_reply_markup(generate_panel_markup(target_user_id))
        except: 
            pass

    # --- Login Handlers ---
    @manager_bot.on_message(filters.command("start"))
    async def start_login(client, message):
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 شماره و شروع", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await message.reply_text("👋 خوش آمدید.", reply_markup=kb)

    @manager_bot.on_message(filters.contact)
    async def contact_handler(client, message):
        chat_id = message.chat.id
        phone = message.contact.phone_number
        await message.reply_text("⏳ در حال اتصال...", reply_markup=ReplyKeyboardRemove())
        user_client = Client(f"login_{chat_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
        await user_client.connect()
        try:
            sent_code = await user_client.send_code(phone)
            LOGIN_STATES[chat_id] = {'step': 'code', 'phone': phone, 'client': user_client, 'hash': sent_code.phone_code_hash}
            await message.reply_text("✅ کد را بفرستید (مثلاً `1.1.1.1.1`)")
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
            sessions_collection.update_one({'phone_number': phone}, {'$set': {'session_string': s_str, 'user_id': me.id}}, upsert=True)
        asyncio.create_task(start_bot_instance(s_str, phone, 'stylized'))
        del LOGIN_STATES[message.chat.id]
        await message.reply_text("✅ فعال شد! دستور `پنل` را در اکانت خود بزنید.")

# --- Flask & Run ---
@app_flask.route('/')
def home(): 
    return "Bot is running..."

async def main():
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    
    # Load saved sessions from MongoDB if available
    if sessions_collection is not None:
        try:
            for doc in sessions_collection.find():
                asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))
        except Exception as e:
            logging.error(f"Error loading sessions: {e}")
    
    # Start manager bot if configured
    if manager_bot:
        try:
            await manager_bot.start()
            logging.info("Manager bot started successfully!")
        except ApiIdInvalid:
            logging.error("❌ API_ID or API_HASH is invalid!")
        except AccessTokenInvalid:
            logging.error("❌ BOT_TOKEN is invalid! Please create a new bot and get a new token.")
        except Exception as e:
            logging.error(f"❌ Failed to start manager bot: {e}")
    else:
        logging.warning("Manager bot not started. Set BOT_TOKEN and MANAGER_BOT_USERNAME to enable.")
    
    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
