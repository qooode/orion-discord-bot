"""
Commands package for Orion Discord Bot
Contains all command modules organized by category
"""

# This file makes the commands directory a Python package
# Import statements can be added here for easier imports

__version__ = "1.0.0"
__author__ = "Orion Bot Team"

# Available command modules
AVAILABLE_MODULES = [
    "moderation",           # Basic moderation commands (kick, ban, warn, etc.)
    "utility",             # Information commands (userinfo, serverinfo, notes)
    "mass_moderation",     # Mass moderation (purgewords, massban, clean)
    "quarantine",          # Quarantine system, prison break games, throw, freshaccounts
    # Add more modules here as they are created
]

# Feature overview
FEATURES = {
    "moderation": ["kick", "ban", "mute", "warn", "lockdown", "unlock", "slowmode", "warnings", "clearwarnings", "userinfo", "serverlock", "serverunlock", "antiraid"],
    "utility": ["userinfo", "serverinfo", "notes", "deletenote"],
    "mass_moderation": ["purgewords", "massban", "masskick", "clean", "idcheck"],
    "quarantine": ["quarantine", "unquarantine", "quarantinelist", "setjailcam", "throw", "freshaccounts", "prisonbreak", "prisonhelp", "quarantinedebug", "quarantinetrigger"],
} 