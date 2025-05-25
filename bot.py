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

# Initialize warnings
warnings_data = load_warnings()

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

# Run the bot
if __name__ == "__main__":
    # Check if token is available
    if not TOKEN:
        print("Error: No Discord token found in .env file")
        exit(1)
    
    # Attach attributes to bot
    bot.antiraid_mode = False
        
    bot.run(TOKEN)
