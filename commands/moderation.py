import discord
import datetime
from discord import app_commands
from discord.ext import commands
from typing import Optional

from config import UTC
from data_manager import warnings_data, save_warnings

async def setup_moderation_commands(bot):
    """Setup basic moderation commands"""
    
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
                "timestamp": str(datetime.datetime.now(UTC)),
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