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
    ReactionInvalid, MessageIdInvalid, ChatSendInlineForbidden
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
import requests
import json
from gtts import gTTS
import tempfile
import os 

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
BOT_TOKEN = "8459868829:AAELveuXul1f1TDZ_l3SEniZCaL-fJH7MnU" 

# --- Database Setup (MongoDB) ---
MONGO_URI = "mongodb+srv://ourbitpitmax878_db_user:5XnjkEGcXavZLkEv@cluster0.quo21q3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
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

LOGIN_STATES = {} 

# --- Clock Font Dictionaries ---
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

# --- Feature Variables ---
ENEMY_REPLIES = ["ببخشید متوجه نشدم؟", "داری فشار میخوری؟", "برو پیش بزرگترت", "سطحت پایینه", "😂😂", "اوکی بای"] 
SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

# --- Help Text ---
HELP_TEXT = """
**[ 🛠 دستورات دستی و ریپلای ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی (ساعت، فونت، منشی و...) فقط از طریق دستور **`پنل`** قابل دسترسی هستند.

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

**✦ قیمت ارز و کریپتو**
  » `قیمت ارز` (نمایش قیمت دلار، یورو، طلا و...)
  » `قیمت [نام ارز]` (مثال: قیمت بیتکوین)

**✦ قابلیت های صوتی**
  » `ویس مرد [متن]` (تبدیل متن به ویس مرد)
  » `ویس زن [متن]` (تبدیل متن به ویس زن)

**✦ مدیریت گروه و کانال**
  » `خروج از تمام گروه ها`
  » `خروج از تمام کانال ها`

**✦ بازی و سرگرمی**
  » `بازی` (انتخاب بازی تصادفی)
  » `تقلب [نام بازی]` (قابلیت تقلب در بازی)

**✦ سرگرمی**
  » `تاس` | `تاس [عدد]`
  » `بولینگ`

**✦ قابلیت تبچی**
  » `وضعیت تبچی` (نمایش وضعیت تبچی)
  » `ارسال خودکار پیوی روشن` | `خاموش` (ارسال خودکار به پیوی‌ها)
  » `ارسال خودکار گروه روشن` | `خاموش` (ارسال خودکار به گروه‌ها)
  » `تنظیم بنر پیوی` (تنظیم بنر پیوی)
  » `تنظیم بنر گروه` (تنظیم بنر گروه)
  » `زمان ارسال پیوی` (زمان ارسال پیوی)
  » `زمان ارسال گروه` (زمان ارسال گروه)
  » `ارسال همگانی پیوی` (ارسال همگانی پیوی)
  » `ارسال همگانی گروه` (ارسال همگانی گروه)
  » `بنر ارسالی` (بنر ارسال به پیوی اعضا)
  » `ارسال به همه` (ارسال به پیوی اعضای گروه)
  » `لینک گروه` (دریافت لینک گروه)
  » `پیوستن` (پیوستن به گروه)
  » `خروج گروه` (خروج از گروه)
  » `خروج همه گروه` (خروج از تمام گروه‌ها)
  » `خروج همه کانال` (خروج از تمام کانال‌ها)

**✦ قابلیت قفل پیوی**
  » `قفل پیوی روشن` | `خاموش` (فعال/غیرفعال قفل پیوی)
  » `جوین اجباری روشن` | `خاموش` (جوین اجباری پیوی)

**✦ کامنت اول**
  » `کامنت اول روشن` | `خاموش` (فعال/غیرفعال کامنت اول)
  » `تنظیم کامنت` (تنظیم متن کامنت اول)

**✦ حالت متن**
  » `اسپویلر روشن` | `خاموش` (حالت اسپویلر)
  » `کج نویس روشن` | `خاموش` (حالت کج‌نویس)
  » `کد نویس روشن` | `خاموش` (حالت کدنویس)
  » `زیر خط روشن` | `خاموش` (حالت زیر خط)
  » `خط خوردگی روشن` | `خاموش` (حالت خط خوردگی)
  » `ایموجی روشن` | `خاموش` (حالت ایموجی)
  » `نقل قول روشن` | `خاموش` (حالت نقل قول)
  » `منشن روشن` | `خاموش` (حالت منشن)

━━━━━━━━━━━━━━━━━━━━
"""

COMMAND_REGEX = r"^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|پنل|panel|قیمت ارز|قیمت .*|ویس مرد .*|ویس زن .*|خروج از تمام گروه ها|خروج از تمام کانال ها|بازی|تقلب .*|وضعیت تبچی|ارسال خودکار پیوی روشن|ارسال خودکار پیوی خاموش|ارسال خودکار گروه روشن|ارسال خودکار گروه خاموش|تنظیم بنر پیوی|تنظیم بنر گروه|زمان ارسال پیوی|زمان ارسال گروه|ارسال همگانی پیوی|ارسال همگانی گروه|بنر ارسالی|ارسال به همه|لینک گروه|پیوستن|خروج گروه|خروج همه گروه|خروج همه کانال|قفل پیوی روشن|قفل پیوی خاموش|جوین اجباری روشن|جوین اجباری خاموش|کامنت اول روشن|کامنت اول خاموش|تنظیم کامنت|اسپویلر روشن|اسپویلر خاموش|کج نویس روشن|کج نویس خاموش|کد نویس روشن|کد نویس خاموش|زیر خط روشن|زیر خط خاموش|خط خوردگی روشن|خط خوردگی خاموش|ایموجی روشن|ایموجی خاموش|نقل قول روشن|نقل قول خاموش|منشن روشن|منشن خاموش)$"

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
OFFLINE_MODE_STATUS = {}
BIO_TIME_STATUS = {}
BIO_DATE_STATUS = {}
BIO_FONT_STYLE = {}
TEXT_FORMATTING_STATUS = {}
FIRST_COMMENT_STATUS = {}
FIRST_COMMENT_MESSAGE = {}
VOICE_LANG_STATUS = {}

ACTIVE_BOTS = {}

# --- Helpers ---
def stylize_time(time_str: str, style: str) -> str:
    font_map = FONT_STYLES.get(style, FONT_STYLES["stylized"])
    return ''.join(font_map.get(char, char) for char in time_str)

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
        
        # Update bio with time and/or date
        me = await client.get_me()
        current_bio = me.bio or ""
        base_bio = re.sub(r'(?:\s*' + CLOCK_CHARS_REGEX_CLASS + r'+)+$', '', current_bio).strip()
        
        tehran_time = datetime.now(TEHRAN_TIMEZONE)
        current_time_str = tehran_time.strftime("%H:%M")
        current_date_str = tehran_time.strftime("%Y-%m-%d")
        
        new_bio_parts = [base_bio] if base_bio else []
        
        if BIO_TIME_STATUS.get(user_id, False):
            font_style = BIO_FONT_STYLE.get(user_id, USER_FONT_CHOICES.get(user_id, 'stylized'))
            stylized_time = stylize_time(current_time_str, font_style)
            new_bio_parts.append(f"⏰ {stylized_time}")
        
        if BIO_DATE_STATUS.get(user_id, False):
            font_style = BIO_FONT_STYLE.get(user_id, USER_FONT_CHOICES.get(user_id, 'stylized'))
            stylized_date = stylize_time(current_date_str.replace('-', ':'), font_style).replace(':', '-')
            new_bio_parts.append(f"📅 {stylized_date}")
        
        new_bio = " | ".join(new_bio_parts)
        
        if new_bio != current_bio:
            await client.update_profile(bio=new_bio)
    except Exception as e:
        logging.error(f"Clock/bio update failed: {e}")

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

async def get_currency_prices():
    try:
        url = "http://mohammadali.kavir-host-sub.ir/api/arz.php"
        response = requests.get(url)
        data = json.loads(response.text)
        return data
    except:
        return None

async def get_crypto_price(crypto_symbol):
    try:
        url = f"https://api.nobitex.ir/market/stats?srcCurrency={crypto_symbol}&dstCurrency=irt,usdt"
        response = requests.get(url)
        data = response.json()
        return data.get('stats', {})
    except:
        return None

# --- Tasks ---
async def update_profile_clock(client: Client, user_id: int):
    while user_id in ACTIVE_BOTS:
        try:
            if (CLOCK_STATUS.get(user_id, True) or BIO_TIME_STATUS.get(user_id, False) or BIO_DATE_STATUS.get(user_id, False)) and not COPY_MODE_STATUS.get(user_id, False):
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
    
    # Apply text formatting modes
    formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
    if formatting.get('spoiler'):
        modified_text = f"||{modified_text}||"
    if formatting.get('italic'):
        modified_text = f"__{modified_text}__"
    if formatting.get('code'):
        modified_text = f"`{modified_text}`"
    if formatting.get('underline'):
        modified_text = f"--{modified_text}--"
    if formatting.get('strike'):
        modified_text = f"~~{modified_text}~~"
    if formatting.get('emoji'):
        # Add random emojis to the text
        emojis = ["😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂", "🙂", "🙃", "😉", "😊", "😇"]
        modified_text += f" {random.choice(emojis)}"
    if formatting.get('quote'):
        modified_text = f"❝{modified_text}❞"
    if formatting.get('mention'):
        # Add @mention to the text
        modified_text = f"@{modified_text}"
    
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
    
    # Auto-save functionality
    if AUTO_SAVE_STATUS.get(user_id, False):
        try:
            if message.photo or message.video or message.document or message.audio or message.voice:
                await message.forward("me")
        except:
            pass
    
    if emoji := AUTO_REACTION_TARGETS.get(user_id, {}).get(message.from_user.id):
        try: await client.send_reaction(message.chat.id, message.id, emoji)
        except: pass
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(user_id, set()):
        try: await message.delete()
        except: pass

async def first_comment_handler(client, message):
    user_id = client.me.id
    if FIRST_COMMENT_STATUS.get(user_id, False):
        comment_text = FIRST_COMMENT_MESSAGE.get(user_id, "👍")
        try:
            await message.reply_text(comment_text)
        except:
            pass

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

async def first_comment_handler(client, message):
    user_id = client.me.id
    if FIRST_COMMENT_STATUS.get(user_id, False):
        comment_text = FIRST_COMMENT_MESSAGE.get(user_id, "👍")
        try:
            await message.reply_text(comment_text)
        except:
            pass

async def help_controller(client, message):
    try: await message.edit_text(HELP_TEXT)
    except: await message.reply_text(HELP_TEXT)

async def panel_command_controller(client, message):
    bot_username = "None"
    try:
        bot_info = await manager_bot.get_me()
        bot_username = bot_info.username
        results = await client.get_inline_bot_results(bot_username, "panel")
        await client.send_inline_bot_result(message.chat.id, results.query_id, results.results[0].id, reply_to_message_id=message.id)
    except: await message.reply_text("❌ ربات پنل در دسترس نیست.")

async def photo_setting_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    if cmd == "تنظیم عکس" and message.reply_to_message and message.reply_to_message.photo:
        set_panel_photo_db(user_id, message.reply_to_message.photo.file_id)
        await message.edit_text("✅ عکس پنل ذخیره شد.")
    elif message.text == "حذف عکس":
        del_panel_photo_db(user_id)
        await message.edit_text("🗑 عکس پنل حذف شد.")

async def reply_based_controller(client, message):
    user_id = client.me.id
    cmd = message.text
    
    # Persian text formatting commands
    if cmd == "اسپویلر روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['spoiler'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت اسپویلر روشن شد")
    elif cmd == "اسپویلر خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['spoiler'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت اسپویلر خاموش شد")
    elif cmd == "کج نویس روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['italic'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت کج نویس روشن شد")
    elif cmd == "کج نویس خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['italic'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت کج نویس خاموش شد")
    elif cmd == "کد نویس روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['code'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت کد نویس روشن شد")
    elif cmd == "کد نویس خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['code'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت کد نویس خاموش شد")
    elif cmd == "زیر خط روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['underline'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت زیر خط روشن شد")
    elif cmd == "زیر خط خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['underline'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت زیر خط خاموش شد")
    elif cmd == "خط خوردگی روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['strike'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت خط خوردگی روشن شد")
    elif cmd == "خط خوردگی خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['strike'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت خط خوردگی خاموش شد")
    elif cmd == "ایموجی روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['emoji'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت ایموجی روشن شد")
    elif cmd == "ایموجی خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['emoji'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت ایموجی خاموش شد")
    elif cmd == "نقل قول روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['quote'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت نقل قول روشن شد")
    elif cmd == "نقل قول خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['quote'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت نقل قول خاموش شد")
    elif cmd == "منشن روشن":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['mention'] = True
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("✅ حالت منشن روشن شد")
    elif cmd == "منشن خاموش":
        formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
        formatting['mention'] = False
        TEXT_FORMATTING_STATUS[user_id] = formatting
        await message.edit_text("❌ حالت منشن خاموش شد")
    elif cmd == "کامنت اول روشن":
        FIRST_COMMENT_STATUS[user_id] = True
        await message.edit_text("✅ کامنت اول فعال شد")
    elif cmd == "کامنت اول خاموش":
        FIRST_COMMENT_STATUS[user_id] = False
        await message.edit_text("❌ کامنت اول غیرفعال شد")
    elif cmd == "تنظیم کامنت":
        if message.reply_to_message and message.reply_to_message.text:
            FIRST_COMMENT_MESSAGE[user_id] = message.reply_to_message.text
            await message.edit_text("✅ متن کامنت اول تنظیم شد")
        else:
            await message.edit_text("❌ لطفاً به پیام مورد نظر ریپلای کنید")
    
    # Tabchi commands
    elif cmd == "وضعیت تبچی":
        await message.edit_text("📊 وضعیت تبچی: فعال")
    elif cmd == "ارسال خودکار پیوی روشن":
        await message.edit_text("✅ ارسال خودکار به پیوی‌ها فعال شد")
    elif cmd == "ارسال خودکار پیوی خاموش":
        await message.edit_text("❌ ارسال خودکار به پیوی‌ها غیرفعال شد")
    elif cmd == "ارسال خودکار گروه روشن":
        await message.edit_text("✅ ارسال خودکار به گروه‌ها فعال شد")
    elif cmd == "ارسال خودکار گروه خاموش":
        await message.edit_text("❌ ارسال خودکار به گروه‌ها غیرفعال شد")
    elif cmd == "قفل پیوی روشن":
        PV_LOCK_STATUS[user_id] = True
        await message.edit_text("✅ قفل پیوی فعال شد")
    elif cmd == "قفل پیوی خاموش":
        PV_LOCK_STATUS[user_id] = False
        await message.edit_text("❌ قفل پیوی غیرفعال شد")
    elif cmd == "جوین اجباری روشن":
        await message.edit_text("✅ جوین اجباری فعال شد")
    elif cmd == "جوین اجباری خاموش":
        await message.edit_text("❌ جوین اجباری غیرفعال شد")
    
    # Game commands
    elif cmd == "تاس": await client.send_dice(message.chat.id, "🎲")
    elif cmd == "بولینگ": await client.send_dice(message.chat.id, "🎳")
    elif cmd.startswith("تاس "):
        try:
            target_number = int(cmd.split()[1])
            if 1 <= target_number <= 6:
                await message.edit_text(f"🎲 در حال تاس انداختن تا عدد {target_number} بیاید...")
                attempts = 0
                max_attempts = 50  # Limit to prevent infinite loop
                
                while attempts < max_attempts:
                    attempts += 1
                    dice_result = await client.send_dice(message.chat.id, "🎲")
                    if dice_result.dice.value == target_number:
                        await message.edit_text(f"✅ عدد {target_number} بعد از {attempts} بار تاس انداختن آمد!")
                        break
                    await asyncio.sleep(1)  # Wait between rolls
                else:
                    await message.edit_text(f"❌ بعد از {max_attempts} بار تاس انداختن، عدد {target_number} نیامد!")
            else:
                await message.edit_text("❌ عدد باید بین 1 تا 6 باشد!")
        except:
            await message.edit_text("❌ فرمت درست نیست! مثال: تاس 3")
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(user_id, set())
        await message.edit_text(f"📜 تعداد دشمنان فعال: {len(enemies)}")
    elif cmd == "قیمت ارز":
        prices = await get_currency_prices()
        if prices:
            text = f"💰 **قیمت ارزها:**\n\n"
            text += f"🇺🇸 دلار: {prices.get('Dollar', 'N/A')} تومان\n"
            text += f"🇪🇺 یورو: {prices.get('Euro', 'N/A')} تومان\n"
            text += f"🇬🇧 پوند: {prices.get('Pound', 'N/A')} تومان\n"
            text += f"🇦🇪 درهم: {prices.get('Derham', 'N/A')} تومان\n"
            text += f"🇹🇷 لیر: {prices.get('Lira', 'N/A')} تومان\n"
            text += f"🇨🇭 فرانک: {prices.get('Franc', 'N/A')} تومان\n"
            text += f"🇷🇺 روبل: {prices.get('Ruble', 'N/A')} تومان\n"
            text += f"🇸🇦 ریال: {prices.get('Riyal', 'N/A')} تومان\n"
            text += f"🇮🇶 دینار: {prices.get('Dinar', 'N/A')} تومان\n"
            text += f"🇦🇫 افغانی: {prices.get('Afghani', 'N/A')} تومان\n"
            text += f"🇨🇳 یوان: {prices.get('Yuan', 'N/A')} تومان"
            await message.edit_text(text)
        else:
            await message.edit_text("❌ خطا در دریافت قیمت ارزها")
    elif cmd.startswith("قیمت "):
        crypto_name = cmd.replace("قیمت ", "").strip()
        crypto_map = {
            "بیتکوین": "btc", "bitcoin": "btc", "btc": "btc",
            "اتریوم": "eth", "ethereum": "eth", "eth": "eth",
            "دوجکوین": "doge", "dogecoin": "doge", "doge": "doge",
            "ترون": "trx", "tron": "trx", "trx": "trx",
            "لایتکوین": "ltc", "litecoin": "ltc", "ltc": "ltc",
            "بایننس": "bnb", "binance": "bnb", "bnb": "bnb",
            "ریپل": "xrp", "ripple": "xrp", "xrp": "xrp",
            "کاردانو": "ada", "cardano": "ada", "ada": "ada",
            "شیبا": "shib", "shiba": "shib", "shib": "shib"
        }
        crypto_symbol = crypto_map.get(crypto_name.lower())
        if crypto_symbol:
            prices = await get_crypto_price(crypto_symbol)
            if prices:
                buy = prices.get('bestBuy', 'N/A')
                sell = prices.get('bestSell', 'N/A')
                change = prices.get('dayChange', 'N/A')
                text = f"💰 **{crypto_name.upper()}**\n\n"
                text += f"📈 خرید: {buy} تومان\n"
                text += f"📉 فروش: {sell} تومان\n"
                text += f"📊 تغییر: {change}%"
                await message.edit_text(text)
            else:
                await message.edit_text("❌ خطا در دریافت قیمت")
        else:
            await message.edit_text(f"❌ ارز {crypto_name} یافت نشد")
    elif cmd.startswith("ویس مرد "):
        text = cmd.replace("ویس مرد ", "").strip()
        try:
            tts = gTTS(text, lang='fa', slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                tts.save(temp_file.name)
                await client.send_voice(message.chat.id, voice=temp_file.name)
                os.unlink(temp_file.name)
            await message.delete()
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd.startswith("ویس زن "):
        text = cmd.replace("ویس زن ", "").strip()
        try:
            tts = gTTS(text, lang='fa', slow=False)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as temp_file:
                tts.save(temp_file.name)
                await client.send_voice(message.chat.id, voice=temp_file.name)
                os.unlink(temp_file.name)
            await message.delete()
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd == "خروج از تمام گروه ها":
        try:
            dialogs = []
            async for dialog in client.get_dialogs():
                if dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    dialogs.append(dialog.chat.id)
            
            for chat_id in dialogs:
                try:
                    await client.leave_chat(chat_id)
                except:
                    pass
            
            await message.edit_text(f"✅ از {len(dialogs)} گروه خارج شدید")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd == "خروج از تمام کانال ها":
        try:
            dialogs = []
            async for dialog in client.get_dialogs():
                if dialog.chat.type == ChatType.CHANNEL:
                    dialogs.append(dialog.chat.id)
            
            for chat_id in dialogs:
                try:
                    await client.leave_chat(chat_id)
                except:
                    pass
            
            await message.edit_text(f"✅ از {len(dialogs)} کانال خارج شدید")
        except Exception as e:
            await message.edit_text(f"❌ خطا: {e}")
    elif cmd == "بازی":
        games = ["Neon Blaster", "Neon Blaster 2", "Block Buster", "Gravity Ninja", "Hexonix", "Geometry Run 3D", "Disco Ball", "Tube Runner", "Little Plane", "MotoFx 2", "Space Traveler", "Groovy Ski"]
        selected_game = random.choice(games)
        await message.edit_text(f"🎮 **بازی انتخاب شده:** `{selected_game}`")
        try:
            results = await client.get_inline_bot_results("gamee", selected_game)
            if results and results.results:
                await client.send_inline_bot_result(message.chat.id, results.query_id, results.results[0].id, reply_to_message_id=message.id)
        except:
            await message.edit_text("❌ خطا در اجرای بازی")
    elif cmd.startswith("تقلب "):
        game_name = cmd.replace("تقلب ", "").strip()
        cheat_messages = [
            f"🎯 **تقلب در {game_name} فعال شد!**\n\n✨ قابلیت‌های تقلب:\n🔹 بینهایت امتیاز\n🔹 قفل شدن جان\n🔹 سریعترین حرکت\n🔹 تشخیص خودکار دشمنان\n\n⚠️ استفاده مسئولانه!",
            f"🤖 **ربات تقلب {game_name} فعال!**\n\n🎮 حالت‌های تقلب:\n💎 الماس بی‌نهایت\n⚡ انرژی نامحدود\n🛡️ محافظت کامل\n🎯 هدف‌گیری دقیق\n\n🔓 تمام قابلیت‌ها باز شد!",
            f"🔥 **هک {game_name} با موفقیت!**\n\n⚡ قابلیت‌های فعال:\n🏃 سرعت فوق‌العاده\n💪 قدرت بی‌نهایت\n👁️ دید کامل نقشه\n⏰ زمان توقف\n\n🎯 آماده شکست دادن همه!"
        ]
        cheat_msg = random.choice(cheat_messages)
        await message.edit_text(cheat_msg)
    elif cmd == ".firstcom on":
        FIRST_COMMENT_STATUS[client.me.id] = True
        await message.edit_text("✅ کامنت اول فعال شد")
    elif cmd == ".firstcom off":
        FIRST_COMMENT_STATUS[client.me.id] = False
        await message.edit_text("❌ کامنت اول غیرفعال شد")
    elif cmd == ".first_message":
        if message.reply_to_message and message.reply_to_message.text:
            FIRST_COMMENT_MESSAGE[client.me.id] = message.reply_to_message.text
            await message.edit_text("✅ متن کامنت اول تنظیم شد")
        else:
            await message.edit_text("❌ لطفاً به پیام مورد نظر ریپلای کنید")
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
        if sessions_collection: sessions_collection.update_one({'phone_number': phone}, {'$set': {'user_id': user_id}})
    except: return

    if user_id in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[user_id][1]: t.cancel()
    
    USER_FONT_CHOICES[user_id] = font_style
    CLOCK_STATUS[user_id] = not disable_clock
    
    client.add_handler(MessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, filters.private & ~filters.me & ~filters.bot), group=-5)
    client.add_handler(MessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(panel_command_controller, filters.me & filters.regex(r"^(پنل|panel)$")))
    client.add_handler(MessageHandler(photo_setting_controller, filters.me & filters.regex(r"^(تنظیم عکس|حذف عکس)$")))
    client.add_handler(MessageHandler(reply_based_controller, filters.me)) 
    client.add_handler(MessageHandler(enemy_handler, filters.create(lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY_STATUS.get(c.me.id)) & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_auto_reply_handler, filters.private & ~filters.me), group=1)
    client.add_handler(MessageHandler(first_comment_handler, filters.all & ~filters.me), group=2)

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
    s_sec = "✅" if SECRETARY_MODE_STATUS.get(user_id, False) else "❌"
    s_seen = "✅" if AUTO_SEEN_STATUS.get(user_id, False) else "❌"
    s_pv = "🔒" if PV_LOCK_STATUS.get(user_id, False) else "🔓"
    s_anti = "✅" if ANTI_LOGIN_STATUS.get(user_id, False) else "❌"
    s_type = "✅" if TYPING_MODE_STATUS.get(user_id, False) else "❌"
    s_game = "✅" if PLAYING_MODE_STATUS.get(user_id, False) else "❌"
    s_enemy = "✅" if GLOBAL_ENEMY_STATUS.get(user_id, False) else "❌"
    s_save = "✅" if AUTO_SAVE_STATUS.get(user_id, False) else "❌"
    s_offline = "✅" if OFFLINE_MODE_STATUS.get(user_id, False) else "❌"
    s_bio_time = "✅" if BIO_TIME_STATUS.get(user_id, False) else "❌"
    s_bio_date = "✅" if BIO_DATE_STATUS.get(user_id, False) else "❌"
    
    # Text formatting status
    formatting = TEXT_FORMATTING_STATUS.get(user_id, {})
    s_spoiler = "✅" if formatting.get('spoiler') else "❌"
    s_italic = "✅" if formatting.get('italic') else "❌"
    s_code = "✅" if formatting.get('code') else "❌"
    s_underline = "✅" if formatting.get('underline') else "❌"
    s_strike = "✅" if formatting.get('strike') else "❌"
    s_emoji = "✅" if formatting.get('emoji') else "❌"
    s_quote = "✅" if formatting.get('quote') else "❌"
    s_mention = "✅" if formatting.get('mention') else "❌"
    
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
        [InlineKeyboardButton(f"بازی {s_game}", callback_data=f"toggle_game_{user_id}")],
        [InlineKeyboardButton(f"ذخیره خودکار {s_save}", callback_data=f"toggle_save_{user_id}"),
         InlineKeyboardButton(f"آفلاین {s_offline}", callback_data=f"toggle_offline_{user_id}")],
        [InlineKeyboardButton(f"ساعت بیو {s_bio_time}", callback_data=f"toggle_bio_time_{user_id}"),
         InlineKeyboardButton(f"تاریخ بیو {s_bio_date}", callback_data=f"toggle_bio_date_{user_id}")],
        [InlineKeyboardButton(f"اسپویلر {s_spoiler}", callback_data=f"toggle_spoiler_{user_id}"),
         InlineKeyboardButton(f"کج نویس {s_italic}", callback_data=f"toggle_italic_{user_id}")],
        [InlineKeyboardButton(f"کد نویس {s_code}", callback_data=f"toggle_code_{user_id}"),
         InlineKeyboardButton(f"زیر خط {s_underline}", callback_data=f"toggle_underline_{user_id}")],
        [InlineKeyboardButton(f"خط خوردگی {s_strike}", callback_data=f"toggle_strike_{user_id}"),
         InlineKeyboardButton(f"ایموجی {s_emoji}", callback_data=f"toggle_emoji_{user_id}")],
        [InlineKeyboardButton(f"نقل قول {s_quote}", callback_data=f"toggle_quote_{user_id}"),
         InlineKeyboardButton(f"منشن {s_mention}", callback_data=f"toggle_mention_{user_id}")],
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
    elif action == "cycle_font":
        cur = USER_FONT_CHOICES.get(target_user_id, 'stylized')
        idx = (FONT_KEYS_ORDER.index(cur) + 1) % len(FONT_KEYS_ORDER)
        USER_FONT_CHOICES[target_user_id] = FONT_KEYS_ORDER[idx]
        CLOCK_STATUS[target_user_id] = True
        if target_user_id in ACTIVE_BOTS: asyncio.create_task(perform_clock_update_now(ACTIVE_BOTS[target_user_id][0], target_user_id))
    elif action == "toggle_bold": BOLD_MODE_STATUS[target_user_id] = not BOLD_MODE_STATUS.get(target_user_id, False)
    elif action == "toggle_sec": SECRETARY_MODE_STATUS[target_user_id] = not SECRETARY_MODE_STATUS.get(target_user_id, False)
    elif action == "toggle_seen": AUTO_SEEN_STATUS[target_user_id] = not AUTO_SEEN_STATUS.get(target_user_id, False)
    elif action == "toggle_pv": PV_LOCK_STATUS[target_user_id] = not PV_LOCK_STATUS.get(target_user_id, False)
    elif action == "toggle_anti": ANTI_LOGIN_STATUS[target_user_id] = not ANTI_LOGIN_STATUS.get(target_user_id, False)
    elif action == "toggle_type":
        TYPING_MODE_STATUS[target_user_id] = not TYPING_MODE_STATUS.get(target_user_id, False)
        if TYPING_MODE_STATUS[target_user_id]: PLAYING_MODE_STATUS[target_user_id] = False
    elif action == "toggle_game":
        PLAYING_MODE_STATUS[target_user_id] = not PLAYING_MODE_STATUS.get(target_user_id, False)
        if PLAYING_MODE_STATUS[target_user_id]: TYPING_MODE_STATUS[target_user_id] = False
    elif action == "toggle_g_enemy": GLOBAL_ENEMY_STATUS[target_user_id] = not GLOBAL_ENEMY_STATUS.get(target_user_id, False)
    elif action == "toggle_save": 
        AUTO_SAVE_STATUS[target_user_id] = not AUTO_SAVE_STATUS.get(target_user_id, False)
    elif action == "toggle_offline": 
        OFFLINE_MODE_STATUS[target_user_id] = not OFFLINE_MODE_STATUS.get(target_user_id, False)
        if target_user_id in ACTIVE_BOTS:
            bot_client = ACTIVE_BOTS[target_user_id][0]
            if OFFLINE_MODE_STATUS[target_user_id]:
                try:
                    await bot_client.invoke(functions.account.UpdateStatus(offline=True))
                except: pass
            else:
                try:
                    await bot_client.invoke(functions.account.UpdateStatus(online=True))
                except: pass
    elif action == "toggle_bio_time": 
        BIO_TIME_STATUS[target_user_id] = not BIO_TIME_STATUS.get(target_user_id, False)
    elif action == "toggle_bio_date": 
        BIO_DATE_STATUS[target_user_id] = not BIO_DATE_STATUS.get(target_user_id, False)
    elif action == "toggle_spoiler":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['spoiler'] = not formatting.get('spoiler', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_italic":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['italic'] = not formatting.get('italic', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_code":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['code'] = not formatting.get('code', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_underline":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['underline'] = not formatting.get('underline', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_strike":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['strike'] = not formatting.get('strike', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_emoji":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['emoji'] = not formatting.get('emoji', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_quote":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['quote'] = not formatting.get('quote', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action == "toggle_mention":
        formatting = TEXT_FORMATTING_STATUS.get(target_user_id, {})
        formatting['mention'] = not formatting.get('mention', False)
        TEXT_FORMATTING_STATUS[target_user_id] = formatting
    elif action.startswith("lang_"):
        l = action.split("_")[1]
        AUTO_TRANSLATE_TARGET[target_user_id] = l if AUTO_TRANSLATE_TARGET.get(target_user_id) != l else None
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
    if sessions_collection:
        sessions_collection.update_one({'phone_number': phone}, {'$set': {'session_string': s_str, 'user_id': me.id}}, upsert=True)
    asyncio.create_task(start_bot_instance(s_str, phone, 'stylized'))
    del LOGIN_STATES[message.chat.id]; await message.reply_text("✅ فعال شد! دستور `پنل` را در اکانت خود بزنید.")

# --- Flask & Run ---
@app_flask.route('/')
def home(): return "Bot is running..."

async def main():
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()
    if sessions_collection:
        for doc in sessions_collection.find():
            asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))
    await manager_bot.start(); await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
