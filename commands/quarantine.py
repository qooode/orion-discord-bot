import discord
import datetime
import random
import asyncio
from discord import app_commands
from discord.ext import tasks
from typing import Optional

from config import UTC, QUARANTINE_CHANNEL_NAME, JAIL_CAM_CHANNEL_NAME, PRISON_BREAK_STAGES, PRISON_BREAK_REWARDS, PRISON_BREAK_FAILURES, HELP_EMOJIS, SABOTAGE_EMOJIS
from data_manager import quarantine_data, save_quarantine_data, fresh_account_settings, save_fresh_account_settings, prison_break_data, save_prison_break_data

async def setup_quarantine_commands(bot):
    """Setup quarantine system commands"""
    
    @bot.tree.command(name="quarantine", description="Quarantine a user by restricting them to a specific channel")
    @app_commands.describe(
        user="The user to quarantine",
        reason="Reason for quarantine",
        minutes="Minutes to keep user quarantined (0 for indefinite)",
        public="Whether to mirror messages to a public channel for everyone to view"
    )
    @app_commands.default_permissions(administrator=True)
    async def quarantine_user(interaction: discord.Interaction, user: discord.Member, 
                            reason: str, minutes: int = 0, public: bool = True):
        try:
            # Don't allow quarantining admins or mods
            if user.guild_permissions.administrator or user.guild_permissions.moderate_members:
                await interaction.response.send_message("⚠️ Cannot quarantine administrators or moderators.", ephemeral=True)
                return
                
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            
            # Create or get the quarantine data structure
            if guild_id not in quarantine_data:
                quarantine_data[guild_id] = {}
                
            # Find or create Quarantine category
            quarantine_category = discord.utils.get(interaction.guild.categories, name="Quarantine")
            if not quarantine_category:
                quarantine_category = await interaction.guild.create_category("Quarantine")
                # Deny view permissions for everyone
                await quarantine_category.set_permissions(interaction.guild.default_role, view_channel=False)
                
            # Find or create quarantine channel
            quarantine_channel = discord.utils.get(interaction.guild.text_channels, name=QUARANTINE_CHANNEL_NAME, category=quarantine_category)
            if not quarantine_channel:
                quarantine_channel = await interaction.guild.create_text_channel(QUARANTINE_CHANNEL_NAME, category=quarantine_category)
                
            # Handle public jail-cam channel if enabled
            jail_cam_channel_id = None
            if public:
                # First priority: Check if server has a configured jail-cam channel
                if guild_id in quarantine_data and "server_settings" in quarantine_data[guild_id]:
                    server_jail_cam_id = quarantine_data[guild_id]["server_settings"].get("jail_cam_channel_id")
                    if server_jail_cam_id:
                        # Verify the channel still exists
                        configured_channel = interaction.guild.get_channel(int(server_jail_cam_id))
                        if configured_channel:
                            jail_cam_channel_id = server_jail_cam_id
                
                # Find or create the default jail-cam channel if no configured channel exists
                if not jail_cam_channel_id:
                    # Try to find existing default jail-cam channel
                    default_jail_cam = discord.utils.get(interaction.guild.text_channels, name=JAIL_CAM_CHANNEL_NAME)
                    if default_jail_cam:
                        jail_cam_channel_id = str(default_jail_cam.id)
                    else:
                        # Create the default jail-cam channel
                        jail_cam_category = discord.utils.get(interaction.guild.categories, name="Public")
                        if not jail_cam_category:
                            jail_cam_category = await interaction.guild.create_category("Public")
                            
                        default_jail_cam = await interaction.guild.create_text_channel(
                            JAIL_CAM_CHANNEL_NAME,
                            category=jail_cam_category,
                            topic="See what quarantined users are saying! Configure with /setjailcam"
                        )
                        jail_cam_channel_id = str(default_jail_cam.id)
            
            # Save user's current roles
            user_roles = [role.id for role in user.roles if not role.is_default()]
            
            # Store quarantine data
            current_time = datetime.datetime.now(UTC)
            quarantine_data[guild_id][user_id] = {
                "reason": reason,
                "moderator": str(interaction.user.id),
                "roles": user_roles,  # Store user's roles for restoration
                "timestamp": str(current_time),
                "channel_id": str(quarantine_channel.id),
                "public_view": public,
                "jail_cam_channel_id": jail_cam_channel_id
            }
            
            # Add expiry time if minutes is specified
            if minutes > 0:
                end_time = current_time + datetime.timedelta(minutes=minutes)
                quarantine_data[guild_id][user_id]["end_time"] = str(end_time)
                quarantine_data[guild_id][user_id]["original_duration_minutes"] = minutes
            
            # Save data
            save_quarantine_data(quarantine_data)
            
            # Send response to confirm
            await interaction.response.send_message(f"Processing quarantine for {user.mention}...", ephemeral=True)
            
            # Hide all channels from user except quarantine channel
            for channel in interaction.guild.channels:
                if channel.id != quarantine_channel.id:
                    try:
                        await channel.set_permissions(user, view_channel=False, reason=f"Quarantine: {reason}")
                    except:
                        pass
                        
            # Allow access to quarantine channel
            await quarantine_channel.set_permissions(user, view_channel=True, read_messages=True, send_messages=True,
                                                  reason=f"Quarantine: {reason}")
            
            # Remove all roles - handle permission errors gracefully
            roles_removed = 0
            roles_failed = 0
            try:
                for role in user.roles:
                    if not role.is_default():
                        try:
                            await user.remove_roles(role, reason=f"Quarantine: {reason}")
                            roles_removed += 1
                        except discord.Forbidden:
                            roles_failed += 1
                        except Exception as e:
                            print(f"Error removing role {role.name}: {e}")
                            roles_failed += 1
                            
                if roles_failed > 0:
                    print(f"Warning: Could not remove {roles_failed} roles due to permissions. Successfully removed {roles_removed} roles.")
                    await interaction.followup.send(f"Warning: Could not remove all roles due to missing permissions.", ephemeral=True)
            except Exception as e:
                print(f"Error removing roles: {e}")
                await interaction.followup.send(f"Warning: Could not remove all roles: {str(e)}", ephemeral=True)
            
            # Send stylish message in original channel
            embed = discord.Embed(
                title="🔒 PRISONER DETAINED",
                description=f"A user has been thrown in the slammer!",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Inmate", value=user.display_name, inline=True)
            embed.add_field(name="Crime", value=reason, inline=True)
            embed.add_field(name="Officer", value=interaction.user.display_name, inline=True)
            
            if minutes > 0:
                embed.add_field(name="Sentence", value=f"{minutes} minutes (until {(current_time + datetime.timedelta(minutes=minutes)).strftime('%H:%M:%S')})", inline=False)
            else:
                embed.add_field(name="Sentence", value="Indefinite", inline=False)
                
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="Justice has been served! Use /throw to throw items at them.")
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
            # Notify user
            try:
                await user.send(f"You have been quarantined in **{interaction.guild.name}**\n**Reason:** {reason}\n\nYou can only access the {quarantine_channel.mention} channel until a moderator releases you.")
            except:
                await interaction.followup.send("Could not DM the user about their quarantine.", ephemeral=True)
                
            # Send a cool embed to quarantine channel
            embed = discord.Embed(
                title="🔒 WELCOME TO JAIL 🔒",
                description="You've been placed in quarantine!",
                color=discord.Color.dark_red()
            )
            
            # Add fields with all the important info
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Sentenced by", value=interaction.user.display_name, inline=True)
            
            if minutes > 0:
                embed.add_field(name="Release Time", value=f"{minutes} minutes ({(current_time + datetime.timedelta(minutes=minutes)).strftime('%H:%M:%S')})", inline=True)
            else:
                embed.add_field(name="Duration", value="Until manually released", inline=True)
                
            # Only show prison break game explanation if there's an active game
            active_prison_game = False
            if guild_id in prison_break_data:
                for game_id, game_data in prison_break_data[guild_id].items():
                    if game_data.get("active", False):
                        active_prison_game = True
                        break
            
            if active_prison_game:
                embed.add_field(
                    name="🎮 Prison Break Game Active!", 
                    value=(
                        "**An escape game is currently running!**\n\n"
                        "**Game Stages:**\n"
                        "🔓 **Stage 1:** Type 4-digit combinations like `1-2-3-4`\n"
                        "🕳️ **Stage 2:** Type directions: `north`, `south`, `east`, `west`\n"
                        "👮 **Stage 3:** Type hiding spots: `behind tree`, `in shadows`, etc.\n"
                        "🚗 **Stage 4:** Work together - all type the secret code word!\n\n"
                        "**Success = Reduced sentence • Failure = Extended sentence**"
                    ), 
                    inline=False
                )
            
            # Add footer with important info
            visibility = "visible to everyone in #jail-cam" if public else "only visible to moderators"
            embed.set_footer(text=f"Your messages are {visibility} | Spectators can react with emojis and use /throw items")
            
            # Set user avatar as thumbnail
            embed.set_thumbnail(url=user.display_avatar.url)
            
            # Send and pin
            quarantine_msg = await quarantine_channel.send(content=f"Hey {user.mention}!", embed=embed)
            
            # Pin the message
            try:
                await quarantine_msg.pin(reason="Quarantine notification")
            except:
                pass
            
            # Log to mod-logs
            log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="🔒 User Quarantined",
                    description=f"{user.mention} has been quarantined.",
                    color=discord.Color.red(),
                    timestamp=datetime.datetime.now(UTC)
                )
                embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
                embed.add_field(name="Moderator", value=f"{interaction.user} ({interaction.user.id})", inline=True)
                embed.add_field(name="Reason", value=reason, inline=False)
                
                if minutes > 0:
                    embed.add_field(name="Duration", value=f"{minutes} minutes (until {(current_time + datetime.timedelta(minutes=minutes)).strftime('%H:%M:%S')})", inline=True)
                else:
                    embed.add_field(name="Duration", value="Indefinite", inline=True)
                    
                embed.add_field(name="Quarantine Channel", value=quarantine_channel.mention, inline=False)
                embed.set_thumbnail(url=user.display_avatar.url)
                await log_channel.send(embed=embed)
                
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="unquarantine", description="Remove a user from quarantine and restore their permissions")
    @app_commands.describe(user="The user to release from quarantine")
    @app_commands.default_permissions(administrator=True)
    async def unquarantine_user(interaction: discord.Interaction, user: discord.Member):
        try:
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            
            # Check if user is quarantined
            if guild_id not in quarantine_data or user_id not in quarantine_data[guild_id]:
                await interaction.response.send_message(f"{user.mention} is not currently quarantined.", ephemeral=True)
                return
                
            # Get quarantine data
            user_data = quarantine_data[guild_id][user_id]
            saved_roles = user_data.get("roles", [])
            
            await interaction.response.send_message(f"Processing release from quarantine for {user.mention}...", ephemeral=True)
            
            # Reset permissions for all channels
            for channel in interaction.guild.channels:
                try:
                    # Remove any specific overrides for this user
                    await channel.set_permissions(user, overwrite=None, reason="Released from quarantine")
                except:
                    pass
                    
            # Restore roles
            try:
                for role_id in saved_roles:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        await user.add_roles(role, reason="Released from quarantine")
            except Exception as e:
                await interaction.followup.send(f"Warning: Could not restore all roles: {str(e)}", ephemeral=True)
                
            # Remove from quarantine data
            del quarantine_data[guild_id][user_id]
            save_quarantine_data(quarantine_data)
            
            # Send stylish unquarantine message
            embed = discord.Embed(
                title="🔓 PRISONER RELEASED",
                description=f"A user has been released from quarantine!",
                color=discord.Color.green()
            )
            embed.add_field(name="Former Inmate", value=user.display_name, inline=True)
            embed.add_field(name="Released by", value=interaction.user.display_name, inline=True)
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.set_footer(text="All access and roles have been restored.")
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
            # Notify user
            try:
                await user.send(f"You have been released from quarantine in **{interaction.guild.name}**. Your access has been restored.")
            except:
                pass
                
            # Log to mod-logs
            log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
            if log_channel:
                embed = discord.Embed(
                    title="🔓 User Released from Quarantine",
                    description=f"{user.mention} has been released from quarantine.",
                    color=discord.Color.green(),
                    timestamp=datetime.datetime.now(UTC)
                )
                embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
                embed.add_field(name="Moderator", value=f"{interaction.user} ({interaction.user.id})", inline=True)
                embed.set_thumbnail(url=user.display_avatar.url)
                await log_channel.send(embed=embed)
                
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="quarantinelist", description="List all currently quarantined users")
    @app_commands.default_permissions(administrator=True)
    async def quarantine_list(interaction: discord.Interaction):
        try:
            guild_id = str(interaction.guild.id)
            
            # Check if there are any quarantined users (filter out server_settings)
            quarantined_users = {}
            if guild_id in quarantine_data:
                quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
            
            if not quarantined_users:
                await interaction.response.send_message("There are no users currently in quarantine.", ephemeral=True)
                return
                
            # Create embed
            embed = discord.Embed(
                title="Quarantined Users",
                description=f"There are {len(quarantined_users)} users in quarantine.",
                color=discord.Color.orange()
            )
            
            # Add each user (excluding server_settings)
            for user_id, data in quarantined_users.items():
                try:
                    user = await interaction.guild.fetch_member(int(user_id))
                    user_mention = user.mention
                except:
                    user_mention = f"User ID: {user_id} (left server)"
                    
                mod_id = data.get("moderator")
                try:
                    mod = await interaction.guild.fetch_member(int(mod_id))
                    mod_mention = mod.mention
                except:
                    mod_mention = f"Mod ID: {mod_id}"
                    
                timestamp = data.get("timestamp", "Unknown")
                reason = data.get("reason", "No reason provided")
                
                embed.add_field(
                    name=f"User: {user_mention}", 
                    value=f"**Quarantined by:** {mod_mention}\n**Reason:** {reason}\n**When:** {timestamp}", 
                    inline=False
                )
                
            await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="throw", description="Throw something at a quarantined user")
    @app_commands.describe(
        item="What to throw at the quarantined user",
        user="The quarantined user to throw at (defaults to any quarantined user)"
    )
    @app_commands.choices(item=[
        app_commands.Choice(name="Tomato 🍅", value="tomato"),
        app_commands.Choice(name="Egg 🥚", value="egg"),
        app_commands.Choice(name="Pie 🥧", value="pie"),
        app_commands.Choice(name="Shoe 👟", value="shoe"),
        app_commands.Choice(name="Flower 🌹", value="flower"),
        app_commands.Choice(name="Money 💰", value="money")
    ])
    async def throw_item(interaction: discord.Interaction, item: str, user: Optional[discord.Member] = None):
        try:
            # Get guild and data
            guild_id = str(interaction.guild.id)
            
            # Check if there are quarantined users (filter out server_settings)
            quarantined_users = {}
            if guild_id in quarantine_data:
                quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
            
            if not quarantined_users:
                await interaction.response.send_message("There's nobody in quarantine to throw things at!", ephemeral=True)
                return
                
            # If user specified, check if they're in quarantine
            if user:
                if str(user.id) not in quarantined_users:
                    await interaction.response.send_message(f"{user.mention} is not in quarantine!", ephemeral=True)
                    return
                target_user = user
                quarantine_channel_id = quarantined_users[str(user.id)].get("channel_id")
            else:
                # Pick a random quarantined user (excluding server_settings)
                quarantined_user_id = random.choice(list(quarantined_users.keys()))
                try:
                    target_user = await interaction.guild.fetch_member(int(quarantined_user_id))
                    quarantine_channel_id = quarantined_users[quarantined_user_id].get("channel_id")
                except:
                    await interaction.response.send_message("Couldn't find a valid quarantined user.", ephemeral=True)
                    return
                
            # Get the quarantine channel
            if not quarantine_channel_id:
                await interaction.response.send_message("Couldn't find the quarantine channel.", ephemeral=True)
                return
                
            quarantine_channel = interaction.guild.get_channel(int(quarantine_channel_id))
            if not quarantine_channel:
                await interaction.response.send_message("Couldn't find the quarantine channel.", ephemeral=True)
                return
                
            # Get the item details
            throw_messages = {
                "tomato": [
                    f"SPLAT! {interaction.user.mention} threw a tomato 🍅 at {target_user.mention}!",
                    f"{interaction.user.mention} hurls a juicy tomato 🍅 that hits {target_user.mention} right in the face!",
                    f"A tomato 🍅 flies through the air and hits {target_user.mention}, courtesy of {interaction.user.mention}!"
                ],
                "egg": [
                    f"CRACK! {interaction.user.mention} hit {target_user.mention} with an egg 🥚!", 
                    f"{interaction.user.mention} throws an egg 🥚 that breaks over {target_user.mention}'s head!",
                    f"Look out {target_user.mention}! {interaction.user.mention} just egged you! 🥚"
                ],
                "pie": [
                    f"SPLAT! {interaction.user.mention} threw a pie 🥧 at {target_user.mention}!",
                    f"{interaction.user.mention} shoves a pie 🥧 right in {target_user.mention}'s face!",
                    f"A cream pie 🥧 from {interaction.user.mention} hits {target_user.mention} perfectly!"
                ],
                "shoe": [
                    f"BONK! {interaction.user.mention} threw a shoe 👟 at {target_user.mention}!",
                    f"{interaction.user.mention} takes off their shoe 👟 and throws it at {target_user.mention}!",
                    f"Duck, {target_user.mention}! A flying shoe 👟 from {interaction.user.mention} is coming your way!"
                ],
                "flower": [
                    f"{interaction.user.mention} tosses a flower 🌹 to {target_user.mention}. How sweet!",
                    f"A beautiful flower 🌹 from {interaction.user.mention} lands near {target_user.mention}.",
                    f"{interaction.user.mention} throws a flower 🌹 at {target_user.mention}. Maybe they're not so mad after all?"
                ],
                "money": [
                    f"{interaction.user.mention} throws money 💰 at {target_user.mention}! Make it rain!",
                    f"{interaction.user.mention} showers {target_user.mention} with cash 💰! Cha-ching!",
                    f"Look! {interaction.user.mention} is throwing money 💰 at {target_user.mention}! How generous!"
                ]
            }
            
            # Get messages for selected item or use default
            messages = throw_messages.get(item, [f"{interaction.user.mention} threw something at {target_user.mention}!"])
            
            # Pick a random message
            message = random.choice(messages)
            
            # Send message to quarantine channel
            await quarantine_channel.send(message)
            
            # Confirm to thrower
            emoji_map = {"tomato": "🍅", "egg": "🥚", "pie": "🥧", "shoe": "👟", "flower": "🌹", "money": "💰"}
            emoji = emoji_map.get(item, "🎯")
            
            await interaction.response.send_message(f"You threw a {item} {emoji} at {target_user.mention}!", ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="freshaccounts", description="Configure fresh account detection settings")
    @app_commands.describe(
        action="Action to take on fresh accounts",
        age_threshold="Minimum account age in days",
        enabled="Enable or disable fresh account detection"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Alert Only", value="alert"),
        app_commands.Choice(name="Auto-Quarantine", value="quarantine"),
        app_commands.Choice(name="Auto-Kick", value="kick")
    ])
    @app_commands.choices(enabled=[
        app_commands.Choice(name="Enable", value=1),
        app_commands.Choice(name="Disable", value=0)
    ])
    @app_commands.default_permissions(administrator=True)
    async def configure_fresh_accounts(interaction: discord.Interaction, action: str, age_threshold: int = 7, enabled: int = 1):
        try:
            guild_id = str(interaction.guild.id)
            
            # Initialize settings if needed
            if guild_id not in fresh_account_settings:
                fresh_account_settings[guild_id] = {}
                
            # Update settings
            fresh_account_settings[guild_id]["action"] = action
            fresh_account_settings[guild_id]["age_threshold"] = age_threshold
            fresh_account_settings[guild_id]["enabled"] = bool(enabled)
            
            # Save settings
            save_fresh_account_settings(fresh_account_settings)
            
            # Create response embed
            embed = discord.Embed(
                title="Fresh Account Detection Settings",
                description="Settings have been updated successfully.",
                color=discord.Color.green() if enabled else discord.Color.red()
            )
            
            embed.add_field(name="Status", value="Enabled" if enabled else "Disabled", inline=True)
            embed.add_field(name="Account Age Threshold", value=f"{age_threshold} days", inline=True)
            embed.add_field(name="Action", value=action.title(), inline=True)
            
            # Explain what the settings do
            if action == "alert":
                embed.add_field(name="What this does", value="New accounts younger than the threshold will trigger an alert in the mod-logs channel.", inline=False)
            elif action == "quarantine":
                embed.add_field(name="What this does", value="New accounts younger than the threshold will be automatically quarantined.", inline=False)
            elif action == "kick":
                embed.add_field(name="What this does", value="New accounts younger than the threshold will be automatically kicked.", inline=False)
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="prisonbreak", description="Start an interactive prison break game for quarantined users")
    @app_commands.describe(
        action="Action to take with the prison break game",
        user="Specific user to start game for (optional)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Start Game", value="start"),
        app_commands.Choice(name="Stop Game", value="stop"),
        app_commands.Choice(name="Check Status", value="status")
    ])
    @app_commands.default_permissions(administrator=True)
    async def prison_break(interaction: discord.Interaction, action: str, user: Optional[discord.Member] = None):
        # IMMEDIATELY defer the response to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id)
        
        try:
            # Check if anyone is quarantined (filter out server_settings)
            quarantined_users = {}
            if guild_id in quarantine_data:
                quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
            
            if not quarantined_users:
                await interaction.followup.send("❌ No one is currently quarantined! Prison break needs prisoners!", ephemeral=True)
                return
                
            if action == "start":
                # Initialize prison break data for guild if not exists
                if guild_id not in prison_break_data:
                    prison_break_data[guild_id] = {}
                    
                # If specific user, check they're quarantined
                if user:
                    if str(user.id) not in quarantined_users:
                        await interaction.followup.send(f"❌ {user.mention} is not quarantined!", ephemeral=True)
                        return
                    players = [user.id]
                    player_names = [user.display_name]
                else:
                    # Get all quarantined users (excluding server_settings)
                    players = [int(user_id) for user_id in quarantined_users.keys()]
                    player_names = []
                    for player_id in players:
                        member = interaction.guild.get_member(player_id)
                        if member:
                            player_names.append(member.display_name)
                            
                if not players:
                    await interaction.followup.send("❌ No valid quarantined players found!", ephemeral=True)
                    return
                    
                # Create new game session
                game_id = str(len(prison_break_data[guild_id]) + 1)
                prison_break_data[guild_id][game_id] = {
                    "players": players,
                    "stage": 1,
                    "start_time": str(datetime.datetime.now(UTC)),
                    "last_activity": str(datetime.datetime.now(UTC)),
                    "attempts": {},
                    "spectator_votes": {"help": 0, "sabotage": 0},
                    "active": True,
                    "challenges_completed": [],
                    "current_challenge": None
                }
                
                save_prison_break_data(prison_break_data)
                
                # Send immediate confirmation
                await interaction.followup.send(f"🎪 **PRISON BREAK STARTED!** Game ID: {game_id}\nPlayers: {', '.join(player_names)}", ephemeral=True)
                
                # Announce the game start
                jail_cam_channel = get_jail_cam_channel(interaction.guild)
                    
                if jail_cam_channel:
                    embed = discord.Embed(
                        title="🚨 PRISON BREAK ALERT! 🚨",
                        description=f"**{len(players)} prisoner(s) are attempting to escape!**\n\nPlayers: {', '.join(player_names)}",
                        color=0xff4444
                    )
                    embed.add_field(
                        name="🎮 How Spectators Can Participate", 
                        value=(
                            "**HELP EMOJIS** (assist prisoners):\n"
                            "✨ Magic assistance • 🤝 Teamwork boost • 💡 Helpful hints\n"
                            "🔦 Light the way • 🗝️ Lock picking tools • ⏰ Extra time\n"
                            "📍 Show directions • 🎯 Tactical advice • 🆘 Emergency help\n\n"
                            "**SABOTAGE EMOJIS** (hinder prisoners):\n"
                            "😈 Alert guards • 🚨 Trigger alarms • 🔒 Jam locks\n"
                            "💥 Create chaos • 🌩️ Cut power • 📢 Make noise\n"
                            "⛔ Block routes • 💀 Extra security • 🔥 Start fires\n\n"
                            "**React to messages in this channel to help or hinder!**"
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="🎯 Game Stages", 
                        value=(
                            "**Stage 1:** 🔓 Lock Picking - Crack the cell door combination\n"
                            "**Stage 2:** 🕳️ Tunnel Digging - Navigate underground maze\n"
                            "**Stage 3:** 👮 Guard Evasion - Sneak past security\n"
                            "**Stage 4:** 🚗 Great Escape - Coordinate team escape"
                        ),
                        inline=False
                    )
                    embed.add_field(
                        name="📊 Current Stage", 
                        value=f"**Stage 1:** {PRISON_BREAK_STAGES[1]['name']}\n{PRISON_BREAK_STAGES[1]['description']}",
                        inline=False
                    )
                    message = await jail_cam_channel.send(embed=embed)
                    
                    # Add reaction emojis automatically for spectators to use
                    try:
                        for emoji in HELP_EMOJIS[:3]:  # Add first 3 help emojis
                            await message.add_reaction(emoji)
                        for emoji in SABOTAGE_EMOJIS[:3]:  # Add first 3 sabotage emojis
                            await message.add_reaction(emoji)
                    except Exception as e:
                        print(f"Error adding reactions to prison break announcement: {e}")
                
                # Start the first challenge
                await start_stage_challenge(interaction.guild, game_id, 1)
                
            elif action == "stop":
                if guild_id not in prison_break_data or not prison_break_data[guild_id]:
                    await interaction.followup.send("❌ No active prison break games!", ephemeral=True)
                    return
                    
                # Stop all active games
                stopped_count = 0
                for game_id in list(prison_break_data[guild_id].keys()):
                    if game_id != "server_settings" and prison_break_data[guild_id][game_id].get("active", False):
                        prison_break_data[guild_id][game_id]["active"] = False
                        stopped_count += 1
                        
                save_prison_break_data(prison_break_data)
                await interaction.followup.send(f"🛑 Stopped {stopped_count} active prison break game(s)!", ephemeral=True)
                
            elif action == "status":
                if guild_id not in prison_break_data or not prison_break_data[guild_id]:
                    await interaction.followup.send("❌ No prison break games found!", ephemeral=True)
                    return
                    
                active_games = []
                for game_id, game_data in prison_break_data[guild_id].items():
                    if game_id != "server_settings" and game_data.get("active", False):
                        players = []
                        for player_id in game_data["players"]:
                            member = interaction.guild.get_member(player_id)
                            if member:
                                players.append(member.display_name)
                        
                        active_games.append({
                            "id": game_id,
                            "players": players,
                            "stage": game_data["stage"],
                            "start_time": game_data["start_time"]
                        })
                        
                if not active_games:
                    await interaction.followup.send("📊 No active prison break games!", ephemeral=True)
                    return
                    
                embed = discord.Embed(title="🎮 Active Prison Break Games", color=0x00ff00)
                for game in active_games:
                    embed.add_field(
                        name=f"Game {game['id']} - Stage {game['stage']}",
                        value=f"Players: {', '.join(game['players'])}\nStarted: {game['start_time'][:19]}",
                        inline=False
                    )
                await interaction.followup.send(embed=embed, ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @bot.tree.command(name="setjailcam", description="Set the channel to use for jail-cam (public quarantine viewing)")
    @app_commands.describe(
        channel="The channel to use for jail-cam, or None to disable public viewing"
    )
    @app_commands.default_permissions(administrator=True)
    async def set_jail_cam(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
        try:
            guild_id = str(interaction.guild.id)
            
            # Initialize guild settings if not exists
            if guild_id not in quarantine_data:
                quarantine_data[guild_id] = {}
            
            # Special key for server settings
            if "server_settings" not in quarantine_data[guild_id]:
                quarantine_data[guild_id]["server_settings"] = {}
            
            if channel:
                # Set the jail-cam channel
                quarantine_data[guild_id]["server_settings"]["jail_cam_channel_id"] = str(channel.id)
                save_quarantine_data(quarantine_data)
                
                embed = discord.Embed(
                    title="🔧 Jail-Cam Channel Configured",
                    description=f"Jail-cam messages will now be sent to {channel.mention}",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="What this means",
                    value="• Quarantined users' messages will be mirrored to this channel when public viewing is enabled\n• Spectators can see prison break games here\n• Users can use `/throw` commands here",
                    inline=False
                )
                
                # Test message
                try:
                    await channel.send("📺 **This channel is now configured for jail-cam!** Quarantined users' public messages will appear here.")
                except:
                    embed.add_field(
                        name="⚠️ Warning", 
                        value="Bot may not have permission to send messages in this channel",
                        inline=False
                    )
                
            else:
                # Remove jail-cam channel (disable public viewing)
                if "jail_cam_channel_id" in quarantine_data[guild_id]["server_settings"]:
                    del quarantine_data[guild_id]["server_settings"]["jail_cam_channel_id"]
                    save_quarantine_data(quarantine_data)
                
                embed = discord.Embed(
                    title="🔧 Jail-Cam Disabled",
                    description="Public jail-cam viewing has been disabled for this server",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="What this means",
                    value="• Quarantined users' messages will only be visible to moderators\n• No public mirror channel for quarantine activity\n• Prison break games will still work but won't be publicly visible",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)

    @bot.tree.command(name="prisonhelp", description="Get help about the prison break game mechanics")
    async def prison_help(interaction: discord.Interaction):
        try:
            embed = discord.Embed(
                title="🎮 Prison Break Game Guide",
                description="Complete guide to the interactive prison escape system!",
                color=0x00ff88
            )
            
            embed.add_field(
                name="🔒 For Prisoners (Quarantined Users)",
                value=(
                    "**How to Play:**\n"
                    "• Wait for a moderator to start a game with `/prisonbreak start`\n"
                    "• Type specific commands in your quarantine channel\n"
                    "• Complete challenges to reduce your sentence\n"
                    "• Fail too many times and your sentence extends!\n\n"
                    "**The 4 Stages:**\n"
                    "🔓 **Lock Picking:** Type `1-2-3-4` format combinations\n"
                    "🕳️ **Tunnel Digging:** Type `north`, `south`, `east`, `west`\n"
                    "👮 **Guard Evasion:** Type hiding spots like `behind tree`\n"
                    "🚗 **Great Escape:** All players type the secret code word together"
                ),
                inline=False
            )
            
            embed.add_field(
                name="👥 For Spectators (Everyone Else)",
                value=(
                    "**How to Help/Hinder:**\n"
                    "• React with emojis on messages in the jail-cam channel\n"
                    "• Use `/throw` commands to throw items at prisoners\n"
                    "• Watch the action unfold in real-time!\n\n"
                    "**Help Emojis:** ✨🤝💡🔦🗝️⏰📍🎯🆘\n"
                    "**Sabotage Emojis:** 😈🚨🔒💥🌩️📢⛔💀🔥\n\n"
                    "**Effects:**\n"
                    "• More help votes = better success chance for prisoners\n"
                    "• More sabotage votes = worse success chance for prisoners"
                ),
                inline=False
            )
            
            embed.add_field(
                name="⚙️ For Moderators",
                value=(
                    "**Commands:**\n"
                    "• `/prisonbreak start` - Start a game for all quarantined users\n"
                    "• `/prisonbreak start @user` - Start a game for specific user\n"
                    "• `/prisonbreak stop` - Stop all active games\n"
                    "• `/prisonbreak status` - Check active games\n"
                    "• `/setjailcam #channel` - Configure jail-cam channel"
                ),
                inline=False
            )
            
            embed.set_footer(text="Prison break games are a fun way to interact with quarantined users!")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="quarantinedebug", description="Debug quarantine timers and check expiration system")
    @app_commands.default_permissions(administrator=True)
    async def quarantine_debug(interaction: discord.Interaction):
        try:
            guild_id = str(interaction.guild.id)
            current_time = datetime.datetime.now(UTC)
            
            embed = discord.Embed(
                title="🔧 Quarantine Timer Debug",
                description=f"Current time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} UTC",
                color=discord.Color.blue()
            )
            
            # Check if guild has quarantine data
            if guild_id not in quarantine_data:
                embed.add_field(name="Status", value="❌ No quarantine data for this guild", inline=False)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Count quarantined users (excluding server_settings)
            quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
            embed.add_field(name="Total Quarantined", value=str(len(quarantined_users)), inline=True)
            
            # Check users with timers
            timed_users = 0
            expired_users = 0
            timer_details = []
            
            for user_id, data in quarantined_users.items():
                if "end_time" in data:
                    timed_users += 1
                    try:
                        end_time_str = data["end_time"]
                        # Parse the end time string
                        end_time = datetime.datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
                        time_remaining = end_time - current_time
                        
                        if current_time >= end_time:
                            expired_users += 1
                            status = "🔴 EXPIRED"
                        else:
                            status = f"⏰ {int(time_remaining.total_seconds())}s left"
                        
                        # Get user info
                        try:
                            member = interaction.guild.get_member(int(user_id))
                            username = member.display_name if member else f"User {user_id}"
                        except:
                            username = f"User {user_id}"
                        
                        timer_details.append(f"**{username}:** {status}")
                        
                        # Add detailed time info for first 3 users
                        if len(timer_details) <= 3:
                            timer_details[-1] += f"\n  End: {end_time.strftime('%H:%M:%S')}"
                            timer_details[-1] += f"\n  Raw: {end_time_str[:19]}"
                        
                    except Exception as e:
                        timer_details.append(f"**User {user_id}:** ❌ Error parsing time: {str(e)}")
            
            embed.add_field(name="With Timers", value=str(timed_users), inline=True)
            embed.add_field(name="Should be Released", value=str(expired_users), inline=True)
            
            # Check if we can access the bot instance to see if the task is running
            try:
                # Try to check if the task exists in the bot's tasks
                running_tasks = [task for task in asyncio.all_tasks() if 'check_quarantine_expirations' in str(task)]
                task_status = f"✅ Found {len(running_tasks)} timer task(s)" if running_tasks else "❌ No timer tasks found"
            except:
                task_status = "❓ Cannot determine task status"
            
            embed.add_field(name="Timer Task Status", value=task_status, inline=False)
            
            # Show timer details for individual users
            if timer_details:
                details_text = "\n".join(timer_details[:10])  # Show max 10 users
                if len(timer_details) > 10:
                    details_text += f"\n...and {len(timer_details) - 10} more"
                
                if len(details_text) > 1024:
                    details_text = details_text[:1020] + "..."
                    
                embed.add_field(name="Timer Details", value=details_text, inline=False)
            
            # Add manual trigger option
            if expired_users > 0:
                embed.add_field(
                    name="⚠️ Manual Action Needed", 
                    value=f"There are {expired_users} users who should be auto-released but aren't. The timer might not be working properly.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"Debug error: {str(e)}", ephemeral=True)

    @bot.tree.command(name="quarantinetrigger", description="Manually trigger quarantine expiration check (emergency use)")
    @app_commands.default_permissions(administrator=True)
    async def manual_quarantine_trigger(interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            
            guild_id = str(interaction.guild.id)
            current_time = datetime.datetime.now(UTC)
            
            # Check if guild has quarantine data
            if guild_id not in quarantine_data:
                await interaction.followup.send("❌ No quarantine data for this guild.", ephemeral=True)
                return
            
            # Get quarantined users (excluding server_settings)
            quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
            
            if not quarantined_users:
                await interaction.followup.send("❌ No quarantined users found.", ephemeral=True)
                return
            
            # Find users to unquarantine
            users_to_unquarantine = []
            results = []
            
            for user_id, data in quarantined_users.items():
                if "end_time" in data:
                    try:
                        end_time = datetime.datetime.fromisoformat(data["end_time"].replace('Z', '+00:00'))
                        if current_time >= end_time:
                            users_to_unquarantine.append(user_id)
                            results.append(f"✅ Will release: User {user_id}")
                        else:
                            time_remaining = int((end_time - current_time).total_seconds())
                            results.append(f"⏰ User {user_id}: {time_remaining}s remaining")
                    except Exception as e:
                        results.append(f"❌ User {user_id}: Error parsing time - {str(e)}")
                else:
                    results.append(f"🔒 User {user_id}: No timer (indefinite)")
            
            if not users_to_unquarantine:
                result_text = "\n".join(results[:10])
                await interaction.followup.send(f"🔍 **Manual Check Complete**\n\nNo expired quarantines found.\n\n{result_text}", ephemeral=True)
                return
            
            # Manually unquarantine expired users
            released_count = 0
            failed_releases = []
            
            for user_id in users_to_unquarantine:
                try:
                    # Get the user and their data
                    member = await interaction.guild.fetch_member(int(user_id))
                    user_data = quarantine_data[guild_id][user_id]
                    saved_roles = user_data.get("roles", [])
                    
                    print(f"Manually unquarantining {member.display_name} in {interaction.guild.name}")
                    
                    # Reset channel permissions
                    for channel in interaction.guild.channels:
                        try:
                            await channel.set_permissions(member, overwrite=None, reason="Manual release from expired quarantine")
                        except:
                            pass
                    
                    # Restore roles
                    for role_id in saved_roles:
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            try:
                                await member.add_roles(role, reason="Manual release from expired quarantine")
                            except:
                                pass
                    
                    # Remove from quarantine data
                    del quarantine_data[guild_id][user_id]
                    save_quarantine_data(quarantine_data)
                    
                    released_count += 1
                    
                    # DM the user
                    try:
                        await member.send(f"You have been released from quarantine in **{interaction.guild.name}**. Your access has been restored.")
                    except:
                        pass
                    
                    # Log to mod-logs
                    log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
                    if log_channel:
                        embed = discord.Embed(
                            title="🔓 User Manually Released from Quarantine",
                            description=f"<@{user_id}> has been manually released from expired quarantine.",
                            color=discord.Color.orange(),
                            timestamp=current_time
                        )
                        embed.add_field(name="Released by", value=f"{interaction.user.mention}", inline=True)
                        embed.add_field(name="Reason", value="Manual trigger - timer expired", inline=True)
                        embed.set_footer(text="Manual quarantine release")
                        await log_channel.send(embed=embed)
                        
                except Exception as e:
                    failed_releases.append(f"User {user_id}: {str(e)}")
                    print(f"Error manually unquarantining user {user_id}: {e}")
            
            # Send results
            result_message = f"🔧 **Manual Trigger Complete**\n\n✅ **Released:** {released_count} users"
            
            if failed_releases:
                result_message += f"\n❌ **Failed:** {len(failed_releases)} users"
                if len(failed_releases) <= 3:
                    result_message += f"\n{chr(10).join(failed_releases)}"
            
            if released_count > 0:
                result_message += f"\n\n💡 **Note:** If the automatic timer isn't working, you may need to restart the bot."
            
            await interaction.followup.send(result_message, ephemeral=True)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Manual trigger error: {str(e)}", ephemeral=True)

    # ===== AUTOMATIC QUARANTINE TIMER SYSTEM =====
    
    @tasks.loop(minutes=1)
    async def check_quarantine_expirations():
        """Background task that automatically releases users when their quarantine time expires"""
        try:
            current_time = datetime.datetime.now(UTC)
            guilds_to_check = list(quarantine_data.keys())
            
            for guild_id in guilds_to_check:
                guild = bot.get_guild(int(guild_id))
                if not guild:
                    continue
                    
                users_to_unquarantine = []
                
                # Get quarantined users (excluding server_settings)
                quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
                
                # Find users whose quarantine has expired
                for user_id, data in quarantined_users.items():
                    if "end_time" in data:
                        try:
                            end_time = datetime.datetime.fromisoformat(data["end_time"].replace('Z', '+00:00'))
                            if current_time >= end_time:
                                users_to_unquarantine.append(user_id)
                        except Exception as e:
                            print(f"Error parsing end time for user {user_id}: {e}")
                
                # Unquarantine expired users
                for user_id in users_to_unquarantine:
                    try:
                        # Get the user and their data
                        member = await guild.fetch_member(int(user_id))
                        user_data = quarantine_data[guild_id][user_id]
                        saved_roles = user_data.get("roles", [])
                        
                        print(f"Auto-releasing {member.display_name} from quarantine in {guild.name}")
                        
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
                        jail_cam_channel = get_jail_cam_channel(guild)
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
                                title="🔓 Prisoner Released",
                                description=freedom_message,
                                color=discord.Color.green(),
                                timestamp=current_time
                            )
                            embed.set_thumbnail(url=member.display_avatar.url)
                            embed.set_footer(text="They've done their time! Back to normal server access.")
                            
                            await jail_cam_channel.send(embed=embed)
                            
                    except Exception as e:
                        print(f"Error auto-unquarantining user {user_id} in guild {guild.name}: {e}")
        except Exception as e:
            print(f"Error in quarantine expiration checker: {e}")

    @check_quarantine_expirations.before_loop
    async def before_quarantine_check():
        await bot.wait_until_ready()

    # Start the background task
    if not check_quarantine_expirations.is_running():
        check_quarantine_expirations.start()
        print("✅ Quarantine expiration checker started!")

# Prison Break Game Helper Functions

def get_jail_cam_channel(guild):
    """Get the configured jail-cam channel for a guild"""
    guild_id = str(guild.id)
    
    # First check if there's a server-configured jail-cam channel
    if guild_id in quarantine_data and "server_settings" in quarantine_data[guild_id]:
        jail_cam_channel_id = quarantine_data[guild_id]["server_settings"].get("jail_cam_channel_id")
        if jail_cam_channel_id:
            channel = guild.get_channel(int(jail_cam_channel_id))
            if channel:
                return channel
    
    # Fall back to finding the default jail-cam channel by name
    return discord.utils.get(guild.text_channels, name=JAIL_CAM_CHANNEL_NAME)

async def start_stage_challenge(guild, game_id, stage):
    """Start a challenge for a specific stage"""
    guild_id = str(guild.id)
    
    if guild_id not in prison_break_data or game_id not in prison_break_data[guild_id]:
        return
        
    game_data = prison_break_data[guild_id][game_id]
    stage_info = PRISON_BREAK_STAGES[stage]
    
    # Generate challenge based on stage
    if stage == 1:  # Lock Picking
        combination = [random.randint(1, 9) for _ in range(4)]
        hint = f"The combination is: {'-'.join(map(str, combination))}"
        game_data["current_challenge"] = {
            "type": "combination",
            "answer": combination,
            "hint": hint,
            "start_time": str(datetime.datetime.now(UTC)),
            "attempts": 0
        }
    elif stage == 2:  # Tunnel Digging
        directions = ["north", "south", "east", "west"]
        path = random.choices(directions, k=5)
        game_data["current_challenge"] = {
            "type": "path",
            "answer": path,
            "progress": [],
            "start_time": str(datetime.datetime.now(UTC)),
            "wrong_attempts": 0
        }
    elif stage == 3:  # Guard Evasion
        guards = random.randint(3, 6)
        safe_spots = ["behind tree", "under truck", "in shadows", "behind dumpster", "in alcove"]
        answer = random.choice(safe_spots)
        game_data["current_challenge"] = {
            "type": "stealth",
            "guards": guards,
            "answer": answer,
            "attempts": 0,
            "start_time": str(datetime.datetime.now(UTC))
        }
    elif stage == 4:  # Great Escape
        code_words = ["freedom", "liberty", "escape", "breakout"]
        selected = random.choice(code_words)
        game_data["current_challenge"] = {
            "type": "teamwork",
            "code_word": selected,
            "players_ready": [],
            "start_time": str(datetime.datetime.now(UTC)),
            "wrong_codes": 0
        }
    
    save_prison_break_data(prison_break_data)
    
    # Create the challenge embed
    embed = discord.Embed(
        title=f"🎯 {stage_info['name']} - Challenge {stage}",
        description=stage_info['description'],
        color=0xffaa00
    )
    
    if stage == 1:
        embed.add_field(
            name="🔢 Lock Combination Challenge",
            value=(
                "**PRISONERS:** Type the correct 4-digit combination to unlock your cell!\n\n"
                "📝 **Format:** `1-2-3-4` (numbers separated by dashes)\n"
                "🎯 **Example:** `3-7-1-9` or `5-2-8-4`\n"
                "⚠️ **Warning:** 3 wrong attempts = lock jams and sentence extends!\n"
                "💡 **Tip:** Try common patterns or listen for spectator hints!"
            ),
            inline=False
        )
    elif stage == 2:
        embed.add_field(
            name="🗺️ Tunnel Navigation Challenge",
            value=(
                "**PRISONERS:** Dig a tunnel by following the correct path!\n\n"
                "📝 **Commands:** Type one direction at a time\n"
                "🧭 **Directions:** `north`, `south`, `east`, `west`\n"
                "🎯 **Goal:** Follow the secret path to reach the other side\n"
                "⚠️ **Warning:** 4 wrong directions = tunnel collapses!\n"
                "💡 **Tip:** Each correct direction shows your progress!"
            ),
            inline=False
        )
    elif stage == 3:
        embed.add_field(
            name="👮 Stealth Challenge", 
            value=(
                f"**PRISONERS:** Hide from {game_data['current_challenge']['guards']} guards patrolling the yard!\n\n"
                "📝 **Commands:** Type where you want to hide\n"
                "🏠 **Options:** `behind tree`, `under truck`, `in shadows`, `behind dumpster`, `in alcove`\n"
                "🎯 **Goal:** Find the one safe hiding spot the guards can't see\n"
                "⚠️ **Warning:** 4 spotted attempts = full alert and sentence extends!\n"
                "💡 **Tip:** Think like a guard - where would YOU look first?"
            ),
            inline=False
        )
    elif stage == 4:
        embed.add_field(
            name="🤝 Teamwork Challenge",
            value=(
                "**PRISONERS:** All prisoners must coordinate for the final escape!\n\n"
                "📝 **Command:** ALL players type the same secret code word\n"
                "🎯 **Goal:** Everyone must say the code word at the same time\n"
                "💭 **Hint:** Think about what you're trying to achieve...\n"
                "⚠️ **Warning:** 5 wrong codes = authorities get suspicious!\n"
                "💡 **Tip:** Communicate! The code is related to your goal!"
            ),
            inline=False
        )
        
    embed.add_field(
        name="⏰ Time Limit",
        value=f"{stage_info['time_limit']} seconds",
        inline=True
    )
    embed.add_field(
        name="🎭 Spectator Actions",
        value="React with help/sabotage emojis on messages to influence the outcome!",
        inline=True
    )
    
    # Send challenge to jail-cam channel (for spectators)
    jail_cam_channel = get_jail_cam_channel(guild)
    if jail_cam_channel:
        await jail_cam_channel.send(embed=embed)
    
    # ===== CRUCIAL FIX: Send challenge to each prisoner's quarantine channel =====
    # Get quarantined users (excluding server_settings)
    quarantined_users = {}
    if guild_id in quarantine_data:
        quarantined_users = {k: v for k, v in quarantine_data[guild_id].items() if k != "server_settings"}
    
    # Send challenge to each prisoner's quarantine channel
    for player_id in game_data["players"]:
        player_user_id = str(player_id)
        if player_user_id in quarantined_users:
            prisoner_data = quarantined_users[player_user_id]
            quarantine_channel_id = prisoner_data.get("channel_id")
            
            if quarantine_channel_id:
                quarantine_channel = guild.get_channel(int(quarantine_channel_id))
                if quarantine_channel:
                    # Create a prisoner-specific embed
                    prisoner_embed = discord.Embed(
                        title=f"🎮 PRISON BREAK - {stage_info['name']}",
                        description=f"**Stage {stage}** has begun! Time to escape!",
                        color=0xff6600
                    )
                    
                    # Add the challenge instructions
                    if stage == 1:
                        prisoner_embed.add_field(
                            name="🔓 Your Mission: Pick the Lock",
                            value=(
                                "**Type a 4-digit combination to unlock your cell door!**\n\n"
                                "📝 **Format:** `1-2-3-4` (numbers with dashes)\n"
                                "🎯 **Examples:** `3-7-1-9`, `5-2-8-4`, `1-0-0-1`\n"
                                "⚠️ **Warning:** 3 wrong tries = lock breaks!\n"
                                "💡 **Hint:** Spectators might help you in the jail-cam!"
                            ),
                            inline=False
                        )
                    elif stage == 2:
                        prisoner_embed.add_field(
                            name="🕳️ Your Mission: Dig a Tunnel",
                            value=(
                                "**Navigate the underground maze to freedom!**\n\n"
                                "📝 **Commands:** Type one direction at a time\n"
                                "🧭 **Options:** `north`, `south`, `east`, `west`\n"
                                "🎯 **Goal:** Find the correct path sequence\n"
                                "⚠️ **Warning:** 4 wrong turns = tunnel collapse!"
                            ),
                            inline=False
                        )
                    elif stage == 3:
                        prisoner_embed.add_field(
                            name="👮 Your Mission: Evade the Guards",
                            value=(
                                f"**{game_data['current_challenge']['guards']} guards are patrolling! Find a safe hiding spot!**\n\n"
                                "📝 **Command:** Type where to hide\n"
                                "🏠 **Options:** `behind tree`, `under truck`, `in shadows`, `behind dumpster`, `in alcove`\n"
                                "🎯 **Goal:** Pick the ONE safe spot\n"
                                "⚠️ **Warning:** 4 failed hides = busted!"
                            ),
                            inline=False
                        )
                    elif stage == 4:
                        prisoner_embed.add_field(
                            name="🚗 Your Mission: The Great Escape",
                            value=(
                                "**ALL prisoners must work together for the final escape!**\n\n"
                                "📝 **Command:** Type the secret escape code word\n"
                                "🤝 **Teamwork:** Everyone must say the same word\n"
                                "💭 **Hint:** What's your ultimate goal here?\n"
                                "⚠️ **Warning:** 5 wrong codes = authorities alerted!"
                            ),
                            inline=False
                        )
                    
                    prisoner_embed.add_field(
                        name="⏰ Time Remaining",
                        value=f"{stage_info['time_limit']} seconds",
                        inline=True
                    )
                    prisoner_embed.add_field(
                        name="📺 Public View",
                        value="Spectators are watching in jail-cam!",
                        inline=True
                    )
                    
                    prisoner_embed.set_footer(text="Type your answer in this channel! Good luck!")
                    
                    try:
                        await quarantine_channel.send(embed=prisoner_embed)
                        print(f"Sent challenge to quarantine channel for player {player_id}")
                    except Exception as e:
                        print(f"Error sending challenge to quarantine channel for player {player_id}: {e}")

async def reduce_quarantine_sentence(guild, user, percentage):
    """Reduce a quarantined user's sentence by a percentage of their original sentence"""
    try:
        guild_id = str(guild.id)
        user_id = str(user.id)
        
        # Check if user is quarantined
        if guild_id not in quarantine_data or user_id not in quarantine_data[guild_id]:
            return False
            
        user_data = quarantine_data[guild_id][user_id]
        
        # Check if user has a timed sentence
        if "end_time" not in user_data or "original_duration_minutes" not in user_data:
            return False
            
        # Calculate reduction based on percentage of original sentence
        original_duration = user_data["original_duration_minutes"]
        reduction_minutes = int((percentage / 100) * original_duration)
        
        # Parse current end time
        end_time = datetime.datetime.fromisoformat(user_data["end_time"].replace('Z', '+00:00'))
        
        # Reduce sentence
        new_end_time = end_time - datetime.timedelta(minutes=reduction_minutes)
        
        # Don't go below current time
        current_time = datetime.datetime.now(UTC)
        if new_end_time < current_time:
            new_end_time = current_time
            
        # Update end time
        user_data["end_time"] = str(new_end_time)
        
        # Save changes
        save_quarantine_data(quarantine_data)
        
        return reduction_minutes
        
    except Exception as e:
        print(f"Error reducing quarantine sentence: {e}")
        return False

async def extend_quarantine_sentence(guild, user, percentage):
    """Extend a quarantined user's sentence by a percentage of their original sentence"""
    try:
        guild_id = str(guild.id)
        user_id = str(user.id)
        
        # Check if user is quarantined
        if guild_id not in quarantine_data or user_id not in quarantine_data[guild_id]:
            return False
            
        user_data = quarantine_data[guild_id][user_id]
        
        # Check if user has a timed sentence
        if "end_time" not in user_data or "original_duration_minutes" not in user_data:
            return False
            
        # Calculate extension based on percentage of original sentence
        original_duration = user_data["original_duration_minutes"]
        extension_minutes = int((percentage / 100) * original_duration)
        
        # Parse current end time
        end_time = datetime.datetime.fromisoformat(user_data["end_time"].replace('Z', '+00:00'))
        
        # Extend sentence
        new_end_time = end_time + datetime.timedelta(minutes=extension_minutes)
        
        # Update end time
        user_data["end_time"] = str(new_end_time)
        
        # Save changes
        save_quarantine_data(quarantine_data)
        
        return extension_minutes
        
    except Exception as e:
        print(f"Error extending quarantine sentence: {e}")
        return False

async def handle_prison_break_attempt(message, guild_id, game_id, game_data, current_challenge):
    """Handle a prison break challenge attempt"""
    try:
        content = message.content.lower().strip()
        stage = game_data["stage"]
        challenge_type = current_challenge["type"]
        
        # Get jail-cam channel for announcements
        jail_cam_channel = get_jail_cam_channel(message.guild)
        
        # Get the prisoner's quarantine channel
        prisoner_quarantine_channel = None
        user_id = str(message.author.id)
        if guild_id in quarantine_data and user_id in quarantine_data[guild_id]:
            quarantine_channel_id = quarantine_data[guild_id][user_id].get("channel_id")
            if quarantine_channel_id:
                prisoner_quarantine_channel = message.guild.get_channel(int(quarantine_channel_id))
        
        success = False
        
        # Helper function to send messages to both channels
        async def send_feedback(jail_cam_msg, prisoner_msg=None):
            if jail_cam_channel:
                await jail_cam_channel.send(jail_cam_msg)
            if prisoner_quarantine_channel:
                await prisoner_quarantine_channel.send(prisoner_msg or jail_cam_msg)
        
        if challenge_type == "combination":  # Stage 1: Lock Picking
            try:
                # Check if message is in format "1-2-3-4"
                if "-" in content and len(content.split("-")) == 4:
                    user_combination = [int(x) for x in content.split("-")]
                    correct_combination = current_challenge["answer"]
                    
                    if user_combination == correct_combination:
                        success = True
                        reward_msg = PRISON_BREAK_REWARDS[f"stage_{stage}"]["message"]
                        await reduce_quarantine_sentence(message.guild, message.author, PRISON_BREAK_REWARDS[f"stage_{stage}"]["sentence_reduction"])
                        
                        await send_feedback(
                            f"🔓 **LOCK PICKED!** {message.author.display_name} cracked the combination! {reward_msg}",
                            f"🔓 **SUCCESS!** You cracked the lock with combination {content}! {reward_msg}"
                        )
                        
                        # Advance to next stage
                        await advance_prison_break_stage(message.guild, guild_id, game_id, game_data)
                    else:
                        # Track failed attempts
                        current_challenge["attempts"] = current_challenge.get("attempts", 0) + 1
                        attempts_left = 3 - current_challenge["attempts"]
                        
                        await send_feedback(
                            f"🔒 {message.author.display_name} tried combination {content} but the lock jammed! Attempt {current_challenge['attempts']}/3",
                            f"❌ **WRONG!** Combination {content} failed. You have {attempts_left} attempts left before the lock breaks!"
                        )
                        
                        # After 3 failed attempts, apply penalty
                        if current_challenge["attempts"] >= 3:
                            failure_msg = PRISON_BREAK_FAILURES[f"stage_{stage}"]["message"]
                            await extend_quarantine_sentence(message.guild, message.author, PRISON_BREAK_FAILURES[f"stage_{stage}"]["sentence_addition"])
                            
                            await send_feedback(
                                f"💥 **LOCK BROKEN!** {message.author.display_name} jammed the lock after too many attempts! {failure_msg}",
                                f"💥 **LOCK BROKEN!** You used all your attempts! {failure_msg} New lock installed - try again!"
                            )
                            # Reset attempts for retry
                            current_challenge["attempts"] = 0
            except ValueError:
                await send_feedback(
                    f"🤔 {message.author.display_name} mumbled something incomprehensible while picking the lock...",
                    f"❓ **Invalid format!** Use format like `1-2-3-4` (numbers with dashes)"
                )
                    
        elif challenge_type == "path":  # Stage 2: Tunnel Digging
            directions = ["north", "south", "east", "west"]
            if content in directions:
                progress = current_challenge.get("progress", [])
                correct_path = current_challenge["answer"]
                
                if len(progress) < len(correct_path) and content == correct_path[len(progress)]:
                    progress.append(content)
                    current_challenge["progress"] = progress
                    
                    if len(progress) == len(correct_path):
                        success = True
                        reward_msg = PRISON_BREAK_REWARDS[f"stage_{stage}"]["message"]
                        await reduce_quarantine_sentence(message.guild, message.author, PRISON_BREAK_REWARDS[f"stage_{stage}"]["sentence_reduction"])
                        
                        await send_feedback(
                            f"🕳️ **TUNNEL COMPLETE!** {message.author.display_name} dug through! Path: {' → '.join(correct_path)} {reward_msg}",
                            f"🕳️ **FREEDOM!** You completed the tunnel! Path was: {' → '.join(correct_path)} {reward_msg}"
                        )
                        
                        await advance_prison_break_stage(message.guild, guild_id, game_id, game_data)
                    else:
                        remaining = len(correct_path) - len(progress)
                        await send_feedback(
                            f"⛏️ {message.author.display_name} dug {content}! Progress: {len(progress)}/{len(correct_path)}",
                            f"✅ **Good!** You dug {content}. Progress: {len(progress)}/{len(correct_path)} - {remaining} more directions needed!"
                        )
                else:
                    await send_feedback(
                        f"💥 {message.author.display_name} hit a rock going {content}! The tunnel collapsed a bit...",
                        f"💥 **WRONG DIRECTION!** You hit a rock going {content}! The tunnel is getting unstable..."
                    )
                        
                    # Track wrong direction attempts
                    current_challenge["wrong_attempts"] = current_challenge.get("wrong_attempts", 0) + 1
                    
                    # After 4 wrong directions, tunnel completely collapses
                    if current_challenge["wrong_attempts"] >= 4:
                        failure_msg = PRISON_BREAK_FAILURES[f"stage_{stage}"]["message"]
                        await extend_quarantine_sentence(message.guild, message.author, PRISON_BREAK_FAILURES[f"stage_{stage}"]["sentence_addition"])
                        
                        await send_feedback(
                            f"🕳️💥 **TUNNEL COLLAPSE!** {message.author.display_name} caused a major cave-in! {failure_msg}",
                            f"🕳️💥 **TUNNEL COLLAPSED!** Too many wrong turns! {failure_msg} Starting over with a new tunnel..."
                        )
                        # Reset progress and attempts for retry
                        current_challenge["progress"] = []
                        current_challenge["wrong_attempts"] = 0
            else:
                await send_feedback(
                    f"🤔 {message.author.display_name} said '{content}' but that's not a direction...",
                    f"❓ **Invalid direction!** Use: `north`, `south`, `east`, or `west`"
                )
        
        elif challenge_type == "stealth":  # Stage 3: Guard Evasion
            safe_spots = ["behind tree", "under truck", "in shadows", "behind dumpster", "in alcove"]
            if content in safe_spots:
                correct_spot = current_challenge["answer"]
                
                if content == correct_spot:
                    success = True
                    reward_msg = PRISON_BREAK_REWARDS[f"stage_{stage}"]["message"]
                    await reduce_quarantine_sentence(message.guild, message.author, PRISON_BREAK_REWARDS[f"stage_{stage}"]["sentence_reduction"])
                    
                    await send_feedback(
                        f"👮 **GUARDS EVADED!** {message.author.display_name} hid {content} and slipped past! {reward_msg}",
                        f"👮 **PERFECT HIDING!** You hid {content} and the guards passed by! {reward_msg}"
                    )
                    
                    await advance_prison_break_stage(message.guild, guild_id, game_id, game_data)
                else:
                    current_challenge["attempts"] += 1
                    attempts_left = 4 - current_challenge["attempts"]
                    
                    await send_feedback(
                        f"🚨 {message.author.display_name} tried to hide {content} but a guard spotted them! Attempt {current_challenge['attempts']}/4",
                        f"🚨 **SPOTTED!** A guard saw you {content}! {attempts_left} attempts left before full alert!"
                    )
                        
                    # After 4 failed hiding attempts, guards become fully alert
                    if current_challenge["attempts"] >= 4:
                        failure_msg = PRISON_BREAK_FAILURES[f"stage_{stage}"]["message"]
                        await extend_quarantine_sentence(message.guild, message.author, PRISON_BREAK_FAILURES[f"stage_{stage}"]["sentence_addition"])
                        
                        await send_feedback(
                            f"👮🚨 **GUARDS ALERTED!** {message.author.display_name} was spotted too many times! {failure_msg}",
                            f"👮🚨 **FULL ALERT!** Guards are everywhere now! {failure_msg} Wait for them to calm down..."
                        )
                        # Reset attempts for retry
                        current_challenge["attempts"] = 0
            else:
                await send_feedback(
                    f"🤔 {message.author.display_name} said '{content}' but that's not a hiding spot...",
                    f"❓ **Invalid hiding spot!** Use: `behind tree`, `under truck`, `in shadows`, `behind dumpster`, or `in alcove`"
                )
        
        elif challenge_type == "teamwork":  # Stage 4: Great Escape
            code_word = current_challenge["code_word"]
            if content == code_word:
                players_ready = current_challenge.get("players_ready", [])
                if message.author.id not in players_ready:
                    players_ready.append(message.author.id)
                    current_challenge["players_ready"] = players_ready
                    
                # Check if all players are ready
                if len(players_ready) == len(game_data["players"]):
                    success = True
                    reward_msg = PRISON_BREAK_REWARDS[f"stage_{stage}"]["message"]
                    
                    # Reduce sentence for all players
                    for player_id in game_data["players"]:
                        member = message.guild.get_member(player_id)
                        if member:
                            await reduce_quarantine_sentence(message.guild, member, PRISON_BREAK_REWARDS[f"stage_{stage}"]["sentence_reduction"])
                        
                    player_names = []
                    for player_id in game_data["players"]:
                        member = message.guild.get_member(player_id)
                        if member:
                            player_names.append(member.display_name)
                    
                    await send_feedback(
                        f"🚗 **FREEDOM ACHIEVED!** All prisoners ({', '.join(player_names)}) escaped together! {reward_msg}",
                        f"🚗 **ESCAPE SUCCESSFUL!** You all said '{code_word}' together and escaped! {reward_msg}"
                    )
                        
                    # End the game
                    game_data["active"] = False
                    game_data["completed"] = True
                else:
                    remaining = len(game_data["players"]) - len(players_ready)
                    await send_feedback(
                        f"🤝 {message.author.display_name} is ready to escape! Waiting for {remaining} more prisoner(s)...",
                        f"🤝 **CORRECT CODE!** You said '{code_word}'! Waiting for {remaining} more prisoner(s) to say the same thing..."
                    )
            else:
                # Wrong code word attempt
                current_challenge["wrong_codes"] = current_challenge.get("wrong_codes", 0) + 1
                codes_left = 5 - current_challenge["wrong_codes"]
                
                await send_feedback(
                    f"❌ {message.author.display_name} said '{content}' but that's not the escape code!",
                    f"❌ **WRONG CODE!** '{content}' is not the escape word. {codes_left} attempts left before authorities get suspicious!"
                )
                
                # After 5 wrong code attempts across all players, authorities get suspicious
                if current_challenge["wrong_codes"] >= 5:
                    failure_msg = PRISON_BREAK_FAILURES[f"stage_{stage}"]["message"]
                    # Apply penalty to all players
                    for player_id in game_data["players"]:
                        member = message.guild.get_member(player_id)
                        if member:
                            await extend_quarantine_sentence(message.guild, member, PRISON_BREAK_FAILURES[f"stage_{stage}"]["sentence_addition"])
                    
                    await send_feedback(
                        f"🚨💥 **ESCAPE FOILED!** Too many wrong codes alerted the authorities! {failure_msg}",
                        f"🚨💥 **AUTHORITIES ALERTED!** Too many wrong codes! {failure_msg} They're onto you - be more careful!"
                    )
                    # Reset for retry
                    current_challenge["wrong_codes"] = 0
                    current_challenge["players_ready"] = []
        
        # Save progress
        save_prison_break_data(prison_break_data)
        
        # Apply spectator vote effects
        help_votes = game_data["spectator_votes"]["help"]
        sabotage_votes = game_data["spectator_votes"]["sabotage"]
        
        if help_votes > sabotage_votes and help_votes > 2:
            # Spectators are helping - increase success chance
            if not success and random.random() < 0.3:  # 30% chance for spectator help to save the day
                await send_feedback(
                    "✨ **SPECTATOR ASSISTANCE WORKED!** The crowd's help made all the difference!",
                    "✨ **SPECTATOR HELP!** The crowd's assistance saved you from failure!"
                )
                # Don't override success but give a small sentence reduction
                await reduce_quarantine_sentence(message.guild, message.author, 2)
                
        elif sabotage_votes > help_votes and sabotage_votes > 2:
            # Spectators are sabotaging - decrease success chance
            if success and random.random() < 0.2:  # 20% chance for sabotage to ruin success
                success = False
                await send_feedback(
                    "💥 **SABOTAGE SUCCESSFUL!** The crowd's interference ruined the escape!",
                    "💥 **SABOTAGED!** Spectators interfered and ruined your attempt!"
                )
                await extend_quarantine_sentence(message.guild, message.author, 3)
        
    except Exception as e:
        print(f"Error handling prison break attempt: {e}")

async def advance_prison_break_stage(guild, guild_id, game_id, game_data):
    """Advance the prison break game to the next stage"""
    try:
        current_stage = game_data["stage"]
        
        if current_stage < 4:
            # Advance to next stage
            next_stage = current_stage + 1
            game_data["stage"] = next_stage
            game_data["challenges_completed"].append(current_stage)
            
            # Reset spectator votes for new stage
            game_data["spectator_votes"] = {"help": 0, "sabotage": 0}
            
            # Reset challenges for new stage
            game_data["current_challenge"] = None
            
            # Start the next stage challenge
            await start_stage_challenge(guild, game_id, next_stage)
                
        else:
            # Game is over
            game_data["active"] = False
            game_data["completed"] = True
            game_data["completed_at"] = str(datetime.datetime.now(UTC))
                
    except Exception as e:
        print(f"Error advancing prison break stage: {e}") 