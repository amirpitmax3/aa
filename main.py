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
    ReactionInvalid, MessageIdInvalid
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
LOGIN_STATES = {} 

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

ALL_CLOCK_CHARS = "".join(set(char for font in FONT_STYLES.values() for char in font.values()))
CLOCK_CHARS_REGEX_CLASS = f"[{re.escape(ALL_CLOCK_CHARS)}]"

# --- Feature Variables ---
ENEMY_REPLIES = [] 

SECRETARY_REPLY_MESSAGE = "سلام! در حال حاضر آفلاین هستم و پیام شما را دریافت کردم. در اولین فرصت پاسخ خواهم داد. ممنون از پیامتون."

# --- Modified Help Text (Professional & No Emojis) ---
HELP_TEXT = """
**[ 𝗦𝗘𝗟𝗙-𝗕𝗢𝗧 𝗖𝗢𝗡𝗧𝗥𝗢𝗟 𝗣𝗔𝗡𝗘𝗟 ]**
━━━━━━━━━━━━━━━━━━━━
**✦ VISUAL & TIME**
  » `ساعت روشن` | `ساعت خاموش`
  » `فونت` (مشاهده لیست)
  » `فونت [1-10]` (تغییر سریع)

**✦ MANAGEMENT**
  » `حذف [تعداد]`
  » `ذخیره` (روی پیام)
  » `تکرار [تعداد]` (روی پیام)
  » `کپی روشن` | `کپی خاموش` (روی کاربر)

**✦ SECURITY & PRIVACY**
  » `پیوی قفل` | `پیوی باز`
  » `منشی روشن` | `منشی خاموش`
  » `انتی لوگین روشن` | `خاموش`
  » `سین روشن` | `سین خاموش`

**✦ DEFENSE SYSTEM**
  » `دشمن روشن` | `خاموش` (روی کاربر)
  » `دشمن همگانی روشن` | `خاموش`
  » `لیست دشمن`
  » `بلاک روشن` | `بلاک خاموش` (روی کاربر)
  » `سکوت روشن` | `سکوت خاموش` (روی کاربر)

**✦ FUN & UTILS**
  » `تایپ روشن` | `خاموش`
  » `بازی روشن` | `خاموش`
  » `ریاکشن [شکلک]` | `خاموش` (روی کاربر)
  » `تاس` | `تاس [عدد]` | `بولینگ`

**✦ TRANSLATOR**
  » `انگیلیسی روشن` | `خاموش`
  » `روسی روشن` | `خاموش`
  » `چینی روشن` | `خاموش`
  » `بولد روشن` | `خاموش`
━━━━━━━━━━━━━━━━━━━━
"""

# --- Updated Regex to include 'انگیلیسی' ---
COMMAND_REGEX = r"^(راهنما|فونت|فونت \d+|ساعت روشن|ساعت خاموش|بولد روشن|بولد خاموش|دشمن روشن|دشمن خاموش|منشی روشن|منشی خاموش|بلاک روشن|بلاک خاموش|سکوت روشن|سکوت خاموش|ذخیره|تکرار \d+|حذف \d+|سین روشن|سین خاموش|ریاکشن .*|ریاکشن خاموش|انگیلیسی روشن|انگیلیسی خاموش|اینگیلیسی روشن|اینگیلیسی خاموش|روسی روشن|روسی خاموش|چینی روشن|چینی خاموش|انتی لوگین روشن|انتی لوگین خاموش|کپی روشن|کپی خاموش|دشمن همگانی روشن|دشمن همگانی خاموش|لیست دشمن|تاس|تاس \d+|بولینگ|تایپ روشن|تایپ خاموش|بازی روشن|بازی خاموش|پیوی قفل|پیوی باز)$"

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
    if not ENEMY_REPLIES: return 
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

# --- Controllers ---
async def help_controller(client, message): await message.edit_text(HELP_TEXT)
async def font_controller(client, message):
    user_id = client.me.id
    cmd = message.text.split()
    if len(cmd) == 1:
        txt = "🔢 **FONTS LIST:**\n" + "\n".join([f"`{stylize_time('12:34', k)}` ({i})" for i, k in enumerate(FONT_KEYS_ORDER, 1)])
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
    # Clock
    if cmd == "ساعت روشن": CLOCK_STATUS[user_id] = True; await message.edit_text("✅ ساعت روشن شد.")
    elif cmd == "ساعت خاموش": CLOCK_STATUS[user_id] = False; await message.edit_text("❌ ساعت خاموش شد.")
    # Privacy
    elif cmd == "پیوی قفل": PV_LOCK_STATUS[user_id] = True; await message.edit_text("🔒 پیوی قفل شد.")
    elif cmd == "پیوی باز": PV_LOCK_STATUS[user_id] = False; await message.edit_text("🔓 پیوی باز شد.")
    elif cmd == "منشی روشن": SECRETARY_MODE_STATUS[user_id] = True; await message.edit_text("✅ منشی فعال شد.")
    elif cmd == "منشی خاموش": SECRETARY_MODE_STATUS[user_id] = False; USERS_REPLIED_IN_SECRETARY[user_id] = set(); await message.edit_text("❌ منشی غیرفعال شد.")
    elif cmd == "انتی لوگین روشن": ANTI_LOGIN_STATUS[user_id] = True; await message.edit_text("🚨 محافظت از نشست فعال شد.")
    elif cmd == "انتی لوگین خاموش": ANTI_LOGIN_STATUS[user_id] = False; await message.edit_text("❌ محافظت از نشست غیرفعال شد.")
    elif cmd == "سین روشن": AUTO_SEEN_STATUS[user_id] = True; await message.edit_text("👁 سین خودکار روشن.")
    elif cmd == "سین خاموش": AUTO_SEEN_STATUS[user_id] = False; await message.edit_text("❌ سین خودکار خاموش.")
    # Status
    elif cmd == "تایپ روشن": TYPING_MODE_STATUS[user_id] = True; PLAYING_MODE_STATUS[user_id] = False; await message.edit_text("✍️ تایپ فعال شد.")
    elif cmd == "تایپ خاموش": TYPING_MODE_STATUS[user_id] = False; await message.edit_text("❌ تایپ متوقف شد.")
    elif cmd == "بازی روشن": PLAYING_MODE_STATUS[user_id] = True; TYPING_MODE_STATUS[user_id] = False; await message.edit_text("🎮 وضعیت بازی فعال شد.")
    elif cmd == "بازی خاموش": PLAYING_MODE_STATUS[user_id] = False; await message.edit_text("❌ وضعیت بازی متوقف شد.")
    # Translate (Updated to support both spellings)
    elif cmd in ["انگیلیسی روشن", "اینگیلیسی روشن"]: AUTO_TRANSLATE_TARGET[user_id] = "en"; await message.edit_text("🇺🇸 ترجمه انگلیسی فعال شد.")
    elif cmd in ["انگیلیسی خاموش", "اینگیلیسی خاموش"]: AUTO_TRANSLATE_TARGET[user_id] = None; await message.edit_text("❌ ترجمه خاموش شد.")
    elif cmd == "روسی روشن": AUTO_TRANSLATE_TARGET[user_id] = "ru"; await message.edit_text("🇷🇺 ترجمه روسی فعال شد.")
    elif cmd == "روسی خاموش": AUTO_TRANSLATE_TARGET[user_id] = None; await message.edit_text("❌ ترجمه خاموش شد.")
    elif cmd == "چینی روشن": AUTO_TRANSLATE_TARGET[user_id] = "zh-CN"; await message.edit_text("🇨🇳 ترجمه چینی فعال شد.")
    elif cmd == "چینی خاموش": AUTO_TRANSLATE_TARGET[user_id] = None; await message.edit_text("❌ ترجمه خاموش شد.")
    # Text Style
    elif cmd == "بولد روشن": BOLD_MODE_STATUS[user_id] = True; await message.edit_text("𝗕 بولد خودکار روشن.")
    elif cmd == "بولد خاموش": BOLD_MODE_STATUS[user_id] = False; await message.edit_text("❌ بولد خودکار خاموش.")
    # Global Enemy
    elif cmd == "دشمن همگانی روشن": GLOBAL_ENEMY_STATUS[user_id] = True; await message.edit_text("⚔️ حالت جنگی فعال شد (پاسخ به همه).")
    elif cmd == "دشمن همگانی خاموش": GLOBAL_ENEMY_STATUS[user_id] = False; await message.edit_text("🏳️ حالت جنگی غیرفعال شد.")
    # Games
    elif cmd == "تاس": await client.send_dice(message.chat.id, "🎲")
    elif cmd == "بولینگ": await client.send_dice(message.chat.id, "🎳")
    elif cmd.startswith("تاس "): 
        try: await client.send_dice(message.chat.id, "🎲", reply_to_message_id=message.reply_to_message_id)
        except: pass
    
    # Reply-based commands
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id if message.reply_to_message.from_user else None
        if cmd.startswith("حذف "):
            try:
                count = int(cmd.split()[1])
                msg_ids = [m.id async for m in client.get_chat_history(message.chat.id, limit=count) if m.from_user.is_self]
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
                photos = [p async for p in client.get_chat_photos("me", limit=1)]
                if photos: ORIGINAL_PROFILE_DATA[user_id]['photo'] = photos[0].file_id
                
                COPY_MODE_STATUS[user_id] = True
                CLOCK_STATUS[user_id] = False
                
                new_bio = user.bio or ""
                target_photos = [p async for p in client.get_chat_photos(target_id, limit=1)]
                
                await client.update_profile(first_name=user.first_name, bio=new_bio[:70])
                if target_photos: await client.set_profile_photo(photo=target_photos[0].file_id)
                await message.edit_text("👤 هویت جعل شد.")
                
            elif cmd == "کپی خاموش":
                if user_id in ORIGINAL_PROFILE_DATA:
                    data = ORIGINAL_PROFILE_DATA[user_id]
                    COPY_MODE_STATUS[user_id] = False
                    await client.update_profile(first_name=data.get('first_name'), bio=data.get('bio'))
                    # Restore photo logic is complex without downloading, skipping for simplicity/safety
                    await message.edit_text("👤 هویت بازگردانده شد.")
            
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
            elif cmd == "بلاک روشن": await client.block_user(target_id); await message.edit_text("🚫 کاربر بلاک شد.")
            elif cmd == "بلاک خاموش": await client.unblock_user(target_id); await message.edit_text("⭕️ کاربر آنبلاک شد.")
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
            elif cmd.startswith("ریاکشن ") and cmd != "ریاکشن خاموش":
                emoji = cmd.split()[1]
                t = AUTO_REACTION_TARGETS.get(user_id, {})
                t[target_id] = emoji
                AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text(f"👍 واکنش {emoji} تنظیم شد.")
            elif cmd == "ریاکشن خاموش":
                t = AUTO_REACTION_TARGETS.get(user_id, {})
                if target_id in t: del t[target_id]
                AUTO_REACTION_TARGETS[user_id] = t
                await message.edit_text("❌ واکنش خودکار حذف شد.")
    elif cmd == "لیست دشمن":
        enemies = ACTIVE_ENEMIES.get(user_id, set())
        await message.edit_text(f"📜 تعداد دشمنان فعال: {len(enemies)}")

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
    client.add_handler(MessageHandler(lambda c, m: m.delete() if PV_LOCK_STATUS.get(c.me.id) else None, filters.private & ~filters.me & ~filters.bot), group=-5)
    client.add_handler(MessageHandler(lambda c, m: c.read_chat_history(m.chat.id) if AUTO_SEEN_STATUS.get(c.me.id) else None, filters.private & ~filters.me), group=-4)
    client.add_handler(MessageHandler(incoming_message_manager, filters.all & ~filters.me), group=-3)
    client.add_handler(MessageHandler(outgoing_message_modifier, filters.text & filters.me & ~filters.reply), group=-1)
    
    # Commands
    client.add_handler(MessageHandler(help_controller, filters.me & filters.regex("^راهنما$")))
    client.add_handler(MessageHandler(font_controller, filters.me & filters.regex(r"^(فونت|فونت \d+)$")))
    client.add_handler(MessageHandler(simple_toggle_controller, filters.me)) 
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
        "👋 به سلف ما خوش آمدید.",
        reply_markup=kb
    )

@manager_bot.on_message(filters.contact)
async def phone_received_handler(client, message):
    chat_id = message.chat.id
    phone_number = message.contact.phone_number
    
    msg = await message.reply_text("⏳ در حال اتصال به سرور تلگرام...", reply_markup=ReplyKeyboardRemove())
    
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
        
        success_text = (
            "✅ کد تایید ارسال شد!\n\n"
            "لطفا کد را به صورت زیر بفرستید:\n"
            "▫️ `1.1.1.1.1` (با نقطه)\n\n"
            "👇 منتظر کد شما هستم:"
        )
        
        try:
            await msg.edit_text(success_text)
        except MessageIdInvalid:
            await message.reply_text(success_text)
            
    except Exception as e:
        await user_client.disconnect()
        error_text = f"❌ خطا در ارسال کد:\n{str(e)}"
        try:
            await msg.edit_text(error_text)
        except MessageIdInvalid:
            await message.reply_text(error_text)

@manager_bot.on_message(filters.text & filters.private)
async def code_password_handler(client, message):
    chat_id = message.chat.id
    state = LOGIN_STATES.get(chat_id)
    
    if not state:
        return 

    user_client = state['client']
    text = message.text
    
    if state['step'] == 'code':
        code = re.sub(r"\D+", "", text)
        if not code:
            await message.reply_text("⚠️ فرمت کد صحیح نیست. لطفا دوباره تلاش کنید.")
            return
            
        try:
            await user_client.sign_in(state['phone'], state['hash'], code)
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
        await user_client.disconnect() 
        
        if sessions_collection is not None:
            sessions_collection.update_one(
                {'phone_number': phone},
                {'$set': {'session_string': session_str, 'font_style': 'stylized', 'disable_clock': False}},
                upsert=True
            )
        
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
    Thread(target=run_flask, daemon=True).start()
    
    if sessions_collection is not None:
        for doc in sessions_collection.find():
            try:
                logging.info(f"Restoring session for {doc.get('phone_number')}...")
                asyncio.create_task(start_bot_instance(doc['session_string'], doc.get('phone_number'), doc.get('font_style', 'stylized')))
            except: pass

    if BOT_TOKEN and BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        logging.info("Starting Manager Bot...")
        await manager_bot.start()
        await idle()
    else:
        logging.error("❌ BOT_TOKEN SET IS NOT SET!")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
