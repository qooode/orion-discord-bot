import os
import json
import datetime
from config import *

# Data stores
warnings_data = {}
reaction_roles_data = {}
custom_commands_data = {}
scheduled_tasks_data = []
temp_voice_data = {}
nickname_filters_data = {}
fresh_account_settings = {}
quarantine_data = {}
notes_data = {}
prison_break_data = {}

# Function to load warnings from file
def load_warnings():
    try:
        if os.path.exists(WARNING_FILE):
            with open(WARNING_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading warnings: {e}")
        return {}

# Function to save warnings to file
def save_warnings(warnings):
    try:
        with open(WARNING_FILE, 'w') as f:
            json.dump(warnings, f, indent=4)
    except Exception as e:
        print(f"Error saving warnings: {e}")

# Function to load reaction roles from file
def load_reaction_roles():
    try:
        if os.path.exists(REACTION_ROLES_FILE):
            with open(REACTION_ROLES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading reaction roles: {e}")
        return {}

# Function to save reaction roles to file
def save_reaction_roles(data):
    try:
        with open(REACTION_ROLES_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving reaction roles: {e}")

# Function to load custom commands from file
def load_custom_commands():
    try:
        if os.path.exists(CUSTOM_COMMANDS_FILE):
            with open(CUSTOM_COMMANDS_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading custom commands: {e}")
        return {}

# Function to save custom commands to file
def save_custom_commands(data):
    try:
        with open(CUSTOM_COMMANDS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving custom commands: {e}")

# Function to load scheduled tasks
def load_scheduled_tasks():
    try:
        if os.path.exists(SCHEDULED_TASKS_FILE):
            with open(SCHEDULED_TASKS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"Error loading scheduled tasks: {e}")
        return []

# Function to save scheduled tasks
def save_scheduled_tasks(data):
    try:
        with open(SCHEDULED_TASKS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving scheduled tasks: {e}")

# Function to load temp voice channels
def load_temp_voice():
    try:
        if os.path.exists(TEMP_VOICE_FILE):
            with open(TEMP_VOICE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading temp voice channels: {e}")
        return {}

# Function to save temp voice channels
def save_temp_voice(data):
    try:
        with open(TEMP_VOICE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving temp voice channels: {e}")

# Function to load fresh account settings
def load_fresh_account_settings():
    try:
        if os.path.exists(FRESH_ACCOUNT_FILE):
            with open(FRESH_ACCOUNT_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading fresh account settings: {e}")
        return {}

# Function to save fresh account settings
def save_fresh_account_settings(data):
    try:
        with open(FRESH_ACCOUNT_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving fresh account settings: {e}")

# Function to load quarantined users
def load_quarantine_data():
    try:
        if os.path.exists(QUARANTINE_FILE):
            with open(QUARANTINE_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading quarantine data: {e}")
        return {}
        
# Function to save quarantined users
def save_quarantine_data(data):
    try:
        with open(QUARANTINE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving quarantine data: {e}")

# Function to load nickname filters
def load_nickname_filters():
    try:
        if os.path.exists(NICKNAME_FILTER_FILE):
            with open(NICKNAME_FILTER_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading nickname filters: {e}")
        return {}

# Function to save nickname filters
def save_nickname_filters(data):
    try:
        with open(NICKNAME_FILTER_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving nickname filters: {e}")

# Function to load notes
def load_notes():
    try:
        if os.path.exists(NOTES_FILE):
            with open(NOTES_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading notes: {e}")
        return {}

# Function to save notes
def save_notes(data):
    try:
        with open(NOTES_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving notes: {e}")

# Function to load prison break game data
def load_prison_break_data():
    try:
        if os.path.exists(PRISON_BREAK_FILE):
            with open(PRISON_BREAK_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error loading prison break data: {e}")
        return {}

# Function to save prison break game data
def save_prison_break_data(data):
    try:
        with open(PRISON_BREAK_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving prison break data: {e}")

# Function to create a backup of all data files
async def create_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    
    # List of files to backup
    files_to_backup = [
        WARNING_FILE, 
        REACTION_ROLES_FILE,
        CUSTOM_COMMANDS_FILE,
        SCHEDULED_TASKS_FILE,
        TEMP_VOICE_FILE,
        FRESH_ACCOUNT_FILE,
        QUARANTINE_FILE,
        NICKNAME_FILTER_FILE,
        NOTES_FILE,
        PRISON_BREAK_FILE
    ]
    
    for file in files_to_backup:
        if os.path.exists(file):
            try:
                with open(file, 'r') as src:
                    content = src.read()
                    
                with open(os.path.join(backup_path, file), 'w') as dest:
                    dest.write(content)
            except Exception as e:
                print(f"Error backing up {file}: {e}")
    
    print(f"Backup created at {backup_path}")
    return backup_path

# Initialize all data stores
def initialize_data():
    global warnings_data, reaction_roles_data, custom_commands_data
    global scheduled_tasks_data, temp_voice_data, nickname_filters_data
    global fresh_account_settings, quarantine_data, notes_data, prison_break_data
    
    # Create backup directory if it doesn't exist
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Load all data
    warnings_data = load_warnings()
    reaction_roles_data = load_reaction_roles()
    custom_commands_data = load_custom_commands()
    scheduled_tasks_data = load_scheduled_tasks()
    temp_voice_data = load_temp_voice()
    nickname_filters_data = load_nickname_filters()
    fresh_account_settings = load_fresh_account_settings()
    quarantine_data = load_quarantine_data()
    notes_data = load_notes()
    prison_break_data = load_prison_break_data()
    
    print("✅ All data files loaded successfully") 