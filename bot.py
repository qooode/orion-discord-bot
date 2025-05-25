import os
import json
import discord
import datetime
import asyncio
import re
from typing import Optional, List, Union
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('bot.env')

# Get the Discord token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')
PREFIX = os.getenv('COMMAND_PREFIX', '!')

# File to store warnings
WARNING_FILE = 'warnings.json'

# Bad words filter (can be expanded)
BAD_WORDS = ['badword1', 'badword2', 'badword3']

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

# File to store reaction roles
REACTION_ROLES_FILE = 'reaction_roles.json'

# File to store custom commands
CUSTOM_COMMANDS_FILE = 'custom_commands.json'

# File to store scheduled tasks
SCHEDULED_TASKS_FILE = 'scheduled_tasks.json'

# File to store temp voice channels
TEMP_VOICE_FILE = 'temp_voice.json'

# Backup directory
BACKUP_DIR = 'backups'

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

# Create backup directory if it doesn't exist
os.makedirs(BACKUP_DIR, exist_ok=True)

# Function to create a backup of all data files
def create_backup():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
    os.makedirs(backup_path, exist_ok=True)
    
    # List of files to backup
    files_to_backup = [
        WARNING_FILE, 
        REACTION_ROLES_FILE,
        CUSTOM_COMMANDS_FILE,
        SCHEDULED_TASKS_FILE,
        TEMP_VOICE_FILE
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

# Initialize data stores
warnings_data = load_warnings()
reaction_roles_data = load_reaction_roles()
custom_commands_data = load_custom_commands()
scheduled_tasks_data = load_scheduled_tasks()
temp_voice_data = load_temp_voice()

# Set up intents for the bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Create bot instance
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Event: Bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    # Set custom status
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for rule breakers"))
    
    # Check for temp voice channels that need to be tracked
    for guild in bot.guilds:
        guild_id = str(guild.id)
        if guild_id in temp_voice_data and "create_channel" in temp_voice_data[guild_id]:
            create_channel_id = temp_voice_data[guild_id]["create_channel"]
            create_channel = guild.get_channel(int(create_channel_id))
            if create_channel:
                print(f"Found temp voice creator channel in {guild.name}")
    
    # Start backup task
    bot.loop.create_task(scheduled_backup())
    
    # Start scheduled tasks handler
    bot.loop.create_task(check_scheduled_tasks())

# Scheduled backup task
async def scheduled_backup():
    while True:
        # Create backup every 12 hours
        await asyncio.sleep(12 * 60 * 60)  # 12 hours
        backup_path = create_backup()
        print(f"Scheduled backup created at {backup_path}")
        
        # Clean up old backups (keep last 7)
        backup_folders = sorted([os.path.join(BACKUP_DIR, d) for d in os.listdir(BACKUP_DIR) 
                               if os.path.isdir(os.path.join(BACKUP_DIR, d))])
        if len(backup_folders) > 7:
            for old_folder in backup_folders[:-7]:
                try:
                    for file in os.listdir(old_folder):
                        os.remove(os.path.join(old_folder, file))
                    os.rmdir(old_folder)
                    print(f"Removed old backup: {old_folder}")
                except Exception as e:
                    print(f"Error removing old backup {old_folder}: {e}")

# Check scheduled tasks
async def check_scheduled_tasks():
    while True:
        await asyncio.sleep(60)  # Check every minute
        current_time = datetime.datetime.utcnow()
        tasks_to_remove = []
        
        for i, task in enumerate(scheduled_tasks_data):
            try:
                execute_time = datetime.datetime.fromisoformat(task["time"])
                if current_time >= execute_time:
                    # Time to execute this task
                    guild_id = int(task["guild_id"])
                    guild = bot.get_guild(guild_id)
                    
                    if guild:
                        action_type = task["action"]
                        
                        if action_type == "unban":
                            user_id = int(task["user_id"])
                            reason = task.get("reason", "Scheduled unban")
                            try:
                                await guild.unban(discord.Object(id=user_id), reason=reason)
                                print(f"Scheduled unban for user {user_id} in {guild.name}")
                            except:
                                print(f"Failed scheduled unban for user {user_id} in {guild.name}")
                                
                        elif action_type == "unmute":
                            user_id = int(task["user_id"])
                            reason = task.get("reason", "Scheduled unmute")
                            try:
                                member = guild.get_member(user_id)
                                if member:
                                    await member.timeout(None, reason=reason)
                                    print(f"Scheduled unmute for user {member.display_name} in {guild.name}")
                            except:
                                print(f"Failed scheduled unmute for user {user_id} in {guild.name}")
                                
                        elif action_type == "reminder":
                            channel_id = int(task["channel_id"])
                            message = task["message"]
                            channel = guild.get_channel(channel_id)
                            if channel:
                                try:
                                    await channel.send(f"⏰ **Scheduled Reminder:** {message}")
                                    print(f"Sent reminder in {channel.name}")
                                except:
                                    print(f"Failed to send reminder in channel {channel_id}")
                    
                    # Mark task for removal
                    tasks_to_remove.append(i)
            except Exception as e:
                print(f"Error processing scheduled task: {e}")
                tasks_to_remove.append(i)
        
        # Remove completed tasks (in reverse order to avoid index issues)
        for index in sorted(tasks_to_remove, reverse=True):
            scheduled_tasks_data.pop(index)
        
        if tasks_to_remove:
            save_scheduled_tasks(scheduled_tasks_data)

# Voice state update event for temporary voice channels
@bot.event
async def on_voice_state_update(member, before, after):
    # Skip for bots
    if member.bot:
        return
        
    guild_id = str(member.guild.id)
    
    # Check if guild has temp voice channels
    if guild_id not in temp_voice_data:
        return
        
    # Handle user joined the create channel
    if after.channel is not None and "create_channel" in temp_voice_data[guild_id]:
        create_channel_id = temp_voice_data[guild_id]["create_channel"]
        if str(after.channel.id) == create_channel_id:
            # User joined the create channel, make them a new channel
            try:
                # Create a new voice channel in the same category
                category = after.channel.category
                new_channel = await category.create_voice_channel(
                    name=f"{member.display_name}'s Channel",
                    bitrate=after.channel.bitrate,
                    user_limit=0  # No user limit by default
                )
                
                # Give the creator manage permissions
                await new_channel.set_permissions(member, manage_channels=True, move_members=True)
                
                # Move the user to their new channel
                await member.move_to(new_channel)
                
                # Track this channel
                if "temp_channels" not in temp_voice_data[guild_id]:
                    temp_voice_data[guild_id]["temp_channels"] = {}
                
                temp_voice_data[guild_id]["temp_channels"][str(new_channel.id)] = {
                    "owner": str(member.id),
                    "created_at": str(datetime.datetime.utcnow())
                }
                save_temp_voice(temp_voice_data)
                
                # Inform the user
                try:
                    await member.send(f"I created a voice channel for you! You can manage it with these commands:\n- `/voicelock` - Lock your channel\n- `/voiceunlock` - Unlock your channel\n- `/voicelimit [number]` - Set user limit\n- `/voicename [name]` - Rename your channel")
                except:
                    pass  # Couldn't DM user
            except Exception as e:
                print(f"Error creating temp voice channel: {e}")
    
    # Handle channel cleanup when empty
    if before.channel is not None:
        if guild_id in temp_voice_data and "temp_channels" in temp_voice_data[guild_id]:
            channel_id = str(before.channel.id)
            if channel_id in temp_voice_data[guild_id]["temp_channels"]:
                # This is a temp channel, check if empty
                if len(before.channel.members) == 0:
                    try:
                        # Delete the empty channel
                        await before.channel.delete(reason="Temporary voice channel - empty")
                        
                        # Remove from tracking
                        del temp_voice_data[guild_id]["temp_channels"][channel_id]
                        save_temp_voice(temp_voice_data)
                    except Exception as e:
                        print(f"Error deleting temp voice channel: {e}")

# Custom commands handler
@bot.event
async def on_message(message):
    # Don't process commands from the bot itself
    if message.author == bot.user:
        return
    
    # Process commands if any
    await bot.process_commands(message)
    
    # Skip DMs
    if not message.guild:
        return
    
    # Auto-moderate content (from earlier code)
    content = message.content.lower()
    
    # Check for bad words
    if any(word in content for word in BAD_WORDS):
        await message.delete()
        await message.channel.send(f"{message.author.mention}, please watch your language!", delete_after=5)
        
        # Auto-warn for bad language
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Initialize guild and user in warnings_data if they don't exist
        if guild_id not in warnings_data:
            warnings_data[guild_id] = {}
        if user_id not in warnings_data[guild_id]:
            warnings_data[guild_id][user_id] = []
        
        # Add the warning
        warning = {
            "reason": "Automatic warning for inappropriate language",
            "timestamp": str(datetime.datetime.utcnow()),
            "moderator": str(bot.user.id)
        }
        warnings_data[guild_id][user_id].append(warning)
        save_warnings(warnings_data)
        
        # DM the user about the warning
        try:
            await message.author.send(f"You have been automatically warned in **{message.guild.name}** for inappropriate language.")
        except:
            pass  # Silently fail if DM cannot be sent
            
    # Check for custom commands
    guild_id = str(message.guild.id)
    if guild_id in custom_commands_data and message.content.startswith(PREFIX):
        cmd = message.content[len(PREFIX):].lower().strip()
        if cmd in custom_commands_data[guild_id]:
            # Execute custom command
            cmd_data = custom_commands_data[guild_id][cmd]
            response = cmd_data["response"]
            
            # Check if this is an embed command
            if cmd_data.get("is_embed", False):
                embed = discord.Embed(
                    title=cmd_data.get("title", "Custom Command"),
                    description=response,
                    color=discord.Color.blue()
                )
                
                if "image" in cmd_data and cmd_data["image"]:
                    embed.set_image(url=cmd_data["image"])
                    
                if "footer" in cmd_data and cmd_data["footer"]:
                    embed.set_footer(text=cmd_data["footer"])
                    
                await message.channel.send(embed=embed)
            else:
                await message.channel.send(response)

# Auto-moderation: Message filter
@bot.event
async def on_message(message):
    # Don't process commands from the bot itself
    if message.author == bot.user:
        return
    
    # Process commands if any
    await bot.process_commands(message)
    
    # Skip moderation in DMs
    if not message.guild:
        return
    
    # Auto-moderate content
    content = message.content.lower()
    
    # Check for bad words
    if any(word in content for word in BAD_WORDS):
        await message.delete()
        await message.channel.send(f"{message.author.mention}, please watch your language!", delete_after=5)
        
        # Auto-warn for bad language
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Initialize guild and user in warnings_data if they don't exist
        if guild_id not in warnings_data:
            warnings_data[guild_id] = {}
        if user_id not in warnings_data[guild_id]:
            warnings_data[guild_id][user_id] = []
        
        # Add the warning
        warning = {
            "reason": "Automatic warning for inappropriate language",
            "timestamp": str(datetime.datetime.utcnow()),
            "moderator": str(bot.user.id)
        }
        warnings_data[guild_id][user_id].append(warning)
        save_warnings(warnings_data)
        
        # DM the user about the warning
        try:
            await message.author.send(f"You have been automatically warned in **{message.guild.name}** for inappropriate language.")
        except:
            pass  # Silently fail if DM cannot be sent

# Member join event
@bot.event
async def on_member_join(member):
    # Skip if bot
    if member.bot:
        return
        
    # Check if anti-raid mode is on
    if getattr(bot, 'antiraid_mode', False):
        # If in anti-raid mode, log the join and consider action
        try:
            # Add a special role if available
            quarantine_role = discord.utils.get(member.guild.roles, name="Quarantine")
            if quarantine_role:
                await member.add_roles(quarantine_role, reason="Auto-quarantine during anti-raid mode")
                
            # Log the join to mod-logs channel
            log_channel = discord.utils.get(member.guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="⚠️ Member Joined During Anti-Raid Mode",
                    description=f"{member.mention} joined while anti-raid protection is active.",
                    color=discord.Color.gold()
                )
                embed.add_field(name="Account Age", value=f"{(discord.utils.utcnow() - member.created_at).days} days")
                embed.set_thumbnail(url=member.display_avatar.url)
                await log_channel.send(embed=embed)
        except:
            pass  # Don't let errors stop the welcome message
    
    # Send welcome message
    welcome_channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if welcome_channel:
        embed = discord.Embed(
            title=f"Welcome to {member.guild.name}!",
            description=f"Hey {member.mention}, welcome to the server! Please read the rules and enjoy your stay.",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{len(member.guild.members)}")
        await welcome_channel.send(embed=embed)

# Reaction add event for reaction roles
@bot.event
async def on_raw_reaction_add(payload):
    # Ignore bot reactions
    if payload.member.bot:
        return
        
    # Check if this message has reaction roles
    message_id = str(payload.message_id)
    if message_id not in reaction_roles_data:
        return
        
    # Get the emoji and check if it's a role emoji
    emoji = str(payload.emoji)
    if emoji not in reaction_roles_data[message_id]:
        return
        
    # Get the role
    role_id = int(reaction_roles_data[message_id][emoji])
    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(role_id)
    
    if role:
        try:
            await payload.member.add_roles(role, reason="Reaction role")
        except Exception as e:
            print(f"Error adding reaction role: {e}")

# Reaction remove event for reaction roles
@bot.event
async def on_raw_reaction_remove(payload):
    # Get guild and member
    guild = bot.get_guild(payload.guild_id)
    if not guild:
        return
        
    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return
        
    # Check if this message has reaction roles
    message_id = str(payload.message_id)
    if message_id not in reaction_roles_data:
        return
        
    # Get the emoji and check if it's a role emoji
    emoji = str(payload.emoji)
    if emoji not in reaction_roles_data[message_id]:
        return
        
    # Get the role
    role_id = int(reaction_roles_data[message_id][emoji])
    role = guild.get_role(role_id)
    
    if role:
        try:
            await member.remove_roles(role, reason="Reaction role removed")
        except Exception as e:
            print(f"Error removing reaction role: {e}")

# Moderation Commands

@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for kicking")
@app_commands.default_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("You cannot kick someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"✅ {member.mention} has been kicked. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to kick this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="The member to ban", reason="Reason for banning", delete_days="Number of days of messages to delete")
@app_commands.default_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: int = 0):
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("You cannot ban someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        await member.ban(reason=reason, delete_message_days=delete_days)
        await interaction.response.send_message(f"🔨 {member.mention} has been banned. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="purge", description="Delete a specified number of messages")
@app_commands.describe(amount="Number of messages to delete (max 100)")
@app_commands.default_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: int = 5):
    if amount <= 0 or amount > 100:
        await interaction.response.send_message("Please provide a number between 1 and 100.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    try:
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to delete messages.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="mute", description="Timeout a member")
@app_commands.describe(member="The member to timeout", duration="Duration in minutes", reason="Reason for the timeout")
@app_commands.default_permissions(moderate_members=True)
async def mute(interaction: discord.Interaction, member: discord.Member, duration: int = 5, reason: str = "No reason provided"):
    if member.top_role >= interaction.user.top_role:
        await interaction.response.send_message("You cannot timeout someone with a higher or equal role!", ephemeral=True)
        return
    
    try:
        # Convert minutes to seconds and create a timedelta
        timeout_duration = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
        await member.timeout(timeout_duration, reason=reason)
        await interaction.response.send_message(f"🔇 {member.mention} has been timed out for {duration} minutes. Reason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout this member.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="warn", description="Warn a member")
@app_commands.describe(member="The member to warn", reason="Reason for the warning")
@app_commands.default_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    try:
        # Check for permission hierarchy
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("You cannot warn someone with a higher or equal role!", ephemeral=True)
            return
            
        # Store warning in our json system
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        # Initialize guild and user in warnings_data if they don't exist
        if guild_id not in warnings_data:
            warnings_data[guild_id] = {}
        if user_id not in warnings_data[guild_id]:
            warnings_data[guild_id][user_id] = []
        
        # Add the warning
        warning = {
            "reason": reason,
            "timestamp": str(datetime.datetime.utcnow()),
            "moderator": str(interaction.user.id)
        }
        warnings_data[guild_id][user_id].append(warning)
        save_warnings(warnings_data)
        
        # Create warning count message
        warning_count = len(warnings_data[guild_id][user_id])
        warning_count_text = f"This is warning #{warning_count} for this user."
        
        # Create embed
        embed = discord.Embed(
            title="⚠️ Warning Issued",
            description=f"{member.mention} has been warned by {interaction.user.mention}",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning Count", value=warning_count_text, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Warned on {discord.utils.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        
        await interaction.response.send_message(embed=embed)
        
        # Also send a DM to the warned user
        try:
            warn_dm = discord.Embed(
                title=f"Warning in {interaction.guild.name}",
                description=f"You have been warned by {interaction.user.display_name}",
                color=discord.Color.yellow()
            )
            warn_dm.add_field(name="Reason", value=reason, inline=False)
            warn_dm.add_field(name="Warning Count", value=warning_count_text, inline=False)
            warn_dm.set_footer(text="Please make sure to follow the server rules to avoid further moderation actions.")
            
            await member.send(embed=warn_dm)
        except:
            pass  # Silently fail if DM cannot be sent
            
        # Auto-moderate based on warning count
        if warning_count == 3:
            await interaction.followup.send(f"⚠️ {member.mention} has reached 3 warnings. Consider taking further action.", ephemeral=True)
        elif warning_count == 5:
            try:
                # Auto-timeout for 1 hour on 5th warning
                timeout_duration = discord.utils.utcnow() + datetime.timedelta(hours=1)
                await member.timeout(timeout_duration, reason="Automatic timeout after 5 warnings")
                await interaction.followup.send(f"🔇 {member.mention} has been automatically timed out for 1 hour after reaching 5 warnings.", ephemeral=False)
            except:
                await interaction.followup.send(f"Failed to auto-timeout {member.mention} after 5 warnings. Please check permissions.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Advanced moderation commands

@bot.tree.command(name="lockdown", description="Lock a channel to prevent messages from regular users")
@app_commands.describe(channel="The channel to lock", reason="Reason for the lockdown", minutes="Minutes to lock the channel (0 for indefinite)")
@app_commands.default_permissions(manage_channels=True)
async def lockdown(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, reason: str = "No reason provided", minutes: int = 0):
    # Default to current channel if not specified
    target_channel = channel or interaction.channel
    
    try:
        # Get the default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Remove send messages permission
        await target_channel.set_permissions(default_role, send_messages=False, reason=f"Lockdown: {reason}")
        
        # Create embed for lockdown notice
        lock_embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"This channel has been locked by {interaction.user.mention}.",
            color=discord.Color.red()
        )
        lock_embed.add_field(name="Reason", value=reason, inline=False)
        if minutes > 0:
            lock_embed.add_field(name="Duration", value=f"{minutes} minutes", inline=False)
        
        await target_channel.send(embed=lock_embed)
        await interaction.response.send_message(f"🔒 {target_channel.mention} has been locked.", ephemeral=True)
        
        # If duration is specified, schedule unlock
        if minutes > 0:
            await interaction.followup.send(f"Channel will be unlocked in {minutes} minutes.", ephemeral=True)
            await asyncio.sleep(minutes * 60)
            await target_channel.set_permissions(default_role, send_messages=None, reason="Lockdown period expired")
            
            # Create embed for unlock notice
            unlock_embed = discord.Embed(
                title="🔓 Channel Unlocked",
                description="This channel has been automatically unlocked.",
                color=discord.Color.green()
            )
            await target_channel.send(embed=unlock_embed)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock a previously locked channel")
@app_commands.describe(channel="The channel to unlock")
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
    # Default to current channel if not specified
    target_channel = channel or interaction.channel
    
    try:
        # Get the default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Reset send messages permission
        await target_channel.set_permissions(default_role, send_messages=None, reason="Channel unlocked")
        
        # Create embed for unlock notice
        unlock_embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"This channel has been unlocked by {interaction.user.mention}.",
            color=discord.Color.green()
        )
        
        await target_channel.send(embed=unlock_embed)
        await interaction.response.send_message(f"🔓 {target_channel.mention} has been unlocked.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="slowmode", description="Set slowmode in a channel")
@app_commands.describe(seconds="Seconds between messages (0-21600, 0 to disable)", channel="The channel to set slowmode for")
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: int, channel: Optional[discord.TextChannel] = None):
    # Default to current channel if not specified
    target_channel = channel or interaction.channel
    
    try:
        # Validate seconds
        if seconds < 0 or seconds > 21600:
            await interaction.response.send_message("Slowmode delay must be between 0 and 21600 seconds (6 hours).", ephemeral=True)
            return
        
        # Set slowmode
        await target_channel.edit(slowmode_delay=seconds)
        
        if seconds == 0:
            await interaction.response.send_message(f"Slowmode has been disabled in {target_channel.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Slowmode set to {seconds} seconds in {target_channel.mention}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="warnings", description="View warnings for a user")
@app_commands.describe(member="The member to check warnings for")
@app_commands.default_permissions(moderate_members=True)
async def warnings(interaction: discord.Interaction, member: discord.Member):
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        # Check if the user has any warnings
        if guild_id not in warnings_data or user_id not in warnings_data[guild_id] or not warnings_data[guild_id][user_id]:
            await interaction.response.send_message(f"{member.display_name} has no warnings.", ephemeral=True)
            return
        
        # Get warnings
        user_warnings = warnings_data[guild_id][user_id]
        warning_count = len(user_warnings)
        
        # Create embed
        embed = discord.Embed(
            title=f"Warnings for {member.display_name}",
            description=f"Total warnings: {warning_count}",
            color=discord.Color.orange()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Add each warning to the embed
        for i, warning in enumerate(user_warnings, 1):
            reason = warning.get("reason", "No reason provided")
            timestamp = warning.get("timestamp", "Unknown time")
            mod_id = warning.get("moderator", "Unknown moderator")
            
            # Try to get moderator name
            try:
                moderator = await interaction.guild.fetch_member(int(mod_id))
                mod_name = moderator.display_name
            except:
                mod_name = f"Unknown Moderator (ID: {mod_id})"
            
            embed.add_field(name=f"Warning #{i}", value=f"**Reason:** {reason}\n**When:** {timestamp}\n**By:** {mod_name}", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="clearwarnings", description="Clear warnings for a user")
@app_commands.describe(member="The member to clear warnings for", amount="Number of warnings to clear (0 for all)")
@app_commands.default_permissions(administrator=True)
async def clearwarnings(interaction: discord.Interaction, member: discord.Member, amount: int = 0):
    try:
        guild_id = str(interaction.guild.id)
        user_id = str(member.id)
        
        # Check if the user has any warnings
        if guild_id not in warnings_data or user_id not in warnings_data[guild_id] or not warnings_data[guild_id][user_id]:
            await interaction.response.send_message(f"{member.display_name} has no warnings to clear.", ephemeral=True)
            return
        
        # Get current warning count
        current_count = len(warnings_data[guild_id][user_id])
        
        # Clear warnings
        if amount <= 0 or amount >= current_count:
            warnings_data[guild_id][user_id] = []
            cleared_count = current_count
        else:
            warnings_data[guild_id][user_id] = warnings_data[guild_id][user_id][:-amount]
            cleared_count = amount
        
        save_warnings(warnings_data)
        
        await interaction.response.send_message(f"Cleared {cleared_count} warnings for {member.display_name}.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="userinfo", description="Get information about a user")
@app_commands.describe(member="The member to get information about")
async def userinfo(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    # Default to command user if no member provided
    target_member = member or interaction.user
    
    try:
        # Get warning count if any
        guild_id = str(interaction.guild.id)
        user_id = str(target_member.id)
        warning_count = 0
        if guild_id in warnings_data and user_id in warnings_data[guild_id]:
            warning_count = len(warnings_data[guild_id][user_id])
        
        # Create account age string
        created_at = target_member.created_at
        account_age = (discord.utils.utcnow() - created_at).days
        created_str = f"{created_at.strftime('%Y-%m-%d %H:%M:%S')} ({account_age} days ago)"
        
        # Create server join age string
        joined_at = target_member.joined_at
        join_age = (discord.utils.utcnow() - joined_at).days if joined_at else 0
        joined_str = f"{joined_at.strftime('%Y-%m-%d %H:%M:%S')} ({join_age} days ago)" if joined_at else "Unknown"
        
        # Create embed
        embed = discord.Embed(
            title=f"User Info: {target_member.display_name}",
            color=target_member.color
        )
        embed.set_thumbnail(url=target_member.display_avatar.url)
        
        embed.add_field(name="User ID", value=target_member.id, inline=True)
        embed.add_field(name="Bot", value=":robot:" if target_member.bot else ":person_standing:", inline=True)
        embed.add_field(name="Warnings", value=warning_count, inline=True)
        
        embed.add_field(name="Created At", value=created_str, inline=False)
        embed.add_field(name="Joined At", value=joined_str, inline=False)
        
        # Roles
        roles = [role.mention for role in target_member.roles if role.name != "@everyone"]
        if roles:
            embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles) if len(" ".join(roles)) < 1024 else f"{len(roles)} roles", inline=False)
        
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="serverlock", description="Lock down the entire server in emergency situations")
@app_commands.describe(reason="Reason for the server lockdown", minutes="Minutes to lock the server (0 for indefinite)")
@app_commands.default_permissions(administrator=True)
async def serverlock(interaction: discord.Interaction, reason: str = "Emergency lockdown", minutes: int = 0):
    try:
        await interaction.response.defer()
        
        # Get the default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Create announcement embed
        lock_embed = discord.Embed(
            title="🚨 SERVER LOCKDOWN ACTIVATED 🚨",
            description=f"This server has been locked down by {interaction.user.mention}.",
            color=discord.Color.red()
        )
        lock_embed.add_field(name="Reason", value=reason, inline=False)
        if minutes > 0:
            lock_embed.add_field(name="Duration", value=f"{minutes} minutes", inline=False)
        lock_embed.add_field(name="What this means", value="All channels have been locked. Please stand by for further instructions from the moderation team.", inline=False)
        
        # Track channels being locked
        locked_channels = 0
        skipped_channels = 0
        
        # Find announcement channel if possible
        announcement_channel = discord.utils.get(interaction.guild.text_channels, name="announcements")
        if not announcement_channel:
            announcement_channel = discord.utils.get(interaction.guild.text_channels, name="general")
        
        # Lock all text channels
        for channel in interaction.guild.text_channels:
            try:
                # Skip channels that might already be locked or have special permissions
                perms = channel.permissions_for(default_role)
                if not perms.send_messages:
                    skipped_channels += 1
                    continue
                    
                await channel.set_permissions(default_role, send_messages=False, reason=f"Server Lockdown: {reason}")
                locked_channels += 1
                
                # Send notification in the channel itself
                if channel != announcement_channel:
                    try:
                        await channel.send(embed=lock_embed)
                    except:
                        pass
            except:
                skipped_channels += 1
        
        # Send main announcement in the announcement channel
        if announcement_channel:
            await announcement_channel.send(embed=lock_embed)
        
        # Send confirmation to moderator
        await interaction.followup.send(f"Server lockdown activated! Locked {locked_channels} channels. {skipped_channels} channels were skipped.")
        
        # Set a special status for the bot during lockdown
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="🚨 SERVER LOCKDOWN 🚨"), status=discord.Status.dnd)
        
        # Store lockdown state
        bot.server_lockdown = True
        
        # If duration is specified, schedule unlock
        if minutes > 0:
            await asyncio.sleep(minutes * 60)
            await server_unlock(interaction, "Automatic unlock after scheduled duration")
            
    except Exception as e:
        await interaction.followup.send(f"Error during server lockdown: {str(e)}")

@bot.tree.command(name="serverunlock", description="Unlock the server after a lockdown")
@app_commands.describe(reason="Reason for unlocking the server")
@app_commands.default_permissions(administrator=True)
async def server_unlock(interaction: discord.Interaction, reason: str = "Lockdown lifted"):
    try:
        await interaction.response.defer()
        
        # Get the default role (@everyone)
        default_role = interaction.guild.default_role
        
        # Create announcement embed
        unlock_embed = discord.Embed(
            title="🔓 SERVER LOCKDOWN LIFTED",
            description=f"This server has been unlocked by {interaction.user.mention}.",
            color=discord.Color.green()
        )
        unlock_embed.add_field(name="Reason", value=reason, inline=False)
        unlock_embed.add_field(name="Notice", value="All channels have been restored to their normal state. Thank you for your patience.", inline=False)
        
        # Track channels being unlocked
        unlocked_channels = 0
        skipped_channels = 0
        
        # Find announcement channel if possible
        announcement_channel = discord.utils.get(interaction.guild.text_channels, name="announcements")
        if not announcement_channel:
            announcement_channel = discord.utils.get(interaction.guild.text_channels, name="general")
        
        # Unlock all text channels
        for channel in interaction.guild.text_channels:
            try:
                # Reset permissions
                await channel.set_permissions(default_role, send_messages=None, reason=f"Server Lockdown Lifted: {reason}")
                unlocked_channels += 1
            except:
                skipped_channels += 1
        
        # Send main announcement in the announcement channel
        if announcement_channel:
            await announcement_channel.send(embed=unlock_embed)
        
        # Send confirmation to moderator
        await interaction.followup.send(f"Server lockdown lifted! Unlocked {unlocked_channels} channels. {skipped_channels} channels were skipped.")
        
        # Reset bot status
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for rule breakers"))
        
        # Store lockdown state
        bot.server_lockdown = False
            
    except Exception as e:
        await interaction.followup.send(f"Error during server unlock: {str(e)}")

@bot.tree.command(name="antiraid", description="Toggle anti-raid mode")
@app_commands.describe(status="Enable or disable anti-raid mode")
@app_commands.choices(status=[
    app_commands.Choice(name="Enable", value=1),
    app_commands.Choice(name="Disable", value=0)
])
@app_commands.default_permissions(administrator=True)
async def antiraid(interaction: discord.Interaction, status: int):
    try:
        # Store anti-raid mode status as a bot attribute
        bot.antiraid_mode = bool(status)
        
        if status:
            embed = discord.Embed(
                title="🛡️ Anti-Raid Mode Enabled",
                description="New members will be carefully monitored for suspicious activity.",
                color=discord.Color.red()
            )
            embed.add_field(name="Effects", value="• New members cannot post links or attachments\n• Quick joins will be flagged\n• Stricter auto-moderation active")
        else:
            embed = discord.Embed(
                title="🛡️ Anti-Raid Mode Disabled",
                description="Server has returned to normal moderation levels.",
                color=discord.Color.green()
            )
        
        # Find a log channel to announce this change
        log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
        if log_channel:
            await log_channel.send(embed=embed)
        
        await interaction.response.send_message(f"Anti-raid mode {'enabled' if status else 'disabled'} successfully.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Mass moderation commands
@bot.tree.command(name="purgewords", description="Delete all messages containing specific words in a channel")
@app_commands.describe(
    channel="The channel to scan", 
    words="Words to search for (space separated)", 
    user="Optional: Only delete messages from this user",
    limit="Optional: Maximum number of messages to scan (0 for all retrievable messages)",
    silent="Optional: Whether to silently delete without showing a report"
)
@app_commands.default_permissions(manage_messages=True)
async def purgewords(interaction: discord.Interaction, channel: discord.TextChannel, words: str, 
                     user: Optional[discord.Member] = None, limit: int = 1000, silent: bool = False):
    try:
        # Immediately defer the response as this could take time
        await interaction.response.defer(ephemeral=True)
        
        # Parse the words to search for
        search_words = [word.lower().strip() for word in words.split() if word.strip()]
        
        if not search_words:
            await interaction.followup.send("Please provide at least one word to search for.", ephemeral=True)
            return
            
        # Validate limit
        if limit <= 0:
            limit = None  # Will retrieve all possible messages
            
        # Create progress message
        progress = await interaction.followup.send(f"Scanning messages in {channel.mention} for: `{', '.join(search_words)}`...", ephemeral=True)
        
        # Keep track of deleted messages
        deleted_count = 0
        scanned_count = 0
        matched_messages = []
        last_report_time = datetime.datetime.now()
        
        # Create a log entry
        log_entry = f"Deleted messages containing: {', '.join(search_words)}\n"
        log_entry += f"Channel: {channel.name} ({channel.id})\n"
        if user:
            log_entry += f"User filter: {user.display_name} ({user.id})\n"
        log_entry += "---\n"
        
        # Iterate through messages in the channel
        async for message in channel.history(limit=limit):
            scanned_count += 1
            
            # Check if message is from the specified user (if any)
            if user and message.author != user:
                continue
                
            # Check message content for the words
            content = message.content.lower()
            if any(word in content for word in search_words):
                # Keep track of deleted message content for logs
                msg_info = f"[{message.author.display_name}]: {message.content[:100]}"
                if len(message.content) > 100:
                    msg_info += "..."
                matched_messages.append(msg_info)
                log_entry += msg_info + "\n"
                
                # Delete the message
                await message.delete()
                deleted_count += 1
                
                # Update progress every 5 messages or 3 seconds
                now = datetime.datetime.now()
                if deleted_count % 5 == 0 or (now - last_report_time).total_seconds() > 3:
                    await progress.edit(content=f"Scanning... Found {deleted_count} messages containing target words (scanned {scanned_count} so far).")
                    last_report_time = now
        
        # Create final report
        report = f"✅ Scan complete! Deleted {deleted_count} messages containing target words.\n"
        report += f"Scanned a total of {scanned_count} messages in {channel.mention}.\n"
        
        # Send to mod-logs if available
        try:
            log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
            if log_channel:
                # Create log embed
                log_embed = discord.Embed(
                    title=f"Channel Purge: Word Filter",
                    description=f"{interaction.user.mention} purged {deleted_count} messages containing target words.",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(name="Channel", value=channel.mention, inline=True)
                log_embed.add_field(name="Target Words", value=f"`{', '.join(search_words)}`", inline=True)
                log_embed.add_field(name="User Filter", value=user.mention if user else "None", inline=True)
                log_embed.add_field(name="Messages Scanned", value=str(scanned_count), inline=True)
                log_embed.add_field(name="Messages Deleted", value=str(deleted_count), inline=True)
                
                # Add sample of deleted messages if not too many
                if deleted_count > 0 and deleted_count <= 15 and not silent:
                    samples = "\n".join(matched_messages[:15])
                    if len(samples) > 1024:
                        samples = samples[:1020] + "..."
                    log_embed.add_field(name="Sample Deleted Messages", value=samples, inline=False)
                
                await log_channel.send(embed=log_embed)
        except Exception as e:
            print(f"Error sending purge log: {e}")
        
        # Send final report to user
        await progress.edit(content=report)
        
    except discord.Forbidden:
        await interaction.followup.send("I don't have permission to delete messages in that channel.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="massban", description="Ban multiple users at once by ID")
@app_commands.describe(user_ids="User IDs separated by spaces", reason="Reason for the ban", delete_days="Number of days of messages to delete")
@app_commands.default_permissions(administrator=True)
async def massban(interaction: discord.Interaction, user_ids: str, reason: str = "Mass ban", delete_days: int = 0):
    try:
        await interaction.response.defer(ephemeral=True)
        
        # Parse user IDs
        ids = [id.strip() for id in user_ids.split() if id.strip().isdigit()]
        
        if not ids:
            await interaction.followup.send("No valid user IDs provided. Please provide space-separated user IDs.", ephemeral=True)
            return
        
        # Track results
        success = []
        failed = []
        
        # Process each ID
        for user_id in ids:
            try:
                # Try to convert to int
                user_id = int(user_id)
                
                # Check if user is in guild
                member = interaction.guild.get_member(user_id)
                
                # Ban the user
                await interaction.guild.ban(discord.Object(id=user_id), reason=f"Mass ban: {reason}", delete_message_days=delete_days)
                success.append(str(user_id))
            except Exception as e:
                failed.append(f"{user_id} ({str(e)})")
        
        # Send results
        result = f"✅ Successfully banned {len(success)} users:\n"
        if success:
            result += ", ".join(success) + "\n\n"
        
        if failed:
            result += f"❌ Failed to ban {len(failed)} users:\n"
            result += ", ".join(failed)
        
        # Send log to mod-logs channel
        log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
        if log_channel:
            log_embed = discord.Embed(
                title="Mass Ban Executed",
                description=f"{len(success)} users were banned by {interaction.user.mention}",
                color=discord.Color.red()
            )
            log_embed.add_field(name="Reason", value=reason)
            log_embed.add_field(name="Banned IDs", value=", ".join(success) if success else "None", inline=False)
            await log_channel.send(embed=log_embed)
        
        await interaction.followup.send(result, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="masskick", description="Kick multiple users at once")
@app_commands.describe(members="The members to kick (space separated mentions)", reason="Reason for the kick")
@app_commands.default_permissions(administrator=True)
async def masskick(interaction: discord.Interaction, members: str, reason: str = "Mass kick"):
    try:
        await interaction.response.defer(ephemeral=True)
        
        # Get member mentions
        mention_pattern = r'<@!?(\d+)>'
        matches = re.findall(mention_pattern, members)
        
        if not matches:
            await interaction.followup.send("No valid member mentions provided. Please mention the users to kick.", ephemeral=True)
            return
        
        # Track results
        success = []
        failed = []
        
        # Process each member
        for user_id in matches:
            try:
                # Try to get member
                member = interaction.guild.get_member(int(user_id))
                if not member:
                    failed.append(f"<@{user_id}> (Not found)")
                    continue
                
                # Check permission hierarchy
                if member.top_role >= interaction.user.top_role:
                    failed.append(f"{member.mention} (Higher role)")
                    continue
                
                # Kick the member
                await member.kick(reason=f"Mass kick: {reason}")
                success.append(member.mention)
            except Exception as e:
                failed.append(f"<@{user_id}> ({str(e)})")
        
        # Send results
        result = f"✅ Successfully kicked {len(success)} members:\n"
        if success:
            result += " ".join(success) + "\n\n"
        
        if failed:
            result += f"❌ Failed to kick {len(failed)} members:\n"
            result += " ".join(failed)
        
        await interaction.followup.send(result, ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

# Reaction roles commands
@bot.tree.command(name="reactrole", description="Create a reaction role message")
@app_commands.describe(
    channel="The channel to send the message in",
    title="The title of the reaction role message",
    description="The description of the reaction role message"
)
@app_commands.default_permissions(administrator=True)
async def reactrole(interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str):
    try:
        # Create the embed
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text="React to get roles | Bot by YOUR_NAME")
        
        # Send the message
        message = await channel.send(embed=embed)
        
        # Initialize entry in reaction_roles_data
        message_id = str(message.id)
        reaction_roles_data[message_id] = {}
        save_reaction_roles(reaction_roles_data)
        
        await interaction.response.send_message(f"Reaction role message created in {channel.mention}. Use `/addrole` to add roles to it.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="addrole", description="Add a role to a reaction role message")
@app_commands.describe(
    message_id="The ID of the reaction role message",
    role="The role to add",
    emoji="The emoji to use for this role"
)
@app_commands.default_permissions(administrator=True)
async def addrole(interaction: discord.Interaction, message_id: str, role: discord.Role, emoji: str):
    try:
        # Check if the message exists in our data
        if message_id not in reaction_roles_data:
            reaction_roles_data[message_id] = {}
        
        # Add the role
        reaction_roles_data[message_id][emoji] = str(role.id)
        save_reaction_roles(reaction_roles_data)
        
        # Try to find the message and add the reaction
        try:
            for channel in interaction.guild.text_channels:
                try:
                    message = await channel.fetch_message(int(message_id))
                    await message.add_reaction(emoji)
                    break
                except:
                    continue
        except:
            await interaction.response.send_message(f"Role added but couldn't find the message to add the reaction. Please add {emoji} manually.", ephemeral=True)
            return
        
        await interaction.response.send_message(f"Added {role.mention} with {emoji} to the reaction role message.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Message logging in mod-logs channel
@bot.event
async def on_message_delete(message):
    # Skip bot messages and DMs
    if message.author.bot or not message.guild:
        return
    
    # Find the mod-logs channel
    log_channel = discord.utils.get(message.guild.text_channels, name="mod-logs")
    if not log_channel:
        return
    
    # Create embed
    embed = discord.Embed(
        title="Message Deleted",
        description=f"**Author:** {message.author.mention} ({message.author.id})\n**Channel:** {message.channel.mention}",
        color=discord.Color.red(),
        timestamp=discord.utils.utcnow()
    )
    
    # Add message content if any
    if message.content:
        if len(message.content) > 1024:
            embed.add_field(name="Content", value=f"{message.content[:1021]}...", inline=False)
        else:
            embed.add_field(name="Content", value=message.content, inline=False)
    
    # Add attachment info if any
    if message.attachments:
        files = "\n".join([f"{a.filename} - {a.url}" for a in message.attachments])
        if len(files) > 1024:
            files = files[:1021] + "..."
        embed.add_field(name="Attachments", value=files, inline=False)
    
    # Send log
    await log_channel.send(embed=embed)

# Custom commands management
@bot.tree.command(name="cmdadd", description="Add a custom command")
@app_commands.describe(
    command="The command name (without prefix)",
    response="The response text",
    is_embed="Whether to format the response as an embed",
    title="Title for the embed (if is_embed is True)",
    image="Image URL for the embed (if is_embed is True)",
    footer="Footer text for the embed (if is_embed is True)"
)
@app_commands.default_permissions(administrator=True)
async def cmdadd(interaction: discord.Interaction, command: str, response: str, is_embed: bool = False, 
                 title: str = None, image: str = None, footer: str = None):
    try:
        # Normalize command name
        command = command.lower().strip()
        
        # Check if command already exists
        guild_id = str(interaction.guild.id)
        if guild_id not in custom_commands_data:
            custom_commands_data[guild_id] = {}
            
        # Create command data
        cmd_data = {
            "response": response,
            "added_by": str(interaction.user.id),
            "added_at": str(datetime.datetime.utcnow()),
            "is_embed": is_embed
        }
        
        # Add optional embed data if this is an embed command
        if is_embed:
            if title:
                cmd_data["title"] = title
            if image:
                cmd_data["image"] = image
            if footer:
                cmd_data["footer"] = footer
                
        # Save the command
        custom_commands_data[guild_id][command] = cmd_data
        save_custom_commands(custom_commands_data)
        
        await interaction.response.send_message(f"Command `{PREFIX}{command}` has been added.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="cmdremove", description="Remove a custom command")
@app_commands.describe(command="The command name to remove (without prefix)")
@app_commands.default_permissions(administrator=True)
async def cmdremove(interaction: discord.Interaction, command: str):
    try:
        # Normalize command name
        command = command.lower().strip()
        
        # Check if command exists
        guild_id = str(interaction.guild.id)
        if guild_id not in custom_commands_data or command not in custom_commands_data[guild_id]:
            await interaction.response.send_message(f"Command `{PREFIX}{command}` does not exist.", ephemeral=True)
            return
            
        # Remove the command
        del custom_commands_data[guild_id][command]
        save_custom_commands(custom_commands_data)
        
        await interaction.response.send_message(f"Command `{PREFIX}{command}` has been removed.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="cmdlist", description="List all custom commands")
async def cmdlist(interaction: discord.Interaction):
    try:
        guild_id = str(interaction.guild.id)
        if guild_id not in custom_commands_data or not custom_commands_data[guild_id]:
            await interaction.response.send_message("No custom commands have been set up yet.", ephemeral=True)
            return
            
        # Create embed
        embed = discord.Embed(
            title="Custom Commands",
            description=f"Use `{PREFIX}commandname` to trigger a command",
            color=discord.Color.blue()
        )
        
        # Sort commands
        commands = sorted(custom_commands_data[guild_id].keys())
        
        # Add commands to embed
        command_list = ""
        for cmd in commands:
            is_embed = custom_commands_data[guild_id][cmd].get("is_embed", False)
            command_list += f"`{PREFIX}{cmd}`" + (" (Embed)" if is_embed else "") + "\n"
            
        embed.add_field(name=f"Available Commands [{len(commands)}]", value=command_list if command_list else "None")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Scheduled tasks commands
@bot.tree.command(name="remindme", description="Schedule a reminder")
@app_commands.describe(
    message="The reminder message",
    hours="Hours from now",
    minutes="Minutes from now"
)
async def remindme(interaction: discord.Interaction, message: str, hours: int = 0, minutes: int = 0):
    try:
        # Check valid time
        if hours <= 0 and minutes <= 0:
            await interaction.response.send_message("Please specify a valid time in the future.", ephemeral=True)
            return
            
        # Calculate reminder time
        reminder_time = datetime.datetime.utcnow() + datetime.timedelta(hours=hours, minutes=minutes)
        
        # Create task
        task = {
            "action": "reminder",
            "guild_id": str(interaction.guild.id),
            "channel_id": str(interaction.channel.id),
            "user_id": str(interaction.user.id),
            "message": message,
            "time": reminder_time.isoformat()
        }
        
        # Add to tasks
        scheduled_tasks_data.append(task)
        save_scheduled_tasks(scheduled_tasks_data)
        
        # Format time for display
        time_str = ""
        if hours > 0:
            time_str += f"{hours} hour{'s' if hours != 1 else ''} "
        if minutes > 0:
            time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"
            
        await interaction.response.send_message(f"✅ Reminder set for {time_str} from now.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="tempban", description="Temporarily ban a user")
@app_commands.describe(
    member="The member to temporarily ban",
    days="Days until automatic unban",
    hours="Hours until automatic unban",
    reason="Reason for the temporary ban",
    delete_days="Number of days of messages to delete"
)
@app_commands.default_permissions(ban_members=True)
async def tempban(interaction: discord.Interaction, member: discord.Member, days: int = 0, hours: int = 0, 
                  reason: str = "No reason provided", delete_days: int = 0):
    try:
        # Check permission hierarchy
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("You cannot ban someone with a higher or equal role!", ephemeral=True)
            return
            
        # Check valid time
        if days <= 0 and hours <= 0:
            await interaction.response.send_message("Please specify a valid time for the temporary ban.", ephemeral=True)
            return
            
        # Calculate unban time
        unban_time = datetime.datetime.utcnow() + datetime.timedelta(days=days, hours=hours)
        
        # Ban the user
        full_reason = f"Temporary ban ({days}d {hours}h): {reason}"
        await member.ban(reason=full_reason, delete_message_days=delete_days)
        
        # Create unban task
        task = {
            "action": "unban",
            "guild_id": str(interaction.guild.id),
            "user_id": str(member.id),
            "reason": f"Temporary ban expired: {reason}",
            "time": unban_time.isoformat()
        }
        
        # Add to tasks
        scheduled_tasks_data.append(task)
        save_scheduled_tasks(scheduled_tasks_data)
        
        # Format time for display
        time_str = ""
        if days > 0:
            time_str += f"{days} day{'s' if days != 1 else ''} "
        if hours > 0:
            time_str += f"{hours} hour{'s' if hours != 1 else ''}"
            
        await interaction.response.send_message(f"🔨 {member.mention} has been temporarily banned for {time_str}. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Temporary voice channel commands
@bot.tree.command(name="setupvoice", description="Set up temporary voice channels")
@app_commands.describe(channel="The voice channel that users will join to create their own channel")
@app_commands.default_permissions(administrator=True)
async def setupvoice(interaction: discord.Interaction, channel: discord.VoiceChannel):
    try:
        guild_id = str(interaction.guild.id)
        
        # Initialize guild in temp voice data if not exists
        if guild_id not in temp_voice_data:
            temp_voice_data[guild_id] = {}
            
        # Set create channel
        temp_voice_data[guild_id]["create_channel"] = str(channel.id)
        
        # Initialize temp channels dict if not exists
        if "temp_channels" not in temp_voice_data[guild_id]:
            temp_voice_data[guild_id]["temp_channels"] = {}
            
        save_temp_voice(temp_voice_data)
        
        await interaction.response.send_message(f"✅ Temporary voice channels have been set up with {channel.name} as the creator channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="voicename", description="Rename your temporary voice channel")
@app_commands.describe(name="The new name for your voice channel")
async def voicename(interaction: discord.Interaction, name: str):
    try:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
            return
            
        voice_channel = interaction.user.voice.channel
        guild_id = str(interaction.guild.id)
        channel_id = str(voice_channel.id)
        
        # Check if this is a temp channel owned by the user
        if guild_id in temp_voice_data and "temp_channels" in temp_voice_data[guild_id] and \
           channel_id in temp_voice_data[guild_id]["temp_channels"] and \
           temp_voice_data[guild_id]["temp_channels"][channel_id]["owner"] == str(interaction.user.id):
            # Rename the channel
            await voice_channel.edit(name=name)
            await interaction.response.send_message(f"Voice channel renamed to {name}.", ephemeral=True)
        else:
            await interaction.response.send_message("You can only rename temporary voice channels that you own.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="voicelimit", description="Set user limit for your temporary voice channel")
@app_commands.describe(limit="The user limit (0 for no limit)")
async def voicelimit(interaction: discord.Interaction, limit: int):
    try:
        if limit < 0 or limit > 99:
            await interaction.response.send_message("User limit must be between 0 and 99.", ephemeral=True)
            return
            
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
            return
            
        voice_channel = interaction.user.voice.channel
        guild_id = str(interaction.guild.id)
        channel_id = str(voice_channel.id)
        
        # Check if this is a temp channel owned by the user
        if guild_id in temp_voice_data and "temp_channels" in temp_voice_data[guild_id] and \
           channel_id in temp_voice_data[guild_id]["temp_channels"] and \
           temp_voice_data[guild_id]["temp_channels"][channel_id]["owner"] == str(interaction.user.id):
            # Set the limit
            await voice_channel.edit(user_limit=limit)
            
            if limit == 0:
                await interaction.response.send_message("Voice channel user limit removed.", ephemeral=True)
            else:
                await interaction.response.send_message(f"Voice channel user limit set to {limit}.", ephemeral=True)
        else:
            await interaction.response.send_message("You can only modify temporary voice channels that you own.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="voicelock", description="Lock your temporary voice channel")
async def voicelock(interaction: discord.Interaction):
    try:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
            return
            
        voice_channel = interaction.user.voice.channel
        guild_id = str(interaction.guild.id)
        channel_id = str(voice_channel.id)
        
        # Check if this is a temp channel owned by the user
        if guild_id in temp_voice_data and "temp_channels" in temp_voice_data[guild_id] and \
           channel_id in temp_voice_data[guild_id]["temp_channels"] and \
           temp_voice_data[guild_id]["temp_channels"][channel_id]["owner"] == str(interaction.user.id):
            # Lock the channel
            await voice_channel.set_permissions(interaction.guild.default_role, connect=False)
            await interaction.response.send_message("Voice channel locked. Only you can move users in now.", ephemeral=True)
        else:
            await interaction.response.send_message("You can only lock temporary voice channels that you own.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

@bot.tree.command(name="voiceunlock", description="Unlock your temporary voice channel")
async def voiceunlock(interaction: discord.Interaction):
    try:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
            return
            
        voice_channel = interaction.user.voice.channel
        guild_id = str(interaction.guild.id)
        channel_id = str(voice_channel.id)
        
        # Check if this is a temp channel owned by the user
        if guild_id in temp_voice_data and "temp_channels" in temp_voice_data[guild_id] and \
           channel_id in temp_voice_data[guild_id]["temp_channels"] and \
           temp_voice_data[guild_id]["temp_channels"][channel_id]["owner"] == str(interaction.user.id):
            # Unlock the channel
            await voice_channel.set_permissions(interaction.guild.default_role, connect=None)
            await interaction.response.send_message("Voice channel unlocked. Anyone can join now.", ephemeral=True)
        else:
            await interaction.response.send_message("You can only unlock temporary voice channels that you own.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    # Check if token is available
    if not TOKEN:
        print("Error: No Discord token found in .env file")
        exit(1)
    
    # Attach attributes to bot
    bot.antiraid_mode = False
    bot.server_lockdown = False
        
    bot.run(TOKEN)
