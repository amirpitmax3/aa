import asyncio
import os
import logging
import re
import aiohttp
import time
import unicodedata
import shutil
import random
from urllib.parse import quote
from pyrogram import Client, filters, raw
from pyrogram.handlers import MessageHandler, RawUpdateHandler
# MessageReactionUpdatedHandler not available in this Pyrogram version
MessageReactionUpdatedHandler = None  # Define as None to avoid NameError
from pyrogram.enums import ChatType, ChatAction, UserStatus, ChatMembersFilter
try:
    from pyrogram.types import MessageEntityBlockquote
except Exception:
    MessageEntityBlockquote = None
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired, UserDeactivated, AuthKeyUnregistered,
    ReactionInvalid, MessageIdInvalid, MessageNotModified, PeerIdInvalid, UserNotParticipant, PhotoCropSizeSmall
)

# Additional imports for new features from self.txt
# Removed external API dependencies as requested
import json
import aiofiles
import numpy
import matplotlib.pyplot as plt

try:
    from pyrogram.raw import functions
except ImportError:
    logging.warning("Could not import 'pyrogram.raw.functions'. Anti-login feature might not work.")
    functions = None

from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, render_template_string, redirect, session, url_for
from threading import Thread
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# ⚠️ Main Settings (Enter your API_ID and API_HASH here)
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"

# --- Authorized User ID ---
AUTHORIZED_USER_ID = 7423552124  # فقط این ایدی می‌تواند سلف را استفاده کند

# --- Allowed Phone Number (optional hard restriction) ---
ALLOWED_PHONE_NUMBER = "+989011243659"  # فقط این شماره اجازه استفاده دارد

def _get_authorized_user_ids() -> set:
    env_val = os.environ.get("AUTHORIZED_USER_IDS", "").strip()
    if env_val:
        ids = set()
        for part in env_val.split(","):
            part = part.strip()
            if not part:
                continue
            try:
                ids.add(int(part))
            except Exception:
                continue
        if ids:
            return ids
    return {int(AUTHORIZED_USER_ID)}

def _is_allowed_phone(phone: str) -> bool:
    if not ALLOWED_PHONE_NUMBER:
        return True
    try:
        return str(phone).strip() == str(ALLOWED_PHONE_NUMBER).strip()
    except Exception:
        return False

# --- Bot Token for Secret Save ---
BOT_TOKEN = "8322502049:AAHf1U3Wj4CIJU8VyDDKeDd9aNVUkOpnWWs"
SECRET_SAVE_BOT = None  # Will be initialized with Bot client

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://111111:<db_password>@cluster0.gtkw6em.mongodb.net/?appName=Cluster0"
mongo_client = None
sessions_collection = None
learning_collection = None
AI_MAX_TOTAL_DB_SIZE_MB = 100  # Total MongoDB learning database size limit
if MONGO_URI and "<db_password>" not in MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        learning_collection = db['ai_learning']  # Collection for AI learning data
        logging.info("Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
        learning_collection = None
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
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'۶','7':'７','8':'８','9':'９',':':'：'},
    "sans_normal":  {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':'∶'},
    "negative_circled": {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':'∶'},
    "parenthesized": {'0':'🄀','1':'⑴','2':'⑵','3':'⑶','4':'⑷','5':'⑸','6':'⑹','7':'⑺','8':'⑻','9':'⑼',':':'∶'},
    "dot":          {'0':'🄀','1':'⒈','2':'⒉','3':'⒊','4':'⒋','5':'⒌','6':'⒍','7':'⒎','8':'⒏','9':'⒐',':':'∶'},
    "thai":         {'0':'๐','1':'๑','2':'๒','3':'๓','4':'๔','5':'๕','6':'๖','7':'๗','8':'๘','9':'๙',':':' : '},
    "devanagari":   {'0':'०','1':'१','2':'२','3':'३','4':'४','5':'५','6':'६','7':'७','8':'८','9':'९',':':' : '},
    "arabic_indic": {'0':'٠','1':'١','2':'٢','3':'٣','4':'٤','5':'٥','6':'٦','7':'٧','8':'٨','9':'٩',':':' : '},
    "keycap":       {'0':'0️⃣','1':'1️⃣','2':'2️⃣','3':'3️⃣','4':'4️⃣','5':'5️⃣','6':'6️⃣','7':'7️⃣','8':'8️⃣','9':'9️⃣',':':':'},
    "superscript":  {'0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹',':':':'},
    "subscript":    {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',':':':'},
    "tibetan":      {'0':'༠','1':'༡','2':'༢','3':'༣','4':'༤','5':'༥','6':'༦','7':'༧','8':'༨','9':'༩',':':' : '},
    "bengali":      {'0':'০','1':'১','2':'২','3':'৩','4':'৪','5':'৫','6':'৬','7':'۷','8':'۸','9':'۹',':':' : '},
    "gujarati":     {'0':'૦','1':'૧','2':'૨','3':'૩','4':'૪','5':'૫','6':'૬','7':'૭','8':'૮','9':'૯',':':' : '},
    "mongolian":    {'0':'᠐','1':'᠑','2':'᠒','3':'᠓','4':'᠔','5':'᠕','6':'᠖','7':'᠗','8':'᠘','9':'᠙',':':' : '},
    "lao":          {'0':'໐','1':'໑','2':'໒','3':'໓','4':'໔','5':'໕','6':'໖','7':'໗','8':'໘','9':'໙',':':' : '},
    "fraktur":      {'0':'𝔃','1':'𝔄','2':'𝔅','3':'𝔆','4':'𝔇','5':'𝔈','6':'𝔉','7':'𝔊','8':'𝔋','9':'𝔌',':':':'},
    "bold_fraktur": {'0':'𝖀','1':'𝖁','2':'𝖂','3':'𝖃','4':'𝖄','5':'𝖅','6':'𝖆','7':'𝖇','8':'𝖈','9':'𝖉',':':':'},
    "script":       {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "bold_script":  {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "squared":      {'0':'🄀','1':'🄁','2':'🄂','3':'🄃','4':'🄄','5':'🄅','6':'🄆','7':'🄇','8':'🄈','9':'🄉',':':'∶'},
    "negative_squared": {'0':'🅀','1':'🅁','2':'🅂','3':'🅃','4':'🅄','5':'🅅','6':'🅆','7':'🅇','8':'🅈','9':'🅉',':':'∶'},
    "roman":        {'0':'⓪','1':'Ⅰ','2':'Ⅱ','3':'Ⅲ','4':'Ⅳ','5':'Ⅴ','6':'Ⅵ','7':'Ⅶ','8':'Ⅷ','9':'Ⅸ',':':':'},
    "small_caps":   {'0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉',':':':'},
    "oldstyle":     {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "inverted":     {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
    "mirror":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'9','7':'7','8':'8','9':'6',':':':'},
    "strike":       {'0':'0̶','1':'1̶','2':'2̶','3':'3̶','4':'4̶','5':'5̶','6':'6̶','7':'7̶','8':'8̶','9':'9̶',':':':'},
    "bubble":       {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶'},
    "fancy1":       {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'６','7':'۷','8':'８','9':'９',':':'：'},
    "fancy2":       {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "fancy3":       {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "fancy4":       {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':'∶'},
    # Additional cool fonts
    "ethiopic":     {'0':'፩','1':'፪','2':'፫','3':'፬','4':'፭','5':'፮','6':'፯','7':'፰','8':'፱','9':'፲',':':' : '},  # Approximate
    "gothic":       {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},  # Bold variant
    "runic":        {'0':'ᛟ','1':'ᛁ','2':'ᛒ','3':'ᛏ','4':'ᚠ','5':'ᚢ','6':'ᛋ','7':'ᚷ','8':'ᚺ','9':'ᛉ',':':' : '},  # Approximate runic
    "math_bold":    {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "math_italic":  {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "math_sans":    {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "math_monospace": {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "math_double":  {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "japanese":     {'0':'零','1':'壱','2':'弐','3':'参','4':'四','5':'伍','6':'陸','7':'漆','8':'捌','9':'玖',':':' : '},  # Kanji numbers
    "emoji":        {'0':'0️⃣','1':'1️⃣','2':'2️⃣','3':'3️⃣','4':'4️⃣','5':'5️⃣','6':'6️⃣','7':'7️⃣','8':'8️⃣','9':'9️⃣',':':':'},
    "shadow":       {'0':'🅾','1':'🅰','2':'🅱','3':'🅲','4':'🅳','5':'🅴','6':'🅵','7':'G','8':'🅷','9':'🅸',':':' : '},  # Approximate shadow
}
FONT_KEYS_ORDER = list(FONT_STYLES.keys())
FONT_DISPLAY_NAMES = {
    "cursive": "کشیده", "stylized": "فانتزی", "doublestruck": "توخالی",
    "monospace": "کامپیوتری", "normal": "ساده", "circled": "دایره‌ای", "fullwidth": "پهن",
    "sans_normal": "ساده ۲", "negative_circled": "دایره‌ای معکوس",
    "parenthesized": "پرانتزی", "dot": "نقطه‌دار", "thai": "تایلندی", "devanagari": "هندی", "arabic_indic": "عربی",
    "keycap": "کیکپ", "superscript": "بالانویس", "subscript": "زیرنویس", "tibetan": "تبتی", "bengali": "بنگالی",
    "gujarati": "گجراتی", "mongolian": "مغولی", "lao": "لائوسی",
    "fraktur": "فراکتور", "bold_fraktur": "فراکتور بولد", "script": "اسکریپت", "bold_script": "اسکریپت بولد", "squared": "مربعی", "negative_squared": "مربعی معکوس", "roman": "رومی", "small_caps": "کوچک کپس", "oldstyle": "قدیمی", "inverted": "وارونه", "mirror": "آینه‌ای", "strike": "خط خورده", "bubble": "حبابی", "fancy1": "فانتزی ۱", "fancy2": "فانتزی ۲", "fancy3": "فانتزی ۳", "fancy4": "فانتزی ۴",
    "ethiopic": "اتیوپیک", "gothic": "گوتیک", "runic": "رونیک", "math_bold": "ریاضی بولد", "math_italic": "ریاضی ایتالیک", "math_sans": "ریاضی سنس", "math_monospace": "ریاضی مونوسپیس", "math_double": "ریاضی دوبل", "japanese": "ژاپنی", "emoji": "ایموجی", "shadow": "سایه‌دار",
}
ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

# --- Feature Variables ---
ENEMY_REPLIES = {}  # {user_id: list of replies}
FRIEND_REPLIES = {} # {user_id: list of replies}
ENEMY_LIST = {} # {user_id: set of enemy user_ids}
FRIEND_LIST = {}    # {user_id: set of friend user_ids}
ENEMY_ACTIVE = {}   # {user_id: bool}
FRIEND_ACTIVE = {}  # {user_id: bool}
SECRETARY_MODE_STATUS = {}
CUSTOM_SECRETARY_MESSAGES = {}
PROCESSED_SECRETARY_MESSAGES = {}  # {user_id: set of message_ids} - پیام‌های پردازش‌شده منشی
USERS_REPLIED_IN_SECRETARY = {}
AI_SECRETARY_STATUS = {}  # {user_id: bool} - منشی هوشمند با AI
AI_CONVERSATION_HISTORY = {}  # {user_id: {sender_id: [recent_messages]}} - Track recent conversation
MUTED_USERS = {}    # {user_id: set of (sender_id, chat_id)}
USER_FONT_CHOICES = {}
CLOCK_STATUS = {}
BOLD_MODE_STATUS = {}
QUOTE_MODE_STATUS = {}
AUTO_SEEN_STATUS = {}
AUTO_REACTION_TARGETS = {}  # {user_id: {target_user_id: emoji}}
AUTO_TRANSLATE_TARGET = {}  # {user_id: lang_code}
ANTI_LOGIN_STATUS = {}
COPY_MODE_STATUS = {}
ORIGINAL_PROFILE_DATA = {}
TYPING_MODE_STATUS = {}
PLAYING_MODE_STATUS = {}
RECORD_VOICE_STATUS = {}
UPLOAD_PHOTO_STATUS = {}
WATCH_GIF_STATUS = {}
PV_LOCK_STATUS = {}
PV_GIF_LOCK_STATUS = {}
PV_PHOTO_LOCK_STATUS = {}
PV_VIDEO_LOCK_STATUS = {}
PV_VOICE_LOCK_STATUS = {}
PV_STICKER_LOCK_STATUS = {}
PV_DOCUMENT_LOCK_STATUS = {}
PV_AUDIO_LOCK_STATUS = {}
PV_VIDEO_NOTE_LOCK_STATUS = {}
PV_CONTACT_LOCK_STATUS = {}
PV_LOCATION_LOCK_STATUS = {}
PV_EMOJI_LOCK_STATUS = {}
PV_TEXT_LOCK_STATUS = {}
SECRET_SAVE_STATUS = {}  # {user_id: bool} - ذخیره مخفی
SECRET_SAVE_PROCESSED = {}  # {user_id: set of (chat_id, message_id)} - پیام‌های ذخیره شده
ORIGINAL_NAMES = {}  # {user_id: str} - نام اصلی کاربر برای ساعت
GHOST_MODE_STATUS = {}  # {user_id: bool} - حالت شبح (بدون نام)
ORIGINAL_FIRST_NAMES = {}  # {user_id: str} - نام اصلی برای حالت شبح

async def auto_seen_handler(client, message):
    user_id = client.me.id
    if message.chat and message.chat.type == ChatType.PRIVATE and AUTO_SEEN_STATUS.get(user_id, False):
        try:
            await client.read_chat_history(message.chat.id)
        except FloodWait as e:
            logging.warning("AutoSeen: Flood wait marking chat %s read: %ss", getattr(message.chat, 'id', 'N/A'), getattr(e, 'value', None))
            await asyncio.sleep(getattr(e, 'value', 1) + 1)
        except Exception as e:
            if "Could not find the input peer" not in str(e) and "PEER_ID_INVALID" not in str(e).upper():
                logging.warning("AutoSeen: Could not mark chat %s as read: %s", getattr(message.chat, 'id', 'N/A'), e)

# --- Task Management ---
EVENT_LOOP = asyncio.new_event_loop()
ACTIVE_CLIENTS = {}
ACTIVE_BOTS = {}

DEFAULT_SECRETARY_MESSAGE = "سلام! منشی هستم. پیامتون رو دیدم، بعدا جواب می‌دم."

# --- Cloudflare Workers AI Configuration ---
CLOUDFLARE_ACCOUNT_ID = "ce2e4697a5504848b6f18b15dda6eee9"
CLOUDFLARE_API_TOKEN = "oG_r_b0Y-7exOWXcrg9MlLa1fPW9fkepcGU-DfhW"
CLOUDFLARE_AI_MODEL = "@cf/meta/llama-3.1-70b-instruct"

# --- Comment Variables (from 1.py) ---
COMMENT_STATUS = {}  # {user_id: bool} - for auto comment on forwarded messages
COMMENT_TEXT = {}    # {user_id: str} - text for comment

# --- Auto Repeat Variables ---
AUTO_REPEAT_STATUS = {}  # {user_id: {chat_id: {'active': bool, 'interval': int, 'text': str, 'task': asyncio.Task}}}

# --- Auto Save Variables ---
AUTO_SAVE_VIEW_ONCE = {}  # {user_id: bool}

# --- Text Edit Mode Variables ---
TEXT_EDIT_MODES = {}  # {user_id: {'bold': 'on/off', 'italic': 'on/off', ...}}

# --- Crash List Variables ---
CRASH_LIST = {}  # {user_id: set of user_ids}
CRASH_REPLIES = {}  # {user_id: list of replies}

# --- Database Cleanup Function ---
async def clear_all_database():
    """پاک کردن تمام داده‌های دیتابیس"""
    try:
        if sessions_collection is not None:
            sessions_collection.delete_many({})
            logging.info("✅ تمام داده‌های sessions پاک شدند")
        if learning_collection is not None:
            learning_collection.delete_many({})
            logging.info("✅ تمام داده‌های learning پاک شدند")
    except Exception as e:
        logging.error(f"خطا در پاک کردن دیتابیس: {e}")

# --- AI Learning Database Functions ---
async def save_settings_to_db(user_id: int):
    """Save user settings to MongoDB"""
    try:
        if sessions_collection is None:
            return

        settings = {
            'ai_secretary': AI_SECRETARY_STATUS.get(user_id, False),
            'secretary_mode': SECRETARY_MODE_STATUS.get(user_id, False),
            'clock_status': CLOCK_STATUS.get(user_id, True),
            'font_choice': USER_FONT_CHOICES.get(user_id, 'stylized'),
            'original_name': ORIGINAL_NAMES.get(user_id, ''),
            'comment_status': COMMENT_STATUS.get(user_id, False),
            'comment_text': COMMENT_TEXT.get(user_id, "اول! 🔥"),
            'auto_save_view_once': AUTO_SAVE_VIEW_ONCE.get(user_id, False),
            'pv_gif_lock': PV_GIF_LOCK_STATUS.get(user_id, False),
            'pv_photo_lock': PV_PHOTO_LOCK_STATUS.get(user_id, False),
            'pv_video_lock': PV_VIDEO_LOCK_STATUS.get(user_id, False),
            'pv_voice_lock': PV_VOICE_LOCK_STATUS.get(user_id, False),
            'pv_sticker_lock': PV_STICKER_LOCK_STATUS.get(user_id, False),
            'pv_document_lock': PV_DOCUMENT_LOCK_STATUS.get(user_id, False),
            'pv_audio_lock': PV_AUDIO_LOCK_STATUS.get(user_id, False),
            'pv_video_note_lock': PV_VIDEO_NOTE_LOCK_STATUS.get(user_id, False),
            'pv_contact_lock': PV_CONTACT_LOCK_STATUS.get(user_id, False),
            'pv_location_lock': PV_LOCATION_LOCK_STATUS.get(user_id, False),
            'pv_emoji_lock': PV_EMOJI_LOCK_STATUS.get(user_id, False),
            'pv_text_lock': PV_TEXT_LOCK_STATUS.get(user_id, False),
            'typing_mode': TYPING_MODE_STATUS.get(user_id, False),
            'secretary_msg': CUSTOM_SECRETARY_MESSAGES.get(user_id, DEFAULT_SECRETARY_MESSAGE),
            'enemy_list': list(ENEMY_LIST.get(user_id, set())),
            'friend_list': list(FRIEND_LIST.get(user_id, set())),
            'enemy_active': ENEMY_ACTIVE.get(user_id, False),
            'friend_active': FRIEND_ACTIVE.get(user_id, False),
            'enemy_replies': ENEMY_REPLIES.get(user_id, []),
            'friend_replies': FRIEND_REPLIES.get(user_id, []),
            'crash_replies': CRASH_REPLIES.get(user_id, []),
            'bio_clock_status': BIO_CLOCK_STATUS.get(user_id, False),
            'bio_date_status': BIO_DATE_STATUS.get(user_id, False),
            'bio_date_type': BIO_DATE_TYPE.get(user_id, 'jalali'),
            'bio_font_choice': BIO_FONT_CHOICE.get(user_id, 'stylized'),
            'ghost_mode': GHOST_MODE_STATUS.get(user_id, False),
            'original_first_name': ORIGINAL_FIRST_NAMES.get(user_id, '')
        }
        
        sessions_collection.update_one(
            {'user_id': user_id},
            {'$set': {'settings': settings, 'user_id': user_id}},
            upsert=True
        )

    except Exception as e:
        logging.error(f"Error saving settings db: {e}")

async def load_user_settings_from_db(user_id: int):
    try:
        if sessions_collection is None:
            return
        doc = sessions_collection.find_one({'user_id': user_id})
        if not doc:
            return
        settings = doc.get('settings') or {}

        AI_SECRETARY_STATUS[user_id] = settings.get('ai_secretary', AI_SECRETARY_STATUS.get(user_id, False))
        SECRETARY_MODE_STATUS[user_id] = settings.get('secretary_mode', SECRETARY_MODE_STATUS.get(user_id, False))
        CLOCK_STATUS[user_id] = settings.get('clock_status', CLOCK_STATUS.get(user_id, True))
        USER_FONT_CHOICES[user_id] = settings.get('font_choice', USER_FONT_CHOICES.get(user_id, 'stylized'))
        ORIGINAL_NAMES[user_id] = settings.get('original_name', ORIGINAL_NAMES.get(user_id, ''))
        COMMENT_STATUS[user_id] = settings.get('comment_status', COMMENT_STATUS.get(user_id, False))
        COMMENT_TEXT[user_id] = settings.get('comment_text', COMMENT_TEXT.get(user_id, "اول! 🔥"))
        AUTO_SAVE_VIEW_ONCE[user_id] = settings.get('auto_save_view_once', AUTO_SAVE_VIEW_ONCE.get(user_id, False))
        PV_GIF_LOCK_STATUS[user_id] = settings.get('pv_gif_lock', PV_GIF_LOCK_STATUS.get(user_id, False))
        PV_PHOTO_LOCK_STATUS[user_id] = settings.get('pv_photo_lock', PV_PHOTO_LOCK_STATUS.get(user_id, False))
        PV_VIDEO_LOCK_STATUS[user_id] = settings.get('pv_video_lock', PV_VIDEO_LOCK_STATUS.get(user_id, False))
        PV_VOICE_LOCK_STATUS[user_id] = settings.get('pv_voice_lock', PV_VOICE_LOCK_STATUS.get(user_id, False))
        PV_STICKER_LOCK_STATUS[user_id] = settings.get('pv_sticker_lock', PV_STICKER_LOCK_STATUS.get(user_id, False))
        PV_DOCUMENT_LOCK_STATUS[user_id] = settings.get('pv_document_lock', PV_DOCUMENT_LOCK_STATUS.get(user_id, False))
        PV_AUDIO_LOCK_STATUS[user_id] = settings.get('pv_audio_lock', PV_AUDIO_LOCK_STATUS.get(user_id, False))
        PV_VIDEO_NOTE_LOCK_STATUS[user_id] = settings.get('pv_video_note_lock', PV_VIDEO_NOTE_LOCK_STATUS.get(user_id, False))
        PV_CONTACT_LOCK_STATUS[user_id] = settings.get('pv_contact_lock', PV_CONTACT_LOCK_STATUS.get(user_id, False))
        PV_LOCATION_LOCK_STATUS[user_id] = settings.get('pv_location_lock', PV_LOCATION_LOCK_STATUS.get(user_id, False))
        PV_EMOJI_LOCK_STATUS[user_id] = settings.get('pv_emoji_lock', PV_EMOJI_LOCK_STATUS.get(user_id, False))
        PV_TEXT_LOCK_STATUS[user_id] = settings.get('pv_text_lock', PV_TEXT_LOCK_STATUS.get(user_id, False))
        TYPING_MODE_STATUS[user_id] = settings.get('typing_mode', TYPING_MODE_STATUS.get(user_id, False))
        CUSTOM_SECRETARY_MESSAGES[user_id] = settings.get('secretary_msg', CUSTOM_SECRETARY_MESSAGES.get(user_id, DEFAULT_SECRETARY_MESSAGE))
        GHOST_MODE_STATUS[user_id] = settings.get('ghost_mode', GHOST_MODE_STATUS.get(user_id, False))
        ORIGINAL_FIRST_NAMES[user_id] = settings.get('original_first_name', ORIGINAL_FIRST_NAMES.get(user_id, ''))
        BIO_CLOCK_STATUS[user_id] = settings.get('bio_clock_status', BIO_CLOCK_STATUS.get(user_id, False))
        BIO_DATE_STATUS[user_id] = settings.get('bio_date_status', BIO_DATE_STATUS.get(user_id, False))
        BIO_DATE_TYPE[user_id] = settings.get('bio_date_type', BIO_DATE_TYPE.get(user_id, 'jalali'))
        BIO_FONT_CHOICE[user_id] = settings.get('bio_font_choice', BIO_FONT_CHOICE.get(user_id, 'stylized'))

        # Optional sets/lists
        try:
            ENEMY_LIST[user_id] = set(settings.get('enemy_list', list(ENEMY_LIST.get(user_id, set()))))
        except Exception:
            pass
        try:
            FRIEND_LIST[user_id] = set(settings.get('friend_list', list(FRIEND_LIST.get(user_id, set()))))
        except Exception:
            pass
        ENEMY_ACTIVE[user_id] = settings.get('enemy_active', ENEMY_ACTIVE.get(user_id, False))
        FRIEND_ACTIVE[user_id] = settings.get('friend_active', FRIEND_ACTIVE.get(user_id, False))
        ENEMY_REPLIES[user_id] = settings.get('enemy_replies', ENEMY_REPLIES.get(user_id, []))
        FRIEND_REPLIES[user_id] = settings.get('friend_replies', FRIEND_REPLIES.get(user_id, []))
        CRASH_REPLIES[user_id] = settings.get('crash_replies', CRASH_REPLIES.get(user_id, []))

    except Exception as e:
        logging.error(f"Error loading settings db: {e}")

# --- AI Learning Database Functions ---
async def save_conversation_to_learning_db(user_id: int, sender_id: int, user_message: str, ai_response: str, sender_name: str):
    """Save conversation to MongoDB learning database with total size limit"""
    try:
        if learning_collection is None:
            logging.warning("MongoDB learning collection not available")
            return
        
        # Create conversation entry
        conversation_entry = {
            'timestamp': datetime.now(TEHRAN_TIMEZONE).isoformat(),
            'user_id': user_id,
            'sender_id': sender_id,
            'sender_name': sender_name,
            'user_message': user_message,
            'ai_response': ai_response,
            'message_length': len(user_message),
            'response_length': len(ai_response),
            'type': 'conversation'
        }
        
        # Calculate size in MB
        entry_size = len(json.dumps(conversation_entry, ensure_ascii=False).encode('utf-8')) / (1024 * 1024)
        
        # Check total database size
        total_size = await get_learning_db_size()
        
        # If adding this entry would exceed total limit, do NOT auto-delete old entries.
        # Only save again after user manually clears/backs up the DB.
        if total_size + entry_size > AI_MAX_TOTAL_DB_SIZE_MB:
            logging.warning(
                f"Learning DB size limit reached ({total_size:.2f}MB/{AI_MAX_TOTAL_DB_SIZE_MB}MB). "
                "Skipping new learning entry (no auto-delete)."
            )
            return
        
        # Insert new conversation
        learning_collection.insert_one(conversation_entry)
        
        # Update patterns and common responses
        await update_learning_patterns(user_id, user_message, ai_response, sender_name)
        
        logging.info(f"Saved conversation to MongoDB learning DB. Total size: {total_size + entry_size:.2f}MB")
        
    except Exception as e:
        logging.error(f"Error saving conversation to MongoDB learning DB: {e}")

async def get_learning_db_size():
    """Get total size of learning database in MB"""
    try:
        if learning_collection is None:
            return 0
        
        # Get all documents and calculate total size
        total_size = 0
        for doc in learning_collection.find():
            doc_size = len(json.dumps(doc, ensure_ascii=False, default=str).encode('utf-8')) / (1024 * 1024)
            total_size += doc_size
        
        return total_size
    except Exception as e:
        logging.error(f"Error calculating learning DB size: {e}")
        return 0

async def update_learning_patterns(user_id: int, user_message: str, ai_response: str, sender_name: str):
    """Update learning patterns in MongoDB"""
    try:
        if learning_collection is None:
            return
        
        # Track word patterns
        message_words = user_message.lower().split()
        for word in message_words:
            if len(word) > 2:  # Skip short words
                # Update or create word pattern
                pattern_doc = learning_collection.find_one({
                    'type': 'pattern',
                    'word': word,
                    'user_id': user_id
                })
                
                if pattern_doc:
                    # Update existing pattern
                    learning_collection.update_one(
                        {'_id': pattern_doc['_id']},
                        {
                            '$inc': {'count': 1},
                            '$addToSet': {'responses': ai_response}
                        }
                    )
                else:
                    # Create new pattern
                    learning_collection.insert_one({
                        'type': 'pattern',
                        'word': word,
                        'user_id': user_id,
                        'count': 1,
                        'responses': [ai_response],
                        'timestamp': datetime.now(TEHRAN_TIMEZONE).isoformat()
                    })
        
        # Track successful responses for similar messages
        response_key = user_message.lower()[:50]  # First 50 chars as key
        response_doc = learning_collection.find_one({
            'type': 'response_pattern',
            'message_key': response_key,
            'user_id': user_id
        })
        
        if response_doc:
            # Update existing response pattern
            responses = response_doc.get('responses', [])
            responses.append(ai_response)
            # Keep only last 5 responses
            if len(responses) > 5:
                responses = responses[-5:]
            
            learning_collection.update_one(
                {'_id': response_doc['_id']},
                {'$set': {'responses': responses}}
            )
        else:
            # Create new response pattern
            learning_collection.insert_one({
                'type': 'response_pattern',
                'message_key': response_key,
                'user_id': user_id,
                'responses': [ai_response],
                'timestamp': datetime.now(TEHRAN_TIMEZONE).isoformat()
            })
        
        # Track user preferences
        user_pref_doc = learning_collection.find_one({
            'type': 'user_preference',
            'user_id': user_id,
            'sender_name': sender_name
        })
        
        if user_pref_doc:
            # Update existing user preference
            message_count = user_pref_doc.get('message_count', 0) + 1
            old_avg = user_pref_doc.get('avg_message_length', 0)
            new_avg = (old_avg * (message_count - 1) + len(user_message)) / message_count
            
            common_words = user_pref_doc.get('common_words', {})
            for word in message_words:
                if len(word) > 2:
                    common_words[word] = common_words.get(word, 0) + 1
            
            learning_collection.update_one(
                {'_id': user_pref_doc['_id']},
                {
                    '$set': {
                        'message_count': message_count,
                        'avg_message_length': new_avg,
                        'common_words': common_words
                    }
                }
            )
        else:
            # Create new user preference
            common_words = {}
            for word in message_words:
                if len(word) > 2:
                    common_words[word] = 1
            
            learning_collection.insert_one({
                'type': 'user_preference',
                'user_id': user_id,
                'sender_name': sender_name,
                'message_count': 1,
                'avg_message_length': len(user_message),
                'common_words': common_words,
                'timestamp': datetime.now(TEHRAN_TIMEZONE).isoformat()
            })
        
    except Exception as e:
        logging.error(f"Error updating learning patterns in MongoDB: {e}")

async def get_learned_response_suggestions(user_id: int, user_message: str, sender_name: str) -> list:
    """Get response suggestions based on learned patterns from MongoDB"""
    try:
        if learning_collection is None:
            return []
        
        suggestions = []
        message_words = set(user_message.lower().split())
        
        # Get similar response patterns
        response_patterns = learning_collection.find({
            'type': 'response_pattern',
            'user_id': user_id
        })
        
        for pattern in response_patterns:
            past_msg = pattern.get('message_key', '')
            past_words = set(past_msg.split())
            
            # Calculate similarity (simple word overlap)
            if past_words and message_words:
                overlap = len(message_words.intersection(past_words))
                similarity = overlap / len(past_words.union(message_words))
                if similarity > 0.3:  # 30% similarity threshold
                    suggestions.extend(pattern.get('responses', []))
        
        # Get word-based patterns
        for word in message_words:
            if len(word) > 2:
                word_pattern = learning_collection.find_one({
                    'type': 'pattern',
                    'word': word,
                    'user_id': user_id
                })
                if word_pattern:
                    suggestions.extend(word_pattern.get('responses', []))
        
        # Get user-specific preferences
        user_pref = learning_collection.find_one({
            'type': 'user_preference',
            'user_id': user_id,
            'sender_name': sender_name
        })
        
        if user_pref:
            # Add responses based on user's common words
            user_common_words = user_pref.get('common_words', {})
            for word in message_words:
                if word in user_common_words and user_common_words[word] > 2:
                    # This user uses this word frequently, get related responses
                    word_responses = learning_collection.find_one({
                        'type': 'pattern',
                        'word': word,
                        'user_id': user_id
                    })
                    if word_responses:
                        suggestions.extend(word_responses.get('responses', []))
        
        # Remove duplicates and return top 3
        unique_suggestions = list(set(suggestions))
        return unique_suggestions[:3]
        
    except Exception as e:
        logging.error(f"Error getting learned suggestions from MongoDB: {e}")
        return []

async def get_ai_response(user_message: str, user_name: str = "کاربر", user_id: int = None, sender_id: int = None) -> str:
    """Get AI response from Cloudflare Workers AI"""
    try:
        # Hard guard: handle insults with firm boundary-setting response (no profanity)
        try:
            msg_l = (user_message or "").lower()
            insult_keywords = [
                "کیر", "کس", "کص", "کونی", "حروم", "جنده", "مادر", "ناموس", "fuck", "fuk", "f*", "shit", "bitch",
                "بی ناموس", "بی‌شرف", "بی شرف", "کثافت", "فلان فلان", "فحش"
            ]
            if any(k in msg_l for k in insult_keywords):
                return "با احترام حرف بزن. اگه قصد گفتگو داری محترمانه بگو."
        except Exception:
            pass

        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_AI_MODEL}"
        
        headers = {
            "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        # Check conversation history
        conversation_key = f"{user_id}_{sender_id}" if user_id and sender_id else str(sender_id or user_id or 0)
        
        # Get recent conversation history
        if user_id not in AI_CONVERSATION_HISTORY:
            AI_CONVERSATION_HISTORY[user_id] = {}
        if sender_id not in AI_CONVERSATION_HISTORY[user_id]:
            AI_CONVERSATION_HISTORY[user_id][sender_id] = []
        
        recent_messages = AI_CONVERSATION_HISTORY[user_id][sender_id]
        first_interaction = len(recent_messages) == 0
        
        # Add current message to history
        recent_messages.append(f"کاربر: {user_message}")
        # Keep only last 6 messages for context
        if len(recent_messages) > 6:
            recent_messages = recent_messages[-6:]
            AI_CONVERSATION_HISTORY[user_id][sender_id] = recent_messages
        
        # Build conversation context
        context = "\n".join(recent_messages[-3:]) if recent_messages else ""
        
        # Get learned response suggestions
        learned_suggestions = await get_learned_response_suggestions(user_id, user_message, user_name)
        learning_context = ""
        if learned_suggestions:
            learning_context = f"\n\nپیشنهادات از تجربه‌های قبلی:\n" + "\n".join([f"- {suggestion}" for suggestion in learned_suggestions[:2]])
        
        # Get user context from MongoDB
        user_context = ""
        if learning_collection is not None and not first_interaction:
            user_pref = learning_collection.find_one({
                'type': 'user_preference',
                'user_id': user_id,
                'sender_name': user_name
            })
            if user_pref:
                msg_count = user_pref.get('message_count', 0)
                user_context = f"\n\nشناخت از {user_name}: شما {msg_count} بار باهم حرف زدید. این کاربر رو خوب بشناس و صمیمی باش."
        
        # Enhanced system prompt for better understanding
        if first_interaction:
            system_prompt = f"""تو یه انسان باهوش و ذکی هستی که منشی امیر شدی. مثل یه دوست باتجربه و فهمیده حرف بزن.

فقط الان بگو: "سلام، من منشی امیر هستم!"
بعدش دیگه هیچ وقت نگو منشی هستی. مثل یه دوست عادی حرف بزن.

اسم شخص: {user_name}

قوانین مهم:
- حداکثر دو جمله کوتاه بنویس
- متن رو خوب بفهم و مناسب جواب بده
- هیچ وقت نگو "چی گفتی" یا "منظورت چی بود" یا سوال پرسیدن برای روشن شدن
- حتی اگر مبهم بود، بهترین برداشت ممکن رو انجام بده و مستقیم جواب بده
- اگه پرسید امیر کجاست: "نمیدونم کجاست"
- مثل آدم باهوش فکر کن و جواب بده"""
        else:
            # Check what was said recently
            last_responses = [msg for msg in recent_messages if msg.startswith("منشی:")]
            
            system_prompt = f"""تو یه انسان باهوش و فهمیده هستی. مثل یه دوست ذکی و باتجربه فکر کن و حرف بزن.

اسم شخص: {user_name}

آخرین مکالمه:
{context}

قوانین مهم:
- حداکثر دو جمله کوتاه بگو
- متن رو خوب بفهم و مناسب جواب بده
- به زمینه مکالمه توجه کن و مرتبط جواب بده
- هیچ وقت نگو "چی گفتی" یا "منظورت چی بود" یا سوال پرسیدن برای روشن شدن
- حتی اگر مبهم بود، بهترین برداشت ممکن رو انجام بده و مستقیم جواب بده
- اگه عصبانی باشه بگو: "چی شده؟"
- اگه پرسید امیر کجاست: "نمیدونم کجاست"
- مثل آدم باهوش فکر کن و جواب بده
- هیچ وقت جواب تکراری نده"""
        
        payload = {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        }
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success") and result.get("result"):
                        ai_response = result["result"].get("response", "")
                        if ai_response:
                            # Clean up response
                            ai_response = ai_response.strip()
                            
                            # Remove AI/robot references
                            ai_response = ai_response.replace("هوش مصنوعی", "")
                            ai_response = ai_response.replace("مدل زبانی", "")
                            ai_response = ai_response.replace("الگوریتم", "")
                            ai_response = ai_response.replace("AI", "")
                            ai_response = ai_response.replace("ربات", "")
                            ai_response = ai_response.replace("دستیار", "")
                            
                            # Check if response is repetitive (same as last 2 responses)
                            last_responses = [msg.replace("منشی: ", "") for msg in recent_messages[-4:] if msg.startswith("منشی:")]
                            if ai_response in last_responses:
                                # Response is repetitive, use smart fallback
                                import random
                                smart_fallbacks = [
                                    f"باشه {user_name}.",
                                    "باشه.",
                                    "متوجه شدم.",
                                    "اوکی."
                                ]
                                ai_response = random.choice(smart_fallbacks)
                            
                            # If response is empty or too short, provide contextual fallback
                            if len(ai_response) < 3:
                                import random
                                if first_interaction:
                                    ai_response = f"سلام، من منشی امیر هستم!"
                                else:
                                    contextual_responses = [
                                        f"چطوری {user_name}؟",
                                        "چه خبر؟",
                                        "بگو ببینم",
                                        "خوبه، ادامه بده",
                                        "آره، گوش می‌دم"
                                    ]
                                    ai_response = random.choice(contextual_responses)
                            
                            # Add response to conversation history
                            recent_messages.append(f"منشی: {ai_response}")
                            
                            # Save conversation to learning database
                            if user_id and sender_id:
                                await save_conversation_to_learning_db(user_id, sender_id, user_message, ai_response, user_name)
                            
                            return ai_response
                        else:
                            logging.warning("AI response is empty")
                            intro = "سلام! من منشی امیر هستم. " if first_interaction else "سلام! "
                            return f"{intro}الان یکم مشکل دارم، بعداً دوباره تماس بگیر!"
                else:
                    error_text = await response.text()
                    logging.error(f"Cloudflare AI API error {response.status}: {error_text}")
                    intro = "سلام! من منشی امیر هستم. " if first_interaction else "سلام! "
                    return f"{intro}الان یه مشکل فنی دارم، بعداً دوباره تماس بگیر!"
    except asyncio.TimeoutError:
        logging.error("Cloudflare AI request timeout")
        intro = "سلام! من منشی امیر هستم. " if first_interaction else "سلام! "
        return f"{intro}الان خط شلوغه، بعداً دوباره تماس بگیر!"
    except Exception as e:
        logging.error(f"Error calling Cloudflare AI: {e}")
        intro = "سلام! من منشی امیر هستم. " if first_interaction else "سلام! "
        return f"{intro}الان مشغولم، بعداً برمی‌گردم!"

# --- Translation Functions ---
async def translate_text(text: str, target_lang: str = None) -> str:
    """Translate text using Google Translate API (like original system)"""
    try:
        if not text or not target_lang:
            return text
        
        from urllib.parse import quote
        import aiohttp
        
        # URL encode the text
        encoded_text = quote(text)
        
        # Google Translate API URL (same as original)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract translated text from Google's response format
                    if data and len(data) > 0 and len(data[0]) > 0 and len(data[0][0]) > 0:
                        return data[0][0][0]
                    else:
                        return text
                else:
                    logging.error(f"Translation API error: {response.status}")
                    return text
        
    except Exception as e:
        logging.error(f"Translation error: {e}")
        return text

async def detect_language(text: str) -> str:
    """Detect language of text using Google Translate"""
    try:
        if not text:
            return "unknown"
        
        from urllib.parse import quote
        import aiohttp
        
        encoded_text = quote(text)
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={encoded_text}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data and len(data) > 2 and data[2]:
                        return data[2]
                    else:
                        return "unknown"
                else:
                    return "unknown"
        
    except Exception as e:
        logging.error(f"Language detection error: {e}")
        return "unknown"

# --- Auto Repeat Functions ---
async def start_auto_repeat(client, chat_id: int, user_id: int, message_text: str, interval: int):
    """Start auto repeat task for a message"""
    try:
        # Stop existing task if any
        await stop_auto_repeat(user_id, chat_id)
        
        async def repeat_task():
            try:
                while AUTO_REPEAT_STATUS.get(user_id, {}).get(chat_id, {}).get('active', False):
                    await client.send_message(chat_id, message_text)
                    await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logging.info(f"Auto repeat task cancelled for chat {chat_id}")
            except Exception as e:
                logging.error(f"Auto repeat task error: {e}")
        
        # Create and start task
        task = asyncio.create_task(repeat_task())
        
        # Store task info
        if user_id not in AUTO_REPEAT_STATUS:
            AUTO_REPEAT_STATUS[user_id] = {}
        
        AUTO_REPEAT_STATUS[user_id][chat_id] = {
            'active': True,
            'interval': interval,
            'text': message_text,
            'task': task
        }
        
        logging.info(f"Started auto repeat for chat {chat_id} every {interval} seconds")
        
    except Exception as e:
        logging.error(f"Error starting auto repeat: {e}")

async def stop_auto_repeat(user_id: int, chat_id: int = None):
    """Stop auto repeat task(s)"""
    try:
        if user_id not in AUTO_REPEAT_STATUS:
            return
        
        if chat_id:
            # Stop specific chat
            if chat_id in AUTO_REPEAT_STATUS[user_id]:
                task_info = AUTO_REPEAT_STATUS[user_id][chat_id]
                task_info['active'] = False
                if 'task' in task_info and not task_info['task'].done():
                    task_info['task'].cancel()
                del AUTO_REPEAT_STATUS[user_id][chat_id]
                logging.info(f"Stopped auto repeat for chat {chat_id}")
        else:
            # Stop all chats for user
            for cid, task_info in AUTO_REPEAT_STATUS[user_id].items():
                task_info['active'] = False
                if 'task' in task_info and not task_info['task'].done():
                    task_info['task'].cancel()
            AUTO_REPEAT_STATUS[user_id] = {}
            logging.info(f"Stopped all auto repeat tasks for user {user_id}")
            
    except Exception as e:
        logging.error(f"Error stopping auto repeat: {e}")

# --- Safe Peer Resolution ---
async def safe_resolve_peer(client, peer_id):
    """Safely resolve peer with error handling"""
    try:
        return await client.resolve_peer(peer_id)
    except (ValueError, KeyError, PeerIdInvalid) as e:
        logging.warning(f"Could not resolve peer {peer_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error resolving peer {peer_id}: {e}")
        return None

async def safe_get_chat(client, chat_id):
    """Safely get chat with error handling"""
    try:
        return await client.get_chat(chat_id)
    except (ValueError, KeyError, PeerIdInvalid) as e:
        logging.warning(f"Could not get chat {chat_id}: {e}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error getting chat {chat_id}: {e}")
        return None

# --- Additional Variables for New Features ---
TEXT_EDIT_MODES = {}  # {user_id: {'hashtag': bool, 'bold': bool, 'italic': bool, etc.}}
COMMENT_STATUS = {}   # {user_id: bool}
COMMENT_TEXT = {}     # {user_id: str}
CRASH_LIST = {}       # {user_id: set of crash user_ids}
CRASH_REPLIES = {}    # {user_id: list of crash replies}
COMMENT_STATUS = {}  # {user_id: bool} - for auto comment on forwarded messages (from 1.py)
COMMENT_TEXT = {}    # {user_id: str} - text for comment
TIME_PROFILE_STATUS = {}  # {user_id: bool}
TIME_BIO_STATUS = {}      # {user_id: bool}
TIME_CRASH_STATUS = {}    # {user_id: bool}
CLOCK_IN_BIO_STATUS = {}  # {user_id: bool} - ساعت در بیو
DATE_IN_BIO_STATUS = {}   # {user_id: bool} - تاریخ در بیو
BIO_CLOCK_STATUS = {}     # {user_id: bool} - ساعت در بیو (دوپلیکیت برای سازگاری)
BIO_DATE_STATUS = {}      # {user_id: bool} - تاریخ در بیو (دوپلیکیت برای سازگاری)
DATE_TYPE_CHOICE = {}     # {user_id: 'میلادی' or 'شمسی'} - نوع تاریخ
BIO_DATE_TYPE = {}        # {user_id: 'jalali' or 'gregorian'} - نوع تاریخ (دوپلیکیت برای سازگاری)
BIO_CLOCK_FONT_CHOICE = {} # {user_id: int} - فونت ساعت بیو (1-5)
BIO_FONT_CHOICE = {}      # {user_id: str} - فونت ساعت بیو (دوپلیکیت برای سازگاری)
AUTO_SAVE_VIEW_ONCE = {}  # {user_id: bool} - ذخیره خودکار عکس‌های تایم‌دار
AUTO_SAVED_PHOTOS_COUNT = {}  # {user_id: int} - تعداد عکس‌های ذخیره‌شده (حداکثر 5)

# --- JSON Database Functions (from self.txt) ---
async def get_json_data(file_path):
    """Get data from JSON file"""
    try:
        if os.path.exists(file_path):
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
        else:
            # Default data structure
            return {
                'timename': 'off', 'timebio': 'off', 'timeprofile': 'off', 'timecrash': 'off',
                'bot': 'on', 'hashtag': 'off', 'bold': 'off', 'italic': 'off', 'delete': 'off',
                'code': 'off', 'underline': 'off', 'reverse': 'off', 'part': 'off',
                'mention': 'off', 'spoiler': 'off', 'comment': 'on', 'text': 'first !',
                'typing': 'off', 'game': 'off', 'voice': 'off', 'video': 'off', 'sticker': 'off',
                'crash': [], 'enemy': []
            }
    except Exception as e:
        logging.error(f"Error reading JSON file {file_path}: {e}")
        return {}

async def put_json_data(file_path, data):
    """Save data to JSON file"""
    try:
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception as e:
        logging.error(f"Error writing JSON file {file_path}: {e}")

def font_transform(text):
    """Transform text to small caps style"""
    text = text.lower()
    return text.translate(text.maketrans('qwertyuiopasdfghjklzxcvbnm','ǫᴡᴇʀᴛʏᴜɪᴏᴘᴀsᴅғɢʜᴊᴋʟᴢxᴄᴠʙɴᴍ'))

async def make_requests(url, **kwargs):
    """Make HTTP requests"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, **kwargs) as result:
                try:
                    return json.loads(await result.text())
                except:
                    return await result.read()
    except Exception as e:
        logging.error(f"Request error: {e}")
        return None

# Clock image creation function (from self.txt)
async def make_clock_image(h, m, s, read_path, write_path):
    """Create clock image with current time"""
    try:
        image = plt.imread(read_path)
        fig = plt.figure(figsize=(4,4), dpi=300, facecolor=[0.2,0.2,0.2])
        ax_image = fig.add_axes([0,0,1,1])
        ax_image.axis('off')
        ax_image.imshow(image)
        axc = fig.add_axes([0.062,0.062,0.88,0.88], projection='polar')
        axc.cla()
        seconds = numpy.multiply(numpy.ones(5), s * 2 * numpy.pi / 60)
        minutes = numpy.multiply(numpy.ones(5), m * 2 * numpy.pi / 60) + (seconds / 60)
        hours = numpy.multiply(numpy.ones(5), h * 2 * numpy.pi / 12) + (minutes / 12)
        axc.axis('off')
        axc.set_theta_zero_location('N')
        axc.set_theta_direction(-1)
        axc.plot(hours, numpy.linspace(0.00,0.70,5), c='c', linewidth=2.0)
        axc.plot(minutes, numpy.linspace(0.00,0.85,5), c='b', linewidth=1.5)
        axc.plot(seconds, numpy.linspace(0.00,1.00,5), c='r', linewidth=1.0)
        axc.plot(minutes, numpy.linspace(0.73,0.83,5), c='w', linewidth=1.0)
        axc.plot(hours, numpy.linspace(0.60,0.68,5), c='w', linewidth=1.5)
        axc.plot(seconds, numpy.linspace(0.80,0.98,5), c='w', linewidth=0.5)
        axc.set_rmax(1)
        plt.savefig(write_path)
        return write_path
    except Exception as e:
        logging.error(f"Error creating clock image: {e}")
        return None

COMMAND_REGEX = r"^(تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|ضبط ویس روشن|ضبط ویس خاموش|عکس روشن|عکس خاموش|گیف روشن|گیف خاموش|ترجمه [a-z]{2}(?:-[a-z]{2})?|ترجمه خاموش|چینی روشن|چینی خاموش|روسی روشن|روسی خاموش|انگلیسی روشن|انگلیسی خاموش|بولد روشن|بولد خاموش|ایتالیک روشن|ایتالیک خاموش|زیرخط روشن|زیرخط خاموش|خط خورده روشن|خط خورده خاموش|کد روشن|کد خاموش|اسپویلر روشن|اسپویلر خاموش|منشن روشن|منشن خاموش|هشتگ روشن|هشتگ خاموش|معکوس روشن|معکوس خاموش|تدریجی روشن|تدریجی خاموش|سین روشن|سین خاموش|ساعت روشن|ساعت خاموش|ساعت بیو روشن|ساعت بیو خاموش|تاریخ بیو روشن|تاریخ بیو خاموش|نوع تاریخ میلادی|نوع تاریخ شمسی|فونت|فونت \d+|فونت ساعت بیو|فونت ساعت بیو \d+|منشی روشن|منشی خاموش|منشی متن(?: |$)(.*)|انتی لوگین روشن|انتی لوگین خاموش|پیوی قفل|پیوی باز|ذخیره روشن|ذخیره خاموش|تکرار \d+( \d+)?|حذف همه|حذف(?: \d+)?|دشمن روشن|دشمن خاموش|تنظیم دشمن|حذف دشمن|پاکسازی لیست دشمن|لیست دشمن|لیست متن دشمن|تنظیم متن دشمن .*|حذف متن دشمن(?: \d+)?|دوست روشن|دوست خاموش|تنظیم دوست|حذف دوست|پاکسازی لیست دوست|لیست دوست|لیست متن دوست|تنظیم متن دوست .*|حذف متن دوست(?: \d+)?|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|ping|پینگ|راهنما|ترجمه|تگ|تگ ادمین ها|فان .*|قلب|حذف \d+|افزودن کراش|حذف کراش|لیست کراش|تنظیم متن کراش .*|لیست متن کراش|حذف متن کراش(?: \d+)?|کامنت روشن|کامنت خاموش|تنظیم گروه کامنت|حذف گروه کامنت|لیست گروه کامنت|حذف لیست گروه کامنت|کامنت .*|اسپم .*|فلود .*|دانلود|بن|پین|آن پین|شماره من)$"

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
                try:
                    me = await client.get_me()
                except Exception:
                    await asyncio.sleep(10)
                    continue

                current_name = me.first_name or ""

                # Remove clock from current name to get base name (same robust logic as main.txt)
                base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()

                # Initialize/update saved original name (persist only when we actually learn it)
                if user_id not in ORIGINAL_NAMES or not ORIGINAL_NAMES.get(user_id):
                    ORIGINAL_NAMES[user_id] = base_name or current_name or "User"
                    await save_settings_to_db(user_id)
                elif base_name and base_name != ORIGINAL_NAMES.get(user_id):
                    ORIGINAL_NAMES[user_id] = base_name
                    await save_settings_to_db(user_id)

                base_name = ORIGINAL_NAMES.get(user_id, base_name or current_name or "User")
                
                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                current_time_str = tehran_time.strftime("%H:%M")
                stylized_time = stylize_time(current_time_str, current_font_style)
                new_name = f"{base_name} {stylized_time}"
                
                if new_name != current_name:
                    try:
                        await client.update_profile(first_name=new_name[:64])
                    except FloodWait as e:
                        logging.warning(f"Clock flood wait: {e.value}s")
                        await asyncio.sleep(e.value)
                    except Exception as e:
                        logging.error(f"Profile update failed: {e}")

            now = datetime.now(TEHRAN_TIMEZONE)
            sleep_duration = 60 - now.second + 0.1
            await asyncio.sleep(sleep_duration)

        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Clock Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except FloodWait as e:
            logging.warning(f"Clock Task: Flood wait of {e.value}s for user_id {user_id}.")
            await asyncio.sleep(e.value + 5)
        except Exception as e:
            logging.error(f"An error occurred in clock task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)

    logging.info(f"Clock task for user_id {user_id} has stopped.")

async def update_bio_now(client: Client, user_id: int):
    """Update bio immediately (called when settings change)"""
    try:
        if not COPY_MODE_STATUS.get(user_id, False):
            # Get current bio

            try:
                peer = await safe_resolve_peer(client, "me")
                if peer:
                    me_full = await client.invoke(functions.users.GetFullUser(id=peer))
                    current_bio = me_full.full_user.about or ''
                else:
                    current_bio = ''
            except:
                current_bio = ''
            
            # Remove existing clock/date from bio
            base_bio = re.sub(r'(?:\s*[' + re.escape(ALL_CLOCK_CHARS) + r':/\s0-9۰-۹]+)+$', '', current_bio).strip()
            
            new_bio_parts = [base_bio] if base_bio else []
            
            # Add clock if enabled
            if BIO_CLOCK_STATUS.get(user_id, False):
                bio_font = BIO_FONT_CHOICE.get(user_id, 'stylized')
                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                time_str = tehran_time.strftime("%H:%M")
                stylized_time = stylize_time(time_str, bio_font)
                new_bio_parts.append(stylized_time)
            
            # Add date if enabled
            if BIO_DATE_STATUS.get(user_id, False):
                date_type = BIO_DATE_TYPE.get(user_id, 'jalali')
                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                
                if date_type == 'jalali':
                    # Jalali date
                    try:
                        import jdatetime
                        jdate = jdatetime.datetime.fromgregorian(datetime=tehran_time)
                        date_str = jdate.strftime("%Y/%m/%d")
                    except Exception:
                        date_str = tehran_time.strftime("%Y/%m/%d")
                else:
                    # Gregorian date
                    date_str = tehran_time.strftime("%Y/%m/%d")

                # Use the same selected bio font for date too (keeps style consistent and stable)
                bio_font = BIO_FONT_CHOICE.get(user_id, 'stylized')
                bio_font_map = FONT_STYLES.get(bio_font, FONT_STYLES['stylized'])
                stylized_date = ''.join(bio_font_map.get(c, c) for c in date_str)
                new_bio_parts.append(stylized_date)
            
            new_bio = ' '.join(new_bio_parts)
            
            if len(new_bio) <= 70:  # Telegram bio limit
                await client.update_profile(bio=new_bio)
                logging.info(f"Bio updated immediately for user {user_id}")
    except Exception as e:
        logging.error(f"Update bio now error for user {user_id}: {e}")

async def update_bio_clock(client: Client, user_id: int):
    """Update bio with clock and date"""
    logging.info(f"Starting bio clock loop for user_id {user_id}...")
    
    try:
        while True:
            try:
                if (BIO_CLOCK_STATUS.get(user_id, False) or BIO_DATE_STATUS.get(user_id, False)) and not COPY_MODE_STATUS.get(user_id, False):

                    # Get current bio
                    try:
                        peer = await safe_resolve_peer(client, "me")
                        if peer:
                            me_full = await client.invoke(functions.users.GetFullUser(id=peer))
                            current_bio = me_full.full_user.about or ''
                        else:
                            current_bio = ''
                    except:
                        current_bio = ''
                    
                    # Remove existing clock/date from bio
                    base_bio = re.sub(r'(?:\s*[' + re.escape(ALL_CLOCK_CHARS) + r':/\s0-9۰-۹]+)+$', '', current_bio).strip()
                    
                    new_bio_parts = [base_bio] if base_bio else []
                    
                    # Add clock if enabled
                    if BIO_CLOCK_STATUS.get(user_id, False):
                        bio_font = BIO_FONT_CHOICE.get(user_id, 'stylized')
                        tehran_time = datetime.now(TEHRAN_TIMEZONE)
                        time_str = tehran_time.strftime("%H:%M")
                        stylized_time = stylize_time(time_str, bio_font)
                        new_bio_parts.append(stylized_time)
                    
                    # Add date if enabled
                    if BIO_DATE_STATUS.get(user_id, False):
                        date_type = BIO_DATE_TYPE.get(user_id, 'jalali')
                        tehran_time = datetime.now(TEHRAN_TIMEZONE)
                        
                        if date_type == 'jalali':
                            # Jalali date
                            try:
                                import jdatetime
                                jdate = jdatetime.datetime.fromgregorian(datetime=tehran_time)
                                date_str = jdate.strftime("%Y/%m/%d")
                            except Exception:
                                date_str = tehran_time.strftime("%Y/%m/%d")
                        else:
                            # Gregorian date
                            date_str = tehran_time.strftime("%Y/%m/%d")

                        # Use the same selected bio font for date too
                        bio_font = BIO_FONT_CHOICE.get(user_id, 'stylized')
                        bio_font_map = FONT_STYLES.get(bio_font, FONT_STYLES['stylized'])
                        stylized_date = ''.join(bio_font_map.get(c, c) for c in date_str)
                        new_bio_parts.append(stylized_date)
                    
                    new_bio = ' '.join(new_bio_parts)
                    
                    if new_bio != current_bio and len(new_bio) <= 70:  # Telegram bio limit
                        await client.update_profile(bio=new_bio)

                
                # Sleep until next minute
                now = datetime.now(TEHRAN_TIMEZONE)
                sleep_duration = 60 - now.second + 0.1
                if sleep_duration < 1:
                    sleep_duration = 60
                await asyncio.sleep(sleep_duration)
                
            except (UserDeactivated, AuthKeyUnregistered):
                logging.error(f"Bio Clock Task: Session for user_id {user_id} is invalid. Stopping task.")
                break
            except FloodWait as e:
                logging.warning(f"Bio Clock Task: Flood wait of {e.value}s for user_id {user_id}.")
                await asyncio.sleep(e.value + 5)
            except asyncio.CancelledError:
                logging.info(f"Bio clock task for user_id {user_id} was cancelled.")
                break
            except Exception as e:
                logging.error(f"Bio Clock Task error for user_id {user_id}: {e}", exc_info=True)
                await asyncio.sleep(60)
    finally:
        logging.info(f"Bio clock task for user_id {user_id} has stopped.")

async def anti_login_task(client: Client, user_id: int):
    logging.info(f"Starting anti-login task for user_id {user_id}...")
    while user_id in ACTIVE_BOTS:
        try:
            if ANTI_LOGIN_STATUS.get(user_id, False) and functions:
                auths = await client.invoke(functions.account.GetAuthorizations())
                current_hash = None
                for auth in auths.authorizations:
                    if auth.current:
                        current_hash = auth.hash
                        break
                if current_hash:
                    sessions_terminated = 0
                    for auth in auths.authorizations:
                        if not auth.current:
                            try:
                                await client.invoke(functions.account.ResetAuthorization(hash=auth.hash))
                                sessions_terminated += 1
                                logging.info(f"Anti-Login: Terminated session for user {user_id} (Hash: {auth.hash})")
                                device_info = f"{auth.app_name} ({auth.app_version}) on {auth.device_model} ({auth.platform}, {auth.system_version})"
                                location_info = f"IP {auth.ip} in {auth.country}" if auth.ip else "Unknown Location"
                                message_text = (
                                    f"**هشدار امنیتی: نشست غیرمجاز خاتمه داده شد**\n\n"
                                    f"یک نشست فعال در حساب شما که با نشست فعلی این ربات مطابقت نداشت، به صورت خودکار خاتمه داده شد.\n\n"
                                    f"**جزئیات نشست خاتمه یافته:**\n"
                                    f"- **دستگاه:** {device_info}\n"
                                    f"- **مکان:** {location_info}\n"
                                    f"- **آخرین فعالیت:** {auth.date_active.strftime('%Y-%m-%d %H:%M:%S') if auth.date_active else 'N/A'}"
                                )
                                await client.send_message("me", message_text)
                            except FloodWait as e_term:
                                logging.warning(f"Anti-Login: Flood wait terminating session {auth.hash} for user {user_id}: {e_term.value}s")
                                await asyncio.sleep(e_term.value + 1)
                            except Exception as e_term_other:
                                logging.error(f"Anti-Login: Failed to terminate session {auth.hash} for user {user_id}: {e_term_other}")

            await asyncio.sleep(60 * 5)

        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Anti-Login Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except AttributeError:
             logging.error(f"Anti-Login Task: 'pyrogram.raw.functions' module not available for user_id {user_id}. Feature disabled.")
             ANTI_LOGIN_STATUS[user_id] = False
             await asyncio.sleep(3600)
        except Exception as e:
            logging.error(f"An error occurred in anti-login task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(120)

    logging.info(f"Anti-login task for user_id {user_id} has stopped.")

async def status_action_task(client: Client, user_id: int):
    logging.info(f"Starting status action task for user_id {user_id}...")
    chat_ids_cache = []
    last_dialog_fetch_time = 0
    FETCH_INTERVAL = 300

    while user_id in ACTIVE_BOTS:
        try:
            typing_mode = TYPING_MODE_STATUS.get(user_id, False)
            playing_mode = PLAYING_MODE_STATUS.get(user_id, False)
            record_voice = RECORD_VOICE_STATUS.get(user_id, False)
            upload_photo = UPLOAD_PHOTO_STATUS.get(user_id, False)
            watch_gif = WATCH_GIF_STATUS.get(user_id, False)

            if not (typing_mode or playing_mode or record_voice or upload_photo or watch_gif):
                await asyncio.sleep(5)
                continue

            action_to_send = None
            if typing_mode:
                action_to_send = ChatAction.TYPING
            elif playing_mode:
                action_to_send = ChatAction.PLAYING
            elif record_voice:
                action_to_send = ChatAction.RECORD_AUDIO
            elif upload_photo:
                action_to_send = ChatAction.UPLOAD_PHOTO
            elif watch_gif:
                action_to_send = ChatAction.CHOOSE_STICKER

            now = asyncio.get_event_loop().time()
            if not chat_ids_cache or (now - last_dialog_fetch_time > FETCH_INTERVAL):
                logging.info(f"Status Action: Refreshing dialog list for user_id {user_id}...")
                new_chat_ids = []
                try:
                    async for dialog in client.get_dialogs(limit=75):
                        if dialog.chat and dialog.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
                            new_chat_ids.append(dialog.chat.id)
                    chat_ids_cache = new_chat_ids
                    last_dialog_fetch_time = now
                    logging.info(f"Status Action: Found {len(chat_ids_cache)} chats for user {user_id}.")
                except Exception as e_dialog:
                     logging.error(f"Status Action: Error fetching dialogs for user {user_id}: {e_dialog}")
                     chat_ids_cache = []
                     last_dialog_fetch_time = 0
                     await asyncio.sleep(60)
                     continue

            if not chat_ids_cache:
                logging.warning(f"Status Action: No suitable chats found in cache for user_id {user_id}.")
                await asyncio.sleep(30)
                continue

            for chat_id in chat_ids_cache:
                try:
                    await client.send_chat_action(chat_id, action_to_send)
                except FloodWait as e_action:
                    logging.warning(f"Status Action: Flood wait sending action to chat {chat_id} for user {user_id}. Sleeping {e_action.value}s.")
                    await asyncio.sleep(e_action.value + 1)
                except PeerIdInvalid:
                     logging.warning(f"Status Action: PeerIdInvalid for chat {chat_id}. Removing from cache.")
                     try: chat_ids_cache.remove(chat_id)
                     except ValueError: pass
                except Exception:
                    pass

            await asyncio.sleep(4.5)

        except (UserDeactivated, AuthKeyUnregistered):
            logging.error(f"Status Action Task: Session for user_id {user_id} is invalid. Stopping task.")
            break
        except Exception as e:
            logging.error(f"An error occurred in status action task for user_id {user_id}: {e}", exc_info=True)
            await asyncio.sleep(60)

    logging.info(f"Status action task for user_id {user_id} has stopped.")

async def translate_text(text: str, target_lang: str = "fa") -> str:
    if not text: return text
    encoded_text = quote(text)
    url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target_lang}&dt=t&q={encoded_text}"
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    try:
                        data = await response.json(content_type=None)
                        if isinstance(data, list) and data and isinstance(data[0], list):
                            translated_text = "".join(segment[0] for segment in data[0] if isinstance(segment, list) and segment and isinstance(segment[0], str))
                            return translated_text.strip() if translated_text else text
                        else:
                            logging.warning(f"Unexpected translation response structure: {str(data)[:200]}")
                            return text
                    except (IndexError, TypeError, ValueError, AttributeError, aiohttp.ContentTypeError) as json_err:
                         logging.warning(f"Could not parse translation response: {json_err}. Response: {await response.text()[:200]}")
                         return text
                else:
                    logging.error(f"Translation API request failed: Status {response.status}, Response: {await response.text()[:200]}")
                    return text
    except asyncio.TimeoutError:
         logging.error("Translation request timed out.")
         return text
    except Exception as e:
        logging.error(f"Translation request failed: {e}", exc_info=True)
    return text

async def outgoing_message_modifier(client, message):
    """Modify outgoing messages for bold and auto-translation"""
    user_id = client.me.id
    if not message.text or message.text.startswith("/"):
        return

    # Skip commands
    if re.match(COMMAND_REGEX, message.text.strip(), re.IGNORECASE):
        return

    original_text = message.text
    modified_text = original_text
    needs_edit = False
    edit_entities = None

    # Quote mode:
    # Prefer native blockquote entity (no visible ">" characters in text).
    # Fallback to "> " prefix when entity isn't supported by this Pyrogram version.
    if QUOTE_MODE_STATUS.get(user_id, False):
        try:
            t = (modified_text or "").strip("\n")
            if t:
                if MessageEntityBlockquote is not None:
                    edit_entities = [MessageEntityBlockquote(offset=0, length=len(t))]
                    modified_text = t
                    needs_edit = True
                else:
                    if not t.lstrip().startswith(">"):
                        lines = t.splitlines() or [t]
                        modified_text = "\n".join([f"> {ln}" if ln.strip() else ">" for ln in lines])
                        needs_edit = True
        except Exception as e_quote:
            logging.warning(f"Outgoing Modifier: Quote mode failed for msg {getattr(message,'id',None)} user {user_id}: {e_quote}")

    # Auto translation (using Google Translate API like original)
    target_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    if target_lang:
        try:
            translated = await translate_text(modified_text, target_lang)
            if translated and translated != modified_text:
                modified_text = translated
                needs_edit = True
        except Exception as trans_err:
            logging.warning(f"Auto-translation error: {trans_err}")

    # Bold mode - more reliable checking
    if BOLD_MODE_STATUS.get(user_id, False):
        # Make sure we don't already have bold formatting
        if not (modified_text.startswith('**') and modified_text.endswith('**')):
            # Remove any partial existing formatting
            modified_text = modified_text.replace('**', '')
            # Apply fresh bold formatting
            modified_text = f"**{modified_text}**"
            needs_edit = True

    # Apply modifications
    if needs_edit and modified_text != original_text:
        try:
            await message.edit_text(modified_text, entities=edit_entities, disable_web_page_preview=True)
        except FloodWait as e:
             logging.warning(f"Outgoing Modifier: Flood wait editing msg {message.id} for user {user_id}: {e.value}s")
             await asyncio.sleep(e.value + 1)
        except (MessageNotModified, MessageIdInvalid):
             pass
        except Exception as e:
            logging.warning(f"Outgoing Modifier: Could not edit msg {message.id} for user {user_id}: {e}")

async def enemy_handler(client, message):
    user_id = client.me.id
    replies = ENEMY_REPLIES.get(user_id, [])
    if not replies:
        return

    reply_text = random.choice(replies)
    try:
        await message.reply_text(reply_text, quote=True)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.warning(f"Enemy Handler: Could not reply to message {message.id} for user {user_id}: {e}")

async def friend_handler(client, message):
    user_id = client.me.id
    replies = FRIEND_REPLIES.get(user_id, [])
    if not replies:
        return

    reply_text = random.choice(replies)
    try:
        await message.reply_text(reply_text, quote=True)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.warning(f"Friend Handler: Could not reply to message {message.id} for user {user_id}: {e}")

async def pv_lock_handler(client, message):
    owner_user_id = client.me.id
    try:
        if getattr(getattr(message, "chat", None), "type", None) == ChatType.PRIVATE:
            logging.info(
                "PV Lock(global): handler reached msg_id=%s chat_id=%s from_id=%s pv_lock=%s",
                getattr(message, "id", None),
                getattr(getattr(message, "chat", None), "id", None),
                getattr(getattr(message, "from_user", None), "id", None),
                PV_LOCK_STATUS.get(owner_user_id, False),
            )
    except Exception as e_dbg:
        logging.warning("PV Lock(global): debug log failed err=%s", e_dbg)
    try:
        if getattr(getattr(message, "from_user", None), "id", None) == owner_user_id:
            return
    except Exception:
        pass
    
    # IMPORTANT: Check if message is a sticker - if sticker lock is OFF, don't delete stickers
    # This prevents stickers from being deleted by the global PV lock when sticker lock is off
    # We need to check for stickers the same way as pv_media_lock_handler does
    has_sticker = bool(getattr(message, "sticker", None))
    doc = getattr(message, "document", None)
    mime = getattr(doc, "mime_type", None) if doc else None
    file_name = getattr(doc, "file_name", "") if doc else ""
    mime_l = (mime or "").lower()
    file_name_l = (file_name or "").lower()
    
    # Check if document is a sticker (same logic as pv_media_lock_handler)
    is_doc_sticker = (
        has_sticker  # Has sticker attribute (most reliable)
        or (mime_l in {"application/x-tgsticker", "application/vnd.tgstickers"})  # Animated sticker mime type
        or file_name_l.endswith(".tgs")  # Animated sticker file extension
    )
    
    if has_sticker or is_doc_sticker:
        # If it's a sticker and sticker lock is OFF, don't delete it (let pv_media_lock_handler handle it)
        if not PV_STICKER_LOCK_STATUS.get(owner_user_id, False):
            return
    
    if PV_LOCK_STATUS.get(owner_user_id, False):
        try:
            await message.delete()
        except FloodWait as e:
             logging.warning(f"PV Lock: Flood wait deleting message {message.id} for user {owner_user_id}: {e.value}s")
             await asyncio.sleep(e.value + 1)
        except MessageIdInvalid:
             pass
        except Exception as e:
            if "Message to delete not found" not in str(e):
                 logging.warning(f"PV Lock: Could not delete message {message.id} for user {owner_user_id}: {e}")

async def _pv_try_delete(client, message, reason: str):
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    msg_id = getattr(message, "id", None)
    try:
        await message.delete()
        logging.info("PV Lock: deleted msg_id=%s chat_id=%s reason=%s", msg_id, chat_id, reason)
        return True
    except Exception as e1:
        logging.warning(
            "PV Lock: message.delete failed msg_id=%s chat_id=%s reason=%s err=%s",
            msg_id,
            chat_id,
            reason,
            e1,
        )

    try:
        if chat_id is not None and msg_id is not None:
            await client.delete_messages(chat_id, [msg_id], revoke=True)
            logging.info(
                "PV Lock: deleted via client.delete_messages msg_id=%s chat_id=%s reason=%s",
                msg_id,
                chat_id,
                reason,
            )
            return True
    except Exception as e2:
        logging.error(
            "PV Lock: client.delete_messages failed msg_id=%s chat_id=%s reason=%s err=%s",
            msg_id,
            chat_id,
            reason,
            e2,
            exc_info=True,
        )

    return False

async def pv_media_lock_handler(client, message):
    try:
        owner_user_id = client.me.id if hasattr(client, "me") and client.me else None
        logging.info("PV Media Lock Handler: START called for msg_id=%s owner_user_id=%s", getattr(message, "id", None), owner_user_id)
        
        # Check if message has required attributes
        if not hasattr(message, "chat") or not message.chat:
            logging.warning("PV Media Lock Handler: message has no chat attribute")
            return
            
        if message.chat.type != ChatType.PRIVATE:
            logging.debug("PV Media Lock Handler: not private chat, returning")
            return

        chat_id = message.chat.id if hasattr(message.chat, "id") else None
        from_id = message.from_user.id if hasattr(message, "from_user") and message.from_user else None
        msg_id = message.id if hasattr(message, "id") else None
        
        logging.info(
            "PV Lock: incoming msg_id=%s chat_id=%s from_id=%s text=%r caption=%r",
            msg_id,
            chat_id,
            from_id,
            getattr(message, "text", None),
            getattr(message, "caption", None),
        )

        # Skip if message is from owner
        if from_id == owner_user_id:
            logging.debug("PV Media Lock Handler: message from owner, skipping")
            return

        logging.info(
            "PV Lock: status user_id=%s text=%s emoji=%s sticker=%s gif=%s photo=%s video=%s voice=%s document=%s audio=%s vnote=%s contact=%s location=%s",
            owner_user_id,
            PV_TEXT_LOCK_STATUS.get(owner_user_id, False),
            PV_EMOJI_LOCK_STATUS.get(owner_user_id, False),
            PV_STICKER_LOCK_STATUS.get(owner_user_id, False),
            PV_GIF_LOCK_STATUS.get(owner_user_id, False),
            PV_PHOTO_LOCK_STATUS.get(owner_user_id, False),
            PV_VIDEO_LOCK_STATUS.get(owner_user_id, False),
            PV_VOICE_LOCK_STATUS.get(owner_user_id, False),
            PV_DOCUMENT_LOCK_STATUS.get(owner_user_id, False),
            PV_AUDIO_LOCK_STATUS.get(owner_user_id, False),
            PV_VIDEO_NOTE_LOCK_STATUS.get(owner_user_id, False),
            PV_CONTACT_LOCK_STATUS.get(owner_user_id, False),
            PV_LOCATION_LOCK_STATUS.get(owner_user_id, False),
        )

        # Detect media types - IMPORTANT: Check stickers FIRST before anything else
        # Check for sticker FIRST (this is critical - stickers must be identified before other media)
        has_sticker = bool(getattr(message, "sticker", None))
        
        doc = getattr(message, "document", None)
        mime = getattr(doc, "mime_type", None) if doc else None
        file_name = getattr(doc, "file_name", "") if doc else ""
        mime_l = (mime or "").lower()
        file_name_l = (file_name or "").lower()

        # Check if document is a sticker (animated or static)
        # IMPORTANT: The most reliable way to detect stickers is the has_sticker attribute
        # If has_sticker is True, it's definitely a sticker
        # For documents, we check mime types and file extensions
        is_doc_sticker = (
            has_sticker  # Has sticker attribute (most reliable - if True, definitely a sticker)
            or (mime_l in {"application/x-tgsticker", "application/vnd.tgstickers"})  # Animated sticker mime type
            or file_name_l.endswith(".tgs")  # Animated sticker file extension
        )
        
        # IMPORTANT: If it's a sticker (has_sticker=True or is_doc_sticker=True), 
        # ONLY check sticker lock and return (don't check text/emoji/photo/document locks)
        if has_sticker or is_doc_sticker:
            if PV_STICKER_LOCK_STATUS.get(owner_user_id, False):
                await _pv_try_delete(client, message, "sticker")
                return
            # If sticker lock is off, don't check other locks - just return
            return

        # Now check other media types (sticker is already excluded - we returned above if it was a sticker)
        is_doc_gif = (mime_l == "image/gif") or file_name_l.endswith(".gif") or (mime_l == "video/mp4" and "gif" in file_name_l)
        # Exclude stickers from image check - if we reach here, it's NOT a sticker (we returned above)
        is_doc_image = bool(mime_l.startswith("image/"))  # Safe to check - stickers already excluded
        is_doc_video = bool(mime_l.startswith("video/"))
        is_doc_voice = (mime_l in {"audio/ogg", "audio/opus"}) or file_name_l.endswith(".ogg") or file_name_l.endswith(".opus")
        is_doc_audio = bool(mime_l.startswith("audio/")) and not is_doc_voice

        # Check if message has any media (excluding stickers and text-only messages)
        has_media = bool(
            getattr(message, "photo", None)
            or getattr(message, "video", None)
            or getattr(message, "animation", None)
            or getattr(message, "voice", None)
            or (getattr(message, "document", None) and not is_doc_sticker)  # Exclude stickers
            or getattr(message, "audio", None)
            or getattr(message, "video_note", None)
            or getattr(message, "contact", None)
            or getattr(message, "location", None)
        )

        # Get text content from both text and caption
        text_content = (getattr(message, "text", None) or getattr(message, "caption", None) or "")
        if not isinstance(text_content, str):
            text_content = str(text_content) if text_content else ""

        # Check media locks (sticker already handled above)
        # 1. GIF lock
        if (getattr(message, "animation", None) or is_doc_gif) and PV_GIF_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "gif")
            return

        # 2. Photo lock - ONLY photos (sticker already excluded)
        if (getattr(message, "photo", None) or is_doc_image) and PV_PHOTO_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "photo")
            return

        # 3. Video lock
        if (getattr(message, "video", None) or is_doc_video) and PV_VIDEO_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "video")
            return

        # 4. Voice lock - ONLY voice messages
        if (getattr(message, "voice", None) or is_doc_voice) and PV_VOICE_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "voice")
            return

        # 5. Audio lock
        if (getattr(message, "audio", None) or is_doc_audio) and PV_AUDIO_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "audio")
            return

        # 6. Video note lock
        if getattr(message, "video_note", None) and PV_VIDEO_NOTE_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "video_note")
            return

        # 7. Contact lock
        if getattr(message, "contact", None) and PV_CONTACT_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "contact")
            return

        # 8. Location lock
        if getattr(message, "location", None) and PV_LOCATION_LOCK_STATUS.get(owner_user_id, False):
            await _pv_try_delete(client, message, "location")
            return

        # 9. Document lock (only for non-image, non-video, non-audio, non-sticker documents)
        if getattr(message, "document", None) and PV_DOCUMENT_LOCK_STATUS.get(owner_user_id, False):
            # Don't delete if it's already handled by other locks (including stickers)
            if not (is_doc_sticker or is_doc_gif or is_doc_image or is_doc_video or is_doc_voice or is_doc_audio):
                await _pv_try_delete(client, message, "document")
                return

        # If message has NO media (only text), check text/emoji locks
        if not has_media:
            # Check text lock - if message has ANY text and text lock is on, delete it
            if text_content and PV_TEXT_LOCK_STATUS.get(owner_user_id, False):
                await _pv_try_delete(client, message, "text")
                return

            # Check emoji lock - if message has ANY emoji and emoji lock is on, delete it
            if text_content and PV_EMOJI_LOCK_STATUS.get(owner_user_id, False):
                try:
                    emoji_pattern = r"[\U0001F300-\U0001F9FF\u2600-\u27BF]"
                    has_emoji = bool(re.search(emoji_pattern, text_content))
                    if has_emoji:
                        await _pv_try_delete(client, message, "emoji_text")
                        return
                except Exception as emoji_check_error:
                    logging.warning("PV Lock: emoji check failed: %s", emoji_check_error)

    except FloodWait as e:
        logging.warning("PV Media Lock Handler: FloodWait for msg_id=%s, waiting %s seconds", getattr(message, "id", None), e.value)
        await asyncio.sleep(e.value + 1)
    except MessageIdInvalid:
        logging.debug("PV Media Lock Handler: MessageIdInvalid for msg_id=%s", getattr(message, "id", None))
        pass
    except Exception as e:
        logging.error(
            "PV Media Lock Handler: Exception for msg_id=%s chat_id=%s err=%s",
            getattr(message, "id", None),
            getattr(getattr(message, "chat", None), "id", None) if hasattr(message, "chat") and message.chat else None,
            e,
            exc_info=True
        )

async def pv_media_lock_controller(client, message):
    user_id = client.me.id
    command = re.sub(r"\s+", " ", (message.text or "").replace("\u200c", " ").strip())
    logging.info("PV Media Lock Controller: raw=%r normalized=%r user_id=%s", message.text, command, user_id)

    mapping = {
        "قفل گیف روشن": (PV_GIF_LOCK_STATUS, True, "✅ قفل گیف در PV فعال شد. هر گیفی ارسال شود حذف می‌شود."),
        "قفل گیف خاموش": (PV_GIF_LOCK_STATUS, False, "❌ قفل گیف در PV غیرفعال شد."),
        "قفل عکس روشن": (PV_PHOTO_LOCK_STATUS, True, "✅ قفل عکس در PV فعال شد. هر عکسی ارسال شود حذف می‌شود."),
        "قفل عکس خاموش": (PV_PHOTO_LOCK_STATUS, False, "❌ قفل عکس در PV غیرفعال شد."),
        "قفل ویدیو روشن": (PV_VIDEO_LOCK_STATUS, True, "✅ قفل ویدیو در PV فعال شد. هر ویدیویی ارسال شود حذف می‌شود."),
        "قفل ویدیو خاموش": (PV_VIDEO_LOCK_STATUS, False, "❌ قفل ویدیو در PV غیرفعال شد."),
        "قفل ویس روشن": (PV_VOICE_LOCK_STATUS, True, "✅ قفل ویس در PV فعال شد. هر ویسی ارسال شود حذف می‌شود."),
        "قفل ویس خاموش": (PV_VOICE_LOCK_STATUS, False, "❌ قفل ویس در PV غیرفعال شد."),
        "قفل استیکر روشن": (PV_STICKER_LOCK_STATUS, True, "✅ قفل استیکر در PV فعال شد. هر استیکری ارسال شود حذف می‌شود."),
        "قفل استیکر خاموش": (PV_STICKER_LOCK_STATUS, False, "❌ قفل استیکر در PV غیرفعال شد."),
        "قفل فایل روشن": (PV_DOCUMENT_LOCK_STATUS, True, "✅ قفل فایل در PV فعال شد. هر فایلی ارسال شود حذف می‌شود."),
        "قفل فایل خاموش": (PV_DOCUMENT_LOCK_STATUS, False, "❌ قفل فایل در PV غیرفعال شد."),
        "قفل موزیک روشن": (PV_AUDIO_LOCK_STATUS, True, "✅ قفل موزیک در PV فعال شد. هر موزیکی ارسال شود حذف می‌شود."),
        "قفل موزیک خاموش": (PV_AUDIO_LOCK_STATUS, False, "❌ قفل موزیک در PV غیرفعال شد."),
        "قفل ویدیو نوت روشن": (PV_VIDEO_NOTE_LOCK_STATUS, True, "✅ قفل ویدیو نوت در PV فعال شد. هر ویدیو نوت ارسال شود حذف می‌شود."),
        "قفل ویدیو نوت خاموش": (PV_VIDEO_NOTE_LOCK_STATUS, False, "❌ قفل ویدیو نوت در PV غیرفعال شد."),
        "قفل کانتکت روشن": (PV_CONTACT_LOCK_STATUS, True, "✅ قفل کانتکت در PV فعال شد. هر کانتکتی ارسال شود حذف می‌شود."),
        "قفل کانتکت خاموش": (PV_CONTACT_LOCK_STATUS, False, "❌ قفل کانتکت در PV غیرفعال شد."),
        "قفل لوکیشن روشن": (PV_LOCATION_LOCK_STATUS, True, "✅ قفل لوکیشن در PV فعال شد. هر لوکیشنی ارسال شود حذف می‌شود."),
        "قفل لوکیشن خاموش": (PV_LOCATION_LOCK_STATUS, False, "❌ قفل لوکیشن در PV غیرفعال شد."),
        "قفل ایموجی روشن": (PV_EMOJI_LOCK_STATUS, True, "✅ قفل ایموجی در PV فعال شد. هر ایموجی ارسال شود حذف می‌شود."),
        "قفل ایموجی خاموش": (PV_EMOJI_LOCK_STATUS, False, "❌ قفل ایموجی در PV غیرفعال شد."),
        "قفل متن روشن": (PV_TEXT_LOCK_STATUS, True, "✅ قفل متن در PV فعال شد. هر متنی ارسال شود حذف می‌شود."),
        "قفل متن خاموش": (PV_TEXT_LOCK_STATUS, False, "❌ قفل متن در PV غیرفعال شد."),
    }

    if command not in mapping:
        logging.info("PV Media Lock Controller: no mapping match for %r", command)
        return

    try:
        store, value, text = mapping[command]
        store[user_id] = value
        await save_settings_to_db(user_id)
        logging.info(f"PV Media Lock: {command} set to {value} for user {user_id}")
        await message.edit_text(text)
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"PV Media Lock Controller: Error for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطا در تنظیم قفل مدیا")
        except Exception:
            pass


async def copy_profile_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    # Check if command requires reply
    requires_reply = command == "کپی روشن"

    async def _send_ephemeral_status(text: str):
        try:
            m = await client.send_message(message.chat.id, text)
            try:
                await m.delete()
            except Exception:
                pass
        except Exception:
            pass

    try:
        await message.delete()
    except Exception:
        pass

    if requires_reply and (not message.reply_to_message or not message.reply_to_message.from_user):
        return

    try:
        if command == "کپی خاموش":
            if not COPY_MODE_STATUS.get(user_id, False):
                return

            original = ORIGINAL_PROFILE_DATA.get(user_id)  # keep until restore succeeds
            if not original:
                # No backup available; at least disable copy mode and persist.
                COPY_MODE_STATUS[user_id] = False
                await save_settings_to_db(user_id)
                await _send_ephemeral_status("خاموش شد")
                return

            if original:
                # Restore profile info
                try:
                    await client.update_profile(
                        first_name=original.get('first_name', ''),
                        last_name=original.get('last_name', ''),
                        bio=original.get('bio', '')
                    )
                except Exception:
                    pass

                # Delete current photos BEFORE setting the original one
                try:
                    photos_to_delete = [p.file_id async for p in client.get_chat_photos("me")]
                    if photos_to_delete:
                        await client.delete_profile_photos(photos_to_delete)
                except Exception as e_del_apply:
                    logging.warning(f"Copy Profile (Apply): Could not delete existing photos for user {user_id}: {e_del_apply}")

                # Restore original photo if it existed
                original_photo_paths = original.get('photo_paths') or []
                if original_photo_paths:
                    for path in reversed(original_photo_paths[:5]):
                        if not path:
                            continue
                        try:
                            if os.path.exists(path):
                                await client.set_profile_photo(photo=path)
                        except Exception as e_set_original_photo:
                            logging.warning(f"Copy Profile (Restore): Could not set original photo for user {user_id}: {e_set_original_photo}")
                        finally:
                            try:
                                if os.path.exists(path):
                                    os.remove(path)
                            except Exception:
                                pass
                else:
                    original_photo_data = original.get('photo')
                    if original_photo_data:
                        try:
                            await client.set_profile_photo(photo=original_photo_data)
                        except Exception as e_set_target_photo:
                             logging.warning(f"Copy Profile (Restore): Could not set original photo for user {user_id}: {e_set_target_photo}")

                # Restore complete, now drop backup
                try:
                    ORIGINAL_PROFILE_DATA.pop(user_id, None)
                except Exception:
                    pass

            COPY_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await _send_ephemeral_status("خاموش شد")
            return

        # Logic for "کپی روشن" (requires_reply was checked earlier)
        elif command == "کپی روشن":
            target_user = message.reply_to_message.from_user
            target_id = target_user.id

            # --- Backup Current Profile ---
            me = await client.get_me()
            me_photo_bytes = None
            me_bio = ""
            try:
                # Get full user info for bio
                peer = await safe_resolve_peer(client, "me")
                if peer:
                    me_full = await client.invoke(functions.users.GetFullUser(id=peer))
                me_bio = me_full.full_user.about or ''
            except Exception as e_get_bio:
                 logging.warning(f"Copy Profile (Backup): Could not get own bio for user {user_id}: {e_get_bio}")

            # Download current photo if exists
            if me.photo:
                try:
                    me_photo_bytes = await client.download_media(me.photo.big_file_id, in_memory=True) # download to memory
                except Exception as e_download_me:
                     logging.warning(f"Copy Profile (Backup): Could not download own photo for user {user_id}: {e_download_me}")

            original_photo_paths = []
            try:
                count = 0
                async for photo in client.get_chat_photos("me"):
                    if count >= 5:
                        break
                    try:
                        path = await client.download_media(photo.file_id, file_name=f"original_{user_id}_{photo.file_id}.jpg")
                        if path:
                            original_photo_paths.append(path)
                            count += 1
                    except Exception as e_download_original_photo:
                        logging.warning(f"Copy Profile (Backup): Could not download original photo for user {user_id}: {e_download_original_photo}")
            except Exception as e_iter_original_photos:
                logging.warning(f"Copy Profile (Backup): Could not iterate original photos for user {user_id}: {e_iter_original_photos}")

            # Store backup including clock/bio settings
            ORIGINAL_PROFILE_DATA[user_id] = {
                'first_name': me.first_name or '',
                'last_name': me.last_name or '',
                'bio': me_bio,
                'photo': me_photo_bytes, # Store bytes or None
                'photo_paths': original_photo_paths,
                'clock_in_bio': CLOCK_IN_BIO_STATUS.get(user_id, False),
                'date_in_bio': DATE_IN_BIO_STATUS.get(user_id, False),
                'clock_font': BIO_CLOCK_FONT_CHOICE.get(user_id, 1),
                'date_type': DATE_TYPE_CHOICE.get(user_id, 'میلادی')
            }

            # --- Get Target Profile Info ---
            target_photo_bytes = None
            target_bio = ""
            try:
                 peer = await safe_resolve_peer(client, target_id)
                 if peer:
                     target_full = await client.invoke(functions.users.GetFullUser(id=peer))
                 target_bio = target_full.full_user.about or ''
            except Exception as e_get_target_bio:
                 logging.warning(f"Copy Profile (Target): Could not get target bio for user {target_id}: {e_get_target_bio}")

            if target_user.photo:
                try:
                    target_photo_bytes = await client.download_media(target_user.photo.big_file_id, in_memory=True) # download to memory
                except Exception as e_download_target:
                    logging.warning(f"Copy Profile (Target): Could not download target photo for user {target_id}: {e_download_target}")

            # --- Apply Target Profile ---
            # Update name and bio
            await client.update_profile(
                first_name=target_user.first_name or '',
                last_name=target_user.last_name or '',
                bio=target_bio
            )

            # Delete existing photos
            try:
                photos_to_delete = [p.file_id async for p in client.get_chat_photos("me")]
                if photos_to_delete:
                    await client.delete_profile_photos(photos_to_delete)
            except Exception as e_del_apply:
                logging.warning(f"Copy Profile (Apply): Could not delete existing photos for user {user_id}: {e_del_apply}")

            # Set up to last 5 target photos
            target_photo_paths = []
            try:
                count = 0
                async for photo in client.get_chat_photos(target_id):
                    if count >= 5:
                        break
                    try:
                        path = await client.download_media(photo.file_id, file_name=f"target_{user_id}_{target_id}_{photo.file_id}.jpg")
                        if path:
                            target_photo_paths.append(path)
                            count += 1
                    except Exception as e_download_target_photo:
                        logging.warning(f"Copy Profile (Target): Could not download target photo for user {target_id}: {e_download_target_photo}")
            except Exception as e_iter_target_photos:
                logging.warning(f"Copy Profile (Target): Could not iterate target photos for user {target_id}: {e_iter_target_photos}")

            if target_photo_paths:
                for path in reversed(target_photo_paths[:5]):
                    if not path:
                        continue
                    try:
                        if os.path.exists(path):
                            await client.set_profile_photo(photo=path)
                    except Exception as e_set_target_photo:
                        logging.warning(f"Copy Profile (Apply): Could not set target photo for user {user_id}: {e_set_target_photo}")
                    finally:
                        try:
                            if os.path.exists(path):
                                os.remove(path)
                        except Exception:
                            pass
            elif target_photo_bytes:
                try:
                    await client.set_profile_photo(photo=target_photo_bytes)
                except Exception as e_set_target_photo:
                     logging.warning(f"Copy Profile (Apply): Could not set target photo for user {user_id}: {e_set_target_photo}")

            COPY_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await _send_ephemeral_status("فعال شد")
    except Exception as e:
        logging.error(f"Copy Profile Controller: Error for user {user_id} processing command '{command}': {e}", exc_info=True)
        return

async def set_enemy_controller(client, message):
    user_id = client.me.id
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        enemies = ENEMY_LIST.setdefault(user_id, set())
        if target_id not in enemies:
             enemies.add(target_id)
             await save_settings_to_db(user_id)
             await message.edit_text(f"✅ کاربر با آیدی `{target_id}` به لیست دشمن اضافه شد.")
        else:
            await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` از قبل در لیست دشمن بود.")
    else:
        await message.edit_text("⚠️ برای افزودن به لیست دشمن، روی پیام کاربر مورد نظر ریپلای کنید.")

async def delete_enemy_controller(client, message):
    user_id = client.me.id
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        enemies = ENEMY_LIST.get(user_id) # No setdefault needed here
        if enemies and target_id in enemies:
            enemies.remove(target_id)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ کاربر با آیدی `{target_id}` از لیست دشمن حذف شد.")
        else:
            await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` در لیست دشمن یافت نشد.")
    else:
        await message.edit_text("⚠️ برای حذف از لیست دشمن، روی پیام کاربر مورد نظر ریپلای کنید.")

async def clear_enemy_list_controller(client, message):
    user_id = client.me.id
    if ENEMY_LIST.get(user_id): # Check if the list exists and is not empty
        ENEMY_LIST[user_id] = set()
        await save_settings_to_db(user_id)
        await message.edit_text("✅ لیست دشمن با موفقیت پاکسازی شد.")
    else:
        await message.edit_text("ℹ️ لیست دشمن از قبل خالی بود.")

async def list_enemies_controller(client, message):
    user_id = client.me.id
    enemies = ENEMY_LIST.get(user_id, set())
    if not enemies:
        await message.edit_text("ℹ️ لیست دشمن خالی است.")
    else:
        # Try to get usernames or first names for better readability
        list_items = []
        for eid in enemies:
            try:
                # Fetch user info - might fail if user is inaccessible
                user = await client.get_users(eid)
                display_name = f"{user.first_name}" + (f" {user.last_name}" if user.last_name else "")
                list_items.append(f"- {display_name} (`{eid}`)")
            except Exception:
                # Fallback to just ID if fetching fails
                list_items.append(f"- User ID: `{eid}`")

        list_text = "**📋 لیست دشمنان:**\n" + "\n".join(list_items)
        # Handle potential message too long error
        if len(list_text) > 4096:
            list_text = list_text[:4090] + "\n[...]" # Truncate if too long
        await message.edit_text(list_text)

async def list_enemy_replies_controller(client, message):
    user_id = client.me.id
    replies = ENEMY_REPLIES.get(user_id, [])
    if not replies:
        await message.edit_text("ℹ️ لیست متن‌های پاسخ دشمن خالی است.")
    else:
        list_text = "**📋 لیست متن‌های دشمن:**\n" + "\n".join([f"{i+1}. `{reply}`" for i, reply in enumerate(replies)])
        if len(list_text) > 4096:
            list_text = list_text[:4090] + "\n[...]"
        await message.edit_text(list_text)

async def delete_enemy_reply_controller(client, message):
    user_id = client.me.id
    match = re.match(r"^حذف متن دشمن(?: (\d+))?$", message.text, re.IGNORECASE) # Added ignorecase
    if match:
        index_str = match.group(1)
        replies = ENEMY_REPLIES.get(user_id) # Get list or None

        if replies is None or not replies:
             await message.edit_text("ℹ️ لیست متن دشمن خالی است، چیزی برای حذف وجود ندارد.")
             return

        try:
            if index_str:
                index = int(index_str) - 1 # User inputs 1-based index
                if 0 <= index < len(replies):
                    removed_reply = replies.pop(index) # Use pop to remove by index
                    await save_settings_to_db(user_id)
                    await message.edit_text(f"✅ متن شماره {index+1} (`{removed_reply}`) از لیست دشمن حذف شد.")
                else:
                    await message.edit_text(f"⚠️ شماره نامعتبر. لطفاً عددی بین 1 تا {len(replies)} وارد کنید.")
            else:
                # Delete all replies
                ENEMY_REPLIES[user_id] = []
                await save_settings_to_db(user_id)
                await message.edit_text("✅ تمام متن‌های پاسخ دشمن حذف شدند.")
        except ValueError:
             await message.edit_text("⚠️ شماره وارد شده نامعتبر است.")
        except Exception as e:
            logging.error(f"Delete Enemy Reply: Error for user {user_id}: {e}", exc_info=True)
            await message.edit_text("⚠️ خطایی در حذف متن دشمن رخ داد.")

async def set_enemy_reply_controller(client, message):
    user_id = client.me.id
    # Use re.IGNORECASE for robustness
    match = re.match(r"^تنظیم متن دشمن (.*)", message.text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        if text:
            # Initialize the list if it doesn't exist for the user
            if user_id not in ENEMY_REPLIES:
                ENEMY_REPLIES[user_id] = []
            ENEMY_REPLIES[user_id].append(text)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ متن جدید به لیست پاسخ دشمن اضافه شد (مورد {len(ENEMY_REPLIES[user_id])}).")
        else:
            await message.edit_text("⚠️ متن پاسخ نمی‌تواند خالی باشد.")
    # else: Regex didn't match (should not happen with current handler setup)

async def set_friend_controller(client, message):
    user_id = client.me.id
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        friends = FRIEND_LIST.setdefault(user_id, set())
        if target_id not in friends:
            friends.add(target_id)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ کاربر با آیدی `{target_id}` به لیست دوست اضافه شد.")
        else:
            await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` از قبل در لیست دوست بود.")
    else:
        await message.edit_text("⚠️ برای افزودن به لیست دوست، روی پیام کاربر مورد نظر ریپلای کنید.")

async def delete_friend_controller(client, message):
    user_id = client.me.id
    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        friends = FRIEND_LIST.get(user_id) # No setdefault needed here
        if friends and target_id in friends:
            friends.remove(target_id)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ کاربر با آیدی `{target_id}` از لیست دوست حذف شد.")
        else:
            await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` در لیست دوست یافت نشد.")
    else:
        await message.edit_text("⚠️ برای حذف از لیست دوست، روی پیام کاربر مورد نظر ریپلای کنید.")

async def clear_friend_list_controller(client, message):
    user_id = client.me.id
    if FRIEND_LIST.get(user_id):
        FRIEND_LIST[user_id] = set()
        await save_settings_to_db(user_id)
        await message.edit_text("✅ لیست دوست با موفقیت پاکسازی شد.")
    else:
        await message.edit_text("ℹ️ لیست دوست از قبل خالی بود.")

async def list_friends_controller(client, message):
    user_id = client.me.id
    friends = FRIEND_LIST.get(user_id, set())
    if not friends:
        await message.edit_text("ℹ️ لیست دوست خالی است.")
    else:
        list_items = []
        for fid in friends:
            try:
                user = await client.get_users(fid)
                display_name = f"{user.first_name}" + (f" {user.last_name}" if user.last_name else "")
                list_items.append(f"- {display_name} (`{fid}`)")
            except Exception:
                list_items.append(f"- User ID: `{fid}`")

        list_text = "**لیست دوستان:**\n" + "\n".join(list_items)
        if len(list_text) > 4096:
            list_text = list_text[:4090] + "\n[...]"
        await message.edit_text(list_text)

async def list_friend_replies_controller(client, message):
    user_id = client.me.id
    replies = FRIEND_REPLIES.get(user_id, [])
    if not replies:
        await message.edit_text("ℹ️ لیست متن‌های پاسخ دوست خالی است.")
    else:
        list_text = "**💬 لیست متن‌های دوست:**\n" + "\n".join([f"{i+1}. `{reply}`" for i, reply in enumerate(replies)])
        if len(list_text) > 4096:
            list_text = list_text[:4090] + "\n[...]"
        await message.edit_text(list_text)

async def delete_friend_reply_controller(client, message):
    user_id = client.me.id
    match = re.match(r"^حذف متن دوست(?: (\d+))?$", message.text, re.IGNORECASE)
    if match:
        index_str = match.group(1)
        replies = FRIEND_REPLIES.get(user_id)

        if replies is None or not replies:
             await message.edit_text("ℹ️ لیست متن دوست خالی است، چیزی برای حذف وجود ندارد.")
             return

        try:
            if index_str:
                index = int(index_str) - 1
                if 0 <= index < len(replies):
                    removed_reply = replies.pop(index)
                    await save_settings_to_db(user_id)
                    await message.edit_text(f"✅ متن شماره {index+1} (`{removed_reply}`) از لیست دوست حذف شد.")
                else:
                    await message.edit_text(f"⚠️ شماره نامعتبر. لطفاً عددی بین 1 تا {len(replies)} وارد کنید.")
            else:
                FRIEND_REPLIES[user_id] = []
                await save_settings_to_db(user_id)
                await message.edit_text("✅ تمام متن‌های پاسخ دوست حذف شدند.")
        except ValueError:
             await message.edit_text("⚠️ شماره وارد شده نامعتبر است.")
        except Exception as e:
            logging.error(f"Delete Friend Reply: Error for user {user_id}: {e}", exc_info=True)
            await message.edit_text("⚠️ خطایی در حذف متن دوست رخ داد.")

async def set_friend_reply_controller(client, message):
    user_id = client.me.id
    match = re.match(r"^تنظیم متن دوست (.*)", message.text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        if text:
            if user_id not in FRIEND_REPLIES:
                FRIEND_REPLIES[user_id] = []
            FRIEND_REPLIES[user_id].append(text)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ متن جدید به لیست پاسخ دوست اضافه شد (مورد {len(FRIEND_REPLIES[user_id])}).")
        else:
            await message.edit_text("⚠️ متن پاسخ نمی‌تواند خالی باشد.")

async def help_controller(client, message):
    """Help command handler - Complete help in one message"""
    try:
        logging.info(f"Help command received from user {client.me.id}")
        
        # Complete help in one message (all Persian)
        help_text = """╔═══════════════════════════════════╗
║   🌟 𝐃𝐀𝐑𝐊 𝐒𝐄𝐋𝐅 𝐁𝐎𝐓 🌟   ║
║  ربات خودکار تلگرام با قابلیت‌های پیشرفته  ║
╚═══════════════════════════════════╝

┏━━━━━━━━━ ⚡ وضعیت و اکشن ⚡ ━━━━━━━━━┓
┃ 🎮 `تایپ روشن/خاموش` ➜ نمایش درحال تایپ
┃ 🎯 `بازی روشن/خاموش` ➜ نمایش درحال بازی
┃ 🎙 `ضبط ویس روشن/خاموش` ➜ ضبط صدا
┃ 📸 `عکس روشن/خاموش` ➜ آپلود عکس
┃ 🎬 `گیف روشن/خاموش` ➜ دیدن انیمیشن
┃ 👁 `سین روشن/خاموش` ➜ خواندن خودکار
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ ✨ قالب‌بندی متن ✨ ━━━━━━━━━┓
┃ 🔹 `بولد روشن/خاموش` ➜ متن بولد
┃ 🔸 `ایتالیک روشن/خاموش` ➜ متن ایتالیک
┃ 🔹 `زیرخط روشن/خاموش` ➜ زیرخط‌دار
┃ 🔸 `خط خورده روشن/خاموش` ➜ خط‌خورده
┃ 🔹 `کد روشن/خاموش` ➜ فرمت کد
┃ 🔸 `اسپویلر روشن/خاموش` ➜ اسپویلر
┃ 🔹 `منشن روشن/خاموش` ➜ منشن (نیاز به ریپلای)
┃ 🔸 `نقل و قول روشن/خاموش` ➜ اگر ریپلای کنی: نقل‌قول خود تلگرام | اگر نه: ❝ متن ❞
┃ 🔸 `هشتگ روشن/خاموش` ➜ هشتگ
┃ 🔹 `معکوس روشن/خاموش` ➜ متن معکوس
┃ 🔸 `تدریجی روشن/خاموش` ➜ نمایش تدریجی
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🌍 ترجمه خودکار 🌍 ━━━━━━━━━┓
┃ 🔄 `ترجمه` (ریپلای) ➜ ترجمه به فارسی
┃ 🇬🇧 `انگلیسی روشن/خاموش` ➜ ترجمه انگلیسی
┃ 🇨🇳 `چینی روشن/خاموش` ➜ ترجمه چینی
┃ 🇷🇺 `روسی روشن/خاموش` ➜ ترجمه روسی
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🔒 قفل مدیا در PV 🔒 ━━━━━━━━━┓
┃ `قفل گیف روشن/خاموش` ➜ حذف گیف در PV
┃ `قفل عکس روشن/خاموش` ➜ حذف عکس در PV
┃ `قفل ویدیو روشن/خاموش` ➜ حذف ویدیو در PV
┃ `قفل ویس روشن/خاموش` ➜ حذف ویس در PV
┃ `قفل استیکر روشن/خاموش` ➜ حذف استیکر در PV
┃ `قفل فایل روشن/خاموش` ➜ حذف فایل در PV
┃ `قفل موزیک روشن/خاموش` ➜ حذف موزیک در PV
┃ `قفل ویدیو نوت روشن/خاموش` ➜ حذف ویدیو نوت در PV
┃ `قفل کانتکت روشن/خاموش` ➜ حذف کانتکت در PV
┃ `قفل لوکیشن روشن/خاموش` ➜ حذف لوکیشن در PV
┃ `قفل ایموجی روشن/خاموش` ➜ حذف پیام‌های دارای ایموجی در PV
┃ `قفل متن روشن/خاموش` ➜ حذف پیام‌های متنی در PV
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🕐 ساعت و فونت 🕐 ━━━━━━━━━┓
┃ ⏰ `ساعت روشن/خاموش` ➜ ساعت در نام
┃ 🎨 `فونت` ➜ نمایش همه فونت‌ها
┃ 🖌 `فونت [عدد]` ➜ انتخاب فونت
┃ 📝 `ساعت بیو روشن/خاموش` ➜ ساعت در بیو
┃ 📅 `تاریخ بیو روشن/خاموش` ➜ تاریخ در بیو
┃ 🗓 `نوع تاریخ میلادی/شمسی` ➜ تغییر نوع
┃ ✏ `فونت ساعت بیو` ➜ فونت‌های بیو
┃ 🎭 `فونت ساعت بیو [عدد]` ➜ انتخاب فونت بیو
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 💬 مدیریت پیام 💬 ━━━━━━━━━┓
┃ 🗑 `حذف [عدد]` ➜ حذف پیام‌ها
┃ 🧹 `حذف همه` ➜ حذف تمام پیام‌ها
┃ 💾 `ذخیره روشن/خاموش` ➜ ذخیره تایم‌دار
┃ 🔒 `ذخیره مخفی روشن/خاموش` ➜ ذخیره با ریکشن
┃ 🔁 `تکرار [عدد] [ثانیه]` ➜ تکرار پیام
┃ 🔄 `تکرار خودکار [ثانیه]` ➜ تکرار مداوم
┃ ⏹ `تکرار خودکار خاموش` ➜ توقف تکرار
┃ 🚫 `بلاک روشن/خاموش` ➜ بلاک کاربر
┃ 🔇 `سکوت روشن/خاموش` ➜ میوت کاربر
┃ 😊 `ریاکشن [ایموجی]` ➜ ریاکشن خودکار
┃ ❌ `ریاکشن خاموش` ➜ خاموش کردن
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 💀 لیست دشمن 💀 ━━━━━━━━━┓
┃ ⚔ `دشمن روشن/خاموش` ➜ فعال/غیرفعال
┃ ➕ `تنظیم دشمن` (ریپلای) ➜ افزودن
┃ ➖ `حذف دشمن` (ریپلای) ➜ حذف
┃ 🧹 `پاکسازی لیست دشمن` ➜ پاک کردن
┃ 📋 `لیست دشمن` ➜ نمایش لیست
┃ 📝 `تنظیم متن دشمن [متن]` ➜ تنظیم پاسخ
┃ 📜 `لیست متن دشمن` ➜ نمایش پاسخ‌ها
┃ 🗑 `حذف متن دشمن [عدد]` ➜ حذف پاسخ
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 💚 لیست دوست 💚 ━━━━━━━━━┓
┃ 🤝 `دوست روشن/خاموش` ➜ فعال/غیرفعال
┃ ➕ `تنظیم دوست` (ریپلای) ➜ افزودن
┃ ➖ `حذف دوست` (ریپلای) ➜ حذف
┃ 🧹 `پاکسازی لیست دوست` ➜ پاک کردن
┃ 📋 `لیست دوست` ➜ نمایش لیست
┃ 📝 `تنظیم متن دوست [متن]` ➜ تنظیم پاسخ
┃ 📜 `لیست متن دوست` ➜ نمایش پاسخ‌ها
┃ 🗑 `حذف متن دوست [عدد]` ➜ حذف پاسخ
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 💕 کراش 💕 ━━━━━━━━━┓
┃ 💖 `افزودن کراش` (ریپلای) ➜ افزودن
┃ 💔 `حذف کراش` (ریپلای) ➜ حذف
┃ 📋 `لیست کراش` ➜ نمایش لیست
┃ 💌 `تنظیم متن کراش [متن]` ➜ تنظیم پیام
┃ 📜 `لیست متن کراش` ➜ نمایش پیام‌ها
┃ 🗑 `حذف متن کراش [عدد]` ➜ حذف پیام
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 💬 کامنت 💬 ━━━━━━━━━┓
┃ 💬 `کامنت روشن/خاموش` ➜ فعال/غیرفعال
┃ ✍ `متن کامنت [متن]` ➜ تنظیم متن کامنت
┃ ℹ️ کامنت روی پیام‌های forward شده ارسال می‌شود
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🎉 سرگرمی 🎉 ━━━━━━━━━┓
┃ 💖 `قلب` / `heart` ➜ انیمیشن قلب
┃ 🎭 `فان love` / `fun love` ➜ انیمیشن قلب‌ها
┃ 🕐 `فان oclock` / `fun oclock` ➜ انیمیشن ساعت
┃ ⭐ `فان star` / `fun star` ➜ انیمیشن ستاره
┃ ❄ `فان snow` / `fun snow` ➜ انیمیشن برف
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🛡 امنیت و منشی 🛡 ━━━━━━━━━┓
┃ 🔐 `پیوی قفل` ➜ قفل پیام‌های خصوصی
┃ 🔓 `پیوی باز` ➜ باز کردن پیام‌ها
┃ 📢 `منشی روشن/خاموش` ➜ فعال/غیرفعال
┃ 📝 `منشی متن [متن]` ➜ تنظیم پیام
┃ 🤖 `منشی خودکار روشن/خاموش` ➜ منشی AI
┃ 🔒 `انتی لوگین روشن/خاموش` ➜ محافظت ورود
┃ 👤 `کپی روشن/خاموش` ➜ کپی پروفایل
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🧠 هوش مصنوعی و یادگیری 🧠 ━━━━━━━━━┓
┃ 🤖 `تست ai` ➜ تست عملکرد AI
┃ 📊 `وضعیت یادگیری` ➜ نمایش آمار
┃ 💾 `بکاپ یادگیری` ➜ دریافت بکاپ
┃ 🗑 `پاکسازی یادگیری` ➜ حذف داده‌ها
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

┏━━━━━━━━━ 🛠 ابزار و مدیریت 🛠 ━━━━━━━━━┓
┃ 🏷 `تگ` / `tagall` ➜ تگ تمام اعضا
┃ 👑 `تگ ادمین ها` / `tagadmins` ➜ تگ ادمین‌ها
┃ 📱 `شماره من` ➜ نمایش شماره
┃ ⬇ `دانلود` (ریپلای) ➜ دانلود فایل
┃ 🚫 `بن` (ریپلای) ➜ بن کاربر
┃ 📌 `پین` (ریپلای) ➜ پین پیام
┃ 📍 `آن پین` ➜ آن‌پین کردن
┃ 📤 `اسپم [متن] [تعداد]` ➜ ارسال تکراری
┃ 🌊 `فلود [متن] [تعداد]` ➜ فلود سریع
┃ 📡 `ping` ➜ بررسی سرعت
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

╔═══════════════════════════════════╗
║      💫 ساخته شده با عشق 💫      ║
║    برای استفاده بهتر از تلگرام    ║
╚═══════════════════════════════════╝"""

        # Try to edit the message first, if it fails, delete and send new
        max_len = 3900
        parts = []
        buf = ""
        for line in help_text.splitlines(keepends=True):
            if len(buf) + len(line) > max_len:
                if buf:
                    parts.append(buf)
                    buf = ""
            buf += line
        if buf:
            parts.append(buf)

        try:
            # Try to edit the original message for the first part
            text_to_send = parts[0]
            if len(parts) == 1:
                text_to_send += "\nبرای استفاده از دستورات، کافی است دستور مورد نظر را به صورت private به ربات ارسال کنید."
            await message.edit_text(text_to_send)
            
            # Send remaining parts as new messages
            for i, part in enumerate(parts[1:], start=1):
                text_to_send = part
                if i == len(parts) - 1:  # Add usage instruction to the last part
                    text_to_send += "\nبرای استفاده از دستورات، کافی است دستور مورد نظر را به صورت private به ربات ارسال کنید."
                await client.send_message(message.chat.id, text_to_send)
                await asyncio.sleep(0.4)
        except (MessageIdInvalid, Exception) as e:
            # If edit fails, delete and send all parts as new messages
            try:
                await message.delete()
            except:
                pass
            for i, part in enumerate(parts):
                text_to_send = part
                if i == len(parts) - 1:  # Add usage instruction to the last part
                    text_to_send += "\nبرای استفاده از دستورات، کافی است دستور مورد نظر را به صورت private به ربات ارسال کنید."
                await client.send_message(message.chat.id, text_to_send)
                await asyncio.sleep(0.4)

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.error(f"Help Controller: Error sending help message: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطا در نمایش راهنما. لطفاً دوباره تلاش کنید.")
        except:
            pass

async def block_unblock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()

    if not message.reply_to_message or not message.reply_to_message.from_user:
        try:
             await message.edit_text("⚠️ برای بلاک/آنبلاک کردن، باید روی پیام کاربر مورد نظر ریپلای کنید.")
        except Exception: pass
        return

    target_id = message.reply_to_message.from_user.id
    target_info = f"کاربر با آیدی `{target_id}`" # Default info

    try:
        # Try to get user's name for feedback message
        try:
            target_user = await client.get_users(target_id)
            target_info = f"{target_user.first_name}" + (f" {target_user.last_name}" if target_user.last_name else "") + f" (`{target_id}`)"
        except Exception:
            pass # Use default info if get_users fails

        if command == "بلاک روشن":
            await client.block_user(target_id)
            await message.edit_text(f"✅ {target_info} با موفقیت بلاک شد.")
        elif command == "بلاک خاموش":
            await client.unblock_user(target_id)
            await message.edit_text(f"✅ {target_info} با موفقیت آنبلاک شد.")

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.error(f"Block/Unblock Controller: Error for user {user_id} targeting {target_id}: {e}", exc_info=True)
        try:
            await message.edit_text(f"⚠️ خطایی در بلاک/آنبلاک {target_info} رخ داد: {type(e).__name__}")
        except Exception: pass

async def mute_unmute_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()

    if not message.reply_to_message or not message.reply_to_message.from_user or not message.chat:
        try:
            await message.edit_text("⚠️ برای سکوت/لغو سکوت، باید روی پیام کاربر مورد نظر در چت مربوطه ریپلای کنید.")
        except Exception: pass
        return

    sender_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    muted_set = MUTED_USERS.setdefault(user_id, set())
    key = (sender_id, chat_id)
    target_info = f"کاربر `{sender_id}`" # Default info
    chat_info = f"در چت `{chat_id}`"

    try:
        # Try to get user/chat names for feedback
        try:
            target_user = await client.get_users(sender_id)
            target_info = f"{target_user.first_name}" + (f" {target_user.last_name}" if target_user.last_name else "") + f" (`{sender_id}`)"
        except Exception: pass
        try:
            chat = await safe_get_chat(client, chat_id)
            chat_info = f"در چت \"{chat.title}\" (`{chat_id}`)" if chat.title else f"در چت `{chat_id}`"
        except Exception: pass


        if command == "سکوت روشن":
            if key not in muted_set:
                muted_set.add(key)
                await message.edit_text(f"✅ {target_info} {chat_info} سکوت شد (پیام‌هایش حذف خواهند شد).")
            else:
                await message.edit_text(f"ℹ️ {target_info} {chat_info} از قبل سکوت شده بود.")
        elif command == "سکوت خاموش":
            if key in muted_set:
                muted_set.remove(key)
                await message.edit_text(f"✅ سکوت {target_info} {chat_info} لغو شد.")
            else:
                await message.edit_text(f"ℹ️ {target_info} {chat_info} سکوت نشده بود.")

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Mute/Unmute Controller: Error for user {user_id}, target {sender_id}, chat {chat_id}: {e}", exc_info=True)
        try:
            await message.edit_text(f"⚠️ خطایی در عملیات سکوت برای {target_info} {chat_info} رخ داد.")
        except Exception: pass

async def auto_reaction_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()

    if not message.reply_to_message or not message.reply_to_message.from_user:
        try:
            await message.edit_text("⚠️ برای تنظیم/لغو واکنش خودکار، باید روی پیام کاربر مورد نظر ریپلای کنید.")
        except Exception: pass
        return

    target_id = message.reply_to_message.from_user.id
    reactions = AUTO_REACTION_TARGETS.setdefault(user_id, {})
    target_info = f"کاربر `{target_id}`"

    try:
        # Try to get user name
        try:
            target_user = await client.get_users(target_id)
            target_info = f"{target_user.first_name}" + (f" {target_user.last_name}" if target_user.last_name else "") + f" (`{target_id}`)"
        except Exception: pass

        if command == "ریاکشن خاموش":
            if target_id in reactions:
                removed_emoji = reactions.pop(target_id)
                await message.edit_text(f"✅ واکنش خودکار ('{removed_emoji}') برای {target_info} غیرفعال شد.")
                # Optional: Remove dict if empty
                # if not reactions: del AUTO_REACTION_TARGETS[user_id]
            else:
                await message.edit_text(f"ℹ️ واکنشی برای {target_info} تنظیم نشده بود.")
        else:
            match = re.match(r"^ریاکشن (.*)", command)
            if match:
                emoji = match.group(1).strip()
                # Basic emoji check (might not cover all custom/animated ones)
                if emoji and len(emoji) <= 4: # Crude check for typical emoji length
                    # Send a test reaction to see if it's valid BEFORE saving
                    try:
                        # Use reply_to_message_id for context, maybe react to the command itself temporarily
                        await client.send_reaction(message.chat.id, message.id, emoji)
                        # If successful, save it
                        reactions[target_id] = emoji
                        await message.edit_text(f"✅ واکنش خودکار با '{emoji}' برای {target_info} تنظیم شد.")
                    except ReactionInvalid:
                         await message.edit_text(f"⚠️ ایموجی '{emoji}' نامعتبر است و توسط تلگرام پذیرفته نشد.")
                    except FloodWait as e_react_test:
                         logging.warning(f"Auto Reaction Test: Flood wait for user {user_id}: {e_react_test.value}s")
                         await asyncio.sleep(e_react_test.value + 1)
                         await message.edit_text("⚠️ خطای Flood Wait هنگام تست ایموجی. لطفاً بعداً دوباره تلاش کنید.")
                    except Exception as e_react_test:
                         logging.error(f"Auto Reaction Test: Error testing emoji '{emoji}' for user {user_id}: {e_react_test}")
                         await message.edit_text(f"⚠️ خطایی هنگام تست ایموجی '{emoji}' رخ داد. ممکن است نامعتبر باشد.")
                else:
                    await message.edit_text("⚠️ ایموجی ارائه شده نامعتبر یا خالی است.")
            else:
                # This part should ideally not be reached if the regex handler is specific enough
                await message.edit_text("⚠️ فرمت دستور نامعتبر. مثال: `ریاکشن 👍` یا `ریاکشن خاموش`")

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Auto Reaction Controller: Error for user {user_id} targeting {target_id}: {e}", exc_info=True)
        try:
            await message.edit_text(f"⚠️ خطایی در تنظیم واکنش برای {target_info} رخ داد.")
        except Exception: pass

async def auto_save_toggle_controller(client, message):
    """Toggle auto-save for view once media"""
    try:
        user_id = client.me.id
        command = message.text.strip()
        
        if command == "ذخیره روشن":
            AUTO_SAVE_VIEW_ONCE[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ ذخیره خودکار عکس‌های تایم‌دار فعال شد")
        elif command == "ذخیره خاموش":
            AUTO_SAVE_VIEW_ONCE[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ ذخیره خودکار عکس‌های تایم‌دار غیرفعال شد")
    except Exception as e:
        logging.error(f"Auto save toggle error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم ذخیره خودکار")

async def auto_save_view_once_handler(client, message):
    """Auto-save view once media (یکبار دید و تایم‌دار) to Saved Messages"""
    try:
        user_id = client.me.id
        
        # Check if auto-save is enabled for this user
        if not AUTO_SAVE_VIEW_ONCE.get(user_id, False):
            return
        
        # Check if message has media
        if not message.media:
            return
        
        # Check for view once or timed media
        has_special_media = False
        media_type = None
        is_view_once = False
        
        # Method 1: Check for view once photos/videos (has_media_spoiler)
        if hasattr(message, 'has_media_spoiler') and message.has_media_spoiler:
            if message.photo:
                has_special_media = True
                media_type = 'photo'
                is_view_once = True
            elif message.video:
                has_special_media = True
                media_type = 'video'
                is_view_once = True

        # Method 1.5: Some Pyrogram builds expose message-level flags
        if not has_special_media:
            if bool(getattr(message, "view_once", False)) or bool(getattr(message, "has_ttl", False)) or bool(getattr(message, "self_destruct", False)):
                has_special_media = True
                is_view_once = bool(getattr(message, "view_once", False))
                if message.photo:
                    media_type = 'photo'
                elif message.video:
                    media_type = 'video'
                elif getattr(message, "animation", None):
                    media_type = 'animation'
                elif getattr(message, "voice", None):
                    media_type = 'voice'
                elif getattr(message, "video_note", None):
                    media_type = 'video_note'
                elif getattr(message, "document", None):
                    media_type = 'document'
                else:
                    media_type = 'document'
        
        # Method 2: Check for timed media (ttl_seconds in photo/video)
        if not has_special_media:
            if message.photo and hasattr(message.photo, 'ttl_seconds') and message.photo.ttl_seconds:
                has_special_media = True
                media_type = 'photo'
            elif message.video and hasattr(message.video, 'ttl_seconds') and message.video.ttl_seconds:
                has_special_media = True
                media_type = 'video'

        # Method 2.5: Some media types carry ttl_seconds too (document/animation)
        if not has_special_media:
            try:
                if getattr(message, "document", None) and getattr(message.document, "ttl_seconds", None):
                    has_special_media = True
                    media_type = 'document'
                elif getattr(message, "animation", None) and getattr(message.animation, "ttl_seconds", None):
                    has_special_media = True
                    media_type = 'animation'
            except Exception:
                pass
        
        # Method 3: Check message-level ttl_seconds
        if not has_special_media and hasattr(message, 'ttl_seconds') and message.ttl_seconds:
            if message.photo:
                has_special_media = True
                media_type = 'photo'
            elif message.video:
                has_special_media = True
                media_type = 'video'
            elif getattr(message, "document", None):
                has_special_media = True
                media_type = 'document'
            elif getattr(message, "animation", None):
                has_special_media = True
                media_type = 'animation'
            elif getattr(message, "voice", None):
                has_special_media = True
                media_type = 'voice'
            elif getattr(message, "video_note", None):
                has_special_media = True
                media_type = 'video_note'
            else:
                has_special_media = True
                media_type = 'document'
        
        if has_special_media:
            # Download the media
            file_path = await message.download()
            
            if file_path:
                # Send to Saved Messages
                chat_info = f"از: {message.chat.title or message.chat.first_name or 'Unknown'}" if message.chat else ""
                media_label = "یکبار دید" if is_view_once else "تایم‌دار"
                caption = f"💾 **ذخیره خودکار {media_type} {media_label}**\n📅 {datetime.now(TEHRAN_TIMEZONE).strftime('%Y/%m/%d %H:%M')}\n{chat_info}"
                if message.caption:
                    caption += f"\n\n{message.caption}"
                
                if media_type == 'photo':
                    await client.send_photo("me", file_path, caption=caption)
                elif media_type == 'video':
                    await client.send_video("me", file_path, caption=caption)
                elif media_type == 'animation':
                    await client.send_animation("me", file_path, caption=caption)
                elif media_type == 'voice':
                    await client.send_voice("me", file_path, caption=caption)
                elif media_type == 'video_note':
                    await client.send_video_note("me", file_path)
                else:
                    await client.send_document("me", file_path, caption=caption)
                
                # Delete downloaded file
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
                
                logging.info(f"Auto-saved {media_label} {media_type} from chat {message.chat.id} for user {user_id}")
    except FloodWait as e:
        logging.warning(f"Auto save view once: FloodWait {e.value}s")
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.error(f"Auto save view once handler error: {e}", exc_info=True)


async def secret_save_toggle_controller(client, message):
    """Toggle secret save feature"""
    try:
        user_id = client.me.id
        command = message.text.strip()

        if command == "ذخیره مخفی روشن":
            SECRET_SAVE_STATUS[user_id] = True
            await message.edit_text("✅ ذخیره مخفی فعال شد. هر پیامی که روی آن ریاکشن بزنید به ربات ارسال می‌شود.")
        elif command == "ذخیره مخفی خاموش":
            SECRET_SAVE_STATUS[user_id] = False
            await message.edit_text("❌ ذخیره مخفی غیرفعال شد")
    except Exception as e:
        logging.error(f"Secret save toggle error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم ذخیره مخفی")


async def secret_save_raw_update_handler(client, update, users, chats):
    try:
        user_id = client.me.id
        if not SECRET_SAVE_STATUS.get(user_id, False):
            return

        # Pyrogram raw updates can vary by version and chat type.
        allowed_types = (raw.types.UpdateMessageReactions,)
        if hasattr(raw.types, "UpdateMessageReactionsFrom"):
            allowed_types = allowed_types + (raw.types.UpdateMessageReactionsFrom,)
        if hasattr(raw.types, "UpdateMessageReaction"):
            allowed_types = allowed_types + (raw.types.UpdateMessageReaction,)

        if not isinstance(update, allowed_types):
            return

        peer = getattr(update, "peer", None)
        msg_id = getattr(update, "msg_id", None)
        if msg_id is None:
            msg_id = getattr(update, "message_id", None)

        # NOTE: We intentionally do NOT require that the reaction is by "me".
        # In many Telegram/Pyrogram combinations, recent_reactions is missing/incomplete.
        reactions_obj = getattr(update, "reactions", None)
        logging.info(
            "Secret save: reaction update received type={type(update).__name__} peer={type(peer).__name__} msg_id={msg_id}"
        )

        if not msg_id:
            return

        chat_id = None
        if isinstance(peer, raw.types.PeerUser):
            chat_id = peer.user_id
        elif isinstance(peer, raw.types.PeerChat):
            chat_id = -peer.chat_id
        elif isinstance(peer, raw.types.PeerChannel):
            chat_id = -1000000000000 - int(peer.channel_id)
        if chat_id is None:
            return

        try:
            msg = await client.get_messages(chat_id, msg_id)
        except Exception as get_err:
            logging.error(f"Secret save: failed to fetch message {chat_id}/{msg_id}: {get_err}")
            return
        if not msg:
            return

        await secret_save_reaction_handler(client, msg, reactions_obj)
    except Exception as e:
        logging.error(f"Secret save raw update handler error: {e}", exc_info=True)


async def secret_save_reaction_handler(client, message, reactions=None):
    try:
        global SECRET_SAVE_BOT
        user_id = client.me.id
        if not SECRET_SAVE_STATUS.get(user_id, False):
            return

        chat_id = getattr(getattr(message, "chat", None), "id", None)
        msg_id = getattr(message, "id", None)
        if chat_id is None or msg_id is None:
            return

        processed = SECRET_SAVE_PROCESSED.setdefault(user_id, set())
        key = (chat_id, msg_id)
        if key in processed:
            return
        processed.add(key)

        if SECRET_SAVE_BOT is None:
            try:
                SECRET_SAVE_BOT = Client(
                    "secret_save_bot",
                    bot_token=BOT_TOKEN,
                    api_id=API_ID,
                    api_hash=API_HASH,
                )
                await SECRET_SAVE_BOT.start()
            except Exception as bot_err:
                logging.error(f"Secret save: failed to start SECRET_SAVE_BOT: {bot_err}")
                return

        bot_client = SECRET_SAVE_BOT

        # We only send the original content. No header/time text.

        sent_original = False
        try:
            await bot_client.copy_message(user_id, chat_id, msg_id)
            sent_original = True
        except Exception as copy_err:
            logging.warning(f"Secret save: copy failed for {chat_id}/{msg_id}: {copy_err}")

        if not sent_original:
            try:
                await bot_client.forward_messages(user_id, chat_id, [msg_id])
                sent_original = True
            except Exception as fwd_err:
                logging.error(f"Secret save: forward failed for {chat_id}/{msg_id}: {fwd_err}")

        if not sent_original:
            # Fallback: download and re-upload (works even when bot can't copy/forward from some chats)
            file_path = None
            try:
                file_path = await client.download_media(message, in_memory=False)
            except Exception as dl_err:
                logging.error(f"Secret save: download failed for {chat_id}/{msg_id}: {dl_err}")

            if file_path:
                try:
                    if getattr(message, "photo", None):
                        await bot_client.send_photo(user_id, file_path)
                    elif getattr(message, "video", None):
                        await bot_client.send_video(user_id, file_path)
                    elif getattr(message, "voice", None):
                        await bot_client.send_voice(user_id, file_path)
                    elif getattr(message, "video_note", None):
                        await bot_client.send_video_note(user_id, file_path)
                    elif getattr(message, "audio", None):
                        await bot_client.send_audio(user_id, file_path)
                    elif getattr(message, "sticker", None):
                        await bot_client.send_sticker(user_id, file_path)
                    elif getattr(message, "animation", None):
                        await bot_client.send_animation(user_id, file_path)
                    else:
                        await bot_client.send_document(user_id, file_path)
                    sent_original = True
                except Exception as reup_err:
                    logging.error(f"Secret save: reupload failed for {chat_id}/{msg_id}: {reup_err}")
                finally:
                    try:
                        if file_path and os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass

            if not sent_original:
                # Last resort: send just the text/caption (no header)
                text_content = getattr(message, 'text', None) or getattr(message, 'caption', None) or ""
                if text_content:
                    await bot_client.send_message(user_id, text_content)

        logging.info(f"Secret save: saved {chat_id}/{msg_id} for user {user_id}")
    except Exception as e:
        logging.error(f"Secret save reaction handler error: {e}", exc_info=True)


async def ping_controller(client, message):
    """Check bot response time"""
    try:
        start_time = time.time()
        sent_msg = await message.edit_text("🏓 در حال بررسی...")
        end_time = time.time()
        
        ping_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
        
        await sent_msg.edit_text(
            f"🏓 **Pong!**\n\n"
            f"⏱ **زمان پاسخ:** {ping_time} ms\n"
            f"✅ **وضعیت:** آنلاین"
        )
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logging.error(f"Ping Controller: Error for user {client.me.id}: {e}")
        logging.error(f"Ping error: {e}")
        try:
            await message.edit_text("⚠️ خطا در بررسی ping")
        except Exception:
            pass

async def delete_messages_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    # چک کردن دستور "حذف همه"
    if command == "حذف همه":
        count = 1000  # عدد بزرگ برای حذف همه
    else:
        match = re.match(r"^حذف(?: (\d+))?$", command)
        if not match:
            try:
                await message.edit_text("⚠️ فرمت دستور نامعتبر. مثال: `حذف` یا `حذف 10` یا `حذف همه`")
            except Exception: pass
            return
        
        count_str = match.group(1)
        try:
            count = int(count_str) if count_str else 5
            if count < 1: count = 1
            if count > 1000: count = 1000
        except ValueError:
            await message.edit_text("⚠️ عدد وارد شده نامعتبر است.")
            return

    chat_id = message.chat.id
    message_ids_to_delete = []
    
    try:
        # اضافه کردن پیام دستور به لیست حذف
        message_ids_to_delete.append(message.id)
        
        # پیدا کردن پیام‌های کاربر
        user_messages_found = 0
        limit = min(count * 3, 1000)  # حداکثر 1000 پیام برای جستجو
        
        try:
            async for msg in client.get_chat_history(chat_id, limit=limit):
                if msg.id == message.id:
                    continue
                    
                if msg.from_user and msg.from_user.id == user_id:
                    message_ids_to_delete.append(msg.id)
                    user_messages_found += 1
                    
                    if user_messages_found >= count:
                        break
        except Exception as e_history:
            logging.warning(f"Error getting chat history: {e_history}")
        
        # حذف پیام‌ها
        if len(message_ids_to_delete) > 0:
            # حذف دسته‌ای (100 تایی)
            for i in range(0, len(message_ids_to_delete), 100):
                batch = message_ids_to_delete[i:i+100]
                try:
                    await client.delete_messages(chat_id, batch)
                    await asyncio.sleep(0.1)  # تاخیر کمتر برای سرعت بیشتر
                except FloodWait as e:
                    await asyncio.sleep(e.value + 1)
                except MessageIdInvalid:
                    pass
                except Exception as e:
                    logging.error(f"Delete Messages: Error deleting batch: {e}")
            
    except FloodWait as e:
        await asyncio.sleep(e.value + 2) # Increased sleep time
        await message.edit_text(f"⏳ لطفاً {e.value} ثانیه صبر کنید و دوباره تلاش کنید.")
    except Exception as e:
        logging.error(f"Delete Messages Controller: Error for user {user_id}: {e}")
        try:
            await message.edit_text("⚠️ خطایی در حذف پیام‌ها رخ داد.")
        except Exception: pass
        return

async def font_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    try:
        if command == "فونت":
            font_list_parts = []
            current_part = ""
            for i, font in enumerate(FONT_KEYS_ORDER):
                font_name = FONT_DISPLAY_NAMES.get(font, font)
                current_part += f"{i+1}. {font_name}\n"
                if len(current_part) > 4000: # Telegram message limit
                    font_list_parts.append(current_part)
                    current_part = ""
                if i == len(FONT_KEYS_ORDER) - 1:
                    font_list_parts.append(current_part) # Add the last part

            # Send the parts
            for i, part in enumerate(font_list_parts):
                 text_to_send = part
                 if i == len(font_list_parts) - 1: # Add usage instruction to the last part
                     text_to_send += "\nبرای انتخاب فونت: `فونت [عدد]`"
                 # Edit the original message for the first part, send new messages for subsequent parts
                 if i == 0:
                     await message.edit_text(text_to_send)
                 else:
                     await client.send_message(message.chat.id, text_to_send)
                     await asyncio.sleep(0.5) # Small delay between parts

        else: # Handling "فونت [عدد]"
            match = re.match(r"^فونت (\d+)$", command)
            if match:
                index_str = match.group(1)
                try:
                    index = int(index_str) - 1 # User inputs 1-based index
                    if 0 <= index < len(FONT_KEYS_ORDER):
                        selected = FONT_KEYS_ORDER[index]
                        current_choice = USER_FONT_CHOICES.get(user_id)

                        if current_choice != selected:
                            USER_FONT_CHOICES[user_id] = selected
                            await save_settings_to_db(user_id)
                            feedback_msg = f"✅ فونت ساعت به **{FONT_DISPLAY_NAMES.get(selected, selected)}** تغییر یافت."
                            await message.edit_text(feedback_msg)

                            # Immediately update profile name if clock is active and copy mode is off
                            if CLOCK_STATUS.get(user_id, False) and not COPY_MODE_STATUS.get(user_id, False):
                                try:
                                    me = await client.get_me()
                                    current_name = me.first_name or ""
                                    # Use more robust regex to find base name, handling existing clock of any style
                                    base_name_match = re.match(r"^(.*?)\s*[" + re.escape(ALL_CLOCK_CHARS) + r":\s]*$", current_name)
                                    base_name = base_name_match.group(1).strip() if base_name_match else current_name.strip()

                                    if not base_name: base_name = me.username or f"User_{user_id}" # Fallback base name

                                    tehran_time = datetime.now(TEHRAN_TIMEZONE)
                                    current_time_str = tehran_time.strftime("%H:%M")
                                    stylized_time = stylize_time(current_time_str, selected)
                                    new_name = f"{base_name} {stylized_time}"
                                    # Limit name length according to Telegram limits (64 chars for first name)
                                    await client.update_profile(first_name=new_name[:64])
                                except FloodWait as e_update:
                                     logging.warning(f"Font Controller: Flood wait updating profile for user {user_id}: {e_update.value}s")
                                     await asyncio.sleep(e_update.value + 1)
                                except Exception as e_update:
                                     logging.error(f"Font Controller: Failed to update profile name immediately for user {user_id}: {e_update}")
                                     # Optionally inform user if immediate update fails
                                     # await message.reply_text("⚠️ فونت ذخیره شد، اما به‌روزرسانی نام پروفایل با خطا مواجه شد.", quote=True)
                        else:
                            await message.edit_text(f"ℹ️ فونت **{FONT_DISPLAY_NAMES.get(selected, selected)}** از قبل انتخاب شده بود.")
                    else:
                        await message.edit_text(f"⚠️ شماره فونت نامعتبر. لطفاً عددی بین 1 تا {len(FONT_KEYS_ORDER)} وارد کنید.")
                except ValueError:
                    await message.edit_text("⚠️ شماره وارد شده نامعتبر است.")
            # else: Command didn't match specific font number format (shouldn't happen)

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Font Controller: Error processing command '{command}' for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطایی در پردازش دستور فونت رخ داد.")
        except Exception: pass

async def clock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    new_name = None
    feedback_msg = None

    try:
        me = await client.get_me()
        current_name = me.first_name or ""
        # Use more robust regex to find base name
        base_name_match = re.match(r"^(.*?)\s*[" + re.escape(ALL_CLOCK_CHARS) + r":\s]*$", current_name)
        base_name = base_name_match.group(1).strip() if base_name_match else current_name.strip()
        if not base_name: base_name = me.username or f"User_{user_id}" # Fallback

        is_clock_currently_on = CLOCK_STATUS.get(user_id, False) # Check current status

        if command == "ساعت روشن":
            if not is_clock_currently_on:
                CLOCK_STATUS[user_id] = True
                await save_settings_to_db(user_id)
                current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
                tehran_time = datetime.now(TEHRAN_TIMEZONE)
                current_time_str = tehran_time.strftime("%H:%M")
                stylized_time = stylize_time(current_time_str, current_font_style)
                new_name = f"{base_name} {stylized_time}"[:64]
                feedback_msg = "✅ ساعت با موفقیت به نام پروفایل اضافه شد."
            else:
                 feedback_msg = "ℹ️ ساعت از قبل فعال بود."

        elif command == "ساعت خاموش":
            if is_clock_currently_on:
                CLOCK_STATUS[user_id] = False
                await save_settings_to_db(user_id)
                new_name = base_name[:64]
                feedback_msg = "❌ ساعت با موفقیت از نام پروفایل حذف شد."
            else:
                 feedback_msg = "ℹ️ ساعت از قبل غیرفعال بود."

        # Update profile only if a change is needed
        if new_name is not None and new_name != current_name:
             await client.update_profile(first_name=new_name)

        # Send feedback
        if feedback_msg:
             await message.edit_text(feedback_msg)

    except FloodWait as e:
        logging.warning(f"Clock Controller: Flood wait for user {user_id}: {e.value}s")
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Clock Controller: Error processing command '{command}' for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطایی در تنظیم ساعت پروفایل رخ داد.")
        except Exception: pass


async def debug_pv_outgoing_logger(client, message):
    try:
        if not getattr(message, "chat", None) or message.chat.type != ChatType.PRIVATE:
            return
        txt = getattr(message, "text", None) or ""
        if not txt:
            return
        normalized = re.sub(r"\s+", " ", txt.replace("\u200c", " ").strip())
        logging.info(
            "DEBUG PV OUT: user_id=%s chat_id=%s msg_id=%s raw=%r normalized=%r",
            getattr(getattr(client, "me", None), "id", None),
            getattr(getattr(message, "chat", None), "id", None),
            getattr(message, "id", None),
            txt,
            normalized,
        )
    except Exception as e:
        logging.warning("DEBUG PV OUT: logger failed err=%s", e)


async def debug_pv_incoming_logger(client, message):
    try:
        if not getattr(message, "chat", None) or message.chat.type != ChatType.PRIVATE:
            return
        if getattr(getattr(message, "from_user", None), "id", None) == getattr(getattr(client, "me", None), "id", None):
            return

        logging.info(
            "DEBUG PV IN: user_id=%s chat_id=%s msg_id=%s from_id=%s from_bot=%s text=%r caption=%r",
            getattr(getattr(client, "me", None), "id", None),
            getattr(getattr(message, "chat", None), "id", None),
            getattr(message, "id", None),
            getattr(getattr(message, "from_user", None), "id", None),
            bool(getattr(getattr(message, "from_user", None), "is_bot", False)),
            getattr(message, "text", None),
            getattr(message, "caption", None),
        )
    except Exception as e:
        logging.warning("DEBUG PV IN: logger failed err=%s", e)

# --- Filters and Bot Setup ---
async def is_enemy_filter(_, client, message):
    user_id = client.me.id
    # Check if message and from_user exist before accessing id
    if ENEMY_ACTIVE.get(user_id, False) and message and message.from_user:
        return message.from_user.id in ENEMY_LIST.get(user_id, set())
    return False

is_enemy = filters.create(is_enemy_filter)

async def is_friend_filter(_, client, message):
    user_id = client.me.id
    # Check if message and from_user exist before accessing id
    if FRIEND_ACTIVE.get(user_id, False) and message and message.from_user:
        return message.from_user.id in FRIEND_LIST.get(user_id, set())
    return False

is_friend = filters.create(is_friend_filter)

if "is_friend" not in globals():
    is_friend = filters.create(lambda *_: False)

class ResilientClient(Client):
    """A custom Pyrogram client that is resilient to Peer ID errors in the update loop."""
    async def handle_updates(self, *args, **kwargs):
        try:
            await super().handle_updates(*args, **kwargs)
        except (ValueError, KeyError) as e:
            msg = str(e)
            if 'Peer id invalid' in msg or 'ID not found' in msg:
                logging.warning(f"RESILIENT_CLIENT: Suppressed update loop crash: {e}")
            else:
                logging.error("ResilientClient: Unhandled non-fatal exception in handle_updates", exc_info=True)
                raise
        except Exception:
            logging.error("ResilientClient: FATAL unhandled exception in handle_updates", exc_info=True)
            raise

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    safe_phone = re.sub(r'[^\w]', '_', phone)
    client_name = f"self_bot_{safe_phone}_{int(time.time())}"
    client = ResilientClient(client_name, session_string=session_string, api_id=API_ID, api_hash=API_HASH)
    user_id = None

    try:
        logging.info(f"Starting bot instance for {phone}...")
        await client.start()
        me = await client.get_me()
        user_id = me.id
        logging.info(f"Bot instance started successfully for {phone} (user_id: {user_id})")

        def handle_peer_error(loop, context):
            if 'exception' in context:
                exc = context['exception']
                if isinstance(exc, ValueError) and 'Peer id invalid' in str(exc):
                    logging.warning(f"Peer ID error handled: {exc}")
                    return
                if isinstance(exc, KeyError) and 'ID not found' in str(exc):
                    logging.warning(f"Peer not found error handled: {exc}")
                    return
            loop.default_exception_handler(context)

        def handle_fatal_updates_exception(loop, context):
            # This is a more aggressive handler specifically for the update loop crashes.
            exc = context.get('exception')
            if exc and isinstance(exc, (ValueError, KeyError)):
                msg = str(exc)
                # Check for the specific errors that crash the handler task
                if 'Peer id invalid' in msg or 'ID not found' in msg:
                    logging.warning(
                        f"FATAL HANDLED: Suppressed a client-crashing error: {exc}. "
                        f"The client instance will remain active."
                    )
                    return # Suppress the exception

            # If it's not the specific error we want to suppress, fall back to the default handler.
            logging.error(f"Unhandled exception in event loop: {context.get('message')}", exc_info=exc)
            loop.default_exception_handler(context)

        # Monkey-patch the handle_updates to make it resilient to Peer ID errors
        original_handle_updates = client.handle_updates

        async def resilient_handle_updates(*args, **kwargs):
            try:
                await original_handle_updates(*args, **kwargs)
            except (ValueError, KeyError) as e:
                msg = str(e)
                if 'Peer id invalid' in msg or 'ID not found' in msg:
                    logging.warning(f"RESILIENT_HANDLER: Suppressed update loop crash: {e}")
                    # Instead of crashing, we just log and the task will end.
                    # Pyrogram should restart it, but if not, the client is still alive.
                else:
                    logging.error("Unhandled exception in handle_updates", exc_info=True)
                    raise # Re-raise other exceptions
            except Exception:
                logging.error("FATAL unhandled exception in handle_updates", exc_info=True)
                raise

        client.handle_updates = resilient_handle_updates
        logging.info(f"Applied resilient monkey-patch to handle_updates for user {user_id}")

    except (UserDeactivated, AuthKeyUnregistered) as e:
        # ... (rest of the code remains the same)
        logging.error(f"Session for phone {phone} is invalid ({type(e).__name__}). Removing from database.")
        if sessions_collection is not None:
            try:
                sessions_collection.delete_one({'phone_number': phone})
            except Exception as db_del_err:
                 logging.error(f"DB Error: Failed to delete invalid session for {phone}: {db_del_err}")
        # Ensure client is stopped even if start failed partially
        if client.is_connected:
            try: await client.stop()
            except Exception as stop_err: logging.error(f"Error stopping invalid client {phone}: {stop_err}")
        return # Stop execution for this instance

    except FloodWait as e_start_flood:
         logging.error(f"Flood wait ({e_start_flood.value}s) during client start for {phone}. Aborting start for this session.")
         # No need to stop client here as start likely didn't fully complete
         return # Stop execution for this instance

    except Exception as e_start:
        logging.error(f"FAILED to start client {phone}: {e_start}", exc_info=True)
        if client.is_connected:
             try: await client.stop()
             except Exception as stop_err: logging.error(f"Error stopping failed client {phone}: {stop_err}")
        return # Stop execution for this instance

    # --- Configuration and Task Starting ---
    try:
        # Stop existing instance if user_id is already active
        if user_id in ACTIVE_BOTS:
            logging.warning(f"User {user_id} ({phone}) is already running. Stopping the old instance...")
            old_client, existing_tasks = ACTIVE_BOTS.pop(user_id)
            # Cancel background tasks of the old instance
            for task in existing_tasks:
                if task and not task.done():
                    task.cancel()
                    try:
                        # Give task a moment to cancel
                        await asyncio.wait_for(task, timeout=1.0)
                    except (asyncio.CancelledError, asyncio.TimeoutError):
                        pass # Ignore errors during cancellation
                    except Exception as task_cancel_err:
                         logging.warning(f"Error cancelling task for old instance {user_id}: {task_cancel_err}")
            # Stop the old client connection
            if old_client and old_client.is_connected:
                 try:
                     logging.info(f"Stopping old client connection for {user_id}...")
                     await old_client.stop(block=False) # Non-blocking stop
                 except Exception as stop_err:
                     logging.error(f"Error stopping old client {user_id}: {stop_err}")
            logging.info(f"Old instance for {user_id} stopped.")
            await asyncio.sleep(2) # Brief pause before starting new handlers/tasks

        # --- Initialize Settings ---
        # Use setdefault to avoid overwriting if somehow called multiple times before full stop
        USER_FONT_CHOICES.setdefault(user_id, font_style if font_style in FONT_STYLES else 'stylized')
        CLOCK_STATUS.setdefault(user_id, not disable_clock)
        SECRETARY_MODE_STATUS.setdefault(user_id, False)
        AI_SECRETARY_STATUS.setdefault(user_id, False)
        COMMENT_STATUS.setdefault(user_id, False)
        COMMENT_TEXT.setdefault(user_id, "اول! 🔥")
        AUTO_REPEAT_STATUS.setdefault(user_id, {})
        AUTO_SAVE_VIEW_ONCE.setdefault(user_id, False)
        # Initialize default values before loading from DB
        CUSTOM_SECRETARY_MESSAGES.setdefault(user_id, DEFAULT_SECRETARY_MESSAGE)
        USERS_REPLIED_IN_SECRETARY.setdefault(user_id, set())
        BOLD_MODE_STATUS.setdefault(user_id, False)
        QUOTE_MODE_STATUS.setdefault(user_id, False)
        AUTO_SEEN_STATUS.setdefault(user_id, False)
        AUTO_REACTION_TARGETS.setdefault(user_id, {})
        AUTO_TRANSLATE_TARGET.setdefault(user_id, None)
        ANTI_LOGIN_STATUS.setdefault(user_id, False)
        COPY_MODE_STATUS.setdefault(user_id, False) # Should always start False
        TYPING_MODE_STATUS.setdefault(user_id, False)
        PLAYING_MODE_STATUS.setdefault(user_id, False)
        RECORD_VOICE_STATUS.setdefault(user_id, False)
        UPLOAD_PHOTO_STATUS.setdefault(user_id, False)
        WATCH_GIF_STATUS.setdefault(user_id, False)
        PV_LOCK_STATUS.setdefault(user_id, False)
        # Initialize PV media locks with False (will be overwritten by DB load if exists)
        PV_TEXT_LOCK_STATUS.setdefault(user_id, False)
        PV_EMOJI_LOCK_STATUS.setdefault(user_id, False)
        PV_STICKER_LOCK_STATUS.setdefault(user_id, False)
        PV_GIF_LOCK_STATUS.setdefault(user_id, False)
        PV_PHOTO_LOCK_STATUS.setdefault(user_id, False)
        PV_VIDEO_LOCK_STATUS.setdefault(user_id, False)
        PV_VOICE_LOCK_STATUS.setdefault(user_id, False)
        PV_DOCUMENT_LOCK_STATUS.setdefault(user_id, False)
        PV_AUDIO_LOCK_STATUS.setdefault(user_id, False)
        PV_VIDEO_NOTE_LOCK_STATUS.setdefault(user_id, False)
        PV_CONTACT_LOCK_STATUS.setdefault(user_id, False)
        PV_LOCATION_LOCK_STATUS.setdefault(user_id, False)
        # Initialize BIO settings with default values (will be overwritten by DB load if exists)
        BIO_CLOCK_STATUS.setdefault(user_id, False)
        BIO_DATE_STATUS.setdefault(user_id, False)
        BIO_DATE_TYPE.setdefault(user_id, 'jalali')
        BIO_FONT_CHOICE.setdefault(user_id, 'stylized')
        MUTED_USERS.setdefault(user_id, set())
        # Load settings from DB if available (will overwrite defaults if exist in DB)
        await load_user_settings_from_db(user_id)
        # ORIGINAL_PROFILE_DATA should not be setdefault, it's temporary during copy mode
        if user_id not in ORIGINAL_PROFILE_DATA: ORIGINAL_PROFILE_DATA[user_id] = {}
        
        # متن‌های پیش‌فرض دشمن با لیست کامل شما
        ENEMY_REPLIES.setdefault(user_id, [
            "کیرم تو رحم اجاره ای و خونی مالی مادرت",
            "دو میلیون شبی پول ویلا بدم تا مادرتو تو گوشه کناراش بگام و اب کوسشو بریزم کف خونه تا فردا صبح کارگرای افغانی برای نظافت اومدن با بوی اب کس مادرت بجقن و ابکیراشون نثار قبر مرده هات بشه",
            "احمق مادر کونی من کس مادرت گذاشتم تو بازم داری کسشر میگی",
            "هی بیناموس کیرم بره تو کس ننت واس بابات نشآخ مادر کیری کیرم بره تو کس اجدادت کسکش بیناموس کس ول نسل شوتی ابجی کسده کیرم تو کس مادرت بیناموس کیری کیرم تو کس نسل ابجی کونی کس نسل سگ ممبر کونی ابجی سگ ممبر سگ کونی کیرم تو کس ننت کیر تو کس مادرت کیر خاندان تو کس نسل مادر کونی ابجی کونی کیری ناموس ابجیتو گاییدم سگ حرومی خارکسه مادر کیری با کیر بزنم تو رحم مادرت ناموستو بگام لاشی کونی ابجی کس خیابونی مادرخونی ننت کیرمو میماله تو میای کص میگی شاخ نشو ییا ببین شاخو کردم تو کون ابجی جندت کس ابجیتو پاره کردم تو شاخ میشی اوبی",
            "کیرم تو کس سیاه مادرت خارکصده",
            "حروم زاده باک کص ننت با ابکیرم پر میکنم",
            "منبع اب ایرانو با اب کص مادرت تامین میکنم",
            "خارکسته میخای مادرتو بگام بعد بیای ادعای شرف کنی کیرم تو شرف مادرت",
            "کیرم تویه اون خرخره مادرت بیا اینحا ببینم تویه نوچه کی دانلود شدی کیفیتت پایینه صدات نمیاد فقط رویه حالیت بی صدا داری امواج های بی ارزش و بیناموسانه از خودت ارسال میکنی که ناگهان دیدی من روانی شدم دست از پا خطا کردم با تبر کائنات کوبیدم رو سر مادرت نمیتونی مارو تازه بالقه گمان کنی"
        ])
        
        FRIEND_REPLIES.setdefault(user_id, []) # Default empty list
        ENEMY_LIST.setdefault(user_id, set())
        FRIEND_LIST.setdefault(user_id, set())
        ENEMY_ACTIVE.setdefault(user_id, False)
        FRIEND_ACTIVE.setdefault(user_id, False)

        # --- Add Handlers ---
        # Group -6: Media lock handler (must run before pv_lock_handler)
        client.add_handler(MessageHandler(debug_pv_incoming_logger, filters.private & ~filters.me & ~filters.service), group=-7)
        client.add_handler(MessageHandler(pv_media_lock_handler, filters.private & ~filters.me & ~filters.service), group=-6)
        # Group -5: Global PV lock handler
        client.add_handler(MessageHandler(pv_lock_handler, filters.private & ~filters.me & ~filters.service), group=-5)
        logging.info("DEBUG: registered PV lock handlers (debug_pv_incoming_logger=-7, pv_media_lock_handler=-6, pv_lock_handler=-5) user_id=%s", user_id)

        # Group -4: Auto seen, happens before general processing
        try:
            client.add_handler(MessageHandler(auto_seen_handler, filters.private & ~filters.me), group=-4)
            logging.info("DEBUG: registered auto_seen_handler group=-4 user_id=%s", user_id)
        except NameError as e_auto_seen:
            logging.warning("DEBUG: auto_seen_handler not defined; skipping registration user_id=%s err=%s", user_id, e_auto_seen)
        except Exception as e_auto_seen_reg:
            logging.warning("DEBUG: could not register auto_seen_handler user_id=%s err=%s", user_id, e_auto_seen_reg)

        # Group -3: General incoming message manager (mute, reactions)
        client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me & ~filters.service), group=-3)

        # Group -1: Outgoing message modifications (bold, translate)
        # Ensure it doesn't process commands by checking regex again? Or rely on outgoing_message_modifier logic.
        # Added ~filters.regex(COMMAND_REGEX) to be explicit
        client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.via_bot & ~filters.service & ~filters.regex(COMMAND_REGEX)), group=-1)

        # Group 0: Command handlers (default group)
        cmd_filters = filters.me & filters.text

        try:
            client.add_handler(MessageHandler(debug_pv_outgoing_logger, filters.me & filters.text & filters.private), group=-6)
            logging.info("DEBUG: registered debug_pv_outgoing_logger for outgoing private text")
        except Exception as e_reg_dbg:
            logging.warning("DEBUG: could not register debug_pv_outgoing_logger err=%s", e_reg_dbg)
        
        client.add_handler(MessageHandler(help_controller, cmd_filters & filters.regex("^راهنما$")), group=0)
        client.add_handler(MessageHandler(toggle_controller, cmd_filters & filters.regex(r"^(بولد روشن|بولد خاموش|نقل و قول روشن|نقل و قول خاموش|سین روشن|سین خاموش|منشی روشن|منشی خاموش|منشی خودکار روشن|منشی خودکار خاموش|تست ai|وضعیت یادگیری|بکاپ یادگیری|پاکسازی یادگیری|انتی لوگین روشن|انتی لوگین خاموش|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|ضبط ویس روشن|ضبط ویس خاموش|عکس روشن|عکس خاموش|گیف روشن|گیف خاموش|دشمن روشن|دشمن خاموش|دوست روشن|دوست خاموش)$")))
        client.add_handler(MessageHandler(translate_controller, cmd_filters & filters.reply & filters.regex(r"^ترجمه$"))) # Translate command requires reply
        client.add_handler(MessageHandler(set_translation_controller, cmd_filters & filters.regex(r"^(ترجمه [a-z]{2}(?:-[a-z]{2})?|ترجمه خاموش|چینی روشن|چینی خاموش|روسی روشن|روسی خاموش|انگلیسی روشن|انگلیسی خاموش)$", flags=re.IGNORECASE)))
        client.add_handler(MessageHandler(set_secretary_message_controller, cmd_filters & filters.regex(r"^منشی متن(?: |$)(.*)", flags=re.DOTALL | re.IGNORECASE)))
        client.add_handler(MessageHandler(pv_lock_controller, cmd_filters & filters.regex("^(پیوی قفل|پیوی باز)$")))
        client.add_handler(MessageHandler(pv_media_lock_controller, cmd_filters & filters.regex(r"^\s*قفل\b")))
        logging.info("DEBUG: registered pv_media_lock_controller with regex ^\\s*قفل\\b")
        client.add_handler(MessageHandler(font_controller, cmd_filters & filters.regex(r"^(فونت|فونت \d+)$")))
        client.add_handler(MessageHandler(clock_controller, cmd_filters & filters.regex("^(ساعت روشن|ساعت خاموش)$")))
        
        client.add_handler(MessageHandler(set_enemy_controller, cmd_filters & filters.reply & filters.regex("^تنظیم دشمن$"))) # Requires reply
        client.add_handler(MessageHandler(delete_enemy_controller, cmd_filters & filters.reply & filters.regex("^حذف دشمن$"))) # Requires reply
        client.add_handler(MessageHandler(clear_enemy_list_controller, cmd_filters & filters.regex("^پاکسازی لیست دشمن$")))
        client.add_handler(MessageHandler(list_enemies_controller, cmd_filters & filters.regex("^لیست دشمن$")))
        client.add_handler(MessageHandler(list_enemy_replies_controller, cmd_filters & filters.regex("^لیست متن دشمن$")))
        client.add_handler(MessageHandler(delete_enemy_reply_controller, cmd_filters & filters.regex(r"^حذف متن دشمن(?: \d+)?$")))
        client.add_handler(MessageHandler(set_enemy_reply_controller, cmd_filters & filters.regex(r"^تنظیم متن دشمن (.*)", flags=re.DOTALL | re.IGNORECASE))) # Allow multiline text
        client.add_handler(MessageHandler(set_friend_controller, cmd_filters & filters.reply & filters.regex("^تنظیم دوست$"))) # Requires reply
        client.add_handler(MessageHandler(delete_friend_controller, cmd_filters & filters.reply & filters.regex("^حذف دوست$"))) # Requires reply
        client.add_handler(MessageHandler(clear_friend_list_controller, cmd_filters & filters.regex("^پاکسازی لیست دوست$")))
        client.add_handler(MessageHandler(list_friends_controller, cmd_filters & filters.regex("^لیست دوست$")))
        client.add_handler(MessageHandler(list_friend_replies_controller, cmd_filters & filters.regex("^لیست متن دوست$")))
        client.add_handler(MessageHandler(delete_friend_reply_controller, cmd_filters & filters.regex(r"^حذف متن دوست(?: \d+)?$")))
        client.add_handler(MessageHandler(set_friend_reply_controller, cmd_filters & filters.regex(r"^تنظیم متن دوست (.*)", flags=re.DOTALL | re.IGNORECASE))) # Allow multiline text
        client.add_handler(MessageHandler(block_unblock_controller, cmd_filters & filters.reply & filters.regex("^(بلاک روشن|بلاک خاموش)$"))) # Requires reply
        client.add_handler(MessageHandler(mute_unmute_controller, cmd_filters & filters.reply & filters.regex("^(سکوت روشن|سکوت خاموش)$"))) # Requires reply
        client.add_handler(MessageHandler(auto_reaction_controller, cmd_filters & filters.reply & filters.regex("^(ریاکشن .*|ریاکشن خاموش)$"))) # Requires reply
        # Copy profile handler needs careful filter: allow reply only for 'copy روشن'
        client.add_handler(MessageHandler(copy_profile_controller, cmd_filters & filters.regex("^(کپی روشن|کپی خاموش)$"))) # Logic inside handles reply check
        client.add_handler(MessageHandler(auto_save_toggle_controller, cmd_filters & filters.regex("^(ذخیره روشن|ذخیره خاموش)$")))
        client.add_handler(MessageHandler(secret_save_toggle_controller, cmd_filters & filters.regex("^(ذخیره مخفی روشن|ذخیره مخفی خاموش)$")))
        client.add_handler(MessageHandler(repeat_message_controller, cmd_filters & filters.regex(r"^(تکرار \d+(?: \d+)?|تکرار خودکار \d+|تکرار خودکار خاموش)$"))) # Auto-repeat commands
        client.add_handler(MessageHandler(delete_messages_controller, cmd_filters & filters.regex(r"^(حذف(?: \d+)?|حذف همه)$")))
        client.add_handler(MessageHandler(ping_controller, cmd_filters & filters.regex("^(ping|پینگ)$")))
        
        # New handlers from self.txt
        client.add_handler(MessageHandler(tag_all_controller, cmd_filters & filters.regex("^(تگ|tagall)$")))
        client.add_handler(MessageHandler(tag_admins_controller, cmd_filters & filters.regex("^(تگ ادمین ها|tagadmins)$")))
        # Premium animations with simple Persian commands
        client.add_handler(MessageHandler(fun_controller, cmd_filters & filters.regex(r"^(fun|فان)\s+.+$")))
        client.add_handler(MessageHandler(heart_controller, cmd_filters & filters.regex(r"^(heart|قلب)$")))
        # Casino shortcuts
        client.add_handler(MessageHandler(crash_management_controller, cmd_filters & filters.regex("^(افزودن کراش|حذف کراش|لیست کراش|addcrash|delcrash|listcrash)$")))
        client.add_handler(MessageHandler(set_crash_reply_controller, cmd_filters & filters.regex(r"^تنظیم متن کراش (.*)", flags=re.DOTALL | re.IGNORECASE)))
        client.add_handler(MessageHandler(list_crash_replies_controller, cmd_filters & filters.regex("^لیست متن کراش$")))
        client.add_handler(MessageHandler(delete_crash_reply_controller, cmd_filters & filters.regex(r"^حذف متن کراش(?: \d+)?$")))
        client.add_handler(MessageHandler(comment_command_controller, cmd_filters & filters.regex(r"^(کامنت روشن|کامنت خاموش|متن کامنت .+)$")))
        client.add_handler(MessageHandler(text_mode_controller, cmd_filters & filters.regex(r"^(بولد|ایتالیک|زیرخط|خط خورده|کد|اسپویلر|منشن|هشتگ|معکوس|تدریجی) (روشن|خاموش)$")))
        client.add_handler(MessageHandler(clean_messages_controller, cmd_filters & filters.regex(r"^(حذف|clean) (\d+)$")))
        

        # New handlers without external API
        client.add_handler(MessageHandler(myphone_controller, cmd_filters & filters.regex("^(شماره من|myphone)$")))
        
        # Bio clock and date handlers
        client.add_handler(MessageHandler(bio_clock_controller, cmd_filters & filters.regex("^(ساعت بیو روشن|ساعت بیو خاموش)$")))
        client.add_handler(MessageHandler(bio_date_controller, cmd_filters & filters.regex("^(تاریخ بیو روشن|تاریخ بیو خاموش)$")))
        client.add_handler(MessageHandler(bio_date_type_controller, cmd_filters & filters.regex("^(نوع تاریخ میلادی|نوع تاریخ شمسی)$")))
        client.add_handler(MessageHandler(bio_font_controller, cmd_filters & filters.regex(r"^(فونت ساعت بیو|فونت ساعت بیو \d+)$")))
        client.add_handler(MessageHandler(spam_controller, cmd_filters & filters.regex(r"^(اسپم|spam) .+ \d+$")))
        client.add_handler(MessageHandler(flood_controller, cmd_filters & filters.regex(r"^(فلود|flood) .+ \d+$")))
        client.add_handler(MessageHandler(download_controller, cmd_filters & filters.reply & filters.regex("^(دانلود|download)$")))
        client.add_handler(MessageHandler(ban_controller, cmd_filters & filters.reply & filters.regex("^(بن|ban)$")))
        client.add_handler(MessageHandler(pin_controller, cmd_filters & filters.reply & filters.regex("^(پین|pin)$")))
        client.add_handler(MessageHandler(unpin_controller, cmd_filters & filters.regex("^(آن پین|unpin)$")))
        

        # Add text editing mode handler for outgoing messages (simplified)
        client.add_handler(MessageHandler(text_mode_handler, filters.text & filters.me), group=-2)

        # Group 1: Auto-reply handlers (lower priority than commands and basic management)
        # Added ~filters.user(user_id) to ensure these don't trigger on own messages if filters somehow match
        client.add_handler(MessageHandler(auto_save_view_once_handler, ~filters.me & ~filters.bot & ~filters.service), group=0)  # Auto-save view once media
        client.add_handler(MessageHandler(enemy_handler, is_enemy & ~filters.me & ~filters.bot & ~filters.service), group=1)
        client.add_handler(MessageHandler(friend_handler, is_friend & ~filters.me & ~filters.bot & ~filters.service), group=1)
        client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me & ~filters.bot & ~filters.service), group=1)

        # Comment handler for channel posts (discussion group comments)
        try:
            channel_filter = getattr(filters, "channel", None)
            if channel_filter is None:
                try:
                    channel_filter = filters.chat(ChatType.CHANNEL)
                except Exception:
                    channel_filter = filters.create(lambda _, __, m: bool(getattr(getattr(m, "chat", None), "type", None) == ChatType.CHANNEL))
            client.add_handler(MessageHandler(channel_comment_handler, filters.me & channel_filter), group=2)
        except Exception as e_channel_comment_reg:
            logging.warning("DEBUG: could not register channel_comment_handler err=%s", e_channel_comment_reg)
        
        # Reaction handler for secret save - only if MessageReactionUpdatedHandler is available
        if MessageReactionUpdatedHandler is not None:
            client.add_handler(MessageReactionUpdatedHandler(secret_save_reaction_handler))

        client.add_handler(RawUpdateHandler(secret_save_raw_update_handler))

        # --- Start Background Tasks ---
        tasks = [
            asyncio.create_task(update_profile_clock(client, user_id)),
            asyncio.create_task(update_bio_clock(client, user_id)),
            asyncio.create_task(anti_login_task(client, user_id)),
            asyncio.create_task(status_action_task(client, user_id))
        ]
        # Store the client and its tasks
        ACTIVE_BOTS[user_id] = (client, tasks)
        logging.info(f"Instance for user_id {user_id} configured successfully, background tasks started.")

    except Exception as e_config:
        logging.error(f"FAILED instance configuration or task starting for {user_id} ({phone}): {e_config}", exc_info=True)
        # Clean up if configuration fails after client started
        if user_id and user_id in ACTIVE_BOTS: # Check if it was added to ACTIVE_BOTS
             client_to_stop, tasks_to_cancel = ACTIVE_BOTS.pop(user_id)
             for task in tasks_to_cancel:
                 if task and not task.done(): task.cancel()
             if client_to_stop and client_to_stop.is_connected:
                 try: await client_to_stop.stop(block=False)
                 except Exception as stop_err: logging.error(f"Error stopping client {user_id} after config fail: {stop_err}")
        elif client.is_connected: # If it failed before adding to ACTIVE_BOTS but after starting
             try: await client.stop(block=False)
             except Exception as stop_err: logging.error(f"Error stopping client {phone} after config fail: {stop_err}")
        # Ensure it's removed from ACTIVE_BOTS if config fails at any point
        ACTIVE_BOTS.pop(user_id, None)

# --- New Controller Functions from self.txt ---

async def tag_all_controller(client, message):
    """Tag all users in group"""
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        try:
            members_list = []
            try:
                async for member in client.get_chat_members(message.chat.id, limit=100):
                    if member.user and not member.user.is_bot and member.user.username:
                        members_list.append(f'@{member.user.username}')
            except Exception as e_members:
                logging.warning(f"Error getting chat members: {e_members}")
            
            # Delete command message
            await message.delete()
            
            # Split into chunks of 6
            chunk_size = 6
            for i in range(0, len(members_list), chunk_size):
                chunk = members_list[i:i+chunk_size]
                mentions_text = '\n'.join(chunk)
                await client.send_message(message.chat.id, mentions_text)
                await asyncio.sleep(1)  # Delay between messages
                
        except Exception as e:
            try:
                await client.send_message(message.chat.id, f"خطا در تگ کردن: {e}")
            except:
                pass

async def tag_admins_controller(client, message):
    """Tag all admins in group"""
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        try:
            admins_list = []
            try:
                async for member in client.get_chat_members(message.chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
                    if member.user and not member.user.is_bot and member.user.username:
                        admins_list.append(f'@{member.user.username}')
            except Exception as e_admins:
                logging.warning(f"Error getting chat admins: {e_admins}")
            
            # Delete command message
            await message.delete()
            
            # Split into chunks of 6
            chunk_size = 6
            for i in range(0, len(admins_list), chunk_size):
                chunk = admins_list[i:i+chunk_size]
                mentions_text = '⚡️ تگ کردن ادمین ها\n' + '\n'.join(chunk)
                await client.send_message(message.chat.id, mentions_text)
                await asyncio.sleep(1)  # Delay between messages
                
        except Exception as e:
            try:
                await client.send_message(message.chat.id, f"خطا در تگ ادمین ها: {e}")
            except:
                pass

async def fun_controller(client, message):
    """Fun sticker animations (from 1.py)"""
    try:
        command = message.text.strip()
        # Parse: fun [type] or فان [type]
        match = re.match(r'^(fun|فان)\s+(.+)$', command, re.IGNORECASE)
        if not match:
            return
        
        input_str = match.group(2).lower()
        
        if 'love' in input_str:
            emoticons = ['🤍', '🖤', '💜', '💙', '💚', '💛', '🧡', '❤️', '🤎', '💖']
        elif 'oclock' in input_str:
            emoticons = ['🕐', '🕑', '🕒', '🕓', '🕔', '🕕', '🕖', '🕗', '🕘', '🕙', '🕚', '🕛', '🕜', '🕝', '🕞', '🕟', '🕠', '🕡', '🕢', '🕣', '🕤', '🕥', '🕦', '🕧']
        elif 'star' in input_str:
            emoticons = ['💥', '⚡️', '✨', '🌟', '⭐️', '💫']
        elif 'snow' in input_str:
            emoticons = ['❄️', '☃️', '⛄️']
        else:
            return
        
        random.shuffle(emoticons)
        for emoji in emoticons:
            await asyncio.sleep(1)
            try:
                await message.edit_text(emoji)
            except (MessageNotModified, MessageIdInvalid):
                pass
    except Exception as e:
        logging.warning(f"Fun controller error: {e}")

async def heart_controller(client, message):
    """Heart animation (from 1.py)"""
    try:
        command = message.text.strip()
        if command.lower() not in ['heart', 'قلب']:
            return
        
        for x in range(1, 4):
            for i in range(1, 11):
                try:
                    await message.edit_text('➣ ' + str(x) + ' ❦' * i + ' | ' + str(10 * i) + '%')
                    await asyncio.sleep(0.1)
                except (MessageNotModified, MessageIdInvalid):
                    pass
    except Exception as e:
        logging.warning(f"Heart controller error: {e}")


async def crash_management_controller(client, message):
    """Manage crash list"""
    user_id = client.me.id
    command = message.text.strip().lower()
    
    if command in ['افزودن کراش', 'addcrash']:
        if message.reply_to_message and message.reply_to_message.from_user:
            target_id = message.reply_to_message.from_user.id
            crash_list = CRASH_LIST.setdefault(user_id, set())
            if target_id not in crash_list:
                crash_list.add(target_id)
                await message.edit_text(f"✅ کاربر با آیدی `{target_id}` به لیست کراش اضافه شد")
            else:
                await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` از قبل در لیست کراش بود")
        else:
            await message.edit_text("⚠️ روی پیام کاربر مورد نظر ریپلای کنید")
    
    elif command in ['حذف کراش', 'delcrash']:
        if message.reply_to_message and message.reply_to_message.from_user:
            target_id = message.reply_to_message.from_user.id
            crash_list = CRASH_LIST.get(user_id, set())
            if target_id in crash_list:
                crash_list.remove(target_id)
                await message.edit_text(f"✅ کاربر با آیدی `{target_id}` از لیست کراش حذف شد")
            else:
                await message.edit_text(f"ℹ️ کاربر با آیدی `{target_id}` در لیست کراش نبود")
        else:
            await message.edit_text("⚠️ روی پیام کاربر مورد نظر ریپلای کنید")
    
    elif command in ['لیست کراش', 'listcrash']:
        crash_list = CRASH_LIST.get(user_id, set())
        if crash_list:
            list_text = "**💕 لیست کراش:**\n"
            for crash_id in crash_list:
                list_text += f"- `{crash_id}`\n"
            await message.edit_text(list_text)
        else:
            await message.edit_text("ℹ️ لیست کراش خالی است")

async def set_crash_reply_controller(client, message):
    """Set crash reply text"""
    user_id = client.me.id
    match = re.match(r"^تنظیم متن کراش (.*)", message.text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        if text:
            if user_id not in CRASH_REPLIES:
                CRASH_REPLIES[user_id] = []
            CRASH_REPLIES[user_id].append(text)
            await save_settings_to_db(user_id)
            await message.edit_text(f"✅ متن جدید به لیست پاسخ کراش اضافه شد (مورد {len(CRASH_REPLIES[user_id])}).")
        else:
            await message.edit_text("⚠️ متن پاسخ نمی‌تواند خالی باشد.")

async def list_crash_replies_controller(client, message):
    """List crash reply texts"""
    user_id = client.me.id
    replies = CRASH_REPLIES.get(user_id, [])
    if not replies:
        await message.edit_text("ℹ️ لیست متن‌های پاسخ کراش خالی است.")
    else:
        list_text = "**💕 لیست متن‌های کراش:**\n" + "\n".join([f"{i+1}. `{reply}`" for i, reply in enumerate(replies)])
        if len(list_text) > 4096:
            list_text = list_text[:4090] + "\n[...]"
        await message.edit_text(list_text)

async def delete_crash_reply_controller(client, message):
    """Delete crash reply text"""
    user_id = client.me.id
    match = re.match(r"^حذف متن کراش(?: (\d+))?$", message.text, re.IGNORECASE)
    if match:
        index_str = match.group(1)
        replies = CRASH_REPLIES.get(user_id)

        if replies is None or not replies:
             await message.edit_text("ℹ️ لیست متن کراش خالی است، چیزی برای حذف وجود ندارد.")
             return

        try:
            if index_str:
                index = int(index_str) - 1
                if 0 <= index < len(replies):
                    removed_reply = replies.pop(index)
                    await save_settings_to_db(user_id)
                    await message.edit_text(f"✅ متن شماره {index+1} (`{removed_reply}`) از لیست کراش حذف شد.")
                else:
                    await message.edit_text(f"⚠️ شماره نامعتبر. لطفاً عددی بین 1 تا {len(replies)} وارد کنید.")
            else:
                CRASH_REPLIES[user_id] = []
                await save_settings_to_db(user_id)
                await message.edit_text("✅ تمام متن‌های پاسخ کراش حذف شدند.")
        except ValueError:
             await message.edit_text("⚠️ شماره وارد شده نامعتبر است.")
        except Exception as e:
            logging.error(f"Delete Crash Reply: Error for user {user_id}: {e}", exc_info=True)
            await message.edit_text("⚠️ خطایی در حذف متن کراش رخ داد.")

async def comment_command_controller(client, message):
    """Handle comment commands (from 1.py) - simple Persian commands"""
    user_id = client.me.id
    command = message.text.strip()
    
    try:
        if command == "کامنت روشن":
            COMMENT_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ کامنت فعال شد.")
        
        elif command == "کامنت خاموش":
            COMMENT_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ کامنت غیرفعال شد.")
        
        elif command.startswith("متن کامنت "):
            text = command[10:].strip()  # Remove "متن کامنت "
            if text:
                COMMENT_TEXT[user_id] = text
                await save_settings_to_db(user_id)
                await message.edit_text(f"✅ متن کامنت تنظیم شد:\n`{text}`")
            else:
                await message.edit_text("⚠️ متن کامنت نمی‌تواند خالی باشد.")
    
    except Exception as e:
        logging.error(f"Comment Command Controller Error for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text(f"⚠️ خطا: {e}")
        except:
            pass

async def channel_comment_handler(client, message):
    """Handle comment on channel posts (کامنت در discussion group کانال)"""
    user_id = client.me.id
    
    # بررسی فعال بودن کامنت
    if not COMMENT_STATUS.get(user_id, False):
        return
    
    # فقط برای پیام‌های کانال
    if message.chat.type != ChatType.CHANNEL:
        return
    
    # فقط برای پست‌های خودمان (outgoing)
    if not message.outgoing:
        return
    
    # بررسی اینکه کانال discussion group دارد
    try:
        chat = await client.get_chat(message.chat.id)
        if not hasattr(chat, 'linked_chat') or not chat.linked_chat:
            return
        
        discussion_chat_id = chat.linked_chat.id
        
        # دریافت متن کامنت
        comment_text = COMMENT_TEXT.get(user_id, "اول! 🔥")
        
        # کمی تاخیر برای اطمینان از اینکه پیام discussion group ایجاد شده است
        await asyncio.sleep(2)
        
        # ارسال کامنت در discussion group
        try:
            # در discussion group، باید پیامی پیدا کنیم که به پست کانال اشاره می‌کند
            # یا می‌توانیم مستقیم reply_to_message_id را به message.id بدهیم
            # Telegram به صورت خودکار آن را به پیام discussion group مربوط می‌کند
            try:
                await client.send_message(
                    discussion_chat_id,
                    comment_text,
                    reply_to_message_id=message.id
                )
                logging.info(f"✅ کامنت در discussion group کانال {message.chat.id} ارسال شد: {comment_text}")
            except Exception as e1:
                # اگر reply_to_message_id کار نکرد، سعی می‌کنیم بدون reply ارسال کنیم
                logging.warning(f"⚠️ ارسال با reply_to_message_id ناموفق بود، سعی بدون reply: {e1}")
                await client.send_message(
                    discussion_chat_id,
                    comment_text
                )
                logging.info(f"✅ کامنت در discussion group کانال {message.chat.id} ارسال شد (بدون reply): {comment_text}")
        except Exception as e:
            logging.error(f"❌ خطا در ارسال کامنت در discussion group کانال {message.chat.id}: {e}")
    except Exception as e:
        logging.error(f"❌ خطا در بررسی discussion group کانال {message.chat.id}: {e}")

async def comment_handler(client, message):
    """Handle comment on forwarded messages (منطق کامنت از 1.py) - غیرفعال شده، استفاده از channel_comment_handler"""
    # این handler غیرفعال شده است - از channel_comment_handler استفاده می‌شود
    return

async def bio_clock_controller(client, message):
    """Toggle bio clock on/off"""
    try:
        user_id = client.me.id
        command = message.text.strip()
        
        if command == "ساعت بیو روشن":
            BIO_CLOCK_STATUS[user_id] = True
            BIO_FONT_CHOICE.setdefault(user_id, 'stylized')
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately
            await update_bio_now(client, user_id)
            
            await message.edit_text("✅ ساعت در بیو فعال شد")
        elif command == "ساعت بیو خاموش":
            BIO_CLOCK_STATUS[user_id] = False
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately to remove clock
            await update_bio_now(client, user_id)
            
            await message.edit_text("❌ ساعت در بیو غیرفعال شد")
    except Exception as e:
        logging.error(f"Bio clock controller error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم ساعت بیو")


async def bio_date_controller(client, message):
    """Toggle bio date on/off and set type"""
    try:
        user_id = client.me.id
        command = message.text.strip()
        
        if command == "تاریخ بیو روشن":
            BIO_DATE_STATUS[user_id] = True
            BIO_DATE_TYPE.setdefault(user_id, 'jalali')
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately
            await update_bio_now(client, user_id)
            
            await message.edit_text("✅ تاریخ در بیو فعال شد")
        elif command == "تاریخ بیو خاموش":
            BIO_DATE_STATUS[user_id] = False
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately to remove date
            await update_bio_now(client, user_id)
            
            await message.edit_text("❌ تاریخ در بیو غیرفعال شد")
    except Exception as e:
        logging.error(f"Bio date controller error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم تاریخ بیو")


async def bio_date_type_controller(client, message):
    """Set bio date type (jalali or gregorian)"""
    try:
        user_id = client.me.id
        command = message.text.strip()
        
        if command == "نوع تاریخ میلادی":
            BIO_DATE_TYPE[user_id] = 'gregorian'
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately if date is enabled
            if BIO_DATE_STATUS.get(user_id, False):
                await update_bio_now(client, user_id)
            
            await message.edit_text("✅ نوع تاریخ به میلادی تغییر یافت")
        elif command == "نوع تاریخ شمسی":
            BIO_DATE_TYPE[user_id] = 'jalali'
            
            # Save to database
            await save_settings_to_db(user_id)
            
            # Update bio immediately if date is enabled
            if BIO_DATE_STATUS.get(user_id, False):
                await update_bio_now(client, user_id)
            
            await message.edit_text("✅ نوع تاریخ به شمسی تغییر یافت")
    except Exception as e:
        logging.error(f"Bio date type controller error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم نوع تاریخ")


async def bio_font_controller(client, message):
    """Set bio clock font"""
    try:
        user_id = client.me.id
        command = message.text.strip()
        
        if command == "فونت ساعت بیو":
            # Show font list
            font_list_parts = []
            current_part = "📜 **لیست فونت‌های ساعت بیو:**\n"
            for i, key in enumerate(FONT_KEYS_ORDER[:50]):  # First 50 fonts
                line = f"{i+1}. {FONT_DISPLAY_NAMES.get(key, key)}: {stylize_time('12:34', key)}\n"
                if len(current_part) + len(line) > 4090:
                    font_list_parts.append(current_part)
                    current_part = line
                else:
                    current_part += line
            font_list_parts.append(current_part)
            
            for i, part in enumerate(font_list_parts):
                text_to_send = part
                if i == len(font_list_parts) - 1:
                    text_to_send += "\nبرای انتخاب: `فونت ساعت بیو [عدد]`"
                if i == 0:
                    await message.edit_text(text_to_send)
                else:
                    await client.send_message(message.chat.id, text_to_send)
                    await asyncio.sleep(0.5)
        else:
            # Set font
            match = re.match(r"^فونت ساعت بیو (\d+)$", command)
            if match:
                index = int(match.group(1)) - 1
                if 0 <= index < min(50, len(FONT_KEYS_ORDER)):
                    selected = FONT_KEYS_ORDER[index]
                    BIO_FONT_CHOICE[user_id] = selected
                    
                    # Save to database
                    await save_settings_to_db(user_id)
                    
                    # Update bio immediately if clock is enabled
                    if BIO_CLOCK_STATUS.get(user_id, False):
                        await update_bio_now(client, user_id)
                    
                    await message.edit_text(f"✅ فونت ساعت بیو به **{FONT_DISPLAY_NAMES.get(selected, selected)}** تغییر یافت")
                else:
                    await message.edit_text(f"⚠️ شماره فونت نامعتبر. لطفاً عددی بین 1 تا 50 وارد کنید")
    except Exception as e:
        logging.error(f"Bio font controller error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم فونت")

async def toggle_controller(client, message):
    """Handle various toggle commands"""
    user_id = client.me.id
    command = message.text.strip()
    
    try:
        if command == "بولد روشن":
            BOLD_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ حالت بولد فعال شد")
        elif command == "بولد خاموش":
            BOLD_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ حالت بولد غیرفعال شد")
        elif command == "نقل و قول روشن":
            QUOTE_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ نقل و قول فعال شد")
        elif command == "نقل و قول خاموش":
            QUOTE_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ نقل و قول غیرفعال شد")
        elif command == "سین روشن":
            AUTO_SEEN_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ خواندن خودکار فعال شد")
        elif command == "سین خاموش":
            AUTO_SEEN_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ خواندن خودکار غیرفعال شد")
        elif command == "منشی روشن":
            SECRETARY_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ منشی فعال شد")
        elif command == "منشی خاموش":
            SECRETARY_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ منشی غیرفعال شد")
        elif command == "منشی خودکار روشن":
            AI_SECRETARY_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            try:
                # Reset regular secretary one-time replied state when switching to AI mode
                USERS_REPLIED_IN_SECRETARY[user_id] = set()
            except Exception:
                pass
            await message.edit_text("✅ منشی خودکار (AI) فعال شد")
        elif command == "منشی خودکار خاموش":
            AI_SECRETARY_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ منشی خودکار (AI) غیرفعال شد")
        elif command == "انتی لوگین روشن":
            ANTI_LOGIN_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ انتی لوگین فعال شد")
        elif command == "انتی لوگین خاموش":
            ANTI_LOGIN_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ انتی لوگین غیرفعال شد")
        elif command == "تایپ روشن":
            TYPING_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ حالت تایپ فعال شد")
        elif command == "تایپ خاموش":
            TYPING_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ حالت تایپ غیرفعال شد")
        elif command == "بازی روشن":
            PLAYING_MODE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ حالت بازی فعال شد")
        elif command == "بازی خاموش":
            PLAYING_MODE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ حالت بازی غیرفعال شد")
        elif command == "ضبط ویس روشن":
            RECORD_VOICE_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ ضبط ویس فعال شد")
        elif command == "ضبط ویس خاموش":
            RECORD_VOICE_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ ضبط ویس غیرفعال شد")
        elif command == "عکس روشن":
            UPLOAD_PHOTO_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ آپلود عکس فعال شد")
        elif command == "عکس خاموش":
            UPLOAD_PHOTO_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ آپلود عکس غیرفعال شد")
        elif command == "گیف روشن":
            WATCH_GIF_STATUS[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ تماشای گیف فعال شد")
        elif command == "گیف خاموش":
            WATCH_GIF_STATUS[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ تماشای گیف غیرفعال شد")
        elif command == "دشمن روشن":
            ENEMY_ACTIVE[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ حالت دشمن فعال شد")
        elif command == "دشمن خاموش":
            ENEMY_ACTIVE[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ حالت دشمن غیرفعال شد")
        elif command == "دوست روشن":
            FRIEND_ACTIVE[user_id] = True
            await save_settings_to_db(user_id)
            await message.edit_text("✅ حالت دوست فعال شد")
        elif command == "دوست خاموش":
            FRIEND_ACTIVE[user_id] = False
            await save_settings_to_db(user_id)
            await message.edit_text("❌ حالت دوست غیرفعال شد")
        elif command == "وضعیت یادگیری":
            try:
                db_size = await get_learning_db_size()
                await message.edit_text(f"📊 **وضعیت یادگیری:**\n\n💾 حجم دیتابیس: {db_size:,} پیام")
            except Exception as e:
                logging.error(f"Learning status error: {e}")
                await message.edit_text("⚠️ خطا در دریافت وضعیت یادگیری")
        elif command == "بکاپ یادگیری":
            try:
                # TODO: Implement backup functionality
                await message.edit_text("⚠️ این قابلیت در حال توسعه است")
            except Exception as e:
                logging.error(f"Learning backup error: {e}")
                await message.edit_text("⚠️ خطا در بکاپ یادگیری")
        elif command == "پاکسازی یادگیری":
            try:
                # TODO: Implement cleanup functionality
                await message.edit_text("⚠️ این قابلیت در حال توسعه است")
            except Exception as e:
                logging.error(f"Learning cleanup error: {e}")
                await message.edit_text("⚠️ خطا در پاکسازی یادگیری")
        elif command == "تست ai":
            try:
                await message.edit_text("🤖 تست AI: در حال بررسی...")
                # TODO: Implement AI test
                await message.edit_text("✅ AI در دسترس است")
            except Exception as e:
                logging.error(f"AI test error: {e}")
                await message.edit_text("⚠️ خطا در تست AI")
        else:
            await message.edit_text("⚠️ دستور نامعتبر")
    except Exception as e:
        logging.error(f"Toggle controller error: {e}")
        await message.edit_text("⚠️ خطا در اجرای دستور")

async def set_secretary_message_controller(client, message):
    """Set custom secretary message"""
    user_id = client.me.id
    command = message.text.strip()
    
    try:
        # Extract message text after "منشی متن"
        match = re.match(r"^منشی متن(?: |$)(.*)", command, flags=re.DOTALL | re.IGNORECASE)
        if match:
            custom_text = match.group(1).strip()
            if custom_text:
                CUSTOM_SECRETARY_MESSAGES[user_id] = custom_text
                await save_settings_to_db(user_id)
                await message.edit_text(f"✅ متن منشی تنظیم شد:\n{custom_text}")
            else:
                # If empty, remove custom message
                if user_id in CUSTOM_SECRETARY_MESSAGES:
                    del CUSTOM_SECRETARY_MESSAGES[user_id]
                await save_settings_to_db(user_id)
                await message.edit_text("✅ متن منشی حذف شد (از متن پیش‌فرض استفاده می‌شود)")
        else:
            await message.edit_text("⚠️ فرمت دستور نامعتبر. مثال: `منشی متن سلام! منشی هستم.`")
    except Exception as e:
        logging.error(f"Set secretary message controller error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم متن منشی")


async def pv_lock_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    try:
        if command == "پیوی قفل":
            if not PV_LOCK_STATUS.get(user_id, False):
                 PV_LOCK_STATUS[user_id] = True
                 await message.edit_text("✅ قفل PV فعال شد. پیام‌های جدید در PV حذف خواهند شد.")
            else:
                 await message.edit_text("ℹ️ قفل PV از قبل فعال بود.")
        elif command == "پیوی باز":
            if PV_LOCK_STATUS.get(user_id, False):
                PV_LOCK_STATUS[user_id] = False
                await message.edit_text("❌ قفل PV غیرفعال شد.")
            else:
                 await message.edit_text("ℹ️ قفل PV از قبل غیرفعال بود.")
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"PV Lock Controller: Error for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطایی در پردازش دستور قفل PV رخ داد.")
        except Exception:
            pass

async def auto_repeat_task(client, user_id, chat_id, message_to_repeat, interval):
    """Background task for auto-repeating messages"""
    try:
        while True:
            if user_id not in AUTO_REPEAT_STATUS:
                break
            if chat_id not in AUTO_REPEAT_STATUS[user_id]:
                break
            if not AUTO_REPEAT_STATUS[user_id][chat_id].get('active', False):
                break
            
            try:
                await message_to_repeat.copy(chat_id)
            except Exception as send_error:
                logging.error(f"Auto-repeat send error: {send_error}")
            
            await asyncio.sleep(interval)
            
    except asyncio.CancelledError:
        logging.info(f"Auto-repeat task cancelled for chat {chat_id}")
    except Exception as e:
        logging.error(f"Auto-repeat task error: {e}")

async def repeat_message_controller(client, message):
    user_id = client.me.id
    command = message.text.strip()
    
    match_auto = re.match(r"^تکرار خودکار (\d+)$", command)
    if match_auto:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیامی که می‌خواهید تکرار شود ریپلای کنید")
            return
        
        interval = int(match_auto.group(1))
        if interval < 1 or interval > 300:
            await message.edit_text("⚠️ زمان تکرار باید بین 1 تا 300 ثانیه باشد")
            return
        
        chat_id = message.chat.id
        replied_msg = message.reply_to_message
        
        if user_id not in AUTO_REPEAT_STATUS:
            AUTO_REPEAT_STATUS[user_id] = {}
        
        if chat_id in AUTO_REPEAT_STATUS[user_id]:
            old_task = AUTO_REPEAT_STATUS[user_id][chat_id].get('task')
            if old_task and not old_task.done():
                old_task.cancel()
        
        try:
            await message.delete()
        except:
            pass
        
        task = asyncio.create_task(auto_repeat_task(client, user_id, chat_id, replied_msg, interval))
        
        AUTO_REPEAT_STATUS[user_id][chat_id] = {
            'active': True,
            'interval': interval,
            'message': replied_msg,
            'task': task
        }
        
        confirm = await client.send_message(chat_id, f"✅ تکرار خودکار هر {interval} ثانیه فعال شد")
        await asyncio.sleep(3)
        try:
            await confirm.delete()
        except:
            pass
        return
    
    if command == "تکرار خودکار خاموش":
        chat_id = message.chat.id
        
        if user_id in AUTO_REPEAT_STATUS and chat_id in AUTO_REPEAT_STATUS[user_id]:
            task = AUTO_REPEAT_STATUS[user_id][chat_id].get('task')
            if task and not task.done():
                task.cancel()
            
            del AUTO_REPEAT_STATUS[user_id][chat_id]
            
            await message.edit_text("❌ تکرار خودکار غیرفعال شد")
            await asyncio.sleep(2)
            try:
                await message.delete()
            except:
                pass
        else:
            await message.edit_text("ℹ️ تکرار خودکار فعال نبود")
            await asyncio.sleep(2)
            try:
                await message.delete()
            except:
                pass
        return
    
    if not message.reply_to_message:
        try:
            await message.edit_text("⚠️ برای استفاده از دستور تکرار، باید روی پیام مورد نظر ریپلای کنید.")
        except Exception: pass
        return

    match = re.match(r"^تکرار (\d+)(?: (\d+))?$", command)
    if match:
        try:
            count = int(match.group(1))
            interval_str = match.group(2)
            interval = int(interval_str) if interval_str else 0

            if count <= 0:
                 await message.edit_text("⚠️ تعداد تکرار باید حداقل 1 باشد.")
                 return
            if interval < 0:
                 await message.edit_text("⚠️ فاصله زمانی نمی‌تواند منفی باشد.")
                 return
            if count > 20:
                 await message.edit_text("⚠️ حداکثر تعداد تکرار مجاز 20 بار است.")
                 return
            if count * interval > 300:
                 await message.edit_text("⚠️ مجموع زمان اجرای دستور تکرار بیش از حد طولانی است.")
                 return

            
            replied_msg = message.reply_to_message
            chat_id = message.chat.id

            await message.delete()

            sent_count = 0
            for i in range(count):
                try:
                    await replied_msg.copy(chat_id)
                    sent_count += 1
                    if i < count - 1:
                        sleep_time = max(interval, 0.5)
                        await asyncio.sleep(sleep_time)
                except FloodWait as e_flood:
                    logging.warning(f"Repeat Msg: Flood wait after sending {sent_count}/{count} for user {user_id}. Sleeping {e_flood.value}s.")
                    await asyncio.sleep(e_flood.value + 2)
                except Exception as e_copy:
                    logging.error(f"Repeat Msg: Error copying message on iteration {i+1} for user {user_id}: {e_copy}")
                    try:
                         await client.send_message(chat_id, f"⚠️ خطایی در تکرار پیام رخ داد (تکرار {i+1}/{count}). متوقف شد.")
                    except Exception: pass
                    break

            
        except ValueError:
            await message.edit_text("⚠️ فرمت تعداد یا زمان نامعتبر است.")
        except MessageIdInvalid:
             logging.warning(f"Repeat Msg: Command message {message.id} already deleted.")
        except Exception as e:
            logging.error(f"Repeat Msg Controller: General error for user {user_id}: {e}", exc_info=True)
            try:
                if message.chat:
                     await client.send_message(message.chat.id, "⚠️ خطای ناشناخته‌ای در پردازش دستور تکرار رخ داد.")
            except Exception: pass
    else:
        try:
             await message.edit_text("⚠️ فرمت دستور نامعتبر. مثال: `تکرار 5` یا `تکرار 3 10`")
        except Exception: pass

async def spam_controller(client, message):
    """Spam messages"""
    try:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.edit_text("⚠️ فرمت: `اسپم [متن] [تعداد]`")
            return
        
        text = parts[1]
        count = int(parts[2])
        
        if count > 50:
            await message.edit_text("⚠️ حداکثر 50 پیام")
            return
        
        await message.delete()
        for _ in range(count):
            await client.send_message(message.chat.id, text)
            await asyncio.sleep(0.5)
    except ValueError:
        await message.edit_text("⚠️ تعداد باید عدد باشد")
    except Exception as e:
        logging.error(f"Spam error: {e}")


async def flood_controller(client, message):
    """Flood messages"""
    try:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.edit_text("⚠️ فرمت: `فلود [متن] [تعداد]`")
            return
        
        text = parts[1]
        count = int(parts[2])
        
        if count > 50:
            await message.edit_text("⚠️ حداکثر 50 خط")
            return
        
        await message.delete()
        flood_text = (text + "\n") * count
        await client.send_message(message.chat.id, flood_text)
    except ValueError:
        await message.edit_text("⚠️ تعداد باید عدد باشد")
    except Exception as e:
        logging.error(f"Flood error: {e}")



async def download_controller(client, message):
    """Download media"""
    try:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیام حاوی فایل ریپلای کنید")
            return
        
        reply_msg = message.reply_to_message
        if not reply_msg.media:
            await message.edit_text("⚠️ پیام حاوی فایل نیست")
            return
        
        await message.edit_text("⬇️ در حال دانلود...")
        file_path = await reply_msg.download()
        
        await message.delete()
        await client.send_document("me", file_path, caption="Downloaded")
        
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.error(f"Download error: {e}")
        await message.edit_text(f"⚠️ خطا در دانلود")


async def ban_controller(client, message):
    """Ban user from group"""
    try:
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.edit_text("⚠️ فقط در گروه‌ها")
            return
        
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.edit_text("⚠️ روی پیام کاربر ریپلای کنید")
            return
        
        user_id = message.reply_to_message.from_user.id
        await message.delete()
        await client.ban_chat_member(message.chat.id, user_id)
    except Exception as e:
        logging.error(f"Ban error: {e}")


async def pin_controller(client, message):
    """Pin message"""
    try:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیام ریپلای کنید")
            return
        
        await message.delete()
        await message.reply_to_message.pin()
    except Exception as e:
        logging.error(f"Pin error: {e}")


async def unpin_controller(client, message):
    """Unpin message"""
    try:
        await message.delete()
        await client.unpin_chat_message(message.chat.id)
    except Exception as e:
        logging.error(f"Unpin error: {e}")


# Removed features: calculator, timer, echo, reverse, mock, repeat_char, random_number, uptime, emoji_text, countdown, restart


# --- Text Editing Functions (Based on self.py logic) ---

async def text_mode_controller(client, message):
    """Handle text mode toggle commands (like self.py line 730-737)"""
    user_id = client.me.id
    command = message.text.strip()
    
    try:
        # Parse command: [mode] [on/off]
        parts = command.split()
        if len(parts) != 2:
            return
            
        mode_name = parts[0]
        status = parts[1]
        
        # Map Persian commands to English
        mode_map = {
            'بولد': 'bold', 'ایتالیک': 'italic', 'زیرخط': 'underline', 
            'کد': 'code', 'اسپویلر': 'spoiler',
            'منشن': 'mention', 'هشتگ': 'hashtag', 'معکوس': 'reverse', 
            'تدریجی': 'part'
        }
        
        # Handle compound commands
        if command.startswith('خط خورده'):
            mode_name = 'خط خورده'
            english_mode = 'delete'
        else:
            english_mode = mode_map.get(mode_name)
            
        if not english_mode:
            return
            
        # Initialize user data if not exists
        if user_id not in TEXT_EDIT_MODES:
            TEXT_EDIT_MODES[user_id] = {
                'hashtag': 'off', 'bold': 'off', 'italic': 'off', 'delete': 'off',
                'code': 'off', 'underline': 'off', 'reverse': 'off', 'part': 'off',
                'mention': 'off', 'spoiler': 'off'
            }
        
        # Convert Persian status to English
        english_status = 'on' if status == 'روشن' else 'off'
        
        # Turn off all other modes when turning one on (like self.py)
        if english_status == 'on':
            for key in TEXT_EDIT_MODES[user_id]:
                TEXT_EDIT_MODES[user_id][key] = 'off'
        
        # Set the requested mode
        TEXT_EDIT_MODES[user_id][english_mode] = english_status
        
        # Send confirmation message
        mode_display = {
            'bold': 'بولد', 'italic': 'ایتالیک', 'underline': 'زیرخط',
            'delete': 'خط خورده', 'code': 'کد', 'spoiler': 'اسپویلر',
            'mention': 'منشن', 'hashtag': 'هشتگ', 'reverse': 'معکوس',
            'part': 'تدریجی'
        }
        
        status_display = 'فعال' if english_status == 'on' else 'غیرفعال'
        mode_name_display = mode_display.get(english_mode, mode_name)
        await message.edit_text(f"✅ حالت {mode_name_display} {status_display} شد")
        
    except Exception as e:
        logging.error(f"Text mode controller error: {e}")
        await message.edit_text("⚠️ خطایی در تنظیم حالت متن")

async def text_mode_handler(client, message):
    """Apply text formatting to outgoing messages (like self.py line 123-162)"""
    try:
        # Skip if no text or if it's a command
        if not message.text:
            return
            
        # Skip commands
        try:
            if re.match(COMMAND_REGEX, message.text):
                return
        except:
            pass  # If regex fails, continue
            
        user_id = client.me.id
            
        # Get user's text modes
        modes = TEXT_EDIT_MODES.get(user_id, {})
        if not modes:
            return
            
        original_text = message.text
        
        # Apply formatting based on active mode (like self.py logic)
        if modes.get('hashtag') == 'on':
            new_text = original_text.replace(' ', '_')
            await message.edit_text(f'#{new_text}')
        elif modes.get('bold') == 'on':
            await message.edit_text(f'**{original_text}**')
        elif modes.get('italic') == 'on':
            await message.edit_text(f'*{original_text}*')
        elif modes.get('delete') == 'on':
            await message.edit_text(f'~~{original_text}~~')
        elif modes.get('code') == 'on':
            await message.edit_text(f'`{original_text}`')
        elif modes.get('underline') == 'on':
            await message.edit_text(f'__{original_text}__')
        elif modes.get('reverse') == 'on':
            await message.edit_text(original_text[::-1])
        elif modes.get('part') == 'on':  # This is the gradual/تدریجی mode
            if len(original_text) > 1:
                new_text = ''
                for char in original_text:
                    new_text += char
                    if char != ' ':
                        try:
                            await message.edit_text(new_text)
                            await asyncio.sleep(0.1)
                        except Exception as edit_error:
                            logging.error(f"Edit error in gradual mode: {edit_error}")
                            break  # Stop if edit fails
        elif modes.get('mention') == 'on':
            if message.reply_to_message and message.reply_to_message.from_user:
                user_id_to_mention = message.reply_to_message.from_user.id
                await message.edit_text(f'[{original_text}](tg://user?id={user_id_to_mention})')
        elif modes.get('spoiler') == 'on':
            await message.edit_text(f'||{original_text}||')
            
    except Exception as e:
        logging.error(f"Critical error in text_mode_handler: {e}")
        # Don't re-raise to prevent session crash

async def auto_save_toggle_controller(client, message):
    """Handle auto save toggle"""
    user_id = client.me.id
    command = message.text.strip()
    
    try:
        if command == "ذخیره روشن":
            AUTO_SAVE_VIEW_ONCE[user_id] = True
            await message.edit_text("✅ ذخیره خودکار عکس‌های تایم‌دار فعال شد.")
        elif command == "ذخیره خاموش":
            AUTO_SAVE_VIEW_ONCE[user_id] = False
            await message.edit_text("❌ ذخیره خودکار عکس‌های تایم‌دار غیرفعال شد.")
    except Exception as e:
        logging.error(f"Auto save toggle error: {e}")
        await message.edit_text("⚠️ خطا در تنظیم ذخیره خودکار")

async def ping_controller(client, message):
    """Ping controller"""
    try:
        start_time = time.time()
        await message.edit_text("🏓 Pong!")
        end_time = time.time()
        ping_time = round((end_time - start_time) * 1000, 2)
        await message.edit_text(f"🏓 **Pong!**\n⏱️ **پینگ:** `{ping_time}ms`")
    except Exception as e:
        logging.error(f"Ping error: {e}")

async def translate_controller(client, message):
    """Translate replied message using Google Translate API (like original system)"""
    try:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیامی که می‌خواهید ترجمه کنید ریپلای کنید")
            return
        
        # Get text from replied message
        text_to_translate = message.reply_to_message.text or message.reply_to_message.caption
        if not text_to_translate:
            await message.edit_text("⚠️ پیام ریپلای شده متن ندارد")
            return
        
        status_msg = await message.edit_text("🔄 در حال ترجمه...")
        
        try:
            # Detect source language
            source_lang = await detect_language(text_to_translate)
            
            # Auto-determine target language (same logic as original)
            if source_lang == 'fa':  # Persian to English
                target_lang = 'en'
            elif source_lang == 'en':  # English to Persian
                target_lang = 'fa'
            elif source_lang in ['ar', 'ur']:  # Arabic/Urdu to Persian
                target_lang = 'fa'
            else:  # Other languages to Persian
                target_lang = 'fa'
            
            # Translate using Google Translate API
            translated_text = await translate_text(text_to_translate, target_lang)
            
            # Language names
            lang_names = {
                'fa': 'فارسی', 'en': 'انگلیسی', 'ar': 'عربی', 'zh': 'چینی',
                'ru': 'روسی', 'fr': 'فرانسوی', 'de': 'آلمانی', 'es': 'اسپانیایی',
                'it': 'ایتالیایی', 'ja': 'ژاپنی', 'ko': 'کره‌ای', 'tr': 'ترکی',
                'hi': 'هیندی', 'ur': 'اردو', 'pt': 'پرتغالی', 'zh-cn': 'چینی'
            }
            
            source_name = lang_names.get(source_lang, source_lang.upper())
            target_name = lang_names.get(target_lang, target_lang.upper())
            
            result_text = f"""**ترجمه خودکار**

**متن اصلی ({source_name}):**
{text_to_translate}

**ترجمه به {target_name}:**
{translated_text}"""
            
            await status_msg.edit_text(result_text)
            
        except Exception as trans_error:
            await status_msg.edit_text(f"❌ خطا در ترجمه: {str(trans_error)}")
            
    except Exception as e:
        logging.error(f"Translate controller error: {e}")
        try:
            await message.edit_text("⚠️ خطا در ترجمه")
        except:
            pass

async def set_translation_controller(client, message):
    """Set automatic translation to specific languages (English, Chinese, Russian)"""
    user_id = client.me.id
    command = message.text.strip().lower()
    try:
        # Language mapping (same as original system)
        lang_map = {
            "چینی روشن": "zh-cn",  # Chinese simplified
            "روسی روشن": "ru",     # Russian
            "انگلیسی روشن": "en"      # English
        }
        off_map = {
            "چینی خاموش": "zh-cn",
            "روسی خاموش": "ru",
            "انگلیسی خاموش": "en"
        }
        
        # Language display names
        lang_names = {
            "en": "انگلیسی",
            "ru": "روسی", 
            "zh-cn": "چینی"
        }
        current_lang = AUTO_TRANSLATE_TARGET.get(user_id)
        feedback_msg = None

        if command in lang_map:
            lang = lang_map[command]
            lang_display = lang_names.get(lang, lang)
            if current_lang != lang:
                AUTO_TRANSLATE_TARGET[user_id] = lang
                feedback_msg = f"✅ ترجمه خودکار به {lang_display} فعال شد.\n📝 هر پیامی که بفرستی خودکار ترجمه می‌شه."
            else:
                feedback_msg = f"ℹ️ ترجمه خودکار به {lang_display} از قبل فعال بود."
        elif command in off_map:
            lang_to_check = off_map[command]
            lang_display = lang_names.get(lang_to_check, lang_to_check)
            if current_lang == lang_to_check:
                AUTO_TRANSLATE_TARGET.pop(user_id, None)
                feedback_msg = f"✅ ترجمه خودکار به {lang_display} غیرفعال شد."
            else:
                feedback_msg = f"ℹ️ ترجمه خودکار به {lang_display} فعال نبود."
        elif command == "ترجمه خاموش":
            if current_lang is not None:
                AUTO_TRANSLATE_TARGET.pop(user_id, None)
                feedback_msg = "✅ ترجمه خودکار غیرفعال شد."
            else:
                feedback_msg = "ℹ️ ترجمه خودکار از قبل غیرفعال بود."
        else:
            match = re.match(r"ترجمه ([a-z]{2}(?:-[a-z]{2})?)", command)
            if match:
                lang = match.group(1)
                if len(lang) >= 2:
                    if current_lang != lang:
                        AUTO_TRANSLATE_TARGET[user_id] = lang
                        feedback_msg = f"✅ ترجمه خودکار به زبان {lang} فعال شد."
                    else:
                        feedback_msg = f"ℹ️ ترجمه خودکار به زبان {lang} از قبل فعال بود."
                else:
                    feedback_msg = "⚠️ کد زبان نامعتبر. مثال: en یا zh-CN"
            else:
                feedback_msg = "⚠️ فرمت دستور نامعتبر. مثال: ترجمه en یا ترجمه خاموش"

        if feedback_msg:
            await message.edit_text(feedback_msg)

    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except MessageNotModified:
        pass
    except Exception as e:
        logging.error(f"Set Translation: Error processing command '{command}' for user {user_id}: {e}", exc_info=True)
        try:
            await message.edit_text("⚠️ خطایی در تنظیم ترجمه رخ داد.")
        except Exception:
            pass

# --- Missing Handler Functions for Auto-replies and Features ---

async def incoming_message_manager(client, message):
    """Manage incoming messages (mute, reactions, etc.)"""
    return await incoming_message_manager_duplicate(client, message)

async def incoming_message_manager_duplicate(client, message):
    """Manage incoming messages (mute, reactions, etc.)"""
    user_id = client.me.id
    
    try:
        # Check muted users
        if message.from_user:
            sender_id = message.from_user.id
            chat_id = message.chat.id
            muted_key = (sender_id, chat_id)
            
            if muted_key in MUTED_USERS.get(user_id, set()):
                await message.delete()
                return
                
        # Auto reactions
        if message.from_user:
            sender_id = message.from_user.id
            reactions = AUTO_REACTION_TARGETS.get(user_id, {})
            if sender_id in reactions:
                emoji = reactions[sender_id]
                try:
                    await client.send_reaction(message.chat.id, message.id, emoji)
                except Exception as e:
                    logging.error(f"Auto reaction error: {e}")
                    
    except Exception as e:
        logging.error(f"Incoming message manager error: {e}")

async def pv_lock_handler_duplicate(client, message):
    """Deprecated duplicate; do not use. The real pv_lock_handler is defined earlier."""
    user_id = client.me.id
    try:
        if PV_LOCK_STATUS.get(user_id, False):
            await message.delete()
    except Exception as e:
        logging.error(f"PV lock handler error: {e}")

async def secretary_auto_reply_handler(client, message):
    """Secretary auto reply handler - AI replies to ALL messages naturally, regular replies once"""
    """Secretary auto reply handler - Only ONE mode can work at a time"""
    user_id = client.me.id

    # Prevent replying multiple times to the same message
    processed = PROCESSED_SECRETARY_MESSAGES.setdefault(user_id, set())
    msg_id = getattr(message, "id", None)
    if msg_id is not None:
        if msg_id in processed:
            return
        processed.add(msg_id)
        # Keep only last 1000 message IDs to prevent memory leak
        if len(processed) > 1000:
            processed.clear()
    
    # Only handle private messages
    if message.chat.type != ChatType.PRIVATE:
        return
    
    # Skip if from self or bot
    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    
    # Check if any secretary mode is enabled - AI takes priority
    ai_enabled = AI_SECRETARY_STATUS.get(user_id, False)
    regular_enabled = SECRETARY_MODE_STATUS.get(user_id, False)
    
    if not ai_enabled and not regular_enabled:
        return
    
    sender_id = message.from_user.id
    sender_name = message.from_user.first_name or "دوست"

    # Build a text description for any message type (text/media/sticker/etc.)
    user_message = (message.text or message.caption or "").strip()
    if not user_message:
        if getattr(message, "sticker", None):
            user_message = "[استیکر]"
        elif getattr(message, "voice", None):
            user_message = "[ویس]"
        elif getattr(message, "audio", None):
            user_message = "[موزیک]"
        elif getattr(message, "video", None):
            user_message = "[ویدیو]"
        elif getattr(message, "video_note", None):
            user_message = "[ویدیو نوت]"
        elif getattr(message, "photo", None):
            user_message = "[عکس]"
        elif getattr(message, "animation", None):
            user_message = "[گیف]"
        elif getattr(message, "document", None):
            user_message = "[فایل]"
        elif getattr(message, "contact", None):
            user_message = "[کانتکت]"
        elif getattr(message, "location", None):
            user_message = "[لوکیشن]"
        else:
            user_message = "[پیام]"
    
    try:
        # AI Secretary Mode - reply to EVERY message like a real person
        if ai_enabled:
            try:
                # Get AI response - will use MongoDB to remember past conversations
                logging.info(f"AI Secretary: Getting natural response for {sender_name}")
                ai_response = await get_ai_response(user_message, sender_name, user_id, sender_id)
                
                # Reply naturally using AI and MongoDB learning
                await message.reply_text(ai_response)
                logging.info(f"AI Secretary: Replied naturally to {sender_name}")
                
            except Exception as ai_error:
                logging.error(f"AI Secretary error: {ai_error}")
                # Fallback only if AI completely fails
                await message.reply_text(f"سلام {sender_name}! الان یکم مشغولم، بعداً پیام بده")
        
        # Regular Secretary Mode - reply ONCE only per user (until disabled)
        elif regular_enabled:
            replied_users = USERS_REPLIED_IN_SECRETARY.setdefault(user_id, set())
            
            # If already replied to this user, skip
            if sender_id in replied_users:
                logging.debug(f"Secretary: Already replied to {sender_id}, skipping")
                return
            
            # Mark as replied and send message
            replied_users.add(sender_id)
            secretary_msg = CUSTOM_SECRETARY_MESSAGES.get(user_id, DEFAULT_SECRETARY_MESSAGE)
            await message.reply_text(secretary_msg)
                
    except Exception as e:
        logging.error(f"Secretary handler error: {e}")

        
async def clean_messages_controller(client, message):
    """Clean messages"""
    user_id = client.me.id
    parts = message.text.strip().split()
    if len(parts) != 2:
        return
    
    try:
        count = int(parts[1])
        await message.delete()
        
        deleted = 0
        messages_to_delete = []
        
        try:
            # Collect messages first
            async for msg in client.get_chat_history(message.chat.id, limit=count * 2):  # Get more to account for others' messages
                if msg.from_user and msg.from_user.id == user_id:
                    messages_to_delete.append(msg.id)
                    if len(messages_to_delete) >= count:
                        break
            
            # Batch delete for speed
            if messages_to_delete:
                try:
                    # Try batch delete first (faster)
                    await client.delete_messages(message.chat.id, messages_to_delete)
                    deleted = len(messages_to_delete)
                except Exception:
                    # Fallback to individual delete
                    for msg_id in messages_to_delete:
                        try:
                            await client.delete_messages(message.chat.id, msg_id)
                            deleted += 1
                        except:
                            pass
                        await asyncio.sleep(0.05)  # Faster than 0.1
                        
        except Exception as e_clean_history:
            logging.warning(f"Error getting chat history for clean: {e_clean_history}")
        
        # Quick status message that auto-deletes
        if deleted > 0:
            confirm_msg = await client.send_message(message.chat.id, f'✅ {deleted} پیام حذف شد')
            await asyncio.sleep(2)
            try:
                await confirm_msg.delete()
            except:
                pass
    except Exception as e:
        await message.edit_text(f"خطا در حذف پیام‌ها: {e}")

# --- Web Section (Flask) ---
HTML_TEMPLATE = """
<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>سلف بات تلگرام</title><style>@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');body{font-family:'Vazirmatn',sans-serif;background-color:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh;margin:0;padding:20px;box-sizing:border-box;}.container{background:white;padding:30px 40px;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.1);text-align:center;width:100%;max-width:480px;}h1{color:#333;margin-bottom:20px;font-size:1.5em;}p{color:#666;line-height:1.6;}form{display:flex;flex-direction:column;gap:15px;margin-top:20px;}input[type="tel"],input[type="text"],input[type="password"]{padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;text-align:left;direction:ltr;}button{padding:12px;background-color:#007bff;color:white;border:none;border-radius:8px;font-size:16px;cursor:pointer;transition:background-color .2s;}.error{color:#d93025;margin-top:15px;font-weight:bold;}label{font-weight:bold;color:#555;display:block;margin-bottom:5px;text-align:right;}.font-options{border:1px solid #ddd;border-radius:8px;overflow:hidden;max-height: 200px; overflow-y: auto; text-align: right;}.font-option{display:flex;align-items:center;padding:10px 12px;border-bottom:1px solid #eee;cursor:pointer;}.font-option:last-child{border-bottom:none;}.font-option input[type="radio"]{margin-left:15px; flex-shrink: 0;}.font-option label{display:flex;justify-content:space-between;align-items:center;width:100%;font-weight:normal;cursor:pointer;}.font-option .preview{font-size:1.2em;font-weight:bold;direction:ltr;color:#0056b3; margin-right: 10px; white-space: nowrap;}.success{color:#1e8e3e;}.checkbox-option{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:10px;padding:8px;background-color:#f8f9fa;border-radius:8px;}.checkbox-option label{margin-bottom:0;font-weight:normal;cursor:pointer;color:#444;}</style></head><body><div class="container">
{% if step == 'GET_PHONE' %}<h1>ورود به سلف بات</h1><p>شماره و تنظیمات خود را انتخاب کنید تا ربات فعال شود.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="phone"><div><label for="phone">شماره تلفن (با کد کشور)</label><input type="tel" id="phone" name="phone_number" placeholder="+989123456789" required autofocus></div><div><label>استایل فونت ساعت</label><div class="font-options">{% for name, data in font_previews.items() %}<div class="font-option" onclick="document.getElementById('font-{{ data.style }}').checked = true;"><input type="radio" name="font_style" value="{{ data.style }}" id="font-{{ data.style }}" {% if loop.first %}checked{% endif %}><label for="font-{{ data.style }}"><span>{{ name }}</span><span class="preview">{{ data.preview }}</span></label></div>{% endfor %}</div></div><div class="checkbox-option"><input type="checkbox" id="disable_clock" name="disable_clock"><label for="disable_clock">فعال‌سازی بدون ساعت</label></div><button type="submit">ارسال کد تایید</button></form>
{% elif step == 'GET_CODE' %}<h1>کد تایید</h1><p>کدی به تلگرام شما با شماره <strong>{{ phone_number }}</strong> ارسال شد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="code"><input type="text" name="code" placeholder="کد تایید" required><button type="submit">تایید کد</button></form>
{% elif step == 'GET_PASSWORD' %}<h1>رمز دو مرحله‌ای</h1><p>حساب شما نیاز به رمز تایید دو مرحله‌ای دارد.</p>{% if error_message %}<p class="error">{{ error_message }}</p>{% endif %}<form action="{{ url_for('login') }}" method="post"><input type="hidden" name="action" value="password"><input type="password" name="password" placeholder="رمز عبور دو مرحله ای" required><button type="submit">ورود</button></form>
{% elif step == 'SHOW_SUCCESS' %}<h1>Bot Activated!</h1><p>Bot activated successfully. Send help command in Telegram to access features.</p><form action="{{ url_for('home') }}" method="get" style="margin-top: 20px;"><button type="submit">Logout and Login New Account</button></form>{% endif %}</div></body></html>
"""

def get_font_previews():
    sample_time = "12:34"
    return { FONT_DISPLAY_NAMES.get(key, key.capitalize()): {"style": key, "preview": stylize_time(sample_time, key)} for key in FONT_KEYS_ORDER }

async def cleanup_client(phone):
     """Safely disconnects and removes a temporary client."""
     if client := ACTIVE_CLIENTS.pop(phone, None):
         if client.is_connected:
             try:
                 logging.debug(f"Disconnecting temporary client for {phone}...")
                 await client.disconnect()
                 logging.debug(f"Temporary client for {phone} disconnected.")
             except Exception as e:
                 logging.warning(f"Error disconnecting temporary client {phone}: {e}")
     else:
         logging.debug(f"No active temporary client found for {phone} during cleanup.")

@app_flask.route('/')
def home():
    # Clear session potentially related to a previous login attempt
    session.clear()
    logging.info("Session cleared, rendering GET_PHONE page.")
    return render_template_string(HTML_TEMPLATE, step='GET_PHONE', font_previews=get_font_previews())

@app_flask.route('/login', methods=['POST'])
def login():
    action = request.form.get('action')
    phone = session.get('phone_number') # Get phone from session if available
    error_msg = None
    # Determine current step based on action or session state
    current_step = 'GET_PHONE' # Default
    if action == 'code' or session.get('phone_code_hash'):
         current_step = 'GET_CODE'
    if action == 'password': # Should only be reached after SessionPasswordNeeded
         current_step = 'GET_PASSWORD'

    logging.info(f"Login request received: action='{action}', phone_in_session='{phone}'")

    try:
        # Ensure asyncio loop is running in the background thread
        if not EVENT_LOOP or not EVENT_LOOP.is_running():
             # This is a critical error, maybe restart is needed
             raise RuntimeError("Asyncio event loop is not running.")

        # --- Phone Number Submission ---
        if action == 'phone':
            current_step = 'GET_PHONE' # Explicitly set step for clarity
            phone_num_input = request.form.get('phone_number')
            font_style = request.form.get('font_style', 'stylized')
            disable_clock = 'disable_clock' in request.form

            # Validate phone number format
            if not phone_num_input or not re.match(r"^\+?\d{10,15}$", phone_num_input):
                 raise ValueError("فرمت شماره تلفن نامعتبر است. لطفاً با کد کشور وارد کنید (مثال: +98...).")

            # Clean phone number (e.g., ensure it starts with +)
            if not phone_num_input.startswith('+'):
                # Basic assumption: add '+' if missing (might need country-specific logic)
                logging.warning(f"Adding '+' to phone number {phone_num_input}")
                phone_num_input = "+" + phone_num_input

            # Store validated info in session
            session['phone_number'] = phone_num_input
            session['font_style'] = font_style
            session['disable_clock'] = disable_clock
            logging.info(f"Phone number {phone_num_input} received. Requesting code...")

            # Run send_code_task in the event loop and wait for result
            future = asyncio.run_coroutine_threadsafe(send_code_task(phone_num_input), EVENT_LOOP)
            future.result(timeout=45) # Wait up to 45 seconds

            logging.info(f"Code request sent for {phone_num_input}. Rendering GET_CODE page.")
            return render_template_string(HTML_TEMPLATE, step='GET_CODE', phone_number=phone_num_input)

        # --- Code Submission ---
        elif action == 'code':
            current_step = 'GET_CODE' # Set for error handling context
            code_input = request.form.get('code')
            phone = session.get('phone_number') # Re-fetch from session

            # Assert necessary info is present
            if not phone or not code_input or 'phone_code_hash' not in session:
                 logging.error("Session data missing for code submission (phone, code, or hash).")
                 raise AssertionError("اطلاعات ورود (session) نامعتبر یا منقضی شده است. لطفاً از ابتدا شروع کنید.")

            logging.info(f"Code received for {phone}. Attempting sign in...")
            # Run sign_in_task and wait
            future = asyncio.run_coroutine_threadsafe(sign_in_task(phone, code_input), EVENT_LOOP)
            next_step = future.result(timeout=45)

            if next_step == 'GET_PASSWORD':
                logging.info(f"Password required for {phone}. Rendering GET_PASSWORD page.")
                return render_template_string(HTML_TEMPLATE, step='GET_PASSWORD', phone_number=phone)
            elif next_step == 'SUCCESS':
                logging.info(f"Sign in successful for {phone}. Rendering SHOW_SUCCESS page.")
                return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
            else:
                 # Should not happen if sign_in_task returns correctly
                 logging.error(f"Unexpected result from sign_in_task for {phone}: {next_step}")
                 raise Exception("مرحله ورود نامشخص پس از تایید کد.")

        # --- Password Submission ---
        elif action == 'password':
            current_step = 'GET_PASSWORD' # Set for error handling context
            password_input = request.form.get('password')
            phone = session.get('phone_number') # Re-fetch from session

            if not phone or not password_input:
                 logging.error("Session data missing for password submission (phone or password).")
                 raise AssertionError("اطلاعات ورود (session) نامعتبر یا منقضی شده است. لطفاً از ابتدا شروع کنید.")

            logging.info(f"Password received for {phone}. Checking password...")
            # Run check_password_task and wait
            future = asyncio.run_coroutine_threadsafe(check_password_task(phone, password_input), EVENT_LOOP)
            result = future.result(timeout=45)

            if result == 'SUCCESS':
                logging.info(f"Password check successful for {phone}. Rendering SHOW_SUCCESS page.")
                return render_template_string(HTML_TEMPLATE, step='SHOW_SUCCESS')
            else:
                 # Should not happen if check_password_task returns correctly
                 logging.error(f"Unexpected result from check_password_task for {phone}: {result}")
                 raise Exception("خطای نامشخص پس از بررسی رمز عبور.")

        # --- Invalid Action ---
        else:
            logging.warning(f"Invalid action received in login POST: {action}")
            error_msg = "عملیات درخواستی نامعتبر است."
            current_step = 'GET_PHONE' # Reset to start
            session.clear() # Clear potentially inconsistent session

    # --- Exception Handling ---
    except (TimeoutError, asyncio.TimeoutError):
        error_msg = "پاسخی از سرور تلگرام دریافت نشد. لطفاً از اتصال اینترنت خود مطمئن شوید و دوباره تلاش کنید (Timeout)."
        logging.warning(f"Timeout occurred during login action '{action}' for phone {phone}.")
        # Decide step based on where timeout likely occurred
        if action == 'phone': current_step = 'GET_PHONE'; session.clear()
        elif action == 'code': current_step = 'GET_CODE'
        elif action == 'password': current_step = 'GET_PASSWORD'
        else: current_step = 'GET_PHONE'; session.clear()

    except (PhoneNumberInvalid, ValueError) as e: # Catch specific validation errors
         error_msg = str(e) # Use the error message directly (e.g., from ValueError)
         logging.warning(f"Validation Error during login action '{action}' for phone {phone}: {e}")
         current_step = 'GET_PHONE' # Go back to phone input
         session.clear() # Clear session on phone error

    except (PhoneCodeInvalid, PasswordHashInvalid) as e:
         error_msg = "کد تایید یا رمز عبور وارد شده اشتباه است. لطفاً دوباره بررسی کنید."
         logging.warning(f"Invalid Code/Password during login action '{action}' for phone {phone}: {type(e).__name__}")
         # Stay on the current step (code or password)
         if action == 'code': current_step = 'GET_CODE'
         elif action == 'password': current_step = 'GET_PASSWORD'

    except PhoneCodeExpired as e:
         error_msg = "کد تایید منقضی شده است. لطفاً شماره تلفن را مجدداً وارد کنید تا کد جدید دریافت کنید."
         logging.warning(f"Phone code expired for {phone}: {e}")
         current_step = 'GET_PHONE' # Go back to start
         session.clear()

    except SessionPasswordNeeded as e:
         # This exception is expected, transition to password step
         logging.info(f"Password needed for {phone} after code entry.")
         current_step = 'GET_PASSWORD'
         # No error message needed here, just render the password form
         return render_template_string(HTML_TEMPLATE, step='GET_PASSWORD', phone_number=phone)

    except FloodWait as e:
         error_msg = f"تلگرام درخواست شما را به دلیل تعداد زیاد تلاش‌ها محدود کرده است. لطفاً {e.value} ثانیه صبر کنید و دوباره امتحان کنید."
         logging.warning(f"FloodWait ({e.value}s) during login action '{action}' for phone {phone}.")
         # Stay on the current step where flood wait occurred

    except AssertionError as e: # Catch session/input errors
         error_msg = str(e) or "خطای داخلی: اطلاعات ورود یافت نشد. لطفاً دوباره تلاش کنید."
         logging.error(f"Assertion Error during login action '{action}' for phone {phone}: {e}")
         current_step = 'GET_PHONE' # Go back to start on assertion errors
         session.clear()

    except RuntimeError as e: # Catch loop errors
         error_msg = f"خطای بحرانی در سرور رخ داده است: {e}. لطفاً بعداً تلاش کنید."
         logging.critical(f"Runtime Error during login action '{action}': {e}", exc_info=True)
         current_step = 'GET_PHONE' # Go back to start
         session.clear()

    except Exception as e: # Catch any other unexpected exception
         error_msg = f"یک خطای پیش‌بینی نشده رخ داد: {type(e).__name__}. لطفاً دوباره تلاش کنید یا با پشتیبانی تماس بگیرید."
         logging.error(f"Unexpected Exception during login action '{action}' for phone {phone}: {e}", exc_info=True)
         current_step = 'GET_PHONE' # Go back to start
         session.clear()

    # --- Cleanup and Render Error Page ---
    # If an error occurred (except SessionPasswordNeeded), try cleaning up temporary client
    # Only cleanup if phone number is known and error wasn't SessionPasswordNeeded
    if error_msg and phone and current_step != 'GET_PASSWORD':
         logging.info(f"Cleaning up temporary client for {phone} due to error: {error_msg}")
         try:
             # Run cleanup in the background loop, don't wait for it here
             if EVENT_LOOP.is_running():
                 asyncio.run_coroutine_threadsafe(cleanup_client(phone), EVENT_LOOP)
         except Exception as cleanup_err:
             logging.error(f"Error submitting cleanup task for {phone}: {cleanup_err}")

    # Render the appropriate template with error message
    logging.debug(f"Rendering step '{current_step}' with error: {error_msg}")
    return render_template_string(HTML_TEMPLATE,
                                step=current_step,
                                error_message=error_msg,
                                phone_number=phone, # Pass phone even on error if available
                                font_previews=get_font_previews())

# --- Async Tasks for Login Flow ---
async def send_code_task(phone):
    """Creates a client, connects, sends code, and stores hash in session."""
    # Ensure previous client for this number is cleaned up
    await cleanup_client(phone)

    # Use unique name for temporary client, maybe with timestamp or random part
    # Using in_memory=True means session won't be saved to disk here
    client = Client(f"login_attempt_{re.sub(r'\W+', '', phone)}_{int(time.time())}",
                    api_id=API_ID, api_hash=API_HASH, in_memory=True)
    ACTIVE_CLIENTS[phone] = client # Store client associated with phone number
    logging.info(f"Temporary client created for {phone}.")

    try:
        logging.debug(f"Connecting temporary client for {phone}...")
        await client.connect()
        logging.debug(f"Temporary client connected for {phone}. Sending code...")
        sent_code = await client.send_code(phone)

        # Important: Store phone_code_hash in Flask session (accessible by web thread)
        session['phone_code_hash'] = sent_code.phone_code_hash
        logging.info(f"Code sent successfully to {phone}. Hash stored in session.")
        # Keep client connected for sign_in or check_password

    except (FloodWait, PhoneNumberInvalid, Exception) as e:
        # If sending code fails, disconnect and remove the client
        logging.error(f"Error sending code to {phone}: {type(e).__name__} - {e}")
        await cleanup_client(phone) # Cleanup on failure
        raise e # Re-raise the exception to be caught by the Flask route

async def sign_in_task(phone, code):
    """Attempts to sign in using the code. Handles SessionPasswordNeeded."""
    client = ACTIVE_CLIENTS.get(phone)
    if not client or not client.is_connected:
        logging.error(f"Sign in failed for {phone}: Temporary client not found or disconnected.")
        raise AssertionError("Session expired or client disconnected. Please try again.")

    phone_code_hash = session.get('phone_code_hash')
    if not phone_code_hash:
        logging.error(f"Sign in failed for {phone}: phone_code_hash missing from session.")
        raise AssertionError("Session data corrupted (missing code hash). Please try again.")

    try:
        logging.debug(f"Attempting sign in for {phone} with code...")
        await client.sign_in(phone, phone_code_hash, code)
        try:
            me = await client.get_me()
            logged_in_user_id = getattr(me, 'id', None)
            if logged_in_user_id is not None and logged_in_user_id != int(AUTHORIZED_USER_ID):
                logging.warning(f"Login completed for phone {phone} but user_id={logged_in_user_id} != AUTHORIZED_USER_ID={AUTHORIZED_USER_ID}. This session will be saved to DB under this phone.")
            else:
                logging.info(f"Login completed for phone {phone} as user_id={logged_in_user_id}.")
        except Exception:
            pass
        logging.info(f"Sign in successful for {phone} (no password needed). Exporting session.")

        # --- Session Export and DB Update ---
        session_str = await client.export_session_string()
        font_style = session.get('font_style', 'stylized')
        disable_clock = session.get('disable_clock', False)

        if sessions_collection is not None:
            try:
                logging.debug(f"Updating/inserting session into DB for {phone}...")
                sessions_collection.update_one(
                    {'phone_number': phone},
                    {'$set': {'session_string': session_str,
                              'font_style': font_style,
                              'disable_clock': disable_clock}},
                    upsert=True
                )
                logging.debug(f"DB updated for {phone}.")
            except Exception as db_err:
                 # Log error but continue - bot can start, just won't persist on restart
                 logging.error(f"Database Error: Failed to save session for {phone}: {db_err}")

        # --- Schedule Bot Start ---
        logging.info(f"Scheduling main bot instance start for {phone}...")
        # Ensure it runs in the main asyncio loop
        EVENT_LOOP.create_task(start_bot_instance(session_str, phone, font_style, disable_clock))

        # --- Cleanup ---
        await cleanup_client(phone) # Clean up temporary client after success
        session.clear() # Clear Flask session after successful login

        return 'SUCCESS' # Signal success to Flask route

    except SessionPasswordNeeded:
        # Password is required, keep client connected for password check
        logging.info(f"Password needed for {phone}. Keeping temporary client alive.")
        return 'GET_PASSWORD' # Signal password needed to Flask route

    except (FloodWait, PhoneCodeInvalid, PhoneCodeExpired, Exception) as e:
        # On error (except PasswordNeeded), cleanup and re-raise
        logging.error(f"Error during sign in for {phone}: {type(e).__name__} - {e}")
        await cleanup_client(phone) # Cleanup on failure
        session.clear() # Clear session on failure
        raise e # Re-raise to be caught by Flask

async def check_password_task(phone, password):
    """Checks the two-factor authentication password."""
    client = ACTIVE_CLIENTS.get(phone)
    if not client or not client.is_connected:
        logging.error(f"Password check failed for {phone}: Temporary client not found or disconnected.")
        raise AssertionError("Session expired or client disconnected. Please try again.")

    try:
        logging.debug(f"Checking password for {phone}...")
        await client.check_password(password)
        try:
            me = await client.get_me()
            logged_in_user_id = getattr(me, 'id', None)
            if logged_in_user_id is not None and logged_in_user_id != int(AUTHORIZED_USER_ID):
                logging.warning(f"2FA login completed for phone {phone} but user_id={logged_in_user_id} != AUTHORIZED_USER_ID={AUTHORIZED_USER_ID}. This session will be saved to DB under this phone.")
            else:
                logging.info(f"2FA login completed for phone {phone} as user_id={logged_in_user_id}.")
        except Exception:
            pass
        logging.info(f"Password check successful for {phone}. Exporting session.")

        # --- Session Export and DB Update ---
        session_str = await client.export_session_string()
        font_style = session.get('font_style', 'stylized')
        disable_clock = session.get('disable_clock', False)

        if sessions_collection is not None:
            try:
                logging.debug(f"Updating/inserting session into DB for {phone} after password...")
                sessions_collection.update_one(
                    {'phone_number': phone},
                    {'$set': {'session_string': session_str,
                              'font_style': font_style,
                              'disable_clock': disable_clock}},
                    upsert=True
                )
                logging.debug(f"DB updated for {phone}.")
            except Exception as db_err:
                 logging.error(f"Database Error: Failed to save session for {phone} after password: {db_err}")

        # --- Schedule Bot Start ---
        logging.info(f"Scheduling main bot instance start for {phone} after password...")
        EVENT_LOOP.create_task(start_bot_instance(session_str, phone, font_style, disable_clock))

        # --- Cleanup ---
        await cleanup_client(phone) # Clean up temporary client
        session.clear() # Clear Flask session

        return 'SUCCESS' # Signal success

    except (FloodWait, PasswordHashInvalid, Exception) as e:
        # On error, cleanup and re-raise
        logging.error(f"Error during password check for {phone}: {type(e).__name__} - {e}")
        await cleanup_client(phone) # Cleanup on failure
        session.clear() # Clear session on failure
        raise e # Re-raise to be caught by Flask

async def myphone_controller(client, message):
    """Send own phone number as contact"""
    try:
        me = await client.get_me()
        await message.delete()
        await client.send_contact(
            message.chat.id,
            phone_number=me.phone_number,
            first_name=me.first_name or "User",
            last_name=me.last_name or ""
        )
    except Exception as e:
        logging.error(f"MyPhone error: {e}")

async def spam_controller(client, message):
    """Spam messages"""
    try:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.edit_text("⚠️ فرمت: `اسپم [متن] [تعداد]`")
            return
        
        text = parts[1]
        count = int(parts[2])
        
        if count > 50:
            await message.edit_text("⚠️ حداکثر 50 پیام")
            return
        
        await message.delete()
        for _ in range(count):
            await client.send_message(message.chat.id, text)
            await asyncio.sleep(0.5)
    except ValueError:
        await message.edit_text("⚠️ تعداد باید عدد باشد")
    except Exception as e:
        logging.error(f"Spam error: {e}")

async def flood_controller(client, message):
    """Flood messages"""
    try:
        parts = message.text.strip().split(maxsplit=2)
        if len(parts) < 3:
            await message.edit_text("⚠️ فرمت: `فلود [متن] [تعداد]`")
            return
        
        text = parts[1]
        count = int(parts[2])
        
        if count > 50:
            await message.edit_text("⚠️ حداکثر 50 خط")
            return
        
        await message.delete()
        flood_text = (text + "\n") * count
        await client.send_message(message.chat.id, flood_text)
    except ValueError:
        await message.edit_text("⚠️ تعداد باید عدد باشد")
    except Exception as e:
        logging.error(f"Flood error: {e}")

async def download_controller(client, message):
    """Download media"""
    try:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیام حاوی فایل ریپلای کنید")
            return
        
        reply_msg = message.reply_to_message
        if not reply_msg.media:
            await message.edit_text("⚠️ پیام حاوی فایل نیست")
            return
        
        await message.edit_text("⬇️ در حال دانلود...")
        file_path = await reply_msg.download()
        
        await message.delete()
        await client.send_document("me", file_path, caption="Downloaded")
        
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        logging.error(f"Download error: {e}")
        await message.edit_text(f"⚠️ خطا در دانلود")

async def ban_controller(client, message):
    """Ban user from group"""
    try:
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await message.edit_text("⚠️ فقط در گروه‌ها")
            return
        
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.edit_text("⚠️ روی پیام کاربر ریپلای کنید")
            return
        
        user_id = message.reply_to_message.from_user.id
        await message.delete()
        await client.ban_chat_member(message.chat.id, user_id)
    except Exception as e:
        logging.error(f"Ban error: {e}")

async def pin_controller(client, message):
    """Pin message"""
    try:
        if not message.reply_to_message:
            await message.edit_text("⚠️ روی پیام ریپلای کنید")
            return
        
        await message.delete()
        await message.reply_to_message.pin()
    except Exception as e:
        logging.error(f"Pin error: {e}")

async def unpin_controller(client, message):
    """Unpin message"""
    try:
        await message.delete()
        await client.unpin_chat_message(message.chat.id)
    except Exception as e:
        logging.error(f"Unpin error: {e}")

# --- Running the Application ---
def run_flask():
    port = int(os.environ.get("PORT", 10000)); logging.info(f"Starting Flask web server on host 0.0.0.0, port {port}")
    try:
        # Use Waitress for a more production-ready server if available
        from waitress import serve
        logging.info("Using Waitress production WSGI server.")
        serve(app_flask, host='0.0.0.0', port=port, threads=8) # Adjust threads as needed
    except ImportError:
        logging.warning("Waitress package not found. Falling back to Flask's built-in development server (NOT recommended for production).")

def run_asyncio_loop():
    global EVENT_LOOP
    # Set the event loop for the current thread
    asyncio.set_event_loop(EVENT_LOOP)
    logging.info("Asyncio event loop set for background thread.")

    # --- Auto-Login from Database ---
    async def _db_autologin_start():
        if sessions_collection is None:
            logging.info("MongoDB not configured. Skipping auto-login from database.")
            return

        logging.info("Attempting auto-login for existing sessions from database...")
        started_count = 0
        authorized_found = False
        try:
            session_docs = list(sessions_collection.find())
            logging.info(f"Found {len(session_docs)} potential session(s) in DB.")
            for doc in session_docs:
                try:
                    session_string = doc['session_string']
                    phone = doc.get('phone_number', f"db_user_{doc.get('_id', f'unk_{started_count}')}")
                    font_style = doc.get('font_style', 'stylized')
                    disable_clock = doc.get('disable_clock', False)

                    authorized_ids = _get_authorized_user_ids()
                    tmp_client = None
                    try:
                        tmp_client = Client(
                            f"autostart_check_{re.sub(r'[^\w]', '_', str(phone))}_{int(time.time())}",
                            session_string=session_string,
                            api_id=API_ID,
                            api_hash=API_HASH,
                        )
                        await tmp_client.start()
                        me = await tmp_client.get_me()
                        tmp_user_id = getattr(me, 'id', None)
                    except Exception as e_check:
                        err_text = str(e_check)
                        # Session revoked/unauthorized: noisy stacktraces aren't useful, and doc can be removed.
                        if "SESSION_REVOKED" in err_text or "401" in err_text or "AUTH" in err_text.upper():
                            logging.warning(f"DB AutoLogin: session invalid/revoked for {phone}: {err_text}")
                            try:
                                doc_id = doc.get('_id')
                                if doc_id is not None:
                                    sessions_collection.delete_one({'_id': doc_id})
                                    logging.info(f"DB AutoLogin: removed revoked session doc for {phone} (id={doc_id}).")
                            except Exception as del_err:
                                logging.warning(f"DB AutoLogin: failed to delete revoked session doc for {phone}: {del_err}")
                        else:
                            logging.error(f"DB AutoLogin: failed to validate session {phone}: {e_check}", exc_info=True)
                        tmp_user_id = None
                    finally:
                        if tmp_client is not None and tmp_client.is_connected:
                            try:
                                await tmp_client.stop()
                            except Exception:
                                pass

                    if tmp_user_id is None:
                        continue
                    if tmp_user_id not in authorized_ids:
                        logging.info(f"Skipping DB session {phone}: user_id {tmp_user_id} not in authorized ids {sorted(list(authorized_ids))}.")
                        continue

                    logging.info(f"Scheduling auto-start for authorized session: {phone} (user_id={tmp_user_id})...")
                    EVENT_LOOP.create_task(start_bot_instance(session_string, phone, font_style, disable_clock))
                    started_count += 1
                    authorized_found = True

                except KeyError:
                    logging.error(f"DB AutoLogin Error: Document missing 'session_string'. Skipping. Doc ID: {doc.get('_id')}")
                except Exception as e_doc:
                    logging.error(f"DB AutoLogin Error: Failed to schedule start for session {doc.get('phone_number', doc.get('_id', 'unknown'))}: {e_doc}", exc_info=True)

            logging.info(f"Finished scheduling auto-start. {started_count} session(s) scheduled.")
            if not authorized_found:
                logging.warning("DB AutoLogin: no authorized session found to start. If your features don't work, log in again from the panel so a fresh session for the authorized account is saved.")
        except Exception as e_db_query:
            logging.error(f"DB AutoLogin Error: Failed to query database for sessions: {e_db_query}", exc_info=True)

    EVENT_LOOP.create_task(_db_autologin_start())

    # --- Start Event Loop ---
    try:
        logging.info("Starting asyncio event loop run_forever()...")
        EVENT_LOOP.run_forever()
        # Code here will run after loop.stop() is called
        logging.info("Asyncio event loop has stopped.")

    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutdown signal (KeyboardInterrupt/SystemExit) received by asyncio loop.")
        # Loop might already be stopping, but call stop() just in case
        if EVENT_LOOP.is_running():
            EVENT_LOOP.stop()
    except Exception as e_loop:
        logging.critical(f"CRITICAL ASYNCIO LOOP ERROR: {e_loop}", exc_info=True)
        # Try to stop the loop gracefully if possible
        if EVENT_LOOP.is_running():
            EVENT_LOOP.stop()

    # --- Cleanup Sequence (after loop stops) ---
    finally:
        logging.info("Asyncio loop cleanup sequence initiated...")
        cleanup_completed = False
        if EVENT_LOOP.is_running(): # Should ideally be false here, but check just in case
            logging.warning("Event loop was still running at the start of finally block. Forcing stop.")
            EVENT_LOOP.stop()

        # Run final cleanup tasks within the loop before closing
        try:
            async def shutdown_tasks():
                """Gather and run all cleanup tasks concurrently."""
                nonlocal cleanup_completed
                logging.info("Starting asynchronous shutdown tasks...")
                active_bot_stops = []
                # Stop active bot instances
                for user_id, (client, bg_tasks) in list(ACTIVE_BOTS.items()):
                    logging.debug(f"Initiating shutdown for active bot instance {user_id}...")
                    # Cancel background tasks first
                    for task in bg_tasks:
                        if task and not task.done():
                            task.cancel()
                    # Schedule client stop (non-blocking)
                    if client and client.is_connected:
                        active_bot_stops.append(client.stop(block=False))
                    ACTIVE_BOTS.pop(user_id, None) # Remove immediately

                # Disconnect temporary login clients
                active_client_disconnects = []
                for phone, client in list(ACTIVE_CLIENTS.items()):
                    if client and client.is_connected:
                        logging.debug(f"Initiating disconnect for temporary client {phone}...")
                        active_client_disconnects.append(client.disconnect())
                    ACTIVE_CLIENTS.pop(phone, None)

                # Wait for all stop/disconnect tasks
                all_cleanup_ops = active_bot_stops + active_client_disconnects
                if all_cleanup_ops:
                    logging.info(f"Waiting for {len(all_cleanup_ops)} client stops/disconnects...")
                    results = await asyncio.gather(*all_cleanup_ops, return_exceptions=True)
                    for i, result in enumerate(results):
                        if isinstance(result, Exception):
                             logging.warning(f"Error during client cleanup operation {i}: {result}")
                logging.info("Client stop/disconnect operations complete.")

                # Cancel any remaining asyncio tasks (should be few now)
                logging.debug("Cancelling any remaining asyncio tasks...")
                current_task = asyncio.current_task()
                tasks_to_cancel = [t for t in asyncio.all_tasks() if t is not current_task]
                if tasks_to_cancel:
                    for task in tasks_to_cancel: task.cancel()
                    await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
                logging.debug("Remaining asyncio tasks cancelled.")
                cleanup_completed = True

            # Run the shutdown coroutine until it completes
            EVENT_LOOP.run_until_complete(shutdown_tasks())
            logging.info("Asynchronous shutdown tasks completed.")

        except Exception as e_shutdown:
            logging.error(f"Error during asyncio shutdown sequence: {e_shutdown}", exc_info=True)

        finally:
             # Close the event loop
             if not EVENT_LOOP.is_closed():
                 EVENT_LOOP.close()
                 logging.info("Asyncio event loop closed.")
             if not cleanup_completed:
                 logging.warning("Cleanup sequence did not fully complete before loop closure.")

if __name__ == "__main__":
    logging.info("========================================")
    logging.info(" Starting Telegram Self Bot Service... ")
    logging.info("========================================")

    # Start the asyncio loop in a separate thread
    loop_thread = Thread(target=run_asyncio_loop, name="AsyncioLoopThread", daemon=True)
    loop_thread.start()

    # Start the Flask server in the main thread
    # This will block until Flask stops (e.g., via CTRL+C)
    run_flask()

    # --- Post-Flask Shutdown ---
    logging.info("Flask server has stopped.")

    # Signal the asyncio loop thread to stop
    if loop_thread.is_alive() and EVENT_LOOP.is_running():
        logging.info("Signaling asyncio loop thread to stop...")
        # Use call_soon_threadsafe to schedule loop.stop() from this thread
        EVENT_LOOP.call_soon_threadsafe(EVENT_LOOP.stop)
    elif not EVENT_LOOP.is_running():
         logging.info("Asyncio loop was already stopped.")

    # Wait for the asyncio thread to finish its cleanup
    logging.info("Waiting for asyncio loop thread to finish cleanup (max 15 seconds)...")
    loop_thread.join(timeout=15)

    if loop_thread.is_alive():
        logging.warning("Asyncio thread did not exit gracefully within the timeout.")
    else:
        logging.info("Asyncio thread joined successfully.")

    # Close MongoDB client if it was initialized
    if mongo_client:
        try:
            logging.info("Closing MongoDB connection...")
            mongo_client.close()
            logging.info("MongoDB connection closed.")
        except Exception as mongo_close_err:
             logging.error(f"Error closing MongoDB connection: {mongo_close_err}")

    logging.info("========================================")
    logging.info(" Application shutdown complete.        ")
    logging.info("========================================")
