import asyncio
import aiohttp
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
BOT_TOKEN = os.getenv('8307741402:AAG0QNCV4Qr_GDSk0uSPgfjSotkVfugkNEw')
if not BOT_TOKEN:
    logger.error("BOT_TOKEN not set in environment variables")
    sys.exit(1)

GROUP_ID = int(os.getenv('GROUP_ID', -1003765179070))
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '6417430059').split(',') if id.strip()]
if not ADMIN_IDS:
    logger.error("ADMIN_IDS not set in environment variables")
    sys.exit(1)

API_URL = os.getenv('API_URL', "https://like-api-frexy.up.railway.app/like?uid={}&server_name={}")
MEDIA_URL = os.getenv('MEDIA_URL', "https://sharevideo.org/fOBSNh1xZy7IJoG/watch")

# Database (in-memory for simplicity, use proper DB in production)
user_data = {}
auto_like_settings = {}
target_like_settings = {}
daily_likes = {}
pending_requests = []

class LikeBot:
    def __init__(self):
        self.running = False
        self.queue = asyncio.Queue()
        self.processing = False
        
    async def send_like(self, uid, region, is_admin=False, is_target=False):
        """Send like to Facebook UID"""
        try:
            url = API_URL.format(uid, region)
            logger.info(f"Sending like to UID: {uid} in region: {region}")
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Like sent successfully to {uid}")
                        return data
                    else:
                        error_msg = f"API Error: {response.status}"
                        logger.error(error_msg)
                        return {"error": error_msg}
        except asyncio.TimeoutError:
            logger.error(f"Timeout while sending like to {uid}")
            return {"error": "Request timeout"}
        except Exception as e:
            logger.error(f"Error sending like to {uid}: {str(e)}")
            return {"error": str(e)}

    def format_response(self, data, uid, region, is_target=False):
        """Format the response message with quote and bold formatting"""
        try:
            name = data.get('name', 'Unknown User')
            current_likes = data.get('current_likes', 0)
            likes_given = data.get('likes_given', 0)
            
            formatted_msg = f"""<blockquote>⚡ LIKE SENT SUCCESSFUL! ⚡
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
👤 NAME : <b>{name}</b>
🆔 UID : <b>{uid}</b>
🌍 Server: <b>{region}</b>
🏷️ USER STATUS: <b>👤 FREE USER</b>
🔥 ENGINE: <b>1API</b>
────────────────────────────
📊 LIKE DETAILS
🔹 👍LIKE BEFORE : <b>{current_likes - likes_given}</b>
⚡ 👍LIKE GIVEN : <b>+{likes_given}</b>
🏆 👍LIKE AFTER : <b>{current_likes}</b>
📊 REMAIN: 1/1
────────────────────────────
👑 VIP SUBSCRIPTION AVAILABLE 👑
💎 VIP USER UNLIMITED REQUEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ POWERED BY @Frexy1only</blockquote>"""
            
            return formatted_msg
        except Exception as e:
            logger.error(f"Error formatting response: {str(e)}")
            return f"<b>Error formatting response</b>"

    async def process_auto_like(self, context):
        """Process auto-like queue"""
        while self.running:
            try:
                # Check current time for scheduled start (7 AM)
                current_time = datetime.now()
                if current_time.hour >= 7:
                    for uid, settings in list(auto_like_settings.items()):
                        if 'active' in settings and settings['active']:
                            # Check if target reached
                            target = target_like_settings.get(uid, {}).get('target_likes', float('inf'))
                            current_likes = daily_likes.get(uid, 0)
                            
                            if current_likes >= target:
                                logger.info(f"Target reached for UID {uid}")
                                continue
                            
                            region = settings.get('region', 'BD')
                            result = await self.send_like(uid, region)
                            
                            if result and 'error' not in result:
                                daily_likes[uid] = daily_likes.get(uid, 0) + 1
                                
                                # Send notification to group
                                formatted_msg = self.format_response(result, uid, region)
                                
                                try:
                                    # Send with media
                                    await context.bot.send_video(
                                        chat_id=GROUP_ID,
                                        video=MEDIA_URL,
                                        caption=formatted_msg,
                                        parse_mode='HTML',
                                        timeout=30
                                    )
                                    logger.info(f"Auto-like notification sent to group for UID {uid}")
                                except Exception as e:
                                    logger.error(f"Error sending auto-like notification: {str(e)}")
                                    # Try sending without video if video fails
                                    try:
                                        await context.bot.send_message(
                                            chat_id=GROUP_ID,
                                            text=formatted_msg,
                                            parse_mode='HTML'
                                        )
                                    except Exception as e2:
                                        logger.error(f"Error sending text notification: {str(e2)}")
                            
                            # Wait 30 seconds before next like
                            await asyncio.sleep(30)
                else:
                    # If before 7 AM, wait until 7 AM
                    wait_seconds = (7 - current_time.hour) * 3600 - current_time.minute * 60
                    if wait_seconds > 0:
                        logger.info(f"Waiting {wait_seconds} seconds until 7 AM")
                        await asyncio.sleep(wait_seconds)
                    
            except Exception as e:
                logger.error(f"Error in auto-like processing: {e}")
                await asyncio.sleep(30)

# Initialize bot instance
like_bot = LikeBot()

# Command Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    welcome_msg = """<b>🤖 Welcome to Like Bot!</b>

<blockquote>Commands:
/help - Show all commands
/like [uid] [region] - Send like to a UID
/status - Check your daily like status
/autolike [region] [uid] - Set auto-like (Admin only)
/tlike [region] [uid] [target] - Set target like (Admin only)
/remove [uid] - Remove auto/target like (Admin only)
/list - Show all active auto-likes (Admin only)</blockquote>

<b>📱 Powered by @Frexy1only</b>"""
    
    await update.message.reply_text(welcome_msg, parse_mode='HTML')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_msg = """<b>📚 Available Commands</b>

<blockquote>/start - Start the bot
/help - Show this help message
/like [uid] [region] - Send like to a Facebook UID
/status - Check your remaining daily likes
/autolike [region] [uid] - Set auto-like (Admin only)
/tlike [region] [uid] [target] - Set target likes (Admin only)
/remove [uid] - Remove auto/target settings (Admin only)
/list - Show all active auto-likes (Admin only)</blockquote>

<b>📱 Powered by @Frexy1only</b>"""
    
    await update.message.reply_text(help_msg, parse_mode='HTML')

async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /like command"""
    user_id = str(update.effective_user.id)
    args = context.args
    
    if len(args) < 2:
        await update.message.reply_text(
            "<b>⚠️ Usage:</b> <code>/like [UID] [REGION]</code>\n"
            "<b>Example:</b> <code>/like 123456789 BD</code>",
            parse_mode='HTML'
        )
        return
    
    uid = args[0]
    region = args[1]
    
    # Check daily limit for free users
    today = datetime.now().date().isoformat()
    key = f"{user_id}_{today}"
    
    if user_id not in [str(admin) for admin in ADMIN_IDS]:
        if daily_likes.get(key, 0) >= 1:
            await update.message.reply_text(
                "<b>❌ Daily limit reached!</b>\n"
                "You can only send 1 like per day as a free user.\n"
                "👑 Upgrade to VIP for unlimited requests!",
                parse_mode='HTML'
            )
            return
    
    # Send like
    result = await like_bot.send_like(uid, region)
    
    if result and 'error' not in result:
        daily_likes[key] = daily_likes.get(key, 0) + 1
        
        formatted_msg = like_bot.format_response(result, uid, region)
        
        try:
            # Send with video
            await update.message.reply_video(
                video=MEDIA_URL,
                caption=formatted_msg,
                parse_mode='HTML',
                timeout=30
            )
        except Exception as e:
            logger.error(f"Error sending video: {str(e)}")
            # Fallback to text only
            await update.message.reply_text(
                formatted_msg,
                parse_mode='HTML'
            )
        
        # Also send to group
        try:
            await context.bot.send_video(
                chat_id=GROUP_ID,
                video=MEDIA_URL,
                caption=formatted_msg,
                parse_mode='HTML',
                timeout=30
            )
        except Exception as e:
            logger.error(f"Error sending to group: {str(e)}")
            try:
                await context.bot.send_message(
                    chat_id=GROUP_ID,
                    text=formatted_msg,
                    parse_mode='HTML'
                )
            except Exception as e2:
                logger.error(f"Error sending text to group: {str(e2)}")
    else:
        error_msg = result.get('error', 'Unknown error')
        await update.message.reply_text(
            f"<b>❌ Error:</b> {error_msg}",
            parse_mode='HTML'
        )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    user_id = str(update.effective_user.id)
    today = datetime.now().date().isoformat()
    key = f"{user_id}_{today}"
    
    used = daily_likes.get(key, 0)
    remaining = 1 - used
    
    status_msg = f"""<b>📊 Your Daily Status</b>

<blockquote>👤 User ID: <code>{user_id}</code>
📅 Date: {datetime.now().strftime('%Y-%m-%d')}
🎯 Daily Limit: 1
✅ Used Today: {used}
⏳ Remaining: {remaining}</blockquote>

👑 <b>Upgrade to VIP for unlimited requests!</b>
📱 Powered by @Frexy1only"""
    
    await update.message.reply_text(status_msg, parse_mode='HTML')

async def autolike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /autolike command (Admin only)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin) for admin in ADMIN_IDS]:
        await update.message.reply_text(
            "<b>⛔ Access Denied!</b>\n"
            "This command is only for administrators.",
            parse_mode='HTML'
        )
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "<b>⚠️ Usage:</b> <code>/autolike [REGION] [UID]</code>\n"
            "<b>Example:</b> <code>/autolike BD 123456789</code>",
            parse_mode='HTML'
        )
        return
    
    region = args[0]
    uid = args[1]
    
    auto_like_settings[uid] = {
        'region': region,
        'active': True,
        'set_by': user_id,
        'set_time': datetime.now().isoformat()
    }
    
    # Start auto-like process if not running
    if not like_bot.running:
        like_bot.running = True
        asyncio.create_task(like_bot.process_auto_like(context))
        logger.info("Auto-like process started")
    
    await update.message.reply_text(
        f"<b>✅ Auto-like configured!</b>\n\n"
        f"<blockquote>📱 UID: <code>{uid}</code>\n"
        f"🌍 Region: {region}\n"
        f"⏱️ Active: Yes</blockquote>\n"
        f"📱 Powered by @Frexy1only",
        parse_mode='HTML'
    )

async def tlike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /tlike command (Admin only)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin) for admin in ADMIN_IDS]:
        await update.message.reply_text(
            "<b>⛔ Access Denied!</b>\n"
            "This command is only for administrators.",
            parse_mode='HTML'
        )
        return
    
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "<b>⚠️ Usage:</b> <code>/tlike [REGION] [UID] [TARGET]</code>\n"
            "<b>Example:</b> <code>/tlike BD 123456789 100</code>",
            parse_mode='HTML'
        )
        return
    
    region = args[0]
    uid = args[1]
    try:
        target = int(args[2])
    except ValueError:
        await update.message.reply_text(
            "<b>❌ Error:</b> Target must be a number",
            parse_mode='HTML'
        )
        return
    
    target_like_settings[uid] = {
        'region': region,
        'target_likes': target,
        'current_likes': daily_likes.get(uid, 0),
        'set_by': user_id,
        'set_time': datetime.now().isoformat()
    }
    
    await update.message.reply_text(
        f"<b>✅ Target like configured!</b>\n\n"
        f"<blockquote>📱 UID: <code>{uid}</code>\n"
        f"🌍 Region: {region}\n"
        f"🎯 Target: {target} likes</blockquote>\n"
        f"📱 Powered by @Frexy1only",
        parse_mode='HTML'
    )

async def remove_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command (Admin only)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin) for admin in ADMIN_IDS]:
        await update.message.reply_text(
            "<b>⛔ Access Denied!</b>\n"
            "This command is only for administrators.",
            parse_mode='HTML'
        )
        return
    
    args = context.args
    if len(args) < 1:
        await update.message.reply_text(
            "<b>⚠️ Usage:</b> <code>/remove [UID]</code>\n"
            "<b>Example:</b> <code>/remove 123456789</code>",
            parse_mode='HTML'
        )
        return
    
    uid = args[0]
    
    removed = False
    if uid in auto_like_settings:
        del auto_like_settings[uid]
        removed = True
    
    if uid in target_like_settings:
        del target_like_settings[uid]
        removed = True
    
    if removed:
        await update.message.reply_text(
            f"<b>✅ Removed settings for UID:</b> <code>{uid}</code>",
            parse_mode='HTML'
        )
    else:
        await update.message.reply_text(
            f"<b>❌ No settings found for UID:</b> <code>{uid}</code>",
            parse_mode='HTML'
        )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command (Admin only)"""
    user_id = str(update.effective_user.id)
    
    if user_id not in [str(admin) for admin in ADMIN_IDS]:
        await update.message.reply_text(
            "<b>⛔ Access Denied!</b>\n"
            "This command is only for administrators.",
            parse_mode='HTML'
        )
        return
    
    if not auto_like_settings and not target_like_settings:
        await update.message.reply_text(
            "<b>📋 No active settings found</b>",
            parse_mode='HTML'
        )
        return
    
    msg = "<b>📋 Active Settings</b>\n\n"
    
    if auto_like_settings:
        msg += "<blockquote><b>🔹 Auto-Like Settings:</b>\n"
        for uid, settings in auto_like_settings.items():
            msg += f"📱 UID: <code>{uid}</code> | Region: {settings['region']}\n"
        msg += "</blockquote>\n\n"
    
    if target_like_settings:
        msg += "<blockquote><b>🔹 Target-Like Settings:</b>\n"
        for uid, settings in target_like_settings.items():
            current = daily_likes.get(uid, 0)
            msg += f"📱 UID: <code>{uid}</code> | Target: {settings['target_likes']} | Current: {current}\n"
        msg += "</blockquote>"
    
    msg += "\n📱 Powered by @Frexy1only"
    
    # Split message if too long
    if len(msg) > 4096:
        for i in range(0, len(msg), 4096):
            await update.message.reply_text(msg[i:i+4096], parse_mode='HTML')
    else:
        await update.message.reply_text(msg, parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "<b>❌ An error occurred!</b>\n"
                "Please try again later or contact the administrator.",
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Error in error handler: {str(e)}")

def main():
    """Main function to run the bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add command handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("like", like_command))
        application.add_handler(CommandHandler("status", status_command))
        application.add_handler(CommandHandler("autolike", autolike_command))
        application.add_handler(CommandHandler("tlike", tlike_command))
        application.add_handler(CommandHandler("remove", remove_command))
        application.add_handler(CommandHandler("list", list_command))
        
        # Add error handler
        application.add_error_handler(error_handler)
        
        # Start the bot
        logger.info("🤖 Bot is starting...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )
    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
