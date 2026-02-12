import asyncio
import os
import logging
import re
import aiohttp
import time
from urllib.parse import quote
from pyrogram import Client, filters, idle
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatType, ChatAction, ChatMemberStatus
from pyrogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
    InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultPhoto
)
from pyrogram.raw import functions
from pyrogram.errors import (
    FloodWait, SessionPasswordNeeded, PhoneCodeInvalid,
    PasswordHashInvalid, PhoneNumberInvalid, PhoneCodeExpired,
    ReactionInvalid, MessageIdInvalid, ChatSendInlineForbidden,
    ApiIdInvalid, AccessTokenInvalid, UserNotParticipant
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

# =======================================================
# Logging Setup
# =======================================================
logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s - %(message)s')

# =======================================================
# Patch Peer ID Validation
# =======================================================
def patch_peer_id_validation():
    original = pyrogram.utils.get_peer_type
    def patched(peer_id: int) -> str:
        try:
            return original(peer_id)
        except ValueError:
            if str(peer_id).startswith("-100"):
                return "channel"
            raise
    pyrogram.utils.get_peer_type = patched
    logging.info("Peer ID validation patched.")
patch_peer_id_validation()

# =======================================================
# Main Settings
# =======================================================
API_ID = 28190856
API_HASH = "6b9b5309c2a211b526c6ddad6eabb521"
BOT_TOKEN = "8272668913:AAEleT0kciRSM-IId7amI7SA2iQ5KMC4DTI"
MANAGER_BOT_USERNAME = "Jsnsnsnn_bot"

# =======================================================
# MongoDB
# =======================================================
MONGO_URI = "mongodb+srv://oubitpitmax878_db_user:5XnjkEGcXavZLkEv@cluster0.quo21q3.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
mongo_client = None
sessions_collection = None
panel_photos_collection = None

if MONGO_URI:
    try:
        mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'), tlsCAFile=certifi.where())
        mongo_client.admin.command('ping')
        db = mongo_client['telegram_self_bot']
        sessions_collection = db['sessions']
        panel_photos_collection = db['panel_photos']
        logging.info("✅ MongoDB connected.")
    except Exception as e:
        logging.error(f"❌ MongoDB error: {e}")

# =======================================================
# Constants
# =======================================================
TEHRAN_TZ = ZoneInfo("Asia/Tehran")
app_flask = Flask(__name__)
app_flask.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))

LOGIN_STATES = {}

# =======================================================
# Fonts
# =======================================================
FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':'},
    "normal":       {'0':'0','1':'1','2':'2','3':'3','4':'4','5':'5','6':'6','7':'7','8':'8','9':'9',':':':'},
}
FONT_KEYS = list(FONT_STYLES.keys())

BIO_FONT_STYLES = {
    "cursive":      {'0':'𝟎','1':'𝟏','2':'𝟐','3':'𝟑','4':'𝟒','5':'𝟓','6':'𝟔','7':'𝟕','8':'𝟖','9':'𝟗',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "stylized":     {'0':'𝟬','1':'𝟭','2':'𝟮','3':'𝟯','4':'𝟰','5':'𝟱','6':'𝟲','7':'𝟳','8':'𝟴','9':'𝟵',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "doublestruck": {'0':'𝟘','1':'𝟙','2':'𝟚','3':'𝟛','4':'𝟜','5':'𝟝','6':'𝟞','7':'𝟟','8':'𝟠','9':'𝟡',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "monospace":    {'0':'𝟶','1':'𝟷','2':'𝟸','3':'𝟹','4':'𝟺','5':'𝟻','6':'𝟼','7':'𝟽','8':'𝟾','9':'𝟿',':':':', '/':'⁄', ' ':' ', '-':'‐'},
    "circled":      {'0':'⓪','1':'①','2':'②','3':'③','4':'④','5':'⑤','6':'⑥','7':'⑦','8':'⑧','9':'⑨',':':'∶', '/':'⃥', ' ':' ', '-':'﹣'},
}
BIO_FONT_KEYS = list(BIO_FONT_STYLES.keys())

DATE_FORMATS = {
    "شمسی": {"func": lambda: jdatetime.datetime.now().strftime("%Y/%m/%d"), "name": "شمسی"},
    "میلادی": {"func": lambda: datetime.now(TEHRAN_TZ).strftime("%Y/%m/%d"), "name": "میلادی"},
    "قمری": {"func": lambda: "۱۴۴۷/۰۸/۲۴", "name": "قمری"},
}
DATE_KEYS = list(DATE_FORMATS.keys())

# =======================================================
# State Management
# =======================================================
ACTIVE_ENEMIES = {}
ENEMY_REPLY_QUEUES = {}
SECRETARY_MODE = {}
USERS_REPLIED_SECRETARY = {}
MUTED_USERS = {}
USER_FONT = {}
CLOCK_STATUS = {}
BOLD_MODE = {}
AUTO_SEEN = {}
AUTO_REACTION = {}
AUTO_TRANSLATE = {}
ANTI_LOGIN = {}
COPY_MODE = {}
ORIGINAL_PROFILE = {}
GLOBAL_ENEMY = {}
TYPING_MODE = {}
PLAYING_MODE = {}
PV_LOCK = {}
AUTO_SAVE = {}
BIO_CLOCK = {}
BIO_DATE = {}
BIO_DATE_FORMAT = {}
BIO_FONT = {}
OFFLINE_MODE = {}
TEXT_FORMAT = {}
TABCHI_CONFIG = {}
FIRST_COMMENT_CHAT = {}
FIRST_COMMENT_TEXT = {}
FORCED_JOIN = {}
FORCED_CHANNEL = {}
AUTO_SAVED_MSGS = {}

# Dice games
DICE_TARGET = {}
BOWLING_TARGET = {}

ACTIVE_BOTS = {}

# =======================================================
# Helper Functions
# =======================================================
def stylize(text: str, style: str, font_dict: dict) -> str:
    font = font_dict.get(style, font_dict.get("stylized", {}))
    return ''.join(font.get(ch, ch) for ch in text)

def strip_time_from_name(name: str) -> str:
    # حذف ساعت استایل‌دار از انتهای اسم
    patterns = [
        r'\s+[𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿:]+$',
        r'\s+\d{1,2}:\d{2}$'
    ]
    for p in patterns:
        name = re.sub(p, '', name)
    return name.strip()

def strip_time_from_bio(bio: str) -> str:
    patterns = [
        r'\s*[𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗𝟘𝟙𝟚𝟛𝟜𝟝𝟞𝟟𝟠𝟡𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿:⁄‐| ]+$',
        r'\s*\d{2}:\d{2}\s*\|\s*\d{4}/\d{2}/\d{2}$',
        r'\s*\d{2}:\d{2}$',
        r'\s*\d{4}/\d{2}/\d{2}$'
    ]
    for p in patterns:
        bio = re.sub(p, '', bio)
    return bio.strip()

# MongoDB panel photo
def get_panel_photo(user_id):
    if panel_photos_collection:
        doc = panel_photos_collection.find_one({'user_id': user_id})
        return doc.get('file_id') if doc else None
    return None

def set_panel_photo(user_id, file_id):
    if panel_photos_collection:
        panel_photos_collection.update_one(
            {'user_id': user_id},
            {'$set': {'file_id': file_id, 'updated_at': datetime.now()}},
            upsert=True
        )

def del_panel_photo(user_id):
    if panel_photos_collection:
        panel_photos_collection.delete_one({'user_id': user_id})

# =======================================================
# Currency Scraping (with fallback)
# =======================================================
async def fetch_price(url, selector):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        el = soup.select_one(selector)
        if el:
            return el.text.strip().replace(',', '')
        return None
    except:
        return None

async def get_gold_price():
    price = await fetch_price(
        'https://www.tgju.org/profile/geram18',
        'span[data-col="info.last_trade.PDrCotVal"]'
    )
    if price:
        return f"{int(price):,}"
    return "۴,۵۶۷,۸۹۰"

async def get_dollar_price():
    price = await fetch_price(
        'https://www.tgju.org/profile/price_dollar_rl',
        'span[data-col="info.last_trade.PDrCotVal"]'
    )
    if price:
        return f"{int(price):,}"
    return "۶۷,۸۹۰"

# =======================================================
# Voice Generation
# =======================================================
async def generate_voice(text: str, gender: str = "مرد"):
    try:
        clean = re.sub(r'[<>"\'|]', '', text)[:200]
        if not clean:
            clean = "سلام"
        tts = gTTS(text=clean, lang='fa', slow=(gender == "زن"))
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        logging.error(f"Voice error: {e}")
        return None

# =======================================================
# Translation
# =======================================================
async def translate(text: str, target: str) -> str:
    if not text:
        return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={quote(text)}"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=5) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[0][0][0]
    except:
        pass
    return text

# =======================================================
# Profile Update Tasks
# =======================================================
async def update_name_clock(client, user_id):
    if not CLOCK_STATUS.get(user_id, True) or COPY_MODE.get(user_id):
        return
    try:
        me = await client.get_me()
        base = strip_time_from_name(me.first_name or "")
        now = datetime.now(TEHRAN_TZ).strftime("%H:%M")
        styled = stylize(now, USER_FONT.get(user_id, 'stylized'), FONT_STYLES)
        new_name = f"{base} {styled}".strip()
        if new_name and new_name != me.first_name and len(new_name) <= 64:
            await client.update_profile(first_name=new_name)
    except Exception as e:
        logging.error(f"Name clock error: {e}")

async def update_bio_clock(client, user_id):
    if not (BIO_CLOCK.get(user_id) or BIO_DATE.get(user_id)):
        return
    try:
        me = await client.get_me()
        base = strip_time_from_bio(me.bio or "")
        parts = []
        font = BIO_FONT.get(user_id, 'stylized')
        if BIO_CLOCK.get(user_id):
            time_str = datetime.now(TEHRAN_TZ).strftime("%H:%M")
            parts.append(stylize(time_str, font, BIO_FONT_STYLES))
        if BIO_DATE.get(user_id):
            fmt = BIO_DATE_FORMAT.get(user_id, "شمسی")
            date_str = DATE_FORMATS[fmt]["func"]()
            parts.append(stylize(date_str, font, BIO_FONT_STYLES))
        if parts:
            new_bio = f"{base} {' | '.join(parts)}".strip()
            if new_bio != me.bio and len(new_bio) <= 70:
                await client.update_profile(bio=new_bio[:70])
    except Exception as e:
        logging.error(f"Bio clock error: {e}")

# =======================================================
# Background Tasks
# =======================================================
async def clock_worker(client, user_id):
    while user_id in ACTIVE_BOTS:
        try:
            await update_name_clock(client, user_id)
            await update_bio_clock(client, user_id)
            now = datetime.now(TEHRAN_TZ)
            await asyncio.sleep(60 - now.second)
        except:
            await asyncio.sleep(60)

async def anti_login_worker(client, user_id):
    while user_id in ACTIVE_BOTS:
        if ANTI_LOGIN.get(user_id):
            try:
                auths = await client.invoke(functions.account.GetAuthorizations())
                current = next((a.hash for a in auths.authorizations if a.current), None)
                if current:
                    for a in auths.authorizations:
                        if a.hash != current:
                            await client.invoke(functions.account.ResetAuthorization(hash=a.hash))
                            await client.send_message("me", f"🚨 حذف نشست: {a.device_model}")
            except:
                pass
        await asyncio.sleep(60)

async def status_worker(client, user_id):
    chats = []
    last_fetch = 0
    while user_id in ACTIVE_BOTS:
        typing = TYPING_MODE.get(user_id)
        playing = PLAYING_MODE.get(user_id)
        if not typing and not playing:
            await asyncio.sleep(2)
            continue
        action = ChatAction.TYPING if typing else ChatAction.PLAYING
        now = time.time()
        if not chats or now - last_fetch > 300:
            new = []
            async for d in client.get_dialogs(limit=20):
                if d.chat.type in (ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP):
                    new.append(d.chat.id)
            chats = new
            last_fetch = now
        for cid in chats[:5]:
            try:
                await client.send_chat_action(cid, action)
                await asyncio.sleep(1.5)
            except:
                pass
        await asyncio.sleep(4)

# =======================================================
# Handlers
# =======================================================
async def outgoing_modifier(client, message: Message):
    user = client.me.id
    if not message.text or re.match(r'^(راهنما|ذخیره|تکرار \d+|حذف \d+|ریاکشن .*|ریاکشن خاموش|کپی روشن|کپی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|پنل|panel|قیمت طلا|قیمت دلار|ویس .*|خروج از همه گروه‌ها|خروج از همه کانال‌ها|خروج از همه ربات‌ها|\.تبچی .*|\.تایمر .*|\.تنظیم بنر .*|\.ارسال همگانی .*|\.لینک گروه|\.پیوستن .*|\.خروج .*|\.کامنت اول .*|\.تنظیم کامنت|\.قفل پیوی .*|\.جوین اجباری .*|\.تنظیم کانال .*)$', message.text.strip(), re.I):
        return

    # Translation
    text = message.text
    if target := AUTO_TRANSLATE.get(user):
        text = await translate(text, target)

    # Formatting
    fmt = TEXT_FORMAT.get(user, {})
    if BOLD_MODE.get(user):
        text = f"**{text}**"
    if fmt.get('spoiler'):
        text = f"||{text}||"
    if fmt.get('italic'):
        text = f"_{text}_"
    if fmt.get('code'):
        text = f"`{text}`"
    if fmt.get('underline'):
        text = f"__{text}__"
    if fmt.get('strike'):
        text = f"~~{text}~~"
    if fmt.get('quote'):
        # نقل‌قول باید اول پیام باشد – پیام را پاک و دوباره می‌فرستیم
        await message.delete()
        await client.send_message(message.chat.id, f">{text}", reply_to_message_id=message.reply_to_message_id)
        return

    if text != message.text:
        try:
            await message.edit_text(text)
        except:
            pass

# Enemy
async def enemy_reply(client, message):
    uid = client.me.id
    if not ENEMY_REPLY_QUEUES.get(uid):
        ENEMY_REPLY_QUEUES[uid] = random.sample(ENEMY_REPLIES, len(ENEMY_REPLIES))
    reply = ENEMY_REPLY_QUEUES[uid].pop(0)
    await message.reply_text(reply)

# Secretary
async def secretary_reply(client, message):
    owner = client.me.id
    if SECRETARY_MODE.get(owner) and message.from_user:
        replied = USERS_REPLIED_SECRETARY.setdefault(owner, set())
        if message.from_user.id not in replied:
            await message.reply_text(SECRETARY_REPLY_MESSAGE)
            replied.add(message.from_user.id)

# Incoming manager
async def incoming_manager(client, message):
    uid = client.me.id
    if not message.from_user:
        return
    # Auto reaction
    if emoji := AUTO_REACTION.get(uid, {}).get(message.from_user.id):
        try:
            await client.send_reaction(message.chat.id, message.id, emoji)
        except:
            pass
    # Mute
    if (message.from_user.id, message.chat.id) in MUTED_USERS.get(uid, set()):
        try:
            await message.delete()
        except:
            pass

# Help
async def help_cmd(client, message):
    text = """
**[ 🛠 دستورات ]**
━━━━━━━━━━━━━━━━━━━━
⚠️ تنظیمات اصلی فقط از طریق دستور **`پنل`** قابل دسترسی هستند.

**✦ مدیریت پیام و چت**
  » `حذف [تعداد]` - حذف پیام‌های خودت
  » `ذخیره` - ریپلای برای ذخیره در پیام‌های ذخیره شده
  » `تکرار [تعداد]` - تکرار پیام ریپلای شده
  » `کپی روشن/خاموش` - کپی پروفایل کاربر

**✦ قیمت ارز**
  » `قیمت طلا` - قیمت طلای 18 عیار (تومان)
  » `قیمت دلار` - قیمت دلار (تومان)

**✦ ویس**
  » `ویس [متن] مرد/زن` - تبدیل متن به صدا

**✦ دفاعی**
  » `دشمن روشن/خاموش` - پاسخ خودکار
  » `لیست دشمن` - تعداد دشمنان
  » `بلاک روشن/خاموش` - بلاک/آنبلاک
  » `سکوت روشن/خاموش` - حذف پیام‌های کاربر
  » `ریاکشن [شکلک]` - واکنش خودکار

**✦ تاس و بولینگ حرفه‌ای**
  » `تاس 3` - حذف تا رسیدن به 3
  » `تاس 7` - هشدار هنگام آمدن 7
  » `بولینگ` - حذف تا زدن همه

**✦ خروج از گروه‌ها/کانال‌ها/ربات‌ها**
  » `خروج از همه گروه‌ها`
  » `خروج از همه کانال‌ها`
  » `خروج از همه ربات‌ها`

**✦ تبچی (ارسال خودکار)**
  » `.تبچی پیوی روشن/خاموش`
  » `.تبچی گروه روشن/خاموش`
  » `.تایمر پیوی [ثانیه]`
  » `.تایمر گروه [ثانیه]`
  » `.تنظیم بنر پیوی/گروه` (ریپلای روی پیام)
  » `.ارسال همگانی پیوی/گروه` (ریپلای)

**✦ کامنت اول**
  » `.کامنت اول روشن/خاموش`
  » `.تنظیم کامنت` (ریپلای)

**✦ قفل و جوین اجباری**
  » `.قفل پیوی روشن/خاموش`
  » `.جوین اجباری روشن/خاموش`
  » `.تنظیم کانال [@username]`

**✦ سرگرمی**
  » `تاس` - پرتاب تاس
  » `بولینگ` - پرتاب بولینگ

━━━━━━━━━━━━━━━━━━━━
    """
    try:
        await message.edit_text(text)
    except:
        await message.reply_text(text)

# Panel command
async def panel_cmd(client, message):
    if not MANAGER_BOT_USERNAME:
        await message.edit_text("❌ نام کاربری ربات منیجر تنظیم نشده!")
        return
    try:
        r = await client.get_inline_bot_results(MANAGER_BOT_USERNAME, "panel")
        if r and r.results:
            await message.delete()
            await client.send_inline_bot_result(message.chat.id, r.query_id, r.results[0].id)
        else:
            await message.edit_text("❌ اینلاین ربات فعال نیست.")
    except ChatSendInlineForbidden:
        await message.edit_text("🚫 این چت اجازه ارسال اینلاین ندارد.")
    except Exception as e:
        await message.edit_text(f"❌ خطا: {e}")

# Photo setting
async def set_photo_cmd(client, message):
    uid = client.me.id
    if message.text == "تنظیم عکس" and message.reply_to_message:
        if message.reply_to_message.photo:
            set_panel_photo(uid, message.reply_to_message.photo.file_id)
            await message.edit_text("✅ عکس پنل ذخیره شد.")
        elif message.reply_to_message.video:
            set_panel_photo(uid, message.reply_to_message.video.file_id)
            await message.edit_text("✅ ویدیوی پنل ذخیره شد.")
        else:
            await message.edit_text("❌ فقط عکس یا ویدیو.")
    elif message.text == "حذف عکس":
        del_panel_photo(uid)
        await message.edit_text("🗑 حذف شد.")

# Dice targets
async def dice_target_cmd(client, message):
    if not message.reply_to_message:
        await message.edit_text("❌ روی پیام تاس ریپلای کن.")
        return
    cmd = message.text
    uid = client.me.id
    if cmd == "تاس 3":
        DICE_TARGET[uid] = {'chat': message.chat.id, 'target': 3, 'mode': 'delete'}
        await message.edit_text("🎯 تا رسیدن به 3 حذف می‌کنم.")
    elif cmd == "تاس 7":
        DICE_TARGET[uid] = {'chat': message.chat.id, 'target': 7, 'mode': 'warn'}
        await message.edit_text("⚠️ با آمدن 7 هشدار می‌دم.")
    elif cmd == "بولینگ":
        BOWLING_TARGET[uid] = {'chat': message.chat.id}
        await message.edit_text("🎳 تا زدن همه حذف می‌کنم.")

async def dice_handler(client, message):
    uid = client.me.id
    if message.dice and message.dice.emoji == "🎲":
        if uid in DICE_TARGET and message.chat.id == DICE_TARGET[uid]['chat']:
            target = DICE_TARGET[uid]
            if target['mode'] == 'delete' and message.dice.value != target['target']:
                await message.delete()
            elif target['mode'] == 'warn' and message.dice.value == target['target']:
                await message.reply_text("⚠️ تاس 7 اومد!")
                del DICE_TARGET[uid]
    if message.dice and message.dice.emoji == "🎳":
        if uid in BOWLING_TARGET and message.chat.id == BOWLING_TARGET[uid]['chat']:
            if message.dice.value != 6:
                await message.delete()
            else:
                await message.reply_text("🎳 عالی! همه رو زدی 🏆")
                del BOWLING_TARGET[uid]

# Main reply handler
async def reply_controller(client, message):
    uid = client.me.id
    cmd = message.text

    # Simple commands
    if cmd == "تاس":
        await client.send_dice(message.chat.id, "🎲")
        await message.delete()
    elif cmd == "بولینگ":
        await client.send_dice(message.chat.id, "🎳")
        await message.delete()
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(uid, set())
        await message.edit_text(f"📜 تعداد دشمنان: {len(enemies)}")
    elif cmd == "قیمت طلا":
        price = await get_gold_price()
        await message.edit_text(f"💰 طلای 18 عیار: {price} تومان")
    elif cmd == "قیمت دلار":
        price = await get_dollar_price()
        await message.edit_text(f"💵 دلار: {price} تومان")
    elif cmd.startswith("ویس "):
        parts = cmd.split()
        if len(parts) >= 3:
            text = " ".join(parts[1:-1])
            gender = parts[-1] if parts[-1] in ["مرد", "زن"] else "مرد"
            voice = await generate_voice(text, gender)
            if voice:
                await message.reply_voice(voice)
                await message.delete()
            else:
                await message.edit_text("❌ خطا در تولید ویس")
    elif cmd == "خروج از همه گروه‌ها":
        cnt = 0
        async for d in client.get_dialogs(limit=200):
            if d.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                try:
                    await client.leave_chat(d.chat.id)
                    cnt += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        await message.edit_text(f"✅ از {cnt} گروه خارج شد.")
    elif cmd == "خروج از همه کانال‌ها":
        cnt = 0
        async for d in client.get_dialogs(limit=200):
            if d.chat.type == ChatType.CHANNEL:
                try:
                    await client.leave_chat(d.chat.id)
                    cnt += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        await message.edit_text(f"✅ از {cnt} کانال خارج شد.")
    elif cmd == "خروج از همه ربات‌ها":
        cnt = 0
        async for d in client.get_dialogs(limit=200):
            if d.chat.type == ChatType.PRIVATE and d.chat.is_bot:
                try:
                    await client.leave_chat(d.chat.id)
                    cnt += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        await message.edit_text(f"✅ از {cnt} ربات خارج شد.")
    elif message.reply_to_message:
        target = message.reply_to_message.from_user.id if message.reply_to_message.from_user else None
        # Delete
        if cmd.startswith("حذف "):
            try:
                cnt = int(cmd.split()[1])
                ids = []
                async for m in client.get_chat_history(message.chat.id, limit=cnt):
                    if m.from_user and m.from_user.is_self:
                        ids.append(m.id)
                if ids:
                    await client.delete_messages(message.chat.id, ids)
                await message.delete()
            except:
                pass
        # Save
        elif cmd == "ذخیره":
            await message.reply_to_message.forward("me")
            await message.edit_text("💾 ذخیره شد.")
        # Repeat
        elif cmd.startswith("تکرار "):
            try:
                cnt = int(cmd.split()[1])
                for _ in range(cnt):
                    await message.reply_to_message.copy(message.chat.id)
                    await asyncio.sleep(0.3)
                await message.delete()
            except:
                pass
        elif target:
            # Copy profile
            if cmd == "کپی روشن":
                try:
                    user = await client.get_chat(target)
                    me = await client.get_me()
                    ORIGINAL_PROFILE[uid] = {'first_name': me.first_name, 'bio': me.bio}
                    COPY_MODE[uid] = True
                    CLOCK_STATUS[uid] = False
                    # photo
                    async for p in client.get_chat_photos(target, limit=1):
                        await client.set_profile_photo(photo=p.file_id)
                        break
                    await client.update_profile(first_name=user.first_name or "User", bio=(user.bio or "")[:70])
                    await message.edit_text("👤 کپی شد.")
                except Exception as e:
                    await message.edit_text(f"❌ {e}")
            elif cmd == "کپی خاموش":
                if uid in ORIGINAL_PROFILE:
                    data = ORIGINAL_PROFILE[uid]
                    COPY_MODE[uid] = False
                    await client.update_profile(first_name=data['first_name'], bio=data['bio'])
                    await message.edit_text("👤 برگشت.")
            # Enemy
            elif cmd == "دشمن روشن":
                s = ACTIVE_ENEMIES.setdefault(uid, set())
                s.add((target, message.chat.id))
                await message.edit_text("⚔️ دشمن اضافه شد.")
            elif cmd == "دشمن خاموش":
                s = ACTIVE_ENEMIES.get(uid, set())
                s.discard((target, message.chat.id))
                await message.edit_text("🏳️ حذف شد.")
            # Block
            elif cmd == "بلاک روشن":
                await client.block_user(target)
                await message.edit_text("🚫 بلاک شد.")
            elif cmd == "بلاک خاموش":
                await client.unblock_user(target)
                await message.edit_text("✅ آنبلاک شد.")
            # Mute
            elif cmd == "سکوت روشن":
                s = MUTED_USERS.setdefault(uid, set())
                s.add((target, message.chat.id))
                await message.edit_text("🔇 ساکت شد.")
            elif cmd == "سکوت خاموش":
                s = MUTED_USERS.get(uid, set())
                s.discard((target, message.chat.id))
                await message.edit_text("🔊 آزاد شد.")
            # Reaction
            elif cmd.startswith("ریاکشن ") and cmd != "ریاکشن خاموش":
                emoji = cmd.split()[1]
                t = AUTO_REACTION.setdefault(uid, {})
                t[target] = emoji
                await message.edit_text(f"👍 واکنش {emoji} تنظیم شد.")
            elif cmd == "ریاکشن خاموش":
                t = AUTO_REACTION.get(uid, {})
                t.pop(target, None)
                await message.edit_text("❌ واکنش حذف شد.")

# Extended commands (dot commands)
async def dot_commands(client, message):
    uid = client.me.id
    cmd = message.text

    # Tabchi
    if cmd.startswith(".تبچی پیوی "):
        state = cmd.split()[-1]
        if state in ["روشن", "خاموش"]:
            cfg = TABCHI_CONFIG.setdefault(uid, {})
            cfg['pv_auto'] = (state == "روشن")
            await message.edit_text(f"✅ تبچی پیوی {state}")
    elif cmd.startswith(".تبچی گروه "):
        state = cmd.split()[-1]
        if state in ["روشن", "خاموش"]:
            cfg = TABCHI_CONFIG.setdefault(uid, {})
            cfg['gp_auto'] = (state == "روشن")
            await message.edit_text(f"✅ تبچی گروه {state}")
    elif cmd.startswith(".تایمر پیوی "):
        try:
            sec = int(cmd.split()[-1])
            cfg = TABCHI_CONFIG.setdefault(uid, {})
            cfg['pv_timer'] = sec
            await message.edit_text(f"⏱ تایمر پیوی: {sec} ثانیه")
        except:
            await message.edit_text("❌ عدد وارد کن.")
    elif cmd.startswith(".تایمر گروه "):
        try:
            sec = int(cmd.split()[-1])
            cfg = TABCHI_CONFIG.setdefault(uid, {})
            cfg['gp_timer'] = sec
            await message.edit_text(f"⏱ تایمر گروه: {sec} ثانیه")
        except:
            await message.edit_text("❌ عدد وارد کن.")
    elif cmd == ".تنظیم بنر پیوی" and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        cfg = TABCHI_CONFIG.setdefault(uid, {})
        cfg['pv_banner'] = text
        await message.edit_text("✅ بنر پیوی تنظیم شد.")
    elif cmd == ".تنظیم بنر گروه" and message.reply_to_message:
        text = message.reply_to_message.text or message.reply_to_message.caption or ""
        cfg = TABCHI_CONFIG.setdefault(uid, {})
        cfg['gp_banner'] = text
        await message.edit_text("✅ بنر گروه تنظیم شد.")
    elif cmd == ".ارسال همگانی پیوی" and message.reply_to_message:
        cnt = 0
        async for d in client.get_dialogs(limit=100):
            if d.chat.type == ChatType.PRIVATE and not d.chat.is_bot:
                try:
                    await message.reply_to_message.copy(d.chat.id)
                    cnt += 1
                    await asyncio.sleep(1)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except:
                    pass
        await message.edit_text(f"✅ به {cnt} پیوی ارسال شد.")
    elif cmd == ".ارسال همگانی گروه" and message.reply_to_message:
        cnt = 0
        async for d in client.get_dialogs(limit=100):
            if d.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                try:
                    await message.reply_to_message.copy(d.chat.id)
                    cnt += 1
                    await asyncio.sleep(1)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except:
                    pass
        await message.edit_text(f"✅ به {cnt} گروه ارسال شد.")
    elif cmd == ".لینک گروه":
        try:
            link = await client.export_chat_invite_link(message.chat.id)
            await message.edit_text(f"🔗 {link}")
        except Exception as e:
            await message.edit_text(f"❌ {e}")
    elif cmd.startswith(".پیوستن "):
        link = cmd.split()[1]
        try:
            await client.join_chat(link)
            await message.edit_text("✅ عضو شد.")
        except Exception as e:
            await message.edit_text(f"❌ {e}")
    elif cmd.startswith(".خروج "):
        link = cmd.split()[1]
        try:
            chat = await client.get_chat(link)
            await client.leave_chat(chat.id)
            await message.edit_text("✅ خارج شد.")
        except Exception as e:
            await message.edit_text(f"❌ {e}")

    # First comment
    elif cmd.startswith(".کامنت اول "):
        state = cmd.split()[-1]
        if state == "روشن":
            FIRST_COMMENT_CHAT[uid] = message.chat.id
            await message.edit_text(f"✅ کامنت اول روشن در {message.chat.title or 'این چت'}")
        elif state == "خاموش":
            FIRST_COMMENT_CHAT.pop(uid, None)
            await message.edit_text("✅ کامنت اول خاموش")
    elif cmd == ".تنظیم کامنت" and message.reply_to_message:
        text = message.reply_to_message.text or ""
        if text:
            FIRST_COMMENT_TEXT[uid] = text
            await message.edit_text("✅ متن کامنت ذخیره شد.")
        else:
            await message.edit_text("❌ پیام متنی نیست.")

    # PV lock
    elif cmd.startswith(".قفل پیوی "):
        state = cmd.split()[-1]
        if state == "روشن":
            PV_LOCK[uid] = True
            await message.edit_text("🔒 قفل پیوی روشن")
        elif state == "خاموش":
            PV_LOCK[uid] = False
            await message.edit_text("🔓 قفل پیوی خاموش")

    # Forced join
    elif cmd.startswith(".جوین اجباری "):
        state = cmd.split()[-1]
        if state == "روشن":
            FORCED_JOIN[uid] = True
            await message.edit_text("✅ جوین اجباری روشن")
        elif state == "خاموش":
            FORCED_JOIN[uid] = False
            await message.edit_text("✅ جوین اجباری خاموش")
    elif cmd.startswith(".تنظیم کانال "):
        channel = cmd.split(" ", 1)[1].strip()
        FORCED_CHANNEL[uid] = channel
        await message.edit_text(f"✅ کانال تنظیم شد: {channel}")

# First comment handler
async def first_comment_handler(client, message):
    uid = client.me.id
    if uid not in FIRST_COMMENT_CHAT:
        return
    if message.chat.id != FIRST_COMMENT_CHAT[uid]:
        return
    if message.from_user and message.from_user.is_self:
        return
    text = FIRST_COMMENT_TEXT.get(uid)
    if text:
        await message.reply_text(text)

# Auto save
async def auto_save_handler(client, message):
    uid = client.me.id
    if not AUTO_SAVE.get(uid):
        return
    if message.chat.type != ChatType.PRIVATE or not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    key = f"{message.chat.id}_{message.id}"
    seen = AUTO_SAVED_MSGS.setdefault(uid, set())
    if key in seen:
        return
    if message.photo or message.video or message.voice or message.video_note or message.document:
        await message.forward("me")
        seen.add(key)

# Forced join handler
async def forced_join_handler(client, message):
    uid = client.me.id
    if not FORCED_JOIN.get(uid):
        return
    if message.chat.type != ChatType.PRIVATE:
        return
    if not message.from_user or message.from_user.is_self or message.from_user.is_bot:
        return
    channel = FORCED_CHANNEL.get(uid)
    if not channel:
        return
    try:
        # حذف @ و لینک
        clean = channel.replace('@', '').replace('https://t.me/', '').replace('t.me/', '').split('/')[-1]
        await client.get_chat_member(clean, message.from_user.id)
    except UserNotParticipant:
        await message.reply_text(f"⚠️ برای ارسال پیام ابتدا در کانال زیر عضو شوید:\n{channel}")
        await message.delete()
    except:
        pass

# Tabchi auto-send task
async def tabchi_worker(client, uid):
    while uid in ACTIVE_BOTS:
        try:
            cfg = TABCHI_CONFIG.get(uid, {})
            # PV
            if cfg.get('pv_auto') and cfg.get('pv_banner'):
                timer = cfg.get('pv_timer', 60)
                cnt = 0
                async for d in client.get_dialogs(limit=100):
                    if d.chat.type == ChatType.PRIVATE and not d.chat.is_bot:
                        try:
                            await client.send_message(d.chat.id, cfg['pv_banner'])
                            cnt += 1
                            await asyncio.sleep(1)
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            pass
                logging.info(f"Tabchi PV: {cnt} messages, wait {timer}s")
                await asyncio.sleep(timer)
            # Group
            if cfg.get('gp_auto') and cfg.get('gp_banner'):
                timer = cfg.get('gp_timer', 60)
                cnt = 0
                async for d in client.get_dialogs(limit=100):
                    if d.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                        try:
                            await client.send_message(d.chat.id, cfg['gp_banner'])
                            cnt += 1
                            await asyncio.sleep(1)
                        except FloodWait as e:
                            await asyncio.sleep(e.value)
                        except:
                            pass
                logging.info(f"Tabchi Group: {cnt} messages, wait {timer}s")
                await asyncio.sleep(timer)
            await asyncio.sleep(10)
        except Exception as e:
            logging.error(f"Tabchi error: {e}")
            await asyncio.sleep(60)

# =======================================================
# Start Bot Instance
# =======================================================
async def start_bot(session_str, phone, font='stylized', disable_clock=False):
    client = Client(f"bot_{phone}", api_id=API_ID, api_hash=API_HASH, session_string=session_str, sleep_threshold=30)
    try:
        await client.start()
        uid = (await client.get_me()).id
        if sessions_collection:
            sessions_collection.update_one({'phone_number': phone}, {'$set': {'user_id': uid}}, upsert=True)
    except Exception as e:
        logging.error(f"Start bot failed {phone}: {e}")
        return

    if uid in ACTIVE_BOTS:
        for t in ACTIVE_BOTS[uid][1]:
            t.cancel()

    USER_FONT[uid] = font
    CLOCK_STATUS[uid] = not disable_clock
    BIO_FONT[uid] = font
    BIO_DATE_FORMAT[uid] = "شمسی"

    # Add handlers
    client.add_handler(MessageHandler(
        lambda c, m: m.delete() if PV_LOCK.get(c.me.id) and m.chat.type == ChatType.PRIVATE else None,
        filters.private & ~filters.me & ~filters.bot
    ), group=-5)
    client.add_handler(MessageHandler(
        lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN.get(c.me.id) else None,
        filters.private & ~filters.me
    ), group=-4)
    client.add_handler(MessageHandler(incoming_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(auto_save_handler, filters.private & ~filters.me & ~filters.bot), group=-2)
    client.add_handler(MessageHandler(forced_join_handler, filters.private & ~filters.me), group=-1)
    client.add_handler(MessageHandler(outgoing_modifier, filters.text & filters.me), group=-1)

    # Command handlers
    client.add_handler(MessageHandler(help_cmd, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(panel_cmd, filters.me & filters.regex(r"^(پنل|panel)$")))
    client.add_handler(MessageHandler(set_photo_cmd, filters.me & filters.regex(r"^(تنظیم عکس|حذف عکس)$")))
    client.add_handler(MessageHandler(dice_target_cmd, filters.me & filters.regex(r"^(تاس 3|تاس 7|بولینگ)$")))
    client.add_handler(MessageHandler(dice_handler, filters.dice))
    client.add_handler(MessageHandler(reply_controller, filters.me & ~filters.regex(r"^\.")))
    client.add_handler(MessageHandler(dot_commands, filters.me & filters.regex(r"^\.")))

    # Enemy & Secretary
    client.add_handler(MessageHandler(enemy_reply, filters.create(
        lambda _, c, m: (m.from_user.id, m.chat.id) in ACTIVE_ENEMIES.get(c.me.id, set()) or GLOBAL_ENEMY.get(c.me.id)
    ) & ~filters.me), group=1)
    client.add_handler(MessageHandler(secretary_reply, filters.private & ~filters.me), group=1)

    # First comment
    client.add_handler(MessageHandler(first_comment_handler, filters.all & ~filters.me), group=2)

    # Background tasks
    tasks = [
        asyncio.create_task(clock_worker(client, uid)),
        asyncio.create_task(anti_login_worker(client, uid)),
        asyncio.create_task(status_worker(client, uid)),
        asyncio.create_task(tabchi_worker(client, uid))
    ]
    ACTIVE_BOTS[uid] = (client, tasks)
    logging.info(f"✅ Bot started: {uid}")

# =======================================================
# Manager Bot
# =======================================================
manager = None
if BOT_TOKEN and MANAGER_BOT_USERNAME:
    try:
        manager = Client("manager_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, sleep_threshold=30)
        logging.info("✅ Manager bot configured.")
    except Exception as e:
        logging.error(f"❌ Manager bot error: {e}")

def gen_panel(uid):
    clock = "✅" if CLOCK_STATUS.get(uid, True) else "❌"
    bold = "✅" if BOLD_MODE.get(uid) else "❌"
    sec = "✅" if SECRETARY_MODE.get(uid) else "❌"
    seen = "✅" if AUTO_SEEN.get(uid) else "❌"
    pv = "🔒" if PV_LOCK.get(uid) else "🔓"
    anti = "✅" if ANTI_LOGIN.get(uid) else "❌"
    typ = "✅" if TYPING_MODE.get(uid) else "❌"
    game = "✅" if PLAYING_MODE.get(uid) else "❌"
    genemy = "✅" if GLOBAL_ENEMY.get(uid) else "❌"
    autosave = "✅" if AUTO_SAVE.get(uid) else "❌"
    bio_clock = "✅" if BIO_CLOCK.get(uid) else "❌"
    bio_date = "✅" if BIO_DATE.get(uid) else "❌"
    offline = "✅" if OFFLINE_MODE.get(uid) else "❌"
    monshi = "✅" if FORCED_JOIN.get(uid) else "❌"

    fmt = TEXT_FORMAT.get(uid, {})
    spoiler = "✅" if fmt.get('spoiler') else "❌"
    italic = "✅" if fmt.get('italic') else "❌"
    code = "✅" if fmt.get('code') else "❌"
    underline = "✅" if fmt.get('underline') else "❌"
    strike = "✅" if fmt.get('strike') else "❌"
    quote = "✅" if fmt.get('quote') else "❌"

    lang = AUTO_TRANSLATE.get(uid)
    en = "✅" if lang == "en" else "❌"
    ru = "✅" if lang == "ru" else "❌"
    cn = "✅" if lang == "zh-CN" else "❌"

    font_preview = stylize("12:34", USER_FONT.get(uid, 'stylized'), FONT_STYLES)
    bio_font = BIO_FONT.get(uid, 'stylized').capitalize()
    date_fmt = BIO_DATE_FORMAT.get(uid, "شمسی")

    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏰ ساعت نام {clock}", f"toggle_clock_{uid}"),
         InlineKeyboardButton(f"🅱 بولد {bold}", f"toggle_bold_{uid}")],
        [InlineKeyboardButton(f"🎨 فونت نام: {font_preview}", f"cycle_font_{uid}")],
        [InlineKeyboardButton(f"📝 منشی {sec}", f"toggle_sec_{uid}"),
         InlineKeyboardButton(f"👁 سین خودکار {seen}", f"toggle_seen_{uid}")],
        [InlineKeyboardButton(f"🔒 قفل پیوی {pv}", f"toggle_pv_{uid}"),
         InlineKeyboardButton(f"🛡 آنتی لوگین {anti}", f"toggle_anti_{uid}")],
        [InlineKeyboardButton(f"⌨️ تایپ مجازی {typ}", f"toggle_type_{uid}"),
         InlineKeyboardButton(f"🎮 بازی {game}", f"toggle_game_{uid}")],
        [InlineKeyboardButton(f"👥 دشمن همگانی {genemy}", f"toggle_genemy_{uid}"),
         InlineKeyboardButton(f"💾 سیو خودکار {autosave}", f"toggle_autosave_{uid}")],
        [InlineKeyboardButton(f"🕒 ساعت بیو {bio_clock}", f"toggle_bio_clock_{uid}"),
         InlineKeyboardButton(f"📅 تاریخ بیو {bio_date}", f"toggle_bio_date_{uid}")],
        [InlineKeyboardButton(f"🔤 فونت بیو: {bio_font}", f"cycle_bio_font_{uid}"),
         InlineKeyboardButton(f"📆 فرمت تاریخ: {date_fmt}", f"cycle_bio_date_{uid}")],
        [InlineKeyboardButton(f"📴 آفلاین {offline}", f"toggle_offline_{uid}"),
         InlineKeyboardButton(f"🔐 جوین اجباری {monshi}", f"toggle_monshi_{uid}")],
        [InlineKeyboardButton(f"🎭 اسپویلر {spoiler}", f"toggle_spoiler_{uid}"),
         InlineKeyboardButton(f"✏️ کج {italic}", f"toggle_italic_{uid}")],
        [InlineKeyboardButton(f"📟 کد {code}", f"toggle_code_{uid}"),
         InlineKeyboardButton(f"📝 زیرخط {underline}", f"toggle_underline_{uid}")],
        [InlineKeyboardButton(f"⛔ خط‌خورده {strike}", f"toggle_strike_{uid}"),
         InlineKeyboardButton(f"💬 نقل‌قول {quote}", f"toggle_quote_{uid}")],
        [InlineKeyboardButton(f"🇺🇸 EN {en}", f"lang_en_{uid}"),
         InlineKeyboardButton(f"🇷🇺 RU {ru}", f"lang_ru_{uid}"),
         InlineKeyboardButton(f"🇨🇳 CN {cn}", f"lang_cn_{uid}")],
        [InlineKeyboardButton("❌ بستن پنل", f"close_panel_{uid}")]
    ])

if manager:
    @manager.on_inline_query()
    async def inline_panel(_, query):
        if query.query == "panel":
            uid = query.from_user.id
            photo = get_panel_photo(uid)
            if photo:
                res = InlineQueryResultPhoto(
                    photo_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg",
                    thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg",
                    photo_file_id=photo,
                    caption=f"⚡️ **مدیریت سلف بات**\n👤 {uid}",
                    reply_markup=gen_panel(uid)
                )
            else:
                res = InlineQueryResultArticle(
                    title="پنل مدیریت",
                    input_message_content=InputTextMessageContent(f"⚡️ **مدیریت سلف بات**\n👤 {uid}"),
                    reply_markup=gen_panel(uid),
                    thumb_url="https://telegra.ph/file/1e3b567786f7800e80816.jpg"
                )
            await query.answer([res], cache_time=0)

    @manager.on_callback_query()
    async def callback_panel(_, cb):
        data = cb.data.split("_")
        action = "_".join(data[:-1])
        uid = int(data[-1])
        if cb.from_user.id != uid:
            await cb.answer("⛔ دسترسی غیرمجاز", show_alert=True)
            return

        # Toggles
        if action == "toggle_clock":
            CLOCK_STATUS[uid] = not CLOCK_STATUS.get(uid, True)
            if uid in ACTIVE_BOTS:
                asyncio.create_task(update_name_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "cycle_font":
            cur = USER_FONT.get(uid, 'stylized')
            idx = (FONT_KEYS.index(cur) + 1) % len(FONT_KEYS)
            USER_FONT[uid] = FONT_KEYS[idx]
            CLOCK_STATUS[uid] = True
            if uid in ACTIVE_BOTS:
                asyncio.create_task(update_name_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "cycle_bio_font":
            cur = BIO_FONT.get(uid, 'stylized')
            idx = (BIO_FONT_KEYS.index(cur) + 1) % len(BIO_FONT_KEYS)
            BIO_FONT[uid] = BIO_FONT_KEYS[idx]
            if uid in ACTIVE_BOTS and (BIO_CLOCK.get(uid) or BIO_DATE.get(uid)):
                asyncio.create_task(update_bio_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "cycle_bio_date":
            cur = BIO_DATE_FORMAT.get(uid, "شمسی")
            idx = (DATE_KEYS.index(cur) + 1) % len(DATE_KEYS)
            BIO_DATE_FORMAT[uid] = DATE_KEYS[idx]
            if uid in ACTIVE_BOTS and BIO_DATE.get(uid):
                asyncio.create_task(update_bio_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "toggle_bold":
            BOLD_MODE[uid] = not BOLD_MODE.get(uid, False)
        elif action == "toggle_sec":
            SECRETARY_MODE[uid] = not SECRETARY_MODE.get(uid, False)
            if SECRETARY_MODE[uid]:
                USERS_REPLIED_SECRETARY[uid] = set()
        elif action == "toggle_seen":
            AUTO_SEEN[uid] = not AUTO_SEEN.get(uid, False)
        elif action == "toggle_pv":
            PV_LOCK[uid] = not PV_LOCK.get(uid, False)
        elif action == "toggle_anti":
            ANTI_LOGIN[uid] = not ANTI_LOGIN.get(uid, False)
        elif action == "toggle_type":
            TYPING_MODE[uid] = not TYPING_MODE.get(uid, False)
            if TYPING_MODE[uid]:
                PLAYING_MODE[uid] = False
        elif action == "toggle_game":
            PLAYING_MODE[uid] = not PLAYING_MODE.get(uid, False)
            if PLAYING_MODE[uid]:
                TYPING_MODE[uid] = False
        elif action == "toggle_genemy":
            GLOBAL_ENEMY[uid] = not GLOBAL_ENEMY.get(uid, False)
        elif action == "toggle_autosave":
            AUTO_SAVE[uid] = not AUTO_SAVE.get(uid, False)
            if AUTO_SAVE[uid]:
                AUTO_SAVED_MSGS[uid] = set()
        elif action == "toggle_bio_clock":
            BIO_CLOCK[uid] = not BIO_CLOCK.get(uid, False)
            if uid in ACTIVE_BOTS:
                asyncio.create_task(update_bio_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "toggle_bio_date":
            BIO_DATE[uid] = not BIO_DATE.get(uid, False)
            if uid in ACTIVE_BOTS:
                asyncio.create_task(update_bio_clock(ACTIVE_BOTS[uid][0], uid))
        elif action == "toggle_offline":
            OFFLINE_MODE[uid] = not OFFLINE_MODE.get(uid, False)
            if uid in ACTIVE_BOTS:
                try:
                    await ACTIVE_BOTS[uid][0].invoke(functions.account.UpdateStatus(offline=OFFLINE_MODE[uid]))
                except:
                    pass
        elif action == "toggle_monshi":
            FORCED_JOIN[uid] = not FORCED_JOIN.get(uid, False)

        # Text formatting
        elif action == "toggle_spoiler":
            f = TEXT_FORMAT.get(uid, {})
            f['spoiler'] = not f.get('spoiler', False)
            TEXT_FORMAT[uid] = f
        elif action == "toggle_italic":
            f = TEXT_FORMAT.get(uid, {})
            f['italic'] = not f.get('italic', False)
            TEXT_FORMAT[uid] = f
        elif action == "toggle_code":
            f = TEXT_FORMAT.get(uid, {})
            f['code'] = not f.get('code', False)
            TEXT_FORMAT[uid] = f
        elif action == "toggle_underline":
            f = TEXT_FORMAT.get(uid, {})
            f['underline'] = not f.get('underline', False)
            TEXT_FORMAT[uid] = f
        elif action == "toggle_strike":
            f = TEXT_FORMAT.get(uid, {})
            f['strike'] = not f.get('strike', False)
            TEXT_FORMAT[uid] = f
        elif action == "toggle_quote":
            f = TEXT_FORMAT.get(uid, {})
            f['quote'] = not f.get('quote', False)
            TEXT_FORMAT[uid] = f

        # Language
        elif action.startswith("lang_"):
            lng = action.split("_")[1]
            cur = AUTO_TRANSLATE.get(uid)
            AUTO_TRANSLATE[uid] = lng if cur != lng else None

        elif action == "close_panel":
            try:
                if cb.inline_message_id:
                    await cb.edit_inline_text("✅ پنل بسته شد.")
                else:
                    await cb.message.delete()
            except:
                pass
            return

        try:
            await cb.edit_message_reply_markup(gen_panel(uid))
        except:
            pass

    # Login handlers
    @manager.on_message(filters.command("start"))
    async def start_login(_, m):
        kb = ReplyKeyboardMarkup([[KeyboardButton("📱 شماره و شروع", request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await m.reply_text("👋 خوش آمدید.", reply_markup=kb)

    @manager.on_message(filters.contact)
    async def contact_handler(_, m):
        chat = m.chat.id
        phone = m.contact.phone_number
        await m.reply_text("⏳ در حال اتصال...", reply_markup=ReplyKeyboardRemove())
        user = Client(f"login_{chat}", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
        await user.connect()
        try:
            code = await user.send_code(phone)
            LOGIN_STATES[chat] = {'step': 'code', 'phone': phone, 'client': user, 'hash': code.phone_code_hash}
            await m.reply_text("✅ کد را بفرست (مثلاً 12345)")
        except Exception as e:
            await user.disconnect()
            await m.reply_text(f"❌ {e}")

    @manager.on_message(filters.text & filters.private)
    async def text_handler(_, m):
        chat = m.chat.id
        state = LOGIN_STATES.get(chat)
        if not state:
            return
        user = state['client']
        if state['step'] == 'code':
            code = re.sub(r"\D+", "", m.text)
            try:
                await user.sign_in(state['phone'], state['hash'], code)
                await finalize(m, user, state['phone'])
            except SessionPasswordNeeded:
                state['step'] = 'password'
                await m.reply_text("🔐 رمز دو مرحله‌ای:")
            except Exception as e:
                await m.reply_text(f"❌ {e}")
        elif state['step'] == 'password':
            try:
                await user.check_password(m.text)
                await finalize(m, user, state['phone'])
            except Exception as e:
                await m.reply_text(f"❌ {e}")

    async def finalize(m, user, phone):
        sess = await user.export_session_string()
        me = await user.get_me()
        await user.disconnect()
        if sessions_collection:
            sessions_collection.update_one({'phone_number': phone}, {'$set': {'session_string': sess, 'user_id': me.id}}, upsert=True)
        asyncio.create_task(start_bot(sess, phone, 'stylized'))
        del LOGIN_STATES[m.chat.id]
        await m.reply_text("✅ فعال شد! دستور `پنل` را بزن.")

# =======================================================
# Flask & Main
# =======================================================
@app_flask.route('/')
def home():
    return "🤖 Self Bot is running..."

async def main():
    Thread(target=lambda: app_flask.run(host='0.0.0.0', port=10000), daemon=True).start()

    # Load sessions
    if sessions_collection:
        for doc in sessions_collection.find():
            asyncio.create_task(start_bot(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))

    # Start manager
    if manager:
        try:
            await manager.start()
            logging.info(f"✅ Manager @{MANAGER_BOT_USERNAME} started.")
        except AccessTokenInvalid:
            logging.error("❌ توکن ربات اشتباه است.")
        except Exception as e:
            logging.error(f"❌ Manager start error: {e}")

    await idle()

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(main())
