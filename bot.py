"""
Telegram Referral Bot - Silent After Completion
After 3 referrals: No more notifications
Author: Your Name
Version: 2.4 (Silent Mode)
"""

import logging
import json
import os
# Environment Variables को लोड करने के लिए यह लाइन ज़रूरी है
from dotenv import load_dotenv 

import time
import shutil
import glob
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, ChatJoinRequestHandler, filters
)
from telegram.error import BadRequest, TelegramError

load_dotenv() 

# ==================== CONFIGURATION ====================
CONFIG = {
    # 🔑 REQUIRED - Load from Environment Variables (Secrets)
    'BOT_TOKEN': os.getenv('BOT_TOKEN'),
    'CHANNEL_ID': os.getenv('CHANNEL_ID'),
    'ADMIN_USER_ID': os.getenv('ADMIN_USER_ID'),
    
    # 🔗 OPTIONAL - Load from Environment Variables or use default if missing
    'MOVIE_CHANNEL_LINK': os.getenv('MOVIE_CHANNEL_LINK', "https://t.me/+stC4uP28SixmMThl"),
    'BOT_USERNAME': os.getenv('BOT_USERNAME', "DeshiMediaHub_bot"),
    'REQUIRED_REFERRALS': int(os.getenv('REQUIRED_REFERRALS', 3)),
    'REFERRAL_POINTS': int(os.getenv('REFERRAL_POINTS', 1)),
    'USER_RETENTION_DAYS': int(os.getenv('USER_RETENTION_DAYS', 7))
}
# ==================== CONFIG END ====================

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('referral_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ReferralBot:
    """Main Referral Bot Class - Silent After Completion"""
    
    def __init__(self):
        self.config = CONFIG
        self.user_data_file = "user_data.json"
        self.backup_dir = "backups"
        
        self.validate_config()
        
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        logger.info(f"✅ Bot initialized: @{self.config['BOT_USERNAME']}")
    
    def validate_config(self):
        """Check if required config is set"""
        required = ['BOT_TOKEN', 'CHANNEL_ID', 'ADMIN_USER_ID']
        missing = []
        
        for key in required:
            if not self.config.get(key) or "YOUR_BOT_TOKEN" in self.config[key]:
                missing.append(key)
        
        if missing:
            error_msg = f"❌ Configuration missing: {', '.join(missing)}\n"
            error_msg += "Pehle CONFIG section mein apne ACTUAL details daalein!"
            print("\n" + "="*60)
            print(error_msg)
            print("="*60 + "\n")
            raise ValueError(error_msg)
    
    def create_backup(self):
        """Create backup of user data"""
        try:
            if os.path.exists(self.user_data_file):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join(self.backup_dir, f"user_data_{timestamp}.json")
                shutil.copy2(self.user_data_file, backup_path)
                
                backups = sorted(glob.glob(os.path.join(self.backup_dir, "user_data_*.json")))
                if len(backups) > 5:
                    for old_backup in backups[:-5]:
                        try:
                            os.remove(old_backup)
                        except:
                            pass
                
                return True
        except Exception as e:
            logger.error(f"❌ Backup error: {e}")
        return False
    
    def restore_from_backup(self):
        """Restore user data from latest backup"""
        try:
            backups = sorted(glob.glob(os.path.join(self.backup_dir, "user_data_*.json")))
            if backups:
                latest_backup = backups[-1]
                shutil.copy2(latest_backup, self.user_data_file)
                return True
        except Exception as e:
            logger.error(f"❌ Restore error: {e}")
        return False
    
    def load_user_data(self):
        """Load user data from JSON file"""
        if not os.path.exists(self.user_data_file):
            return {}
        
        try:
            with open(self.user_data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except json.JSONDecodeError:
            if self.restore_from_backup():
                try:
                    with open(self.user_data_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except:
                    return {}
            return {}
        except Exception as e:
            logger.error(f"❌ Load error: {e}")
            return {}
    
    def save_user_data(self, data):
        """Save user data to JSON file"""
        try:
            self.create_backup()
            
            with open(self.user_data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            logger.error(f"❌ Save error: {e}")
            return False
    
    def cleanup_old_users(self):
        """Remove inactive users"""
        try:
            user_data = self.load_user_data()
            if not user_data:
                return
            
            cutoff_date = datetime.now() - timedelta(days=self.config['USER_RETENTION_DAYS'])
            users_removed = 0
            
            for user_id, user_info in list(user_data.items()):
                last_activity_str = user_info.get('last_activity')
                if not last_activity_str:
                    continue
                
                try:
                    last_activity = datetime.fromisoformat(last_activity_str)
                    if last_activity < cutoff_date:
                        del user_data[user_id]
                        users_removed += 1
                except:
                    continue
            
            if users_removed > 0:
                self.save_user_data(user_data)
                logger.info(f"✅ {users_removed} inactive users removed")
                
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    def get_referral_link(self, user_id):
        """Generate referral link for user"""
        username = self.config['BOT_USERNAME']
        if username:
            return f"https://t.me/{username}?start={user_id}"
        return f"t.me/{username}?start={user_id}"
    
    async def notify_admin(self, context: ContextTypes.DEFAULT_TYPE, user_info, user_id):
        """Notify admin when referrals complete"""
        try:
            admin_message = f"""
🎯 **REFERRAL TARGET COMPLETED!**

👤 **User:**
• Name: {user_info.get('first_name', 'N/A')}
• Username: @{user_info.get('username', 'N/A')}
• User ID: `{user_id}`
• Total Referrals: {len(user_info.get('referrals', []))}
• Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

✅ **User eligible for channel access!**
"""
            
            await context.bot.send_message(
                chat_id=self.config['ADMIN_USER_ID'],
                text=admin_message,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"❌ Admin notify error: {e}")
    
    async def is_user_in_channel(self, user_id, context: ContextTypes.DEFAULT_TYPE):
        """Check if user is already in channel"""
        try:
            member = await context.bot.get_chat_member(self.config['CHANNEL_ID'], user_id)
            return member.status in ['member', 'administrator', 'creator']
        except:
            return False
    
    async def approve_channel_request(self, user_id, context: ContextTypes.DEFAULT_TYPE):
        """Approve user's channel join request"""
        try:
            await context.bot.approve_chat_join_request(self.config['CHANNEL_ID'], user_id)
            logger.info(f"✅ Approved user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Approve error: {e}")
            return False
    
    async def decline_channel_request(self, user_id, context: ContextTypes.DEFAULT_TYPE):
        """Decline user's channel join request"""
        try:
            await context.bot.decline_chat_join_request(self.config['CHANNEL_ID'], user_id)
            logger.info(f"❌ Declined user {user_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Decline error: {e}")
            return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command - SILENT AFTER 3 REFERRALS"""
        user = update.effective_user
        user_id = str(user.id)
        user_data = self.load_user_data()
        
        logger.info(f"📥 /start from: {user_id}")
        
        # ✅ REFERRAL PROCESSING - MODIFIED
        if context.args and len(context.args) > 0:
            referrer_id = context.args[0]
            
            # Validate referrer
            if (referrer_id.isdigit() and 
                referrer_id != user_id and 
                referrer_id in user_data):
                
                # Get current referrals count BEFORE adding
                current_referrals = len(user_data[referrer_id].get('referrals', []))
                
                logger.info(f"🔗 Referral for {referrer_id}, Current: {current_referrals} refs")
                
                # Initialize if needed
                if 'referrals' not in user_data[referrer_id]:
                    user_data[referrer_id]['referrals'] = []
                
                # Check if already referred
                if user_id not in user_data[referrer_id]['referrals']:
                    # ✅ ADD REFERRAL
                    user_data[referrer_id]['referrals'].append(user_id)
                    
                    # ✅ Update points (for tracking only, not notifying)
                    user_data[referrer_id]['points'] = user_data[referrer_id].get('points', 0) + self.config['REFERRAL_POINTS']
                    
                    # Save data
                    self.save_user_data(user_data)
                    
                    # Get NEW referrals count
                    new_referrals_count = len(user_data[referrer_id]['referrals'])
                    
                    logger.info(f"✅ {referrer_id} now has {new_referrals_count} refs")
                    
                    # ✅ NOTIFICATION LOGIC - MODIFIED
                    try:
                        # 🚨 ONLY SEND NOTIFICATIONS IF LESS THAN 3 REFERRALS
                        if current_referrals < self.config['REQUIRED_REFERRALS']:
                            # Current user has less than 3 referrals
                            if new_referrals_count < self.config['REQUIRED_REFERRALS']:
                                # Still less than 3 - Send normal notification
                                points_msg = f"""
🎉 **+{self.config['REFERRAL_POINTS']} Point Received!**

📊 **Your Progress:**
• Referrals: {new_referrals_count}/{self.config['REQUIRED_REFERRALS']}
• Points: {user_data[referrer_id].get('points', 0)}

🎯 **Only {self.config['REQUIRED_REFERRALS'] - new_referrals_count} more needed!**
"""
                                await context.bot.send_message(
                                    chat_id=int(referrer_id),
                                    text=points_msg,
                                    parse_mode='Markdown'
                                )
                            
                            # ✅ Check if user JUST REACHED 3 referrals
                            elif new_referrals_count == self.config['REQUIRED_REFERRALS']:
                                # User JUST completed 3 referrals - Send FINAL message
                                channel_msg = f"""
🎉 **CONGRATULATIONS!**

✅ You have completed {self.config['REQUIRED_REFERRALS']} referrals!

📺 **You can now join the channel:**
{self.config['MOVIE_CHANNEL_LINK']}

🚀 **Send join request to get auto-approved!**
"""
                                await context.bot.send_message(
                                    chat_id=int(referrer_id),
                                    text=channel_msg,
                                    parse_mode='Markdown'
                                )
                                
                                # Notify admin
                                await self.notify_admin(context, user_data[referrer_id], referrer_id)
                                logger.info(f"🎯 {referrer_id} completed {self.config['REQUIRED_REFERRALS']} refs - FINAL MSG SENT")
                        
                        # 🚨 If user already had 3+ referrals - COMPLETELY SILENT
                        # No notification sent for 4th, 5th, etc referrals
                        
                    except Exception as e:
                        logger.error(f"❌ Notification error: {e}")
                else:
                    logger.info(f"⚠️ Already referred: {user_id}")
            else:
                logger.info(f"⚠️ Invalid referrer: {referrer_id}")
        
        # Initialize/update user
        if user_id not in user_data:
            user_data[user_id] = {
                'points': 0,
                'referrals': [],
                'is_approved': False,
                'username': user.username,
                'first_name': user.first_name,
                'registered_at': datetime.now().isoformat(),
                'last_activity': datetime.now().isoformat()
            }
        else:
            user_data[user_id]['last_activity'] = datetime.now().isoformat()
        
        self.save_user_data(user_data)
        
        user_info = user_data[user_id]
        referral_link = self.get_referral_link(user_id)
        
        # Welcome message
        welcome_text = f"""
🤖 **Welcome to Referral Bot!** {user.first_name}

📊 **Your Status:**
• Points: {user_info['points']}
• Referrals: {len(user_info['referrals'])}/{self.config['REQUIRED_REFERRALS']}

📨 **Your Link:**
`{referral_link}`

**📋 Rules:**
1. Share link with {self.config['REQUIRED_REFERRALS']} people
2. Complete referrals for channel access
3. Auto-approval system

**🎯 Target: {self.config['REQUIRED_REFERRALS']} Referrals**
"""
        
        share_url = f"https://t.me/share/url?url={referral_link}&text=Join this bot!"
        
        keyboard = [
            [InlineKeyboardButton("📱 Share Link", url=share_url)],
            [InlineKeyboardButton("📊 My Status", callback_data="status")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def handle_chat_join_request(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Auto handle channel join requests - SILENT"""
        join_request = update.chat_join_request
        user_id = str(join_request.from_user.id)
        
        user_data = self.load_user_data()
        
        if user_id in user_data:
            user_info = user_data[user_id]
            referrals_count = len(user_info.get('referrals', []))
            
            if referrals_count >= self.config['REQUIRED_REFERRALS']:
                # Auto-approve
                success = await self.approve_channel_request(int(user_id), context)
                if success:
                    user_data[user_id]['is_approved'] = True
                    user_data[user_id]['approved_at'] = datetime.now().isoformat()
                    self.save_user_data(user_data)
            else:
                # Decline - not enough referrals
                await self.decline_channel_request(int(user_id), context)
        else:
            # Decline - not registered
            await self.decline_channel_request(int(user_id), context)
    
    async def status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user status"""
        query = update.callback_query
        if query:
            await query.answer()
            user_id = str(query.from_user.id)
            message = query.message
        else:
            user_id = str(update.effective_user.id)
            message = update.message
        
        user_data = self.load_user_data()
        
        if user_id not in user_data:
            text = "❌ Use /start first."
            if query:
                await query.edit_message_text(text)
            else:
                await message.reply_text(text)
            return
        
        user_info = user_data[user_id]
        referral_link = self.get_referral_link(user_id)
        
        # Update activity
        user_info['last_activity'] = datetime.now().isoformat()
        user_data[user_id] = user_info
        self.save_user_data(user_data)
        
        # Check channel status
        in_channel = await self.is_user_in_channel(int(user_id), context)
        
        status_text = f"""
📊 **YOUR STATUS**

👤 **User:** {user_info.get('first_name', 'User')}
🏆 **Points:** {user_info['points']}
👥 **Referrals:** {len(user_info['referrals'])}/{self.config['REQUIRED_REFERRALS']}
📺 **Channel:** {'✅ Joined' if in_channel else '❌ Not Joined'}
🔗 **Your Link:** `{referral_link}`

"""
        
        keyboard = []
        
        if len(user_info['referrals']) >= self.config['REQUIRED_REFERRALS']:
            if not in_channel:
                status_text += "✅ **Eligible for channel access!**\n"
                keyboard.append([InlineKeyboardButton("🎬 Join Channel", 
                                                    url=self.config['MOVIE_CHANNEL_LINK'])])
            else:
                status_text += "🎉 **Already in channel!**\n"
        else:
            needed = self.config['REQUIRED_REFERRALS'] - len(user_info['referrals'])
            status_text += f"🎯 **Need {needed} more referral{'s' if needed > 1 else ''}**\n"
            keyboard.append([InlineKeyboardButton("📱 Share Link", 
                                                url=f"https://t.me/share/url?url={referral_link}&text=Join!")])
        
        keyboard.append([InlineKeyboardButton("🔄 Refresh", callback_data="status")])
        keyboard.append([InlineKeyboardButton("🏠 Home", callback_data="home")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if query:
                await query.edit_message_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await message.reply_text(status_text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                if query:
                    await query.answer("✅ Updated!")
    
    async def home(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return to home screen"""
        query = update.callback_query
        await query.answer()
        
        user_id = str(query.from_user.id)
        user_data = self.load_user_data()
        
        if user_id not in user_data:
            await query.edit_message_text("❌ Use /start first.")
            return
        
        user_info = user_data[user_id]
        referral_link = self.get_referral_link(user_id)
        
        home_text = f"""
🏠 **Referral Bot Home**

📊 **Progress:**
• Points: {user_info['points']}
• Referrals: {len(user_info['referrals'])}/{self.config['REQUIRED_REFERRALS']}

📨 **Your Link:**
`{referral_link}`

**Next Steps:**
1. Share link 👥
2. Complete {self.config['REQUIRED_REFERRALS']} referrals ✅
3. Join channel 📺
"""
        
        keyboard = [
            [InlineKeyboardButton("📱 Share Link", 
                                 url=f"https://t.me/share/url?url={referral_link}&text=Join!")],
            [InlineKeyboardButton("📊 My Status", callback_data="status")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        
        if len(user_info['referrals']) >= self.config['REQUIRED_REFERRALS']:
            keyboard.insert(2, [InlineKeyboardButton("🎬 Join Channel", url=self.config['MOVIE_CHANNEL_LINK'])])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await query.edit_message_text(home_text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                await query.answer("✅ On home!")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        query = update.callback_query
        if query:
            await query.answer()
            message = query.message
        else:
            message = update.message
        
        help_text = f"""
❓ **Referral Bot Help**

**🤔 How it works:**
1. /start - Get referral link
2. Share with {self.config['REQUIRED_REFERRALS']} people
3. Complete referrals
4. Join channel (auto-approved)

**📋 Commands:**
/start - Start bot
/status - Check status
/help - This message
/admin - Admin stats

**🎯 Notes:**
- {self.config['REQUIRED_REFERRALS']} referrals required
- Auto-approval for eligible users
- No notifications after completion
"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 Home", callback_data="home")],
            [InlineKeyboardButton("📊 Status", callback_data="status")],
            [InlineKeyboardButton("🚀 Start", callback_data="start_callback")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if query:
                await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await message.reply_text(help_text, reply_markup=reply_markup, parse_mode='Markdown')
        except BadRequest as e:
            if "Message is not modified" in str(e):
                if query:
                    await query.answer("✅ Help shown!")
    
    async def start_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle start callback"""
        query = update.callback_query
        await query.answer("Use /start in chat!")
    
    async def admin_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show admin statistics"""
        user_id = str(update.effective_user.id)
        
        if user_id != self.config['ADMIN_USER_ID']:
            await update.message.reply_text("❌ Admin only.")
            return
        
        self.cleanup_old_users()
        
        user_data = self.load_user_data()
        total_users = len(user_data)
        
        completed_users = 0
        total_referrals = 0
        
        for info in user_data.values():
            referrals_count = len(info.get('referrals', []))
            total_referrals += referrals_count
            
            if referrals_count >= self.config['REQUIRED_REFERRALS']:
                completed_users += 1
        
        pending_users = total_users - completed_users
        
        stats_text = f"""
📊 **ADMIN STATS**

👥 **Users:**
• Total: {total_users}
• Completed: {completed_users}
• Pending: {pending_users}
• Total Referrals: {total_referrals}

💾 **System:**
• Bot: @{self.config['BOT_USERNAME']}
"""
        
        await update.message.reply_text(stats_text, parse_mode='Markdown')
    
    def setup_handlers(self, application):
        """Setup all bot handlers"""
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("status", self.status))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("admin", self.admin_stats))
        
        application.add_handler(ChatJoinRequestHandler(self.handle_chat_join_request))
        
        application.add_handler(CallbackQueryHandler(self.status, pattern="^status"))
        application.add_handler(CallbackQueryHandler(self.home, pattern="home"))
        application.add_handler(CallbackQueryHandler(self.help_command, pattern="help"))
        application.add_handler(CallbackQueryHandler(self.start_callback, pattern="start_callback"))
    
    def run(self):
        """Start the bot"""
        self.validate_config()
        
        application = Application.builder().token(self.config['BOT_TOKEN']).build()
        
        self.setup_handlers(application)
        
        self.cleanup_old_users()
        
        print("\n" + "="*60)
        print("🤖 REFERRAL BOT - SILENT MODE")
        print("="*60)
        print(f"📱 Bot: @{self.config['BOT_USERNAME']}")
        print(f"🎯 Required: {self.config['REQUIRED_REFERRALS']} referrals")
        print(f"🔕 Mode: SILENT after completion")
        print("="*60)
        print("✅ No notifications after 3 referrals")
        print("✅ Only final channel link sent")
        print("✅ 4th+ referrals completely silent")
        print("="*60)
        print("🚀 Bot starting...")
        print("="*60 + "\n")
        
        application.run_polling(allowed_updates=Update.ALL_TYPES)

def main():
    """Main function"""
    bot = ReferralBot()
    bot.run()

if __name__ == '__main__':
    main()
