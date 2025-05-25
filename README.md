# Discord Moderation Bot

A powerful Discord moderation bot with advanced features and slash commands.

## Features

### Core Features
- **Slash Command Interface**: All commands use Discord's `/` command system
- **Advanced Moderation Tools**: Kick, ban, mute, warn, lockdown and more
- **Mass-Moderation**: Ban or kick multiple users at once
- **Auto-Moderation**: Bad word filtering with automatic warnings
- **Warning System**: Persistent warning storage with automatic actions

### Emergency & Protection Features
- **Server Lockdown**: Emergency controls to lock the entire server
- **Raid Protection**: Tools to prevent and mitigate raids
- **Rate Limiting**: Prevent spam with configurable message rate limits
- **Nickname Filters**: Auto-rename users with inappropriate nicknames

### Content Scanning & Cleanup
- **Word Purge**: Delete all messages containing specific words
- **Regex Scanning**: Find messages matching complex patterns
- **Thread Management**: Bulk archive inactive threads
- **Message Logging**: Track deleted messages for moderation purposes

### User Engagement Features
- **User Information**: Detailed user statistics and warning history
- **Reaction Roles**: Self-assignable roles through reactions
- **Custom Commands**: Create server-specific commands with optional embeds
- **Scheduled Actions**: Set reminders and temporary bans with auto-expiration
- **Temp Voice Channels**: Users can create and manage their own voice channels

### System Features
- **Automatic Backups**: Bot creates regular backups of all data files
- **JSON Data Storage**: Simple, persistent storage for all bot data

## Setup

1. **Requirements**:
   - Python 3.8 or higher
   - Discord.py 2.0.0 or higher

2. **Discord Bot Setup**:
   - Go to [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a new application and add a bot
   - Enable all Privileged Gateway Intents (Message Content, Server Members, Presence)
   - Use the OAuth2 URL Generator to create an invite link with `bot` and `applications.commands` scopes
   - Select appropriate bot permissions (Administrator recommended for full functionality)

3. **Installation**:
   ```bash
   # Clone the repository
   git clone https://github.com/qooode/discord-mod-bot.git
   
   # Navigate to the project directory
   cd discord-mod-bot
   
   # Install dependencies
   pip install -r requirements.txt
   ```

4. **Configuration**:
   - Rename `bot.env` to `.env` (or keep as is)
   - Edit with your Discord bot token
   ```
   DISCORD_TOKEN=your_discord_bot_token_here
   COMMAND_PREFIX=!
   ```

5. **Running the Bot**:
   ```bash
   # Simple start
   python bot.py
   
   # Alternative: Run in background (Linux/Mac)
   nohup python bot.py > bot.log 2>&1 &
   
   # Alternative: Run with auto-restart (requires nodemon)
   nodemon bot.py
   ```

6. **First-Time Setup**:
   - After inviting the bot to your server, use these commands to set up basic functionality:
     - `/setupvoice` - Set up auto-voice channels
     - `/nickfilter` - Add nickname filters
     - `/ratelimit` - Configure anti-spam measures
   - Create a channel named `mod-logs` for automatic logging
   - Create a role named `Quarantine` for anti-raid protection

## Commands

### Basic Moderation
- `/kick @user [reason]` - Kick a user from the server
- `/ban @user [reason] [delete_days]` - Ban a user from the server
- `/mute @user [duration] [reason]` - Timeout a user for a specified duration
- `/purge [amount]` - Delete a specified number of messages

### Warning System
- `/warn @user [reason]` - Warn a user (stores in warnings.json)
- `/warnings @user` - View all warnings for a user
- `/clearwarnings @user [amount]` - Clear warnings for a user

### Channel Management
- `/lockdown [channel] [reason] [minutes]` - Lock a channel
- `/unlock [channel]` - Unlock a previously locked channel
- `/slowmode [seconds] [channel]` - Set slowmode in a channel

### Emergency Controls
- `/serverlock [reason] [minutes]` - Lock down the ENTIRE server in emergency situations
- `/serverunlock [reason]` - Unlock the server after a lockdown

### User Info
- `/userinfo [@user]` - Get detailed information about a user

### Raid Protection
- `/antiraid <enable/disable>` - Toggle anti-raid protection mode

## Auto-Moderation Features

- **Bad Word Filter**: Automatically deletes messages containing bad words
- **Warning Escalation**: 
  - 3 warnings: Moderator notification
  - 5 warnings: Automatic 1-hour timeout
- **Welcome Messages**: Automatically welcomes new members

## Customization

You can customize this bot by:

1. Editing the `BAD_WORDS` list in `bot.py`
2. Modifying warning thresholds and actions
3. Adding new commands following the existing patterns

## Need Help?

For any issues or suggestions, please open an issue on the GitHub repository.

---

Made with ❤️ by qooode
