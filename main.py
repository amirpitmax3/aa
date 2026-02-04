import asyncio
import os
import logging
import re
import aiohttp
import time
import json
import random
from urllib.parse import quote, unquote, urlparse, parse_qs, urljoin
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
    ReactionInvalid, MessageIdInvalid, ChatSendInlineForbidden
)
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask
from threading import Thread
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import certifi
import pyrogram.utils 

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
BOT_TOKEN = "8349353893:AAE6n_bcK1GfDEoMlbyHcBS0A7EInD5-x8A"

# --- Cloudflare AI Configuration ---
CLOUDFLARE_ACCOUNT_ID = "ce2e4697a5504848b6f18b15dda6eee9"
CLOUDFLARE_API_TOKEN = "oG_r_b0Y-7exOWXcrg9MlLa1fPW9fkepcGU-DfhW"
CLOUDFLARE_AI_MODEL = "@cf/meta/llama-3.1-70b-instruct"

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://amirpitmax1_db_user:DvkIhwWzUfBT4L5j@cluster0.kdvbr3p.mongodb.net/?appName=Cluster0"
mongo_client = None
sessions_collection = None
learning_collection = None 

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot_full']
        sessions_collection = db['sessions']
        learning_collection = db['ai_learning']
        logging.info("Successfully connected to MongoDB!")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        mongo_client = None
        sessions_collection = None
else:
    logging.warning("MONGO_URI is not configured.")

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
    "fullwidth":    {'0':'０','1':'１','2':'２','3':'３','4':'４','5':'５','6':'۶','7':'７','8':'۸','9':'۹',':':'：'},
    "filled":       {'0':'⓿','1':'❶','2':'❷','3':'❸','4':'❹','5':'❺','6':'❻','7':'❼','8':'❽','9':'❾',':':':'},
    "sans":         {'0':'𝟢','1':'𝟣','2':'𝟤','3':'𝟥','4':'𝟦','5':'𝟧','6':'𝟨','7':'𝟩','8':'𝟪','9':'𝟫',':':':'},
    "inverted":     {'0':'0','1':'Ɩ','2':'ᄅ','3':'Ɛ','4':'ㄣ','5':'ϛ','6':'9','7':'ㄥ','8':'8','9':'6',':':':'},
}
FONT_KEYS_ORDER = ["cursive", "stylized", "doublestruck", "monospace", "normal", "circled", "fullwidth", "filled", "sans", "inverted"]

ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

# --- Feature Variables (Default Values) ---
ENEMY_REPLIES = ["ببخشید متوجه نشدم؟", "داری فشار میخوری؟", "برو پیش بزرگترت", "سطحت پایینه", "😂😂", "اوکی بای"] 
SECRETARY_REPLY_MESSAGE = "سلام! منشی هوشمند هستم. پیام شما دریافت شد."

# --- Help Text ---
HELP_TEXT = """
**[ 🛠 دستورات دستی و ریپلای ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی (ساعت، فونت، منشی و...) فقط از طریق دستور **`پنل`** قابل دسترسی هستند.

**✦ دانلودر و سرچ پیشرفته 🔞**
  » `دانلود [متن]` (دانلودر اختصاصی از سایت‌های خاص)
  » `عکس [متن]` (جستجوی عکس با کیفیت بالا بدون سانسور)
  * مثال: `دانلود فیلم` یا `عکس ماشین`.

**✦ هوش مصنوعی**
  » `منشی روشن` | `منشی خاموش` (پاسخگویی هوشمند)

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

**✦ تنظیمات ظاهری**
  » `تنظیم عکس` (ریپلای روی عکس برای پنل)
  » `حذف عکس` (حذف عکس پنل)
━━━━━━━━━━━━━━━━━━━━
"""

# Regex Updated
COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تنظیم عکس|حذف عکس|پنل|panel|دانلود .*|عکس .*|منشی روشن|منشی خاموش)$"

# --- State Management ---
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
SECRETARY_MODE_STATUS = {}
AI_SECRETARY_STATUS = {}  # AI Enabled?
AI_CONVERSATION_HISTORY = {} # Context for AI
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

# --- Database Helper Functions ---
async def save_settings_to_db(user_id: int):
    """Save user settings to MongoDB"""
    try:
        if sessions_collection is None: return

        settings = {
            'ai_secretary': AI_SECRETARY_STATUS.get(user_id, False),
            'secretary_mode': SECRETARY_MODE_STATUS.get(user_id, False),
            'clock_status': CLOCK_STATUS.get(user_id, True),
            'font_choice': USER_FONT_CHOICES.get(user_id, 'stylized'),
            'auto_seen': AUTO_SEEN_STATUS.get(user_id, False),
            'bold_mode': BOLD_MODE_STATUS.get(user_id, False),
            'pv_lock': PV_LOCK_STATUS.get(user_id, False),
            'anti_login': ANTI_LOGIN_STATUS.get(user_id, False),
            'typing_mode': TYPING_MODE_STATUS.get(user_id, False),
            'playing_mode': PLAYING_MODE_STATUS.get(user_id, False),
            'global_enemy': GLOBAL_ENEMY_STATUS.get(user_id, False),
            'translate_target': AUTO_TRANSLATE_TARGET.get(user_id, None),
            # Save Sets as Lists
            'active_enemies': [list(x) for x in ACTIVE_ENEMIES.get(user_id, set())], # List of [target_id, chat_id]
            'muted_users': [list(x) for x in MUTED_USERS.get(user_id, set())],
            'auto_reaction_targets': AUTO_REACTION_TARGETS.get(user_id, {})
        }
        
        sessions_collection.update_one(
            {'user_id': user_id},
            {'$set': {'settings': settings}},
            upsert=True
        )
    except Exception as e:
        logging.error(f"Error saving settings db: {e}")

async def load_user_settings_from_db(user_id: int):
    """Load settings from MongoDB"""
    try:
        if sessions_collection is None: return
        doc = sessions_collection.find_one({'user_id': user_id})
        if not doc or 'settings' not in doc: return

        s = doc['settings']
        AI_SECRETARY_STATUS[user_id] = s.get('ai_secretary', False)
        SECRETARY_MODE_STATUS[user_id] = s.get('secretary_mode', False)
        CLOCK_STATUS[user_id] = s.get('clock_status', True)
        USER_FONT_CHOICES[user_id] = s.get('font_choice', 'stylized')
        AUTO_SEEN_STATUS[user_id] = s.get('auto_seen', False)
        BOLD_MODE_STATUS[user_id] = s.get('bold_mode', False)
        PV_LOCK_STATUS[user_id] = s.get('pv_lock', False)
        ANTI_LOGIN_STATUS[user_id] = s.get('anti_login', False)
        TYPING_MODE_STATUS[user_id] = s.get('typing_mode', False)
        PLAYING_MODE_STATUS[user_id] = s.get('playing_mode', False)
        GLOBAL_ENEMY_STATUS[user_id] = s.get('global_enemy', False)
        AUTO_TRANSLATE_TARGET[user_id] = s.get('translate_target', None)
        AUTO_REACTION_TARGETS[user_id] = s.get('auto_reaction_targets', {})
        
        # Restore Sets
        ACTIVE_ENEMIES[user_id] = set(tuple(x) for x in s.get('active_enemies', []))
        MUTED_USERS[user_id] = set(tuple(x) for x in s.get('muted_users', []))

    except Exception as e:
        logging.error(f"Error loading settings db: {e}")

# --- AI Helper Functions ---
async def get_ai_response(user_message: str, user_name: str = "کاربر", user_id: int = None, sender_id: int = None) -> str:
    """Get AI response from Cloudflare Workers AI"""
    try:
        url = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run/{CLOUDFLARE_AI_MODEL}"
        headers = {"Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}", "Content-Type": "application/json"}
        
        # History Management
        if user_id not in AI_CONVERSATION_HISTORY: AI_CONVERSATION_HISTORY[user_id] = {}
        if sender_id not in AI_CONVERSATION_HISTORY[user_id]: AI_CONVERSATION_HISTORY[user_id][sender_id] = []
        
        recent_messages = AI_CONVERSATION_HISTORY[user_id][sender_id]
        recent_messages.append(f"کاربر: {user_message}")
        if len(recent_messages) > 6: recent_messages = recent_messages[-6:]
        
        context = "\n".join(recent_messages[-3:])
        system_prompt = f"""تو یک انسان باهوش و منشی {user_name} هستی. صمیمی و کوتاه جواب بده. فارسی صحبت کن.
آخرین مکالمه:
{context}"""
        
        payload = {"messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]}
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    ai_response = result.get("result", {}).get("response", "متوجه نشدم.")
                    recent_messages.append(f"منشی: {ai_response}")
                    return ai_response
                else:
                    return "الان مشغولم، بعدا جواب میدم."
    except Exception as e:
        logging.error(f"AI Error: {e}")
        return "فعلا در دسترس نیستم."

# --- Advanced Search & Download Helper ---
async def search_and_download_media(client, message, query, media_type='video'):
    """
    1. Images: YANDEX IMAGES (Uncensored).
    2. Videos: PORNHUB Direct Scraping (No API library, just requests).
    """
    status_msg = await message.reply_text(f"🔍 در حال جستجو (مخصوص) برای: {query} ...")
    try:
        # Standard header to mimic a real browser
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Cookie": "age_verified=1" # Needed for some sites
        }
        
        found_file_path = None
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # ==========================================
            # 🖼 IMAGE SEARCH (YANDEX - UNCENSORED)
            # ==========================================
            if media_type == 'image':
                found_link = None
                try:
                    # Yandex is the best for unfiltered image search
                    search_url = f"https://yandex.com/images/search?text={quote(query)}"
                    async with session.get(search_url, timeout=15) as resp:
                        if resp.status == 200:
                            html = await resp.text()
                            # Extract image URLs from Yandex's JSON data in HTML
                            # Looking for "img_href":"http..."
                            matches = re.findall(r'"img_href":"(https?://[^"]+?)"', html)
                            
                            if matches:
                                # Pick a random one from top 5 for variety
                                found_link = random.choice(matches[:5])
                                # Yandex escapes slashes, fix them
                                found_link = found_link.replace('\\/', '/')
                except Exception as e:
                    logging.error(f"Yandex Error: {e}")
                
                # Fallback to direct download if link found
                if found_link:
                    try:
                        async with session.get(found_link, timeout=20) as img_resp:
                            if img_resp.status == 200:
                                ext = found_link.split('.')[-1].split('?')[0]
                                if len(ext) > 4: ext = "jpg"
                                filename = f"download_{int(time.time())}.{ext}"
                                with open(filename, 'wb') as f:
                                    f.write(await img_resp.read())
                                found_file_path = filename
                    except: pass

            # ==========================================
            # 🎥 VIDEO SEARCH (PORNHUB SCRAPER)
            # ==========================================
            else:
                video_page_url = None
                target_dl_url = None
                
                # Step 1: Search on Pornhub website directly
                try:
                    search_url = f"https://www.pornhub.com/video/search?search={quote(query)}"
                    async with session.get(search_url, timeout=15) as s_resp:
                        if s_resp.status == 200:
                            html = await s_resp.text()
                            # Find view_video.php links
                            # Regex looks for <a href="/view_video.php?viewkey=...">
                            matches = re.findall(r'href="(/view_video\.php\?viewkey=[a-zA-Z0-9]+)"', html)
                            if matches:
                                video_page_url = "https://www.pornhub.com" + matches[0]
                                await status_msg.edit_text(f"🔞 ویدیو پیدا شد. در حال پردازش لینک...")
                except Exception as e:
                    logging.error(f"PH Search Error: {e}")

                # Step 2: Extract MP4 from Video Page
                if video_page_url:
                    try:
                        async with session.get(video_page_url, timeout=15) as v_resp:
                            if v_resp.status == 200:
                                v_html = await v_resp.text()
                                
                                # Method A: Look for direct mp4 in mediaDefinitions (JSON)
                                # This regex looks for "videoUrl":"https://...mp4..."
                                urls = re.findall(r'"videoUrl":"(https?://[^"]+)"', v_html)
                                for u in urls:
                                    u_clean = u.replace('\\/', '/')
                                    if '.mp4' in u_clean:
                                        target_dl_url = u_clean
                                        break
                                
                                # Method B: Fallback Regex for any mp4
                                if not target_dl_url:
                                    mp4s = re.findall(r'(https?://[^"\'\s]+\.mp4(?:\?[^"\'\s]*)?)', v_html)
                                    if mp4s: target_dl_url = mp4s[0]

                    except Exception as e:
                        logging.error(f"PH Extract Error: {e}")

                # Step 3: Download
                if target_dl_url:
                    await status_msg.edit_text(f"⬇️ شروع دانلود (بدون محدودیت)...")
                    filename = f"download_{int(time.time())}.mp4"
                    try:
                        async with session.get(target_dl_url, timeout=1800) as dl_resp: # 30 min timeout
                            if dl_resp.status == 200:
                                with open(filename, 'wb') as f:
                                    # Stream to disk
                                    async for chunk in dl_resp.content.iter_chunked(1024 * 1024):
                                        f.write(chunk)
                                
                                if os.path.exists(filename) and os.path.getsize(filename) > 1024:
                                    found_file_path = filename
                    except Exception as e:
                        logging.error(f"PH Download Error: {e}")
                        if os.path.exists(filename): os.remove(filename)

        # ==========================================
        # 📤 UPLOAD
        # ==========================================
        if found_file_path:
            await status_msg.edit_text("📤 در حال آپلود...")
            try:
                if media_type == 'video':
                    await client.send_video(message.chat.id, found_file_path, caption=f"✅ {query}", reply_to_message_id=message.id)
                else:
                    await client.send_photo(message.chat.id, found_file_path, caption=f"✅ {query}", reply_to_message_id=message.id)
            except Exception as e:
                await status_msg.edit_text(f"❌ خطا در ارسال: {e}")
            finally:
                if os.path.exists(found_file_path): os.remove(found_file_path)
                await status_msg.delete()
        else:
            await status_msg.edit_text("❌ نتیجه‌ای یافت نشد. (مطمئن شوید موضوع دقیق است)")

    except Exception as e:
        logging.error(f"Global Handler Error: {e}")
        try: await status_msg.edit_text(f"❌ خطا: {e}")
        except: pass

# --- Helpers ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

async def perform_clock_update_now(client, user_id):
    try:
        if CLOCK_STATUS.get(user_id, True) and not COPY_MODE_STATUS.get(user_id, False):
            current_font_style = USER_FONT_CHOICES.get(user_id, 'stylized')
            me = await client.get_me()
            current_name = me.first_name or ""
            base_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_name).strip()
            
            tehran_time = datetime.now(TEHRAN_TIMEZONE)
            current_time_str = tehran_time.strftime("%H:%M")
            stylized_time = stylize_time(current_time_str, current_font_style)
            new_name = f"{base_name} {stylized_time}"
            
            if new_name != current_name:
                await client.update_profile(first_name=new_name)
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
    if sessions_collection is not None:
        doc = sessions_collection.find_one({'user_id': user_id})
        return doc.get('panel_photo') if doc else None
    return None

def set_panel_photo_db(user_id, file_id):
    if sessions_collection is not None:
        sessions_collection.update_one({'user_id': user_id}, {'$set': {'panel_photo': file_id}}, upsert=False)

def del_panel_photo_db(user_id):
    if sessions_collection is not None:
        sessions_collection.update_one({'user_id': user_id}, {'$unset': {'panel_photo': ""}})

# --- Tasks ---
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

# --- Handlers ---
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
    ai_enabled = AI_SECRETARY_STATUS.get(owner_id, False)
    simple_enabled = SECRETARY_MODE_STATUS.get(owner_id, False)
    
    if not ai_enabled and not simple_enabled: return
    if not message.from_user: return
    
    sender_id = message.from_user.id
    
    if ai_enabled:
        user_msg = message.text or "[رسانه]"
        sender_name = message.from_user.first_name or "کاربر"
        response = await get_ai_response(user_msg, sender_name, owner_id, sender_id)
        try: await message.reply_text(response)
        except: pass
        return

    replied = USERS_REPLIED_IN_SECRETARY.get(owner_id, set())
    if sender_id not in replied:
        try:
            await message.reply_text(SECRETARY_REPLY_MESSAGE)
            replied.add(sender_id)
            USERS_REPLIED_IN_SECRETARY[owner_id] = replied
        except: pass

async def incoming_message_manager(client, message):
    if not message.from_user: return
    user_id = client.me.id
    
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(user_id, set()):
        try: await message.delete()
        except: pass
        return

    if emoji := AUTO_REACTION_TARGETS.get(user_id, {}).get(message.from_user.id):
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except: pass

async def help_controller(client, message):
    try: await message.edit_text(HELP_TEXT)
    except: await message.reply_text(HELP_TEXT)

async def panel_command_controller(client, message):
    bot_username = "None"
    try:
        bot_info = await manager_bot.get_me()
        bot_username = bot_info.username
        results = await client.get_inline_bot_results(bot_username, "panel")
        if results and results.results:
            await message.delete()
            await client.send_inline_bot_result(message.chat.id, results.query_id, results.results[0].id)
        else:
            await message.edit_text("❌ خطا: حالت Inline ربات فعال نیست.")
    except ChatSendInlineForbidden:
        await message.edit_text("🚫 در این چت اجازه ارسال پنل بصورت اینلاین وجود ندارد. لطفاً در پیوی یا پیام‌های ذخیره شده تست کنید.")
    except Exception as e:
        try: await message.edit_text(f"❌ خطا در لود پنل: {e}\n\n⚠️ از استارت بودن @{bot_username} مطمئن شوید.")
        except: pass

async def photo_setting_controller(client, message):
    user_id = client.me.id
    if message.text == "تنظیم عکس" and message.reply_to_message and message.reply_to_message.photo:
        set_panel_photo_db(user_id, message.reply_to_message.photo.file_id)
        await message.edit_text("✅ عکس پنل ذخیره شد.")
    elif message.text == "حذف عکس":
        del_panel_photo_db(user_id)
        await message.edit_text("🗑 عکس پنل حذف شد.")

async def search_media_controller(client, message):
    cmd = message.text.strip()
    
    if cmd.startswith("دانلود "):
        query = cmd[7:].strip()
        if query:
            await search_and_download_media(client, message, query, media_type='video')
            
    elif cmd.startswith("عکس "):
        query = cmd[4:].strip()
        if query:
            await search_and_download_media(client, message, query, media_type='image')

async def reply_based_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    
    async def save(): await save_settings_to_db(user_id)

    if cmd == "تاس": await client.send_dice(message.chat.id, "🎲")
    elif cmd == "بولینگ": await client.send_dice(message.chat.id, "🎳")
    elif cmd.startswith("تاس "): 
        try: await client.send_dice(message.chat.id, "🎲", reply_to_message_id=message.reply_to_message_id)
        except: pass
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(user_id, set())
        await message.edit_text(f"📜 تعداد دشمنان فعال: {len(enemies)}")
    
    elif cmd == "منشی روشن":
        AI_SECRETARY_STATUS[user_id] = True
        await save()
        await message.edit_text("✅ منشی هوشمند (AI) روشن شد.")
    elif cmd == "منشی خاموش":
        AI_SECRETARY_STATUS[user_id] = False
        SECRETARY_MODE_STATUS[user_id] = False
        await save()
        await message.edit_text("❌ منشی خاموش شد.")

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
                await save()
                await message.edit_text("👤 هویت جعل شد.")
            elif cmd == "کپی خاموش":
                if user_id in ORIGINAL_PROFILE_DATA:
                    data = ORIGINAL_PROFILE_DATA[user_id]
                    COPY_MODE_STATUS[user_id] = False
                    await client.update_profile(first_name=data.get('first_name'), bio=data.get('bio'))
                    await save()
                    await message.edit_text("👤 هویت بازگردانده شد.")
            elif cmd == "دشمن روشن":
                s = ACTIVE_ENEMIES.get(user_id, set()); s.add((target_id, message.chat.id)); ACTIVE_ENEMIES[user_id] = s
                await save()
                await message.edit_text("⚔️ دشمن اضافه شد.")
            elif cmd == "دشمن خاموش":
                s = ACTIVE_ENEMIES.get(user_id, set()); s.discard((target_id, message.chat.id)); ACTIVE_ENEMIES[user_id] = s
                await save()
                await message.edit_text("🏳️ دشمن حذف شد.")
            elif cmd == "بلاک روشن": await client.block_user(target_id); await message.edit_text("🚫 کاربر بلاک شد.")
            elif cmd == "بلاک خاموش": await client.unblock_user(target_id); await message.edit_text("⭕️ کاربر آنبلاک شد.")
            elif cmd == "سکوت روشن":
                s = MUTED_USERS.get(user_id, set()); s.add((target_id, message.chat.id)); MUTED_USERS[user_id] = s
                await save()
                await message.edit_text("🔇 کاربر ساکت شد.")
            elif cmd == "سکوت خاموش":
                s = MUTED_USERS.get(user_id, set()); s.discard((target_id, message.chat.id)); MUTED_USERS[user_id] = s
                await save()
                await message.edit_text("🔊 کاربر از سکوت خارج شد.")
            elif cmd.startswith("ریاکشن ") and cmd != "ریاکشن خاموش":
                emoji = cmd.split()[1]
                t = AUTO_REACTION_TARGETS.get(user_id, {}); t[target_id] = emoji; AUTO_REACTION_TARGETS[user_id] = t
                await save()
                await message.edit_text(f"👍 واکنش {emoji} تنظیم شد.")
            elif cmd == "ریاکشن خاموش":
                t = AUTO_REACTION_TARGETS.get(user_id, {}); t.pop(target_id, None); AUTO_REACTION_TARGETS[user_id] = t
                await save()
                await message.edit_text("❌ واکنش حذف شد.")

async def start_bot_instance(session_string: str, phone: str, font_style: str, disable_clock: bool = False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_string)
    try:
        await client.start()
        user_id = (await client.get_me()).id
        if sessions_collection is not None:
            sessions_collection.update_one({'phone_number': phone}, {'$set': {'user_id': user_id}})
    except: return

    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: t.cancel()
    
    await load_user_settings_from_db(user_id)
    
    if user_id not in USER_FONT_CHOICES: USER_FONT_CHOICES[user_id] = font_style
    if user_id not in CLOCK_STATUS: CLOCK_STATUS[user_id] = not disable_clock
    
    client.add_handler(MessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, filters.private & ~filters.me & ~filters.bot), group=-5)
    client.add_handler(MessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(panel_command_controller, filters.me & filters.regex(r"^(پنل|panel)$")))
    client.add_handler(MessageHandler(photo_setting_controller, filters.me & filters.regex(r"^(تنظیم عکس|حذف عکس)$")))
    client.add_handler(MessageHandler(search_media_controller, filters.me & filters.regex(r"^(دانلود .*|عکس .*)$"))) 
    client.add_handler(MessageHandler(reply_based_controller, filters.me)) 
    client.add_handler(MessageHandler(enemy_handler, filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me), group=1)

    tasks = [
        asyncio.create_task(update_profile_clock(client, user_id)),
        asyncio.create_task(anti_login_task(client, user_id)),
        asyncio.create_task(status_action_task(client, user_id))
    ]
    ACTIVE_BOTS[user_id] = (client, tasks)

# =======================================================
# 🤖 MANAGER BOT
# =======================================================
manager_bot = Client("manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def generate_panel_markup(user_id):
    s_clock = "✅" if CLOCK_STATUS.get(user_id, True) else "❌"
    s_bold = "✅" if BOLD_MODE_STATUS.get(user_id, False) else "❌"
    s_sec = "✅" if AI_SECRETARY_STATUS.get(user_id, False) else "❌"
    s_seen = "✅" if AUTO_SEEN_STATUS.get(user_id, False) else "❌"
    s_pv = "🔒" if PV_LOCK_STATUS.get(user_id, False) else "🔓"
    s_anti = "✅" if ANTI_LOGIN_STATUS.get(user_id, False) else "❌"
    s_type = "✅" if TYPING_MODE_STATUS.get(user_id, False) else "❌"
    s_game = "✅" if PLAYING_MODE_STATUS.get(user_id, False) else "❌"
    s_enemy = "✅" if GLOBAL_ENEMY_STATUS.get(user_id, False) else "❌"
    t_lang = AUTO_TRANSLATE_TARGET.get(user_id)
    l_en, l_ru, l_cn = ("✅" if t_lang == x else "❌" for x in ("en", "ru", "zh-CN"))
    preview = stylize_time("12:34", USER_FONT_CHOICES.get(user_id, 'stylized'))

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"ساعت {s_clock}", callback_data=f"toggle_clock_{user_id}"),
         InlineKeyboardButton(f"بولد {s_bold}", callback_data=f"toggle_bold_{user_id}")],
        [InlineKeyboardButton(f"تغییر فونت: {preview}", callback_data=f"cycle_font_{user_id}")],
        [InlineKeyboardButton(f"منشی هوشمند {s_sec}", callback_data=f"toggle_sec_{user_id}"),
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
    ])

@manager_bot.on_inline_query()
async def inline_panel_handler(client, query):
    user_id = query.from_user.id
    if query.query == "panel":
        photo_id = get_panel_photo(user_id)
        if photo_id:
            result = InlineQueryResultPhoto(
                photo_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg", thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg",
                photo_file_id=photo_id, caption=f"⚡️ **مدیریت پیشرفته سلف بات**\n👤 کاربر: {user_id}\n\nوضعیت اتصال: ✅ برقرار",
                reply_markup=generate_panel_markup(user_id)
            )
        else:
            result = InlineQueryResultArticle(
                title="پنل مدیریت", input_message_content=InputTextMessageContent(f"⚡️ **مدیریت پیشرفته سلف بات**\n👤 کاربر: {user_id}\n\nوضعیت اتصال: ✅ برقرار"),
                reply_markup=generate_panel_markup(user_id), thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg"
            )
        await query.answer([result], cache_time=0)

@manager_bot.on_callback_query()
async def callback_panel_handler(client, callback):
    data = callback.data.split("_")
    action = "_".join(data[:-1])
    target_user_id = int(data[-1])
    if callback.from_user.id != target_user_id:
        await callback.answer("⛔️ دسترسی غیرمجاز!", show_alert=True); return

    async def save(): await save_settings_to_db(target_user_id)

    if action == "toggle_clock":
        new_state = not CLOCK_STATUS.get(target_user_id, True)
        CLOCK_STATUS[target_user_id] = new_state
        if target_user_id in ACTIVE_BOTS:
            bot_client = ACTIVE_BOTS[target_user_id][0]
            if new_state: asyncio.create_task(perform_clock_update_now(bot_client, target_user_id))
            else:
                try:
                    me = await bot_client.get_me()
                    clean_name = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', me.first_name).strip()
                    if clean_name != me.first_name: await bot_client.update_profile(first_name=clean_name)
                except: pass
        await save()
    elif action == "cycle_font":
        cur = USER_FONT_CHOICES.get(target_user_id, 'stylized')
        idx = (FONT_KEYS_ORDER.index(cur) + 1) % len(FONT_KEYS_ORDER)
        USER_FONT_CHOICES[target_user_id] = FONT_KEYS_ORDER[idx]
        CLOCK_STATUS[target_user_id] = True
        if target_user_id in ACTIVE_BOTS: asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[target_user_id][0], target_user_id))
        await save()
    elif action == "toggle_bold": BOLD_MODE_STATUS[target_user_id] = not BOLD_MODE_STATUS.get(target_user_id, False); await save()
    elif action == "toggle_sec": AI_SECRETARY_STATUS[target_user_id] = not AI_SECRETARY_STATUS.get(target_user_id, False); await save()
    elif action == "toggle_seen": AUTO_SEEN_STATUS[target_user_id] = not AUTO_SEEN_STATUS.get(target_user_id, False); await save()
    elif action == "toggle_pv": PV_LOCK_STATUS[target_user_id] = not PV_LOCK_STATUS.get(target_user_id, False); await save()
    elif action == "toggle_anti": ANTI_LOGIN_STATUS[target_user_id] = not ANTI_LOGIN_STATUS.get(target_user_id, False); await save()
    elif action == "toggle_type":
        TYPING_MODE_STATUS[target_user_id] = not TYPING_MODE_STATUS.get(target_user_id, False)
        if TYPING_MODE_STATUS[target_user_id]: PLAYING_MODE_STATUS[target_user_id] = False
        await save()
    elif action == "toggle_game":
        PLAYING_MODE_STATUS[target_user_id] = not PLAYING_MODE_STATUS.get(target_user_id, False)
        if PLAYING_MODE_STATUS[target_user_id]: TYPING_MODE_STATUS[target_user_id] = False
        await save()
    elif action == "toggle_g_enemy": GLOBAL_ENEMY_STATUS[target_user_id] = not GLOBAL_ENEMY_STATUS.get(target_user_id, False); await save()
    elif action.startswith("lang_"):
        l = action.split("_")[1]
        AUTO_TRANSLATE_TARGET[target_user_id] = l if AUTO_TRANSLATE_TARGET.get(target_user_id) != l else None
        await save()
    elif action == "close_panel":
        try:
            if callback.inline_message_id: await client.edit_inline_text(callback.inline_message_id, "✅ پنل بسته شد.")
            else: await callback.message.delete()
        except: pass
        return

    try: await callback.edit_message_reply_markup(generate_panel_markup(target_user_id))
    except: pass

# --- Login Handlers ---
@manager_bot.on_message(filters.command("start"))
async def start_login(client, message):
    kb = ReplyKeyboardMarkup([[KeyboardButton("📱 شماره و شروع", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await message.reply_text("👋 خوش آمدید.", reply_markup=kb)

@manager_bot.on_message(filters.contact)
async def contact_handler(client, message):
    chat_id = message.chat.id; phone = message.contact.phone_number
    await message.reply_text("⏳ در حال اتصال...", reply_markup=ReplyKeyboardRemove())
    user_client = Client(f"login_{chat_id}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
    await user_client.connect()
    try:
        sent_code = await user_client.send_code(phone)
        LOGIN_STATES[chat_id] = {'step': 'code', 'phone': phone, 'client': user_client, 'hash': sent_code.phone_code_hash}
        await message.reply_text("✅ کد را بفرستید (مثلاً `1.1.1.1.1`)")
    except Exception as e:
        await user_client.disconnect(); await message.reply_text(f"❌ خطا: {e}")

@manager_bot.on_message(filters.text & filters.private)
async def text_handler(client, message):
    chat_id = message.chat.id; state = LOGIN_STATES.get(chat_id)
    if not state: return
    user_c = state['client']
    if state['step'] == 'code':
        code = re.sub(r"\D+", "", message.text)
        try:
            await user_c.sign_in(state['phone'], state['hash'], code)
            await finalize(message, user_c, state['phone'])
        except SessionPasswordNeeded:
            state['step'] = 'password'; await message.reply_text("🔐 رمز دو مرحله‌ای را وارد کنید:")
        except Exception as e: await message.reply_text(f"❌ خطا: {e}")
    elif state['step'] == 'password':
        try:
            await user_c.check_password(message.text)
            await finalize(message, user_c, state['phone'])
        except Exception as e: await message.reply_text(f"❌ خطا: {e}")

async def finalize(message, user_c, phone):
    s_str = await user_c.export_session_string(); me = await user_c.get_me(); await user_c.disconnect()
    if sessions_collection is not None:
        sessions_collection.update_one({'phone_number': phone}, {'$set': {'session_string': s_str, 'user_id': me.id}}, upsert=True)
    asyncio.create_task(start_bot_instance(s_str, phone, 'stylized'))
    del LOGIN_STATES[message.chat.id]; await message.reply_text("✅ فعال شد! دستور `پنل` را در اکانت خود بزنید.")

# --- Flask & Run ---
@app_flask.route('/')
def home(): return "Bot is running..."

async def main():
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    if sessions_collection is not None:
        for doc in sessions_collection.find():
            asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))
    await manager_bot.start(); await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
