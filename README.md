# 🤖 Orion Discord Bot - Modular Architecture

A powerful Discord moderation bot with advanced features, completely restructured into a clean modular architecture for better maintainability and scalability.

## 🚀 **Quick Start (New Modular System)**

### **Option 1: Automatic Setup (Recommended)**
```bash
# Use the startup script that checks everything for you
python3 start_bot.py
```

### **Option 2: Manual Setup**
```bash
# Step 1: Install dependencies
pip3 install discord.py python-dotenv

# Step 2: Create bot.env file
echo "DISCORD_TOKEN=your_bot_token_here" > bot.env
echo "COMMAND_PREFIX=!" >> bot.env

# Step 3: Edit bot.env with your actual token, then run
python3 main.py
```

### **Option 3: Run Without Dependencies Check**
```bash
# If you already have everything set up
python3 main.py

# The old bot.py has been renamed to bot_original_backup.py (backup only)
```

## 📁 **New Project Structure**

```
Orion/
├── main.py                 # 🚀 NEW ENTRY POINT - Use this!
├── config.py              # ⚙️ Configuration settings and constants  
├── data_manager.py         # 💾 JSON data loading/saving functions
├── events.py              # 📡 Discord event handlers
├── bot_original_backup.py  # 📦 Original 5148-line file (BACKUP ONLY)
├── bot.env                # 🔑 Environment variables (TOKEN, PREFIX)
├── commands/              # 📂 Command modules
│   ├── moderation.py      # 🔨 Basic moderation (kick, ban, warn, mute)
│   ├── utility.py         # ℹ️ Utility commands (userinfo, serverinfo, notes)
│   ├── mass_moderation.py # ⚡ Advanced tools (purgewords, massban, clean)
│   ├── quarantine.py      # 🔒 Quarantine system + Prison Break Games
│   └── __init__.py        # 📋 Module index
├── utils/                 # 🛠️ Utility functions (future expansion)
├── backups/               # 💾 Automatic data backups
├── *.json                 # 📊 Data files (warnings, quarantine, etc.)
├── README.md              # 📖 This file
└── MIGRATION_GUIDE.md     # 📋 Migration details
```

## ✨ **Available Commands**

### **🔨 Basic Moderation**
- `/kick` - Kick a member
- `/ban` - Ban a member  
- `/mute` - Timeout a member
- `/warn` - Warn a member
- `/warnings` - View user warnings
- `/clearwarnings` - Clear warnings

### **ℹ️ Utility Commands**
- `/userinfo` - Get user information
- `/serverinfo` - Get server information
- `/note` - Add moderator notes about users
- `/notes` - View notes for a user

### **⚡ Mass Moderation**
- `/purgewords` - **Advanced word scanning with batch processing**
- `/massban` - Ban multiple users by ID
- `/clean` - Delete messages by criteria

### **🔒 Quarantine System**
- `/quarantine` - Place user in quarantine with optional timer
- `/unquarantine` - Release user from quarantine
- `/quarantinelist` - List quarantined users
- `/throw` - Throw items at quarantined users (fun interaction)
- `/freshaccounts` - Configure new account detection

### **🎮 Prison Break Games**
- `/prisonbreak start` - Start interactive escape game
- `/prisonbreak stop/status` - Manage games
- **Emoji Reactions** - Spectators help (✨🤝💡) or sabotage (😈🚨🔒)

## 🎯 **Key Features**

### **🔒 Advanced Quarantine System**
- **Message Mirroring**: Quarantined users chat through `#jail-cam`
- **Timed Quarantine**: Auto-release after specified time
- **Role Preservation**: Automatically restores roles on release
- **Fresh Account Detection**: Auto-quarantine new Discord accounts

### **🎮 Interactive Prison Break Games**
- **4-Stage Challenges**: Lock picking → Tunnel digging → Guard evasion → Great escape
- **Community Interaction**: Spectators influence outcomes via emoji reactions
- **Dynamic Consequences**: Success reduces sentence, failure extends it
- **Real-time Broadcasting**: Games stream live to `#jail-cam`

### **⚡ Powerful Mass Moderation**
- **Smart Purgewords**: Batch processing with rate limiting
- **Interactive UI**: Buttons and modals for complex operations
- **Advanced Filtering**: Regex support, user-specific targeting
- **Safe Operations**: Built-in safeguards and confirmations

## 🛠️ **Setup Instructions**

### **1. Discord Developer Portal**
1. Create a new application at https://discord.com/developers/applications
2. Create a bot user and copy the token
3. Invite bot with these permissions:
   - `Manage Roles`
   - `Manage Channels` 
   - `Kick Members`
   - `Ban Members`
   - `Manage Messages`
   - `Send Messages`
   - `Use Slash Commands`

### **2. Environment Configuration**
Create `bot.env` file:
```env
DISCORD_TOKEN=your_actual_bot_token_here
COMMAND_PREFIX=!
```

### **3. File Permissions**
Make sure the bot can create/modify these files:
- `*.json` files for data storage
- `backups/` directory for automatic backups

## 📊 **Data Management**

The bot automatically manages these data files:
- `warnings.json` - User warnings
- `quarantine.json` - Quarantine data  
- `prison_break_games.json` - Game sessions
- `reaction_roles.json` - Reaction role setup
- `fresh_accounts.json` - Account detection settings
- `backups/` - Automatic backups every 12 hours

## 🎮 **Prison Break Game Guide**

### **For Moderators:**
```bash
/prisonbreak start          # Start game for all quarantined users
/prisonbreak start @user    # Start game for specific user
/prisonbreak stop           # Stop all active games
/prisonbreak status         # Check game status
```

### **For Players (Quarantined Users):**
- **Stage 1**: Type combinations like `1-2-3-4`
- **Stage 2**: Type directions: `north`, `south`, `east`, `west`
- **Stage 3**: Type hiding spots: `behind tree`, `in shadows`, etc.
- **Stage 4**: Coordinate with team to type the secret code word

### **For Spectators:**
- React with help emojis: ✨🤝💡🔦🗝️⏰📍🎯🆘
- React with sabotage emojis: 😈🚨🔒💥🌩️📢⛔💀🔥
- Use `/throw` to throw items at prisoners

## 🔧 **Troubleshooting**

### **Bot not responding to slash commands?**
1. Make sure bot has `applications.commands` scope
2. Wait up to 1 hour for commands to sync in large servers
3. Try removing and re-adding the bot

### **Permission errors?**
1. Check bot role is high enough in role hierarchy
2. Ensure bot has required permissions in each channel
3. Verify bot can manage roles it's trying to assign/remove

### **Module import errors?**
1. Make sure all files are in correct directories
2. Check that `__init__.py` files exist in command folders
3. Verify Python path includes the bot directory

## 🔄 **Migration from Old Bot**

If you were using the old `bot.py` (now renamed to `bot_original_backup.py`):

✅ **Automatic Migration** - All data files remain compatible
✅ **Same Commands** - All commands work exactly the same  
✅ **Same Behavior** - No functionality changes
✅ **Better Performance** - Cleaner code architecture

**Simply run `python3 main.py` instead of the old file**

### **📦 About the Backup File**

We've renamed the original `bot.py` to `bot_original_backup.py` for these reasons:
- **Safety**: Keep original code as backup during transition
- **Reference**: Contains ~25 advanced commands not yet migrated (reaction roles, voice channels, etc.)
- **Prevents Confusion**: Clear which file to run (`main.py`)

**You can safely ignore or delete `bot_original_backup.py` once you're confident the modular system works for your needs.**

## 📈 **Development**

### **Adding New Commands:**
1. Create new file in `commands/` directory
2. Follow existing patterns in other command files
3. Import and register in `main.py`
4. Update `commands/__init__.py`

### **Module Structure:**
```python
# commands/new_module.py
async def setup_new_commands(bot):
    @bot.tree.command(name="example")
    async def example_command(interaction):
        await interaction.response.send_message("Hello!")
```

## 🛡️ **Security Features**

- **Permission Checks** - All commands verify user permissions
- **Role Hierarchy** - Prevents users from moderating higher roles
- **Rate Limiting** - Built-in protection against command spam
- **Data Validation** - Input sanitization for all user data
- **Automatic Backups** - Regular data backups prevent loss

## 📞 **Support**

- **Documentation**: Check `MIGRATION_GUIDE.md` for detailed migration info
- **Issues**: Review console logs for error messages
- **Features**: All original bot features are preserved and enhanced

---

## 🎉 **Success!**

Your Orion bot is now running on a **modern, modular architecture** with:
- ✅ **Better maintainability** - Easy to modify and extend
- ✅ **Enhanced features** - Interactive prison break games  
- ✅ **Improved stability** - Better error handling
- ✅ **Future-ready** - Scalable for new features

**Start the bot with `python main.py` and enjoy! 🚀**
