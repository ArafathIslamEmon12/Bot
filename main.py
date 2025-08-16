import os
import logging
import random
import asyncio
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

# Initialize environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ALLOWED_USERS = set(map(int, os.getenv("ALLOWED_USERS", "").split(","))) if os.getenv("ALLOWED_USERS") else set()
OWNER_ID = int(os.getenv("OWNER_ID", 0))  # Add owner ID from environment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global storage for predictions and language preferences
user_predictions = {}
user_language = {}  # Stores language preference: key=user_id, value='en' or 'bn'
prediction_lock = asyncio.Lock()

# Initialize bot and dispatcher
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# Create reply keyboard
keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✨ Generate Prediction"), 
         KeyboardButton(text="💎 Get Subscription")],
        [KeyboardButton(text="❓ Help"), 
         KeyboardButton(text="💸 Plans 💸")]
    ],
    resize_keyboard=True
)

# Helper function to calculate next draw time in UTC+6 (with 7-second advance)
def get_next_draw_seconds():
    # Get current UTC time and convert to UTC+6
    utc_now = datetime.utcnow()
    utc6_time = utc_now + timedelta(hours=6)
    
    # Extract seconds from current time
    current_second = utc6_time.second
    
    # Calculate seconds until next draw (every 30 seconds)
    base_seconds = 30 - (current_second % 30)
    
    # Show 7 seconds earlier than actual draw time
    adjusted_seconds = base_seconds - 4
    
    # Handle case when adjusted seconds would be negative
    if adjusted_seconds < 0:
        # Add 30 seconds to wrap to next period
        adjusted_seconds += 30
    
    return adjusted_seconds

# Calculate the next period timestamp (with 7-second advance)
def get_next_period_timestamp():
    utc_now = datetime.utcnow()
    utc6_time = utc_now + timedelta(hours=6)
    
    # Calculate next draw time (30-second intervals)
    current_second = utc6_time.second
    seconds_to_add = 30 - (current_second % 30)
    
    # Adjust to show 7 seconds earlier
    seconds_to_add -= 7
    if seconds_to_add < 0:
        seconds_to_add += 30
    
    next_draw_time = utc6_time + timedelta(seconds=seconds_to_add)
    return next_draw_time.strftime("%Y%m%d%H%M%S")

# =====================
# LANGUAGE MANAGEMENT
# =====================

def get_user_language(user_id):
    """Get user's language preference with English as default"""
    return user_language.get(user_id, 'en')

def create_translate_button(command):
    """Create inline button for translating current command"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="বাংলায় অনুবাদ করুন", callback_data=f"setlang_bn_{command}")]
    ])

# Callback handler for language selection
@dp.callback_query(F.data.startswith("setlang_bn_"))
async def set_bangla_language(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    command = callback.data.split('_')[2]  # Extract command name
    user_language[user_id] = 'bn'  # Set to Bangla
    
    # Edit original message to remove translate button
    await callback.message.edit_reply_markup(reply_markup=None)
    
    # Resend the command in Bangla
    if command == "start":
        await start_command(callback.message, force_bangla=True)
    elif command == "help":
        await help_command(callback.message, force_bangla=True)
    elif command == "generate":
        await generate_command(callback.message, force_bangla=True)
    
    await callback.answer()

# =====================
# COMMAND HANDLERS (BANGLA/ENGLISH)
# =====================

@dp.message(Command("start"))
async def start_command(message: types.Message, force_bangla=False):
    user_id = message.from_user.id
    lang = get_user_language(user_id) if not force_bangla else 'bn'
    
    if lang == 'bn':
        # Bangla version
        uid_display = f"🔑 <b>আপনার UID:</b> <code>{user_id}</code>\n\n"
        
        if user_id not in ALLOWED_USERS:
            await message.answer(
                uid_display +
                "🌟 <b>WinGo 30s প্রেডিকশন বটে স্বাগতম!</b> 🌟\n\n"
                "আমি WinGo 30s গেমের জন্য AI-চালিত ভবিষ্যদ্বাণী প্রদান করি। "
                "বর্তমানে, আপনি সীমিত অ্যাক্সেস সহ <b>ফ্রি সংস্করণ</b> ব্যবহার করছেন।\n\n"
                "🔓 <b>প্রিমিয়াম বৈশিষ্ট্য:</b>\n"
                "✅ ৫০০টি ঐতিহাসিক ডেটা বিশ্লেষণ করে পরবর্তী রাউন্ডের ভবিষ্যদ্বাণী\n"
                "👉 প্রিমিয়াম সাবস্ক্রিপশনের মাধ্যমে <b>সম্পূর্ণ অ্যাক্সেস পান</b>!",
                reply_markup=keyboard
            )
            return

        await message.answer(
            "🎉 <b>WinGo 30s প্রেডিকশন বটে স্বাগতম!</b> 🎉\n\n"
            "আমি আপনার ব্যক্তিগত AI সহকারী, WinGo 30s গেমের ফলাফল ভবিষ্যদ্বাণীর জন্য "
            "<b>উন্নত অ্যালগরিদম</b> এবং <b>রিয়েল-টাইম ডেটা বিশ্লেষণ</b> সহ!\n\n"
            "💎 <b>প্রিমিয়াম অ্যাকাউন্ট সক্রিয়!</b>\n"
            "আপনার সমস্ত বৈশিষ্ট্যে সম্পূর্ণ অ্যাক্সেস রয়েছে:\n"
            "✅ উন্নত ভবিষ্যদ্বাণী তৈরি করুন\n\n"
            "<b>উপলব্ধ কমান্ড:</b>\n"
            "✨ /generate - পরবর্তী ভবিষ্যদ্বাণী পান\n"
            "💎 /buy - আপনার সাবস্ক্রিপশন কিনুন এবং অ্যাক্সেস পান\n"
            "❓ /help - বিস্তারিত নির্দেশাবলী\n\n"
            "শুরু করতে <b>✨ Generate Prediction</b> ট্যাপ করুন!",
            reply_markup=keyboard
        )
    else:
        # English version with translate button
        uid_display = f"🔑 <b>Your UID:</b> <code>{user_id}</code>\n\n"
        
        if user_id not in ALLOWED_USERS:
            await message.answer(
                uid_display +
                "🌟 <b>Welcome to WinGo 30s Prediction Bot!</b> 🌟\n\n"
                "I provide AI-powered predictions for WinGo 30s game. "
                "Currently, you're using the <b>free version</b> with limited access.\n\n"
                "🔓 <b>Premium Features:</b>\n"
                "✅ Next round predictions by Analysing 500 historical data\n"
                "👉 <b>Get full access</b> with our premium subscription!",
                reply_markup=create_translate_button("start")
            )
            return

        await message.answer(
            "🎉 <b>Welcome to WinGo 30s Prediction Bot!</b> 🎉\n\n"
            "I'm your personal AI assistant for predicting WinGo 30s game results with "
            "<b>advanced algorithms</b> and <b>real-time data analysis</b>!\n\n"
            "💎 <b>Premium Account Activated!</b>\n"
            "You have full access to all features:\n"
            "✅ Generate Advance predictions\n\n"
            "<b>Available Commands:</b>\n"
            "✨ /generate - Get next prediction\n"
            "💎 /buy - Buy your subscription and get access\n"
            "❓ /help - Detailed instructions\n\n"
            "Tap <b>✨ Generate Prediction</b> to get started!",
            reply_markup=create_translate_button("start")
        )

@dp.message(Command("help"))
async def help_command(message: types.Message, force_bangla=False):
    user_id = message.from_user.id
    lang = get_user_language(user_id) if not force_bangla else 'bn'
    
    if lang == 'bn':
        # Bangla version
        await message.answer(
            "📚 <b>WinGo প্রেডিকশন বট গাইড</b>\n\n"
            "আমি উন্নত অ্যালগরিদম ব্যবহার করে WinGo 30s গেমের ফলাফল ভবিষ্যদ্বাণী করতে সাহায্য করি।\n\n"
            "✨ <b>/generate</b>\n"
            "পরবর্তী গেম রাউন্ডের জন্য ভবিষ্যদ্বাণী পান। প্রতিটি ভবিষ্যদ্বাণী অন্তর্ভুক্ত করে:\n"
            "- 🎯 সাইজ (বড়/ছোট)\n"
            "- 🎨 রঙ (লাল/সবুজ/বেগুনি)\n\n"
            "💎 <b>/buy</b>\n"
            "ভবিষ্যদ্বাণী তৈরি করতে প্রিমিয়াম বৈশিষ্ট্য আনলক করুন। নির্দেশাবলী অনুসরণ করুন "
            "আপনার সাবস্ক্রিপশন পেতে।\n\n"
            "❓ <b>/help</b>\n"
            "এই সহায়তা বার্তাটি দেখান\n\n"
            "🔁 <b>কিভাবে ভবিষ্যদ্বাণী কাজ করে:</b>\n"
            "1. আমি AI ব্যবহার করে ঐতিহাসিক প্যাটার্ন বিশ্লেষণ করি\n"
            "2. পরবর্তী রাউন্ডের জন্য ভবিষ্যদ্বাণী তৈরি করি\n"
            "সাহায্যের প্রয়োজন? @Emon001100-এ যোগাযোগ করুন",
            reply_markup=keyboard
        )
    else:
        # English version with translate button
        await message.answer(
            "📚 <b>WinGo Prediction Bot Guide</b>\n\n"
            "I help you predict WinGo 30s game results using advanced algorithms. "
            "Here's how to use me:\n\n"
            "✨ <b>/generate</b>\n"
            "Get the prediction for the next game round. Each prediction includes:\n"
            "- 🎯 Size (Big/Small)\n"
            "- 🎨 Color (Red/Green/Violet)\n\n"
            "💎 <b>/buy</b>\n"
            "Unlock premium features to generate predictions. Follow the instructions "
            "to get your subscription.\n\n"
            "❓ <b>/help</b>\n"
            "Show this help message\n\n"
            "🔁 <b>How predictions work:</b>\n"
            "1. I analyze historical patterns using AI\n"
            "2. Generate prediction for the NEXT round\n"
            "Need help? Contact @Emon001100",
            reply_markup=create_translate_button("help")
        )

@dp.message(Command("buy"))
async def buy_command(message: types.Message, force_bangla=False):
    user_id = message.from_user.id
    lang = get_user_language(user_id) if not force_bangla else 'bn'
    
    if lang == 'bn':
        # Bangla version
        await message.answer(
            f"💎 <b>প্রিমিয়াম সাবস্ক্রিপশন - সম্পূর্ণ অ্যাক্সেস আনলক করুন</b>\n\n"
            f"🔑 <b>আপনার UID:</b> <code>{user_id}</code>\n\n"
            "📝 <b>কিভাবে সাবস্ক্রাইব করবেন:</b>\n"
            "1. মালিক @Emon001100-কে টেলিগ্রামে যোগাযোগ করুন\n"
            "2. উপরে দেখানো আপনার টেলিগ্রাম আইডি পাঠান\n"
            "3. বিকাশ বা নগদ অ্যাকাউন্টে টাকা পাঠান\n\n"
            "   বিকাশ+নগদ: 01756519749\n\n"
            "4. পেমেন্ট সম্পূর্ণ করুন\n\n"
            "🔄 <b>পেমেন্টের পর:</b>\n"
            "• পেমেন্ট প্রমাণ মালিক @Emon001100-কে পাঠান\n"
            "• ৫ মিনিটের মধ্যে আপনার অ্যাকাউন্ট সক্রিয় করা হবে\n"
            "• আপনি নিশ্চিতকরণ বার্তা পাবেন\n\n"
            "🌟 <b>প্রিমিয়াম সুবিধা:</b>\n"
            "• সীমাহীন ভবিষ্যদ্বাণী\n"
            "• প্রাথমিক সমর্থন\n"
            "• বিশেষ বোনাস বৈশিষ্ট্য\n\n"
            "সাহায্যের প্রয়োজন? সরাসরি মালিক @Emon001100-এর সাথে যোগাযোগ করুন!",
            reply_markup=keyboard
        )
    else:
        # English version
        await message.answer(
            f"💎 <b>Premium Subscription - Unlock Full Access</b>\n\n"
            f"🔑 <b>Your UID:</b> <code>{user_id}</code>\n\n"
            "📝 <b>How to subscribe:</b>\n"
            "1. Contact the OWNER @Emon001100 on Telegram\n"
            "2. Send your telegram ID shown above\n"
            "3. Send money on Bkash or Nagad account\n\n"
            "   Bkash+Nagat: 01756519749\n\n"
            "4. Complete payment\n\n"
            "🔄 <b>After payment:</b>\n"
            "• Send payment proof to OWNER @Emon001100\n"
            "• Your account will be activated within 5 minutes\n"
            "• You'll receive confirmation message\n\n"
            "🌟 <b>Premium Benefits:</b>\n"
            "• Unlimited predictions\n"
            "• Priority support\n"
            "• Special bonus features\n\n"
            "Need help? Contact with OWNER @Emon001100 directly!",
            reply_markup=create_translate_button("buy")
        )

@dp.message(Command("removeuser"))
async def remove_user_command(message: types.Message):
    """Remove a user from the allowed list (Owner only)"""
    if message.from_user.id != OWNER_ID:
        logger.warning(f"Unauthorized removeuser attempt by {message.from_user.id}")
        return
        
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ <b>Usage:</b>\n<code>/removeuser USER_ID</code>")
            return
            
        user_id = int(args[1])
        
        if user_id in ALLOWED_USERS:
            ALLOWED_USERS.remove(user_id)
            
            # Update .env file
            with open('.env', 'w') as f:
                f.write(f"BOT_TOKEN={BOT_TOKEN}\n")
                f.write(f"OWNER_ID={OWNER_ID}\n")
                if ALLOWED_USERS:  # Only write if not empty
                    f.write(f"ALLOWED_USERS={','.join(map(str, ALLOWED_USERS))}")
                
            await message.answer(f"✅ <b>User removed!</b>\nUser ID: <code>{user_id}</code> can no longer generate predictions.")
            logger.info(f"Removed user: {user_id}")
            
            # Optional: Notify the removed user
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="⚠️ <b>Subscription Ended</b>\n\n"
                         "Your access to premium predictions has been removed.\n"
                         "Contact @Emon001100 if this was a mistake."
                )
            except Exception as e:
                logger.error(f"Could not notify user {user_id}: {e}")
        else:
            await message.answer(f"ℹ️ User <code>{user_id}</code> was not in the allowed list.")
            
    except (ValueError, IndexError):
        await message.answer("❌ <b>Invalid format</b>\nUsage: <code>/removeuser USER_ID</code>\nExample: <code>/removeuser 123456789</code>")
    except Exception as e:
        await message.answer(f"⚠️ <b>Error:</b> {str(e)}")
        logger.error(f"Removeuser error: {e}")

@dp.message(Command("adduser"))
async def add_user_command(message: types.Message):
    # Only allow owner to use this command
    if message.from_user.id != OWNER_ID:
        logger.warning(f"Unauthorized adduser attempt by {message.from_user.id}")
        return
        
    try:
        # Extract user ID from command
        args = message.text.split()
        if len(args) < 2:
            await message.answer("❌ <b>Usage:</b>\n<code>/adduser USER_ID</code>")
            return
            
        user_id = int(args[1])
        
        # Add user to allowed list
        if user_id not in ALLOWED_USERS:
            ALLOWED_USERS.add(user_id)
            
            # Update .env file
            with open('.env', 'a') as f:
                f.write(f"\nALLOWED_USERS={','.join(map(str, ALLOWED_USERS))}")
                
            await message.answer(f"✅ <b>User added!</b>\nUser ID: <code>{user_id}</code> can now generate predictions.")
            logger.info(f"Added new user: {user_id}")
        else:
            await message.answer(f"ℹ️ User <code>{user_id}</code> is already in the allowed list.")
            
    except (ValueError, IndexError):
        await message.answer("❌ <b>Invalid format</b>\nUsage: <code>/adduser USER_ID</code>\nExample: <code>/adduser 123456789</code>")
    except Exception as e:
        await message.answer(f"⚠️ <b>Error:</b> {str(e)}")
        logger.error(f"Adduser error: {e}")

@dp.message(F.text.casefold() == "💎 get subscription")
async def buy_button(message: types.Message):
    await buy_command(message)

@dp.message(F.text.casefold() == "❓ help")
async def help_button(message: types.Message):
    await help_command(message)

@dp.message(Command("generate"))
@dp.message(F.text.casefold() == "✨ generate prediction")
async def generate_command(message: types.Message, force_bangla=False):
    user_id = message.from_user.id
    lang = get_user_language(user_id) if not force_bangla else 'bn'
    
    if lang == 'bn':
        uid_display = f"🔑 <b>আপনার UID:</b> <code>{user_id}</code>\n\n"
    else:
        uid_display = f"🔑 <b>Your UID:</b> <code>{user_id}</code>\n\n"

    # Subscription check
    if user_id not in ALLOWED_USERS:
        if lang == 'bn':
            await message.answer(
                uid_display +
                "🔒 <b>প্রিমিয়াম সাবস্ক্রিপশন প্রয়োজন</b>\n\n"
                "ভবিষ্যদ্বাণী তৈরি করতে আপনার একটি প্রিমিয়াম সাবস্ক্রিপশন প্রয়োজন।\n\n"
                "👉 <b>আপগ্রেড করার সুবিধা:</b>\n"
                "• সীমাহীন ভবিষ্যদ্বাণী\n"
                "• রিয়েল-টাইম ভবিষ্যদ্বাণী\n"
                "সম্পূর্ণ অ্যাক্সেস আনলক করতে <b>💎 Get Subscription</b> ট্যাপ করুন!",
                reply_markup=keyboard
            )
        else:
            await message.answer(
                uid_display +
                "🔒 <b>Premium Subscription Required</b>\n\n"
                "You need a premium subscription to generate predictions.\n\n"
                "👉 <b>Benefits of upgrading:</b>\n"
                "• Unlimited predictions\n"
                "• Real-time prediction\n"
                "Tap <b>💎 Get Subscription</b> to unlock full access!",
                reply_markup=create_translate_button("generate")
            )
        return

    # Show loading animation with proper language
    if lang == 'bn':
        loading_text = "🔮 <i>গেম প্যাটার্ন বিশ্লেষণ করা হচ্ছে...</i>"
        calculating_text = "🧠 <i>সম্ভাবনা গণনা করা হচ্ছে...</i>"
    else:
        loading_text = "🔮 <i>Analyzing game patterns...</i>"
        calculating_text = "🧠 <i>Calculating probabilities...</i>"
    
    loading_msg = await message.answer(loading_text)
    await asyncio.sleep(1)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=loading_msg.message_id,
        text=calculating_text
    )
    await asyncio.sleep(1)
    await bot.delete_message(chat_id=message.chat.id, message_id=loading_msg.message_id)

    # Get next period and seconds left
    next_period = get_next_period_timestamp()
    seconds_left = get_next_draw_seconds()
    is_fresh = False

    async with prediction_lock:
        # Get existing or create new prediction
        if (user_id, next_period) in user_predictions:
            size, color = user_predictions[(user_id, next_period)]
        else:
            size = random.choice(["Big", "Small"])
            color = random.choice(["Red", "Green", "Violet"])
            user_predictions[(user_id, next_period)] = (size, color)
            is_fresh = True
            # Cleanup old predictions
            current_time = datetime.utcnow() + timedelta(hours=6)
            current_timestamp = current_time.strftime("%Y%m%d%H%M%S")
            for key in list(user_predictions.keys()):
                if key[1] < current_timestamp:
                    del user_predictions[key]

    # Format response
    color_emoji = "🔴" if color == "Red" else "🟢" if color == "Green" else "🟣"
    
    if lang == 'bn':
        # Bangla prediction
        await message.answer(
            f"🎯 <b>WinGo 30s ভবিষ্যদ্বাণী</b>\n\n"
            f"🔮 <b>পরবর্তী সময়ের জন্য ভবিষ্যদ্বাণী</b>\n\n"
            f"📏 <b>সাইজ:</b> {'বড়' if size == 'Big' else 'ছোট'}\n\n"
            f"🎨 <b>রঙ:</b> {color_emoji} {'লাল' if color == 'Red' else 'সবুজ' if color == 'Green' else 'বেগুনি'}\n\n"
            f"⏳ <b>পরবর্তী ড্র: {seconds_left} সেকেন্ডে</b>\n",
            reply_markup=keyboard
        )
    else:
        # English prediction with translate button
        await message.answer(
            f"🎯 <b>WinGo 30s Prediction</b>\n\n"
            f"🔮 <b>Prediction for next Period</b>\n\n"
            f"📏 <b>Size:</b> {size}\n\n"
            f"🎨 <b>Color:</b> {color_emoji} {color}\n\n"
            f"⏳ <b>Next draw in: {seconds_left} seconds</b>\n",
            reply_markup=create_translate_button("generate")
        )

# =====================
# PLANS COMMANDS SECTION
# =====================

# Main Plans Keyboard
plans_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💸৫০০TK Plan💸"), 
         KeyboardButton(text="💸১০০০TK Plan💸")],
        [KeyboardButton(text="💸২০০০TK Plan💸"),
         KeyboardButton(text="🔙 Main Menu")]
    ],
    resize_keyboard=True
)

# 500TK Plan Options
plan_500_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤑 ৫০০ TK ৭ স্টেপ প্যান 🤑"),
         KeyboardButton(text="🤑 ৫০০ TK ৬ স্টেপ প্যান 🤑")],
        [KeyboardButton(text="🔙 Plans Menu")]
    ],
    resize_keyboard=True
)

# 1000TK Plan Options
plan_1000_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤑 ১০০০ TK ৭ স্টেপ প্যান 🤑"),
         KeyboardButton(text="🤑 ১০০০ TK ৬ স্টেপ প্যান 🤑")],
        [KeyboardButton(text="🔙 Plans Menu")]
    ],
    resize_keyboard=True
)

# 2000TK Plan Options
plan_2000_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🤑 ২০০০ TK ৭ স্টেপ প্যান 🤑"),
         KeyboardButton(text="🤑 ২০০০ TK ৬ স্টেপ প্যান 🤑")],
        [KeyboardButton(text="🔙 Plans Menu")]
    ],
    resize_keyboard=True
)

# Main Plans Menu Handler
@dp.message(F.text.casefold() == "💸 plans 💸")
async def plans_menu(message: types.Message):
    await message.answer(
        "💰 <b>বেটিং প্ল্যান সিলেক্ট করুন</b> 💰\n\n"
        "নিচ থেকে আপনার পছন্দের প্ল্যানটি সিলেক্ট করুন:",
        reply_markup=plans_keyboard
    )

# Back to Main Menu
@dp.message(F.text.casefold() == "🔙 main menu")
async def back_to_main(message: types.Message):
    await message.answer(
        "🏠 <b>মেইন মেনুতে ফিরে আসা হয়েছে</b>",
        reply_markup=keyboard
    )

# Back to Plans Menu
@dp.message(F.text.casefold() == "🔙 plans menu")
async def back_to_plans(message: types.Message):
    await message.answer(
        "🔙 <b>প্ল্যান মেনুতে ফিরে আসা হয়েছে</b>",
        reply_markup=plans_keyboard
    )

# =====================
# 500TK PLAN HANDLERS
# =====================

@dp.message(F.text.casefold() == "💸৫০০tk plan💸")
async def plan_500_menu(message: types.Message):
    await message.answer(
        "💵 <b>৫০০ টাকা প্ল্যান</b> 💵\n\n"
        "নিচ থেকে আপনার পছন্দের স্টেপ প্যান সিলেক্ট করুন:",
        reply_markup=plan_500_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ৫০০ tk ৭ স্টেপ প্যান 🤑")
async def plan_500_option_a(message: types.Message):
    await message.answer(
        "🤑 <b>৫০০ টাকা ৭ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৯০% \n"
        "✅ ১ম ৩৳ মারবেন\n"
        "✅ ৩৳ হারলে ৬৳ \n"
        "✅ ৬৳ হারলে ১২৳\n"
        "✅ ১২৳ হারলে ২৪৳\n"
        "✅ ২৪৳ হারলে ৪৮৳\n"
        "✅ ৪৮৳ হারলে ৯৬৳\n"
        "✅ ৯৬৳ হারলে ১৯২ \n"
        "🏆১৯৬৳ Win🏆  (৯০% chance)\n"
        "⚠️১৯২৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_500_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ৫০০ tk ৬ স্টেপ প্যান 🤑")
async def plan_500_option_b(message: types.Message):
    await message.answer(
        "🤑 <b>৫০০ টাকা ৬ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৮০% 💸\n"
        "✅ ১ম ৫৳ মারবেন\n"
        "✅ ৫৳ হারলে ১০৳ \n"
        "✅ ১০৳ হারলে ২০৳\n"
        "✅ ২০৳ হারলে ৪০৳\n"
        "✅ ৪০৳ হারলে ৮০৳\n"
        "✅ ৮০৳ হারলে ১৬০৳\n"
        "🏆১৬০৳ Win🏆  (৮০% chance)\n"
        "⚠️১৬০৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_500_keyboard
    )

# =====================
# 1000TK PLAN HANDLERS
# =====================

@dp.message(F.text.casefold() == "💸১০০০tk plan💸")
async def plan_1000_menu(message: types.Message):
    await message.answer(
        "💵 <b>১০০০ টাকা প্ল্যান</b> 💵\n\n"
        "নিচ থেকে আপনার পছন্দের স্টেপ প্যান সিলেক্ট করুন:",
        reply_markup=plan_1000_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ১০০০ tk ৭ স্টেপ প্যান 🤑")
async def plan_1000_option_a(message: types.Message):
    await message.answer(
        "🤑 <b>১০০০ টাকা ৭ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৯০% 💸\n"
        "✅ ১ম ৫৳ মারবেন\n"
        "✅ ৫৳ হারলে ১০৳ \n"
        "✅ ১০৳ হারলে ২০৳\n"
        "✅ ২০৳ হারলে ৪০৳\n"
        "✅ ৪০৳ হারলে ৮০৳\n"
        "✅ ৮০৳ হারলে ১৬০৳\n"
        "✅ ১৬০৳ হারলে ৩২০৳ \n"
        "🏆৩২০৳ Win🏆  (৯০% chance)\n"
        "⚠️৩২০৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_1000_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ১০০০ tk ৬ স্টেপ প্যান 🤑")
async def plan_1000_option_b(message: types.Message):
    await message.answer(
        "🤑 <b>১০০০ টাকা ৬ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৮০% 💸\n"
        "✅ ১ম ১০৳ মারবেন\n"
        "✅ ১০৳ হারলে ২০৳ \n"
        "✅ ২০৳ হারলে ৪০৳\n"
        "✅ ৪০৳ হারলে ৮০৳\n"
        "✅ ৮০৳ হারলে ১৬০৳\n"
        "✅ ১৬০৳ হারলে ৩২০৳\n"
        "🏆৩২০৳ Win🏆 (৮০% chance)\n"
        "⚠️৩২০৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_1000_keyboard
    )

# =====================
# 2000TK PLAN HANDLERS
# =====================

@dp.message(F.text.casefold() == "💸২০০০tk plan💸")
async def plan_2000_menu(message: types.Message):
    await message.answer(
        "💵 <b>২০০০ টাকা প্ল্যান</b> 💵\n\n"
        "নিচ থেকে আপনার পছন্দের স্টেপ প্যান সিলেক্ট করুন:",
        reply_markup=plan_2000_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ২০০০ tk ৭ স্টেপ প্যান 🤑")
async def plan_2000_option_a(message: types.Message):
    await message.answer(
        "🤑 <b>২০০০ টাকা ৭ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৯০% 💸\n"
        "✅ ১ম ১০৳ মারবেন\n"
        "✅ ১০৳ হারলে ২০৳ \n"
        "✅ ২০৳ হারলে ৪০৳\n"
        "✅ ৪০৳ হারলে ৮০৳\n"
        "✅ ৮০৳ হারলে ১৬০৳\n"
        "✅ ১৬০৳ হারলে ৩২০৳\n"
        "✅ ৩২০৳ হারলে ৬৪০৳ \n"
        "🏆৬৪০৳ Win🏆  (৯০% chance)\n"
        "⚠️৬৪০৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_2000_keyboard
    )

@dp.message(F.text.casefold() == "🤑 ২০০০ tk ৬ স্টেপ প্যান 🤑")
async def plan_2000_option_b(message: types.Message):
    await message.answer(
        "🤑 <b>২০০০ টাকা ৬ স্টেপ প্যান</b> 🤑\n\n"
        "💸 Win rate ৮০% 💸\n"
        "✅ ১ম ২০৳ মারবেন\n"
        "✅ ২০৳ হারলে ৪০৳ \n"
        "✅ ৪০৳ হারলে ৮০৳\n"
        "✅ ৮০৳ হারলে ১৬০৳\n"
        "✅ ১৬০৳ হারলে ৩২০৳\n"
        "✅ ৩২০৳ হারলে ৬৪০৳\n"
        "🏆৬৪০৳ Win🏆  (৮০% chance)\n"
        "⚠️৬৪০৳ হারলে ১ম স্টেপ থেকে শুরু করবেন⚠️",
        reply_markup=plan_2000_keyboard
    )

# Start the bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
