# main.py
import os
import asyncio
import aiohttp
import json
import logging
from datetime import datetime
from pytz import timezone as pytz_timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
import pytz
import re

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8307741402:AAGLI1lDZY6mbG-EwGXSxVZeZs62aeuPktc')
API_URL = os.environ.get('API_URL', 'https://like-api-frexy.up.railway.app')
ADMIN_IDS = [int(id.strip()) for id in os.environ.get('ADMIN_IDS', '6417430059').split(',')]
ALLOWED_GROUP_ID = int(os.environ.get('ALLOWED_GROUP_ID', '-1003982689528'))
VIDEO_HOST_URL = os.environ.get('VIDEO_HOST_URL', 'https://files.catbox.moe/3dfc4m.mp4')

# Data storage
user_data = {}
like_queue = {}
pending_operations = {}

# Region mapping
REGIONS = {
    'bd': 'Bangladesh',
    'ind': 'India',
    'us': 'United States',
    'uk': 'United Kingdom',
    'id': 'Indonesia',
    'my': 'Malaysia',
    'sg': 'Singapore',
    'ph': 'Philippines'
}

def get_indian_time():
    """Get current time in IST"""
    ist = pytz_timezone('Asia/Kolkata')
    return datetime.now(ist)

def format_time():
    """Format time in IST"""
    return get_indian_time().strftime('%I:%M:%S %p IST')

def get_time_display():
    """Get full time display"""
    now = get_indian_time()
    return now.strftime('%I:%M:%S %p IST | %d %b %Y')

async def api_request(endpoint, method='GET', data=None):
    """Make API requests without JWT"""
    url = f"{API_URL}{endpoint}"
    async with aiohttp.ClientSession() as session:
        try:
            if method.upper() == 'GET':
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API Error {response.status}: {await response.text()}")
                        return None
            elif method.upper() == 'POST':
                async with session.post(url, json=data, timeout=30) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"API Error {response.status}: {await response.text()}")
                        return None
        except asyncio.TimeoutError:
            logger.error(f"API Timeout: {endpoint}")
            return None
        except Exception as e:
            logger.error(f"API Error: {e}")
            return None

async def call_jwt_endpoint():
    """Call /jwt endpoint 3 times with 1 minute gap"""
    results = []
    for i in range(3):
        try:
            result = await api_request('/jwt', method='POST')
            if result:
                results.append(f"✅ Call {i+1}: Success")
                logger.info(f"JWT call {i+1}/3: Success")
            else:
                results.append(f"❌ Call {i+1}: Failed")
                logger.error(f"JWT call {i+1}/3: Failed")
            await asyncio.sleep(60)  # 1 minute gap
        except Exception as e:
            results.append(f"❌ Call {i+1}: Error - {str(e)}")
            logger.error(f"JWT call {i+1}/3: {e}")
    return results

async def get_user_info(uid):
    """Get user information from API"""
    try:
        result = await api_request(f'/user/{uid}')
        return result
    except Exception as e:
        logger.error(f"Failed to get user info for {uid}: {e}")
        return None

async def send_like(uid, count=1):
    """Send likes to a UID"""
    try:
        result = await api_request(f'/like/{uid}', method='POST', data={'count': count})
        return result
    except Exception as e:
        logger.error(f"Failed to send likes to {uid}: {e}")
        return None

def parse_video_url(video_data):
    """Parse video URL from API response"""
    if not video_data:
        return None
    
    # If video_data is a string, check if it's a URL or file path
    if isinstance(video_data, str):
        if video_data.startswith('http'):
            return video_data
        elif video_data.startswith('/'):
            return f"{VIDEO_HOST_URL}{video_data}"
        else:
            return f"{VIDEO_HOST_URL}/{video_data}"
    
    # If video_data is a dict with URL field
    if isinstance(video_data, dict):
        if 'url' in video_data:
            return video_data['url']
        if 'path' in video_data:
            return f"{VIDEO_HOST_URL}{video_data['path']}"
        if 'video' in video_data:
            return video_data['video']
    
    return None

async def send_like_with_media(uid, count, like_type, context, user_info=None):
    """Send likes with video/media support"""
    try:
        # Get user info if not provided
        if not user_info:
            user_info = await get_user_info(uid)
            if not user_info:
                logger.error(f"Failed to get user info for {uid}")
                return False
        
        # Send likes
        like_response = await send_like(uid, count)
        
        if like_response:
            current_time = get_indian_time()
            
            # Get video URL
            video_url = None
            if 'video' in user_info:
                video_url = parse_video_url(user_info['video'])
            elif 'video_url' in user_info:
                video_url = parse_video_url(user_info['video_url'])
            
            # Prepare message
            message = (
                f"✅ *LIKE SENT SUCCESSFULLY!*\n\n"
                f"👤 *PLAYER:* {user_info.get('name', 'Unknown')}\n"
                f"🆔 *UID:* `{uid}`\n"
                f"🌍 *REGION:* {user_info.get('region', 'N/A').upper()}\n"
                f"📊 *LIKES BEFORE:* {user_info.get('likes_before', 0)}\n"
                f"💖 *LIKES GIVEN:* {count}\n"
                f"✨ *LIKES AFTER:* {user_info.get('likes_after', 0)}\n"
                f"⚙️ *BATCH:* {like_response.get('batch', 0)}\n"
                f"💞 *LEFT:* {like_response.get('remaining', 0)}\n"
                f"📌 *TYPE:* {like_type.upper()}\n"
                f"⏰ *TIME:* {current_time.strftime('%I:%M:%S %p IST')}"
            )
            
            # Send to group with video if available
            try:
                if video_url and video_url.startswith('http'):
                    # Send video
                    await context.bot.send_video(
                        chat_id=ALLOWED_GROUP_ID,
                        video=video_url,
                        caption=message,
                        parse_mode='Markdown',
                        supports_streaming=True
                    )
                else:
                    # Send text only
                    await context.bot.send_message(
                        chat_id=ALLOWED_GROUP_ID,
                        text=message,
                        parse_mode='Markdown'
                    )
            except Exception as e:
                logger.error(f"Failed to send media: {e}")
                # Fallback to text only
                await context.bot.send_message(
                    chat_id=ALLOWED_GROUP_ID,
                    text=message,
                    parse_mode='Markdown'
                )
            
            # Notify admin
            admin_message = (
                f"🤖 *LIKE EXECUTED*\n\n"
                f"🆔 *UID:* `{uid}`\n"
                f"👤 *Player:* {user_info.get('name', 'Unknown')}\n"
                f"📌 *Type:* {like_type.upper()}\n"
                f"📊 *Count:* {count}\n"
                f"⏰ *Time:* {format_time()}\n"
                f"📹 *Video:* {'✅' if video_url else '❌'}"
            )
            
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
            
            logger.info(f"✅ Like sent to {uid} - {count} likes")
            return True
        else:
            logger.error(f"❌ Failed to send like to {uid}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing like for {uid}: {e}")
        return False

async def process_auto_likes(context: ContextTypes.DEFAULT_TYPE):
    """Process auto likes for all UIDs"""
    try:
        current_time = get_indian_time()
        hour = current_time.hour
        minute = current_time.minute
        
        # Check if it's 4:10 AM - call /jwt 3 times
        if hour == 4 and minute == 10:
            logger.info("⏰ 4:10 AM - Calling JWT endpoint 3 times")
            results = await call_jwt_endpoint()
            
            # Notify admin about JWT calls
            admin_message = "🤖 *JWT ENDPOINT CALLED*\n\n" + "\n".join(results) + f"\n\n⏰ Time: {format_time()}"
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=admin_message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin {admin_id}: {e}")
        
        # Check if it's 4:55 AM - start auto likes
        if hour == 4 and minute == 55:
            logger.info("⏰ 4:55 AM - Starting auto likes")
            
            auto_like_uids = [uid for uid, data in user_data.items() if data.get('auto_like', False)]
            
            if auto_like_uids:
                admin_message = (
                    f"🤖 *AUTO LIKE STARTED*\n\n"
                    f"📊 Total: {len(auto_like_uids)} UIDs\n"
                    f"⏰ Time: {format_time()}"
                )
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass
            
            for uid in auto_like_uids:
                try:
                    await process_single_like(uid, 'auto', context)
                    await asyncio.sleep(60)  # 1 minute gap between users
                except Exception as e:
                    logger.error(f"Auto like failed for {uid}: {e}")
        
        # Check if it's 5:55 AM - process target likes
        if hour == 5 and minute == 55:
            logger.info("⏰ 5:55 AM - Processing target likes")
            
            target_like_uids = [uid for uid, data in user_data.items() if data.get('target_likes', 0) > 0]
            
            if target_like_uids:
                admin_message = (
                    f"🤖 *TARGET LIKE STARTED*\n\n"
                    f"📊 Total: {len(target_like_uids)} UIDs\n"
                    f"⏰ Time: {format_time()}"
                )
                for admin_id in ADMIN_IDS:
                    try:
                        await context.bot.send_message(
                            chat_id=admin_id,
                            text=admin_message,
                            parse_mode='Markdown'
                        )
                    except Exception:
                        pass
            
            for uid in target_like_uids:
                try:
                    target_count = user_data[uid].get('target_likes', 0)
                    await process_single_like(uid, 'target', context, target_count)
                    await asyncio.sleep(60)  # 1 minute gap between users
                except Exception as e:
                    logger.error(f"Target like failed for {uid}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in auto like processor: {e}")

async def process_single_like(uid, like_type, context, count=10):
    """Process a single like operation"""
    try:
        # Get user info
        user_info = await get_user_info(uid)
        if not user_info:
            logger.error(f"Failed to get user info for {uid}")
            return False
        
        # Determine like count
        if like_type == 'auto':
            like_count = 10
        elif like_type == 'target':
            like_count = count if count > 0 else 10
        else:
            like_count = 1
        
        # Send likes with media
        return await send_like_with_media(uid, like_count, like_type, context, user_info)
        
    except Exception as e:
        logger.error(f"Error processing like for {uid}: {e}")
        return False

async def check_auth(update: Update):
    """Check if user is authorized"""
    try:
        user_id = update.effective_user.id
        
        # Admin check
        if user_id in ADMIN_IDS:
            return True
        
        # Group check
        chat_id = update.effective_chat.id
        if chat_id == ALLOWED_GROUP_ID:
            return True
        
        return False
    except Exception as e:
        logger.error(f"Auth check error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized access!")
        return
    
    await update.message.reply_text(
        "🤖 *LIKE BOT ACTIVE*\n\n"
        "*Commands:*\n"
        "• `/like <region> <uid>` - Send 1 like\n"
        "• `/autolike <region> <uid>` - Set auto like (10 likes at 4:55 AM)\n"
        "• `/tlike <region> <uid> <count>` - Set target likes (at 5:55 AM)\n"
        "• `/list` - Show all configured UIDs\n"
        "• `/dlike <uid>` - Delete settings for UID\n"
        "• `/check <uid>` - Check user info\n"
        "• `/stats` - Show bot statistics\n\n"
        "*Regions:* bd, ind, us, uk, id, my, sg, ph\n\n"
        "⚠️ *Admin only commands*",
        parse_mode='Markdown'
    )

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a single like"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ *Usage:* `/like <region> <uid>`\n"
                "Example: `/like bd 12345`",
                parse_mode='Markdown'
            )
            return
        
        region = args[0].lower()
        uid = args[1]
        
        if region not in REGIONS:
            await update.message.reply_text(
                f"❌ Invalid region!\nAvailable: {', '.join(REGIONS.keys())}",
                parse_mode='Markdown'
            )
            return
        
        # Process like
        success = await process_single_like(uid, 'single', context)
        
        if success:
            await update.message.reply_text(
                f"✅ *Like sent successfully!*\n\n"
                f"🆔 UID: `{uid}`\n"
                f"🌍 Region: {REGIONS[region]}\n"
                f"⏰ Time: {format_time()}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ Failed to send like to UID: `{uid}`\n"
                f"Please check if UID is valid.",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def autolike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set auto like"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ *Usage:* `/autolike <region> <uid>`\n"
                "Example: `/autolike bd 12345`",
                parse_mode='Markdown'
            )
            return
        
        region = args[0].lower()
        uid = args[1]
        
        if region not in REGIONS:
            await update.message.reply_text(
                f"❌ Invalid region!\nAvailable: {', '.join(REGIONS.keys())}",
                parse_mode='Markdown'
            )
            return
        
        # Get user info for name
        user_info = await get_user_info(uid)
        if not user_info:
            await update.message.reply_text(
                f"❌ Failed to get user info for UID: `{uid}`\n"
                f"Please check if UID is valid.",
                parse_mode='Markdown'
            )
            return
        
        name = user_info.get('name', f'Player_{uid[:5]}')
        
        # Store settings
        user_data[uid] = {
            'region': region,
            'auto_like': True,
            'target_likes': 0,
            'name': name,
            'added_by': update.effective_user.id,
            'added_time': format_time()
        }
        
        await update.message.reply_text(
            f"✅ *AUTO LIKE SET*\n\n"
            f"👤 *Player:* {name}\n"
            f"🆔 *UID:* `{uid}`\n"
            f"🌍 *Region:* {REGIONS[region]}\n"
            f"⚙️ *Type:* Auto Like (10 likes)\n"
            f"🕐 *Schedule:* 4:55 AM IST\n"
            f"📅 *Added:* {format_time()}",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def tlike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set target likes"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "❌ *Usage:* `/tlike <region> <uid> <count>`\n"
                "Example: `/tlike bd 12345 50`",
                parse_mode='Markdown'
            )
            return
        
        region = args[0].lower()
        uid = args[1]
        target_count = int(args[2])
        
        if region not in REGIONS:
            await update.message.reply_text(
                f"❌ Invalid region!\nAvailable: {', '.join(REGIONS.keys())}",
                parse_mode='Markdown'
            )
            return
        
        if target_count <= 0:
            await update.message.reply_text("❌ Target count must be greater than 0!")
            return
        
        # Get user info for name
        user_info = await get_user_info(uid)
        if not user_info:
            await update.message.reply_text(
                f"❌ Failed to get user info for UID: `{uid}`\n"
                f"Please check if UID is valid.",
                parse_mode='Markdown'
            )
            return
        
        name = user_info.get('name', f'Player_{uid[:5]}')
        
        # Store settings
        user_data[uid] = {
            'region': region,
            'auto_like': False,
            'target_likes': target_count,
            'name': name,
            'added_by': update.effective_user.id,
            'added_time': format_time()
        }
        
        await update.message.reply_text(
            f"✅ *TARGET LIKE SET*\n\n"
            f"👤 *Player:* {name}\n"
            f"🆔 *UID:* `{uid}`\n"
            f"🌍 *Region:* {REGIONS[region]}\n"
            f"⚙️ *Type:* Target Like\n"
            f"🎯 *Target:* {target_count} likes\n"
            f"🕐 *Schedule:* 5:55 AM IST\n"
            f"📅 *Added:* {format_time()}",
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text("❌ Count must be a valid number!")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def dlike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete like settings"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "❌ *Usage:* `/dlike <uid>`\n"
                "Example: `/dlike 12345`",
                parse_mode='Markdown'
            )
            return
        
        uid = args[0]
        
        if uid in user_data:
            data = user_data[uid]
            settings_type = "Target Like" if data.get('target_likes', 0) > 0 else "Auto Like"
            name = data.get('name', 'Unknown')
            
            del user_data[uid]
            
            await update.message.reply_text(
                f"✅ *SETTINGS DELETED*\n\n"
                f"👤 *Player:* {name}\n"
                f"🆔 *UID:* `{uid}`\n"
                f"⚙️ *Type:* {settings_type}\n"
                f"📌 *Status:* Removed\n"
                f"⏰ *Time:* {format_time()}",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ No settings found for UID: `{uid}`",
                parse_mode='Markdown'
            )
    
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all configured UIDs with details"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    if not user_data:
        await update.message.reply_text(
            "📋 *No UIDs configured*\n\n"
            "Use `/autolike` or `/tlike` to add UIDs.",
            parse_mode='Markdown'
        )
        return
    
    # Send as separate messages if too many UIDs
    uids_list = list(user_data.items())
    total_uids = len(uids_list)
    
    # First message - overview
    overview = (
        f"📋 *CONFIGURED UIDs - OVERVIEW*\n\n"
        f"📊 Total: {total_uids} UIDs\n"
        f"🔄 Auto Like: {sum(1 for d in user_data.values() if d.get('auto_like', False))}\n"
        f"🎯 Target Like: {sum(1 for d in user_data.values() if d.get('target_likes', 0) > 0)}\n"
        f"⏰ Updated: {format_time()}"
    )
    await update.message.reply_text(overview, parse_mode='Markdown')
    
    # Detailed list - split into chunks of 5
    chunk_size = 5
    for i in range(0, total_uids, chunk_size):
        chunk = uids_list[i:i+chunk_size]
        message = "📋 *UID DETAILS*\n\n"
        
        for uid, data in chunk:
            settings_type = "Auto Like (10)" if data.get('auto_like', False) else f"Target ({data.get('target_likes', 0)})"
            message += (
                f"👤 *{data.get('name', 'Unknown')}*\n"
                f"🆔 `{uid}`\n"
                f"🌍 {data.get('region', 'N/A').upper()}\n"
                f"⚙️ {settings_type}\n"
                f"📅 {data.get('added_time', 'N/A')}\n"
                f"───────────────\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        await asyncio.sleep(0.5)  # Small delay to avoid rate limiting

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check user info"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        args = context.args
        if len(args) < 1:
            await update.message.reply_text(
                "❌ *Usage:* `/check <uid>`\n"
                "Example: `/check 12345`",
                parse_mode='Markdown'
            )
            return
        
        uid = args[0]
        
        # Get user info
        user_info = await get_user_info(uid)
        if not user_info:
            await update.message.reply_text(
                f"❌ Failed to get info for UID: `{uid}`\n"
                f"Please check if UID is valid.",
                parse_mode='Markdown'
            )
            return
        
        # Prepare message
        message = (
            f"👤 *USER INFORMATION*\n\n"
            f"🆔 *UID:* `{uid}`\n"
            f"👤 *Name:* {user_info.get('name', 'Unknown')}\n"
            f"🌍 *Region:* {user_info.get('region', 'N/A').upper()}\n"
            f"📊 *Likes:* {user_info.get('likes_before', 0)}\n"
        )
        
        # Add video info if available
        if 'video' in user_info or 'video_url' in user_info:
            video_url = user_info.get('video') or user_info.get('video_url')
            if video_url:
                message += f"📹 *Video:* [Link]({parse_video_url(video_url)})\n"
        
        # Check if UID is configured
        if uid in user_data:
            data = user_data[uid]
            settings = "Auto Like" if data.get('auto_like') else f"Target: {data.get('target_likes', 0)}"
            message += (
                f"\n📌 *Status:* Configured\n"
                f"⚙️ *Setting:* {settings}\n"
                f"📅 *Added:* {data.get('added_time', 'N/A')}"
            )
        else:
            message += f"\n📌 *Status:* Not configured"
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics"""
    if not await check_auth(update):
        await update.message.reply_text("❌ Unauthorized!")
        return
    
    try:
        total_uids = len(user_data)
        auto_like_count = sum(1 for d in user_data.values() if d.get('auto_like', False))
        target_like_count = sum(1 for d in user_data.values() if d.get('target_likes', 0) > 0)
        total_target_likes = sum(d.get('target_likes', 0) for d in user_data.values())
        
        message = (
            f"📊 *BOT STATISTICS*\n\n"
            f"📋 *Total UIDs:* {total_uids}\n"
            f"🔄 *Auto Like:* {auto_like_count}\n"
            f"🎯 *Target Like:* {target_like_count}\n"
            f"📊 *Total Target Likes:* {total_target_likes}\n"
            f"👥 *Admins:* {len(ADMIN_IDS)}\n"
            f"💬 *Group ID:* `{ALLOWED_GROUP_ID}`\n"
            f"⏰ *Time:* {format_time()}\n"
            f"⚡ *Status:* 🟢 Running"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ *An error occurred!*\n\n"
                "Please try again later or contact admin.",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")

def main():
    """Main function"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("like", like_command))
    application.add_handler(CommandHandler("autolike", autolike_command))
    application.add_handler(CommandHandler("tlike", tlike_command))
    application.add_handler(CommandHandler("dlike", dlike_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("stats", stats_command))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Schedule auto like jobs (check every minute)
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(process_auto_likes, interval=60, first=10)
        logger.info("✅ Auto-like scheduler started")
    
    # Start bot
    logger.info("🤖 Bot is starting...")
    logger.info(f"👥 Admins: {ADMIN_IDS}")
    logger.info(f"💬 Group: {ALLOWED_GROUP_ID}")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"Bot crashed: {e}")

if __name__ == '__main__':
    main()
