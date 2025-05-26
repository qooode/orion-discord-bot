"""
Orion Discord Bot - Modular Architecture
Main entry point for the bot
"""

import discord
import sys
import os
from discord.ext import commands

# Import configuration and data management
from config import TOKEN, PREFIX
from data_manager import initialize_data

# Import event handlers
from events import setup_events

# Import command modules
from commands.moderation import setup_moderation_commands
from commands.utility import setup_utility_commands
from commands.mass_moderation import setup_mass_moderation_commands
from commands.quarantine import setup_quarantine_commands

def create_bot():
    """Create and setup the bot with all its components"""
    
    # Set up intents for the bot
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True

    # Create bot instance
    bot = commands.Bot(command_prefix=PREFIX, intents=intents)
    
    # Initialize all data stores
    initialize_data()
    
    # Attach bot attributes
    bot.antiraid_mode = False
    bot.server_lockdown = False
    bot.rate_limit = None
    
    # Setup event handlers (non-async registration)
    setup_events(bot)
    
    return bot

def main():
    """Main function to run the bot"""
    
    # Check if token is available
    if not TOKEN:
        print("❌ Error: No Discord token found!")
        print("Please create a 'bot.env' file with:")
        print("DISCORD_TOKEN=your_token_here")
        print("COMMAND_PREFIX=!")
        return
    
    # Print diagnostic info
    print("\n🤖 === ORION BOT STARTUP ===")
    print(f"Discord.py version: {discord.__version__}")
    print(f"Python version: {sys.version.split()[0]}")
    print(f"Command prefix: {PREFIX}")
    print("🔧 Loading modular architecture...")
    print("📦 Modules: config, data_manager, events, moderation, utility, mass_moderation, quarantine")
    print("⚡ Features: Basic moderation, purgewords, quarantine system, prison break games")
    print("================================\n")
    
    # Create the bot
    bot = create_bot()
    
    # Run the bot
    try:
        # This will trigger the on_ready event which loads all modules
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("❌ Invalid Discord token! Please check your bot.env file")
    except Exception as e:
        print(f"❌ Error running bot: {e}")

if __name__ == "__main__":
    main() 