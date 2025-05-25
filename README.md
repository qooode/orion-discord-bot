# Discord Moderation Bot

A powerful Discord moderation bot with advanced features and slash commands.

## Features

- **Slash Command Interface**: All commands use Discord's `/` command system
- **Advanced Moderation Tools**: Kick, ban, mute, warn, lockdown and more
- **Mass-Moderation**: Ban or kick multiple users at once
- **Auto-Moderation**: Bad word filtering with automatic warnings
- **Warning System**: Persistent warning storage with automatic actions
- **Server Lockdown**: Emergency controls to lock the entire server
- **Raid Protection**: Tools to prevent and mitigate raids
- **User Information**: Detailed user statistics and warning history
- **Reaction Roles**: Self-assignable roles through reactions
- **Message Logging**: Track deleted messages for moderation purposes
- **Custom Commands**: Create server-specific commands with optional embeds
- **Scheduled Actions**: Set reminders and temporary bans with auto-expiration
- **Temp Voice Channels**: Users can create and manage their own voice channels
- **Automatic Backups**: Bot creates regular backups of all data files

## Setup

1. **Requirements**:
   - Python 3.8 or higher
   - Discord.py 2.0.0 or higher

2. **Installation**:
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/discord-mod-bot.git
   
   # Navigate to the project directory
   cd discord-mod-bot
   
   # Install dependencies
   pip install -r requirements.txt
   ```

3. **Configuration**:
   - Rename `bot.env` to `.env`
   - Edit `.env` with your Discord bot token
   ```
   DISCORD_TOKEN=your_token_here
   COMMAND_PREFIX=!
   ```

4. **Start the Bot**:
   ```bash
   python bot.py
   ```

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

Made with ❤️ by YOUR_NAME_HERE
