import discord
import datetime
import asyncio
import re
import random
from config import *
from data_manager import *

def setup_events(bot):
    """Setup all Discord event handlers"""
    
    @bot.event
    async def on_ready():
        print(f'{bot.user.name} has connected to Discord!')
        print(f'Bot ID: {bot.user.id}')
        print(f'Bot is in {len(bot.guilds)} guild(s)')
        
        # Setup command modules
        print("🔧 Setting up command modules...")
        try:
            from commands.moderation import setup_moderation_commands
            from commands.utility import setup_utility_commands  
            from commands.mass_moderation import setup_mass_moderation_commands
            from commands.quarantine import setup_quarantine_commands
            
            await setup_moderation_commands(bot)
            await setup_utility_commands(bot)
            await setup_mass_moderation_commands(bot)
            await setup_quarantine_commands(bot)
            
            print("✅ All command modules loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading command modules: {e}")
        
        # Set initial presence
        await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="for spammers | !help"))
        
        # Setup recurring scheduled tasks
        # Start the background tasks
        bot.loop.create_task(scheduled_backup())
        bot.loop.create_task(check_scheduled_tasks())
        
        if not check_quarantine_expirations.is_running():
            check_quarantine_expirations.start()
        
        # Create backup on startup
        await create_backup()
        
        # DIAGNOSTIC: Print all commands registered in the command tree
        print("\nDIAGNOSTIC - Commands registered in tree:")
        for cmd in bot.tree.get_commands():
            print(f"Global command: {cmd.name} - {cmd.description}")
        
        # Sync commands globally - simpler and more reliable approach
        print("\nSyncing commands globally...")
        try:
            # First sync globally
            synced = await bot.tree.sync()
            print(f"Successfully synced {len(synced)} commands globally")
            print(f"Global commands: {[cmd.name for cmd in synced]}")
            
            # Check if important commands are in the list
            quarantine_cmds = [cmd for cmd in synced if cmd.name in ['quarantine', 'unquarantine', 'quarantinelist', 'freshaccounts']]
            print(f"Important commands found: {[cmd.name for cmd in quarantine_cmds]}")
        except Exception as e:
            print(f"Failed to sync commands globally: {e}")
        print("Command sync complete!")
        
        print("\nIMPORTANT: If slash commands aren't appearing in Discord:")
        print("1. Make sure the bot has 'applications.commands' scope when added to servers")
        print("2. It can take up to an hour for commands to appear in large servers")
        print("3. Try removing and re-adding the bot to the server if needed")
        
        print("\n🎉 Bot is fully ready and operational!")

    @bot.event
    async def on_message(message):
        # Skip if message is from bot
        if message.author.bot:
            return
        
        # Skip DMs
        if not message.guild:
            return
            
        # Always process commands AFTER checking quarantine status
        # This ensures we mirror messages before processing them as commands
        
        # Check if message is from a quarantined user
        guild_id = str(message.guild.id)
        user_id = str(message.author.id)
        
        # Mirror messages from quarantined users to jail-cam channel if public viewing is enabled
        if guild_id in quarantine_data and user_id in quarantine_data[guild_id]:
            # Check if public viewing is enabled for this user
            user_data = quarantine_data[guild_id][user_id]
            
            # Only mirror if public_view is True
            if user_data.get("public_view", False):
                # Get the jail-cam channel ID from user data or server settings
                jail_cam_channel_id = user_data.get("jail_cam_channel_id")
                
                # If no specific channel is set for this user, check server settings
                if not jail_cam_channel_id and "server_settings" in quarantine_data[guild_id]:
                    jail_cam_channel_id = quarantine_data[guild_id]["server_settings"].get("jail_cam_channel_id")
                
                # If still no channel, try to find the default one
                if not jail_cam_channel_id:
                    jail_cam_channel = discord.utils.get(message.guild.text_channels, name=JAIL_CAM_CHANNEL_NAME)
                    if jail_cam_channel:
                        jail_cam_channel_id = str(jail_cam_channel.id)
                
                # Get the actual channel object
                jail_cam_channel = None
                if jail_cam_channel_id:
                    jail_cam_channel = message.guild.get_channel(int(jail_cam_channel_id))
                
                if jail_cam_channel:
                    # Format the message in a simple text format
                    content = message.content if message.content else "(No message content)"
                    
                    # Add info about attachments if any
                    attachments_text = ""
                    if message.attachments:
                        attachment_list = ", ".join([attachment.filename for attachment in message.attachments])
                        attachments_text = f" [Attached: {attachment_list}]"
                    
                    # Create the simple mirror message
                    mirror_message = f"**{message.author.display_name}** in #{message.channel.name} said: {content}{attachments_text}"
                    
                    # Send to jail-cam with better error handling
                    try:
                        await jail_cam_channel.send(mirror_message)
                        print(f"Successfully mirrored message from {message.author.name} to jail-cam")
                    except Exception as e:
                        print(f"Failed to mirror message to jail-cam: {e}")
                        # Try to log more details about why mirroring failed
                        print(f"jail-cam channel: {jail_cam_channel}, public_view: {user_data.get('public_view')}, user: {message.author.name}")
                        
                    # Debug log
                    print(f"Quarantined user {message.author.name} said: {content} in #{message.channel.name}") 

        # NEW: Check if message is FROM jail-cam channel to quarantined users (reverse mirroring)
        elif message.channel.name == JAIL_CAM_CHANNEL_NAME:
            # This is a message sent in jail-cam by a normal user, forward it to quarantined users
            # Only process if there are actually quarantined users in this guild
            if guild_id in quarantine_data and quarantine_data[guild_id]:
                # Check if this channel is configured as the jail-cam channel
                is_jail_cam_channel = False
                
                # Check if this is the server-configured jail-cam channel
                if "server_settings" in quarantine_data[guild_id]:
                    configured_jail_cam_id = quarantine_data[guild_id]["server_settings"].get("jail_cam_channel_id")
                    if configured_jail_cam_id and message.channel.id == int(configured_jail_cam_id):
                        is_jail_cam_channel = True
                
                # If not configured channel, check if it's the default jail-cam channel
                if not is_jail_cam_channel and message.channel.name == JAIL_CAM_CHANNEL_NAME:
                    is_jail_cam_channel = True
                
                if is_jail_cam_channel:
                    content = message.content if message.content else "(No message content)"
                    
                    # Add info about attachments if any
                    attachments_text = ""
                    if message.attachments:
                        attachment_list = ", ".join([attachment.filename for attachment in message.attachments])
                        attachments_text = f" [Attached: {attachment_list}]"
                    
                    # Create message to send to quarantined users
                    jail_cam_message = f"📺 **{message.author.display_name}** from jail-cam says: {content}{attachments_text}"
                    
                    # Find all quarantined users in this guild and send message to their quarantine channels
                    quarantined_users = quarantine_data[guild_id]
                    messages_sent = 0
                    
                    for user_id, user_data in quarantined_users.items():
                        if user_data.get("public_view", False):  # Only if public viewing is enabled
                            quarantine_channel_id = user_data.get("channel_id")
                            if quarantine_channel_id:
                                quarantine_channel = message.guild.get_channel(int(quarantine_channel_id))
                                if quarantine_channel:
                                    try:
                                        await quarantine_channel.send(jail_cam_message)
                                        messages_sent += 1
                                    except Exception as e:
                                        print(f"Failed to forward jail-cam message to quarantine channel: {e}")
                    
                    if messages_sent > 0:
                        print(f"Successfully forwarded jail-cam message from {message.author.name} to {messages_sent} quarantine channel(s)")
                        # Add a reaction to show the message was forwarded
                        try:
                            await message.add_reaction("📨")  # Envelope emoji to show it was delivered
                        except:
                            pass
                    else:
                        print(f"No active quarantined users to forward jail-cam message to")
            # If no quarantined users, silently ignore the message (don't forward anything)

        # Process commands AFTER checking quarantine status
        await bot.process_commands(message)
        
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
                "timestamp": str(datetime.datetime.now(UTC)),
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

        # NEW: Prison Break Game Challenge Handling
        # Check if user is in a quarantine room and participating in a prison break game
        if guild_id in quarantine_data and user_id in quarantine_data[guild_id]:
            if guild_id in prison_break_data:
                for game_id, game_data in prison_break_data[guild_id].items():
                    if game_data.get("active", False) and int(user_id) in game_data["players"]:
                        current_challenge = game_data.get("current_challenge")
                        if current_challenge:
                            # Import the handler function from quarantine module
                            from commands.quarantine import handle_prison_break_attempt
                            await handle_prison_break_attempt(message, guild_id, game_id, game_data, current_challenge)
                            break

    @bot.event
    async def on_member_join(member):
        # Skip if bot
        if member.bot:
            return
            
        # Get guild and member IDs
        guild_id = str(member.guild.id)
        user_id = str(member.id)
        
        # Check account age
        join_time = datetime.datetime.now(UTC)
        account_age_days = (join_time - member.created_at).days
        
        # Check for fresh account detection settings
        fresh_account_detected = False
        if guild_id in fresh_account_settings and fresh_account_settings[guild_id].get("enabled", False):
            settings = fresh_account_settings[guild_id]
            age_threshold = settings.get("age_threshold", 7)  # Default 7 days
            action = settings.get("action", "log")  # Default action is just to log
            
            # Check if account is fresh
            if account_age_days < age_threshold:
                fresh_account_detected = True
                
                # Take configured action
                if action == "kick":
                    try:
                        await member.kick(reason=f"Fresh account detection: Account age {account_age_days} days")
                        
                        # Log to mod-logs
                        log_channel = discord.utils.get(member.guild.text_channels, name="mod-logs")
                        if log_channel:
                            embed = discord.Embed(
                                title="🔨 Fresh Account Kicked",
                                description=f"A fresh Discord account was kicked.",
                                color=discord.Color.red(),
                                timestamp=join_time
                            )
                            embed.add_field(name="User", value=f"{member} ({member.id})", inline=True)
                            embed.add_field(name="Account Age", value=f"{account_age_days} days", inline=True)
                            embed.add_field(name="Threshold", value=f"{age_threshold} days", inline=True)
                            embed.set_thumbnail(url=member.display_avatar.url)
                            await log_channel.send(embed=embed)
                            
                        # Skip the rest of the function since the user is kicked
                        return
                            
                    except Exception as e:
                        print(f"Error kicking fresh account: {e}")
                
                elif action == "quarantine":
                    try:
                        # Get quarantine channel
                        quarantine_channel_id = settings.get("quarantine_channel_id")
                        if quarantine_channel_id:
                            quarantine_channel = member.guild.get_channel(int(quarantine_channel_id))
                            if quarantine_channel:
                                # Set permissions for all channels to deny access
                                for channel in member.guild.channels:
                                    if channel.id != int(quarantine_channel_id) and isinstance(channel, discord.TextChannel):
                                        try:
                                            await channel.set_permissions(member, read_messages=False, send_messages=False,
                                                                        reason="Fresh account quarantine")
                                        except:
                                            pass
                                
                                # Allow access to quarantine channel
                                await quarantine_channel.set_permissions(member, read_messages=True, send_messages=True,
                                                                      reason="Fresh account quarantine")
                                
                                # Send message to quarantine channel
                                quarantine_message = settings.get("quarantine_message", "Your account is new, so you've been placed in quarantine. Please wait for staff to verify your account.")
                                await quarantine_channel.send(
                                    f"{member.mention} {quarantine_message}\n\n" +
                                    f"**Account Age:** {account_age_days} days (Threshold: {age_threshold} days)"
                                )
                    except Exception as e:
                        print(f"Error quarantining fresh account: {e}")
        
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
                        "created_at": str(datetime.datetime.now(UTC))
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

    @bot.event  
    async def on_reaction_add(reaction, user):
        """Handle emoji reactions for prison break spectator interaction"""
        # Skip bot reactions
        if user.bot:
            return
            
        # Only handle reactions in jail-cam channel during prison break games
        if not (hasattr(reaction.message.channel, 'name') and reaction.message.channel.name == JAIL_CAM_CHANNEL_NAME):
            return
            
        guild_id = str(reaction.message.guild.id)
        user_id = str(user.id)
        
        # Check if there are any active prison break games
        if guild_id not in prison_break_data:
            return
            
        active_games = []
        for game_id, game_data in prison_break_data[guild_id].items():
            if game_data.get("active", False):
                active_games.append((game_id, game_data))
                
        if not active_games:
            return
            
        # Check if user is quarantined (quarantined users can't help from outside)
        is_quarantined = guild_id in quarantine_data and user_id in quarantine_data[guild_id]
        
        if is_quarantined:
            # Remove the reaction and notify
            try:
                await reaction.remove(user)
            except:
                pass
            return
            
        emoji_str = str(reaction.emoji)
        
        # Handle help reactions
        if emoji_str in HELP_EMOJIS:
            help_messages = [
                f"🤝 {user.display_name} threw a rope ladder to the prisoners!",
                f"💡 {user.display_name} whispered helpful hints through the bars!",
                f"🔦 {user.display_name} provided a flashlight for better visibility!",
                f"🗝️ {user.display_name} slipped lock picking tools under the door!",
                f"⏰ {user.display_name} created a distraction, buying more time!",
                f"📍 {user.display_name} pointed out the guard patrol routes!",
                f"🎯 {user.display_name} gave tactical advice from outside!",
                f"✨ {user.display_name} used magic to aid the escape!",
                f"🆘 {user.display_name} called in backup assistance!"
            ]
            
            help_message = random.choice(help_messages)
            
            # Add help vote to active games and provide hints
            for game_id, game_data in active_games:
                game_data["spectator_votes"]["help"] += 1
                
                # Provide helpful hint based on current stage
                stage = game_data.get("stage", 1)
                current_challenge = game_data.get("current_challenge")
                hint = ""
                
                if stage == 1 and current_challenge:
                    hint = f"\n💡 **Spectator Hint:** Try different 4-digit combinations like '1-2-3-4'!"
                elif stage == 2 and current_challenge:
                    hint = f"\n💡 **Spectator Hint:** Try directions like 'north', 'south', 'east', 'west'!"
                elif stage == 3 and current_challenge:
                    hint = f"\n💡 **Spectator Hint:** Look for hiding spots like 'behind tree' or 'in shadows'!"
                elif stage == 4 and current_challenge:
                    hint = f"\n💡 **Spectator Hint:** Work together and say the secret escape code word!"
            
            save_prison_break_data(prison_break_data)
            
            # Send help message to jail-cam
            await reaction.message.channel.send(f"🆘 **PRISONER ASSISTANCE!**\n{help_message}{hint}")
            
        # Handle sabotage reactions  
        elif emoji_str in SABOTAGE_EMOJIS:
            sabotage_messages = [
                f"😈 {user.display_name} alerted the guards to suspicious activity!",
                f"🚨 {user.display_name} triggered the alarm system!",
                f"🔒 {user.display_name} jammed the lock mechanism!",
                f"💥 {user.display_name} caused a distraction that brought more guards!",
                f"🌩️ {user.display_name} cut the power, making everything harder!",
                f"📢 {user.display_name} made noise to attract guard attention!",
                f"⛔ {user.display_name} blocked the escape routes!",
                f"💀 {user.display_name} summoned more security!",
                f"🔥 {user.display_name} started chaos to hinder the escape!"
            ]
            
            sabotage_message = random.choice(sabotage_messages)
            
            # Add sabotage vote to active games
            for game_id, game_data in active_games:
                game_data["spectator_votes"]["sabotage"] += 1
                
            save_prison_break_data(prison_break_data)
            
            # Send sabotage message to jail-cam
            await reaction.message.channel.send(f"😈 **SABOTAGE DETECTED!**\n{sabotage_message}\n🔥 The escape just got harder!")


# Scheduled tasks functions
async def scheduled_backup():
    while True:
        try:
            # Create backup every 12 hours
            await asyncio.sleep(12 * 60 * 60)  # 12 hours
            backup_path = await create_backup()
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
        except Exception as e:
            print(f"Error in scheduled backup: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying if there's an error

async def check_scheduled_tasks():
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            current_time = datetime.datetime.now(UTC)
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
                
        except Exception as e:
            print(f"Error in scheduled tasks checker: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying if there's an error

# Import the quarantine task
from discord.ext import tasks

@tasks.loop(minutes=1)
async def check_quarantine_expirations():
    try:
        current_time = datetime.datetime.now(UTC)
        guilds_to_check = list(quarantine_data.keys())
        
        for guild_id in guilds_to_check:
            guild = bot.get_guild(int(guild_id))
            if not guild:
                continue
                
            users_to_unquarantine = []
            
            # Find users whose quarantine has expired (filter out server_settings)
            for user_id, data in quarantine_data[guild_id].items():
                # Skip server settings - only process actual user quarantine records
                if user_id == "server_settings":
                    continue
                    
                if "end_time" in data:
                    try:
                        end_time = datetime.datetime.fromisoformat(data["end_time"].replace('Z', '+00:00'))
                        if current_time >= end_time:
                            users_to_unquarantine.append(user_id)
                            print(f"Quarantine expired for user {user_id} in guild {guild.name}")
                    except Exception as e:
                        print(f"Error parsing end time for user {user_id}: {e}")
            
            # Unquarantine expired users
            for user_id in users_to_unquarantine:
                try:
                    # Get the user and their data
                    member = await guild.fetch_member(int(user_id))
                    user_data = quarantine_data[guild_id][user_id]
                    saved_roles = user_data.get("roles", [])
                    
                    print(f"Auto-unquarantining {member.display_name} in {guild.name}")
                    
                    # Reset channel permissions
                    for channel in guild.channels:
                        try:
                            await channel.set_permissions(member, overwrite=None, reason="Auto-released from timed quarantine")
                        except:
                            pass
                    
                    # Restore roles
                    for role_id in saved_roles:
                        role = guild.get_role(int(role_id))
                        if role:
                            try:
                                await member.add_roles(role, reason="Auto-released from timed quarantine")
                            except:
                                pass
                    
                    # Remove from quarantine data
                    del quarantine_data[guild_id][user_id]
                    save_quarantine_data(quarantine_data)
                    
                    # DM the user
                    try:
                        await member.send(f"You have been automatically released from quarantine in **{guild.name}**. Your access has been restored.")
                    except:
                        pass
                    
                    # Log to mod-logs
                    log_channel = discord.utils.get(guild.text_channels, name="mod-logs")
                    if log_channel:
                        embed = discord.Embed(
                            title="🔓 User Auto-Released from Quarantine",
                            description=f"<@{user_id}> has been automatically released from quarantine (timer expired).",
                            color=discord.Color.green(),
                            timestamp=current_time
                        )
                        embed.add_field(name="User", value=f"<@{user_id}> ({user_id})", inline=True)
                        embed.set_footer(text="Automatic timed release")
                        await log_channel.send(embed=embed)
                    
                    # Also announce it in the jail-cam channel
                    jail_cam_channel = discord.utils.get(guild.text_channels, name=JAIL_CAM_CHANNEL_NAME)
                    if jail_cam_channel:
                        freedom_messages = [
                            f"🔓 **FREEDOM!** {member.mention} has served their time and been released!",
                            f"🕊️ {member.mention} has been set free! Their sentence is complete.",
                            f"⏱️ Time's up! {member.mention} has been released from quarantine.",
                            f"🎉 Congratulations {member.mention}! You're free to go!",
                            f"🚪 The cell door opens... {member.mention} walks free once more!"
                        ]
                        freedom_message = random.choice(freedom_messages)
                        
                        # Create a fancy embed for the jail-cam
                        embed = discord.Embed(
                            title="Prisoner Released",
                            description=freedom_message,
                            color=discord.Color.green(),
                            timestamp=current_time
                        )
                        embed.set_thumbnail(url=member.display_avatar.url)
                        embed.set_footer(text="They've done their time! Back to normal server access.")
                        
                        await jail_cam_channel.send(embed=embed)
                        
                except Exception as e:
                    print(f"Error auto-unquarantining user {user_id}: {e}")
    except Exception as e:
        print(f"Error in quarantine expiration task: {e}")

@check_quarantine_expirations.before_loop
async def before_quarantine_check():
    await bot.wait_until_ready()

async def handle_prison_break_attempt(message, guild_id, game_id, game_data, current_challenge):
    """Handle a prison break challenge attempt - this is a placeholder for now"""
    pass  # This will be implemented in the quarantine module 