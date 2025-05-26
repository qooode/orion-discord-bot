import os
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('bot.env')

# Define UTC timezone constant to fix deprecation warnings
UTC = datetime.timezone.utc

# Get the Discord token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('COMMAND_PREFIX', '!')

# Data file paths
WARNING_FILE = 'warnings.json'
REACTION_ROLES_FILE = 'reaction_roles.json'
CUSTOM_COMMANDS_FILE = 'custom_commands.json'
SCHEDULED_TASKS_FILE = 'scheduled_tasks.json'
TEMP_VOICE_FILE = 'temp_voice.json'
FRESH_ACCOUNT_FILE = 'fresh_accounts.json'
QUARANTINE_FILE = 'quarantine.json'
NICKNAME_FILTER_FILE = 'nickname_filters.json'
NOTES_FILE = 'mod_notes.json'
PRISON_BREAK_FILE = 'prison_break_games.json'

# Backup directory
BACKUP_DIR = 'backups'

# Quarantine channel names
QUARANTINE_CHANNEL_NAME = 'quarantine-room'
JAIL_CAM_CHANNEL_NAME = 'jail-cam'

# Bad words filter (can be expanded)
BAD_WORDS = ['badword1', 'badword2', 'badword3']

# Prison Break Game Constants
PRISON_BREAK_STAGES = {
    1: {
        "name": "🔓 Lock Picking",
        "description": "Pick the lock on your cell door",
        "challenge": "Type the correct combination! Look for patterns...",
        "time_limit": 90,
        "spectator_help": True
    },
    2: {
        "name": "🕳️ Tunnel Digging", 
        "description": "Dig a tunnel under the prison wall",
        "challenge": "Solve the digging puzzle by following the right path",
        "time_limit": 120,
        "spectator_help": True
    },
    3: {
        "name": "👮 Guard Evasion",
        "description": "Sneak past the guards without being caught",
        "challenge": "Navigate the maze without getting spotted",
        "time_limit": 150,
        "spectator_help": True
    },
    4: {
        "name": "🚗 Great Escape",
        "description": "Reach the getaway vehicle",
        "challenge": "Final challenge - coordinate with other prisoners",
        "time_limit": 180,
        "spectator_help": True
    }
}

PRISON_BREAK_REWARDS = {
    "stage_1": {"sentence_reduction": 15, "message": "🎉 Cell door unlocked! -15% of sentence!"},
    "stage_2": {"sentence_reduction": 20, "message": "🕳️ Tunnel complete! -20% of sentence!"},
    "stage_3": {"sentence_reduction": 25, "message": "👮 Guards evaded! -25% of sentence!"},
    "stage_4": {"sentence_reduction": 30, "message": "🚗 FREEDOM ACHIEVED! -30% of sentence!"}
}

PRISON_BREAK_FAILURES = {
    "stage_1": {"sentence_addition": 5, "message": "🔒 Lock picking failed! +5% sentence extension!"},
    "stage_2": {"sentence_addition": 7, "message": "🕳️ Tunnel collapsed! +7% sentence extension!"},
    "stage_3": {"sentence_addition": 10, "message": "👮 Caught by guards! +10% sentence extension!"},
    "stage_4": {"sentence_addition": 15, "message": "🚨 Escape failed! +15% sentence extension!"}
}

# Emoji reactions for prison break spectator interaction
HELP_EMOJIS = ["✨", "🤝", "💡", "🔦", "🗝️", "⏰", "📍", "🎯", "🆘"]
SABOTAGE_EMOJIS = ["😈", "🚨", "🔒", "💥", "🌩️", "📢", "⛔", "💀", "🔥"]

# Prison Break Game status and validation
GAME_TIMEOUT_MINUTES = 30  # Games auto-expire after 30 minutes of inactivity 