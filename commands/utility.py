import discord
import datetime
from discord import app_commands
from typing import Optional

from config import UTC
from data_manager import warnings_data, notes_data, save_notes

async def setup_utility_commands(bot):
    """Setup utility commands"""
    
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

    @bot.tree.command(name="serverinfo", description="Get detailed information about the server")
    async def server_info(interaction: discord.Interaction):
        try:
            guild = interaction.guild
            
            # Count members by status
            total_members = len(guild.members)
            humans = sum(1 for m in guild.members if not m.bot)
            bots = sum(1 for m in guild.members if m.bot)
            
            # Count channel types
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            threads = sum(1 for c in guild.threads)
            
            # Count roles
            role_count = len(guild.roles) - 1  # Subtract @everyone
            
            # Create embed
            embed = discord.Embed(
                title=f"{guild.name} Server Information",
                description=guild.description or "No description set",
                color=discord.Color.blue()
            )
            
            # Set thumbnail to server icon
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
                
            # General info
            embed.add_field(name="Owner", value=f"<@{guild.owner_id}>", inline=True)
            embed.add_field(name="Server ID", value=guild.id, inline=True)
            embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
            
            # Member counts
            embed.add_field(name="Members", value=f"👥 Total: {total_members}\n👤 Humans: {humans}\n🤖 Bots: {bots}", inline=True)
            
            # Channel counts
            embed.add_field(name="Channels", value=f"💬 Text: {text_channels}\n🎤 Voice: {voice_channels}\n📁 Categories: {categories}\n🧳 Threads: {threads}", inline=True)
            
            # Feature info
            embed.add_field(name="Roles", value=f"🎖️ {role_count}", inline=True)
            
            # Server features
            if guild.features:
                features = "\n".join([f"• {feature.replace('_', ' ').title()}" for feature in guild.features])
                embed.add_field(name="Server Features", value=features or "None", inline=False)
                
            # Boost status
            boost_level = f"Level {guild.premium_tier}"
            boost_count = guild.premium_subscription_count
            embed.add_field(name="Boost Status", value=f"{boost_level} ({boost_count} boosts)", inline=False)
            
            await interaction.response.send_message(embed=embed)
                
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @bot.tree.command(name="note", description="Add a note about a user (only visible to mods)")
    @app_commands.describe(user="The user to add a note about", note="The note content")
    @app_commands.default_permissions(moderate_members=True)
    async def add_note(interaction: discord.Interaction, user: discord.Member, note: str):
        try:
            # Initialize data structure if needed
            guild_id = str(interaction.guild.id)
            user_id = str(user.id)
            
            if guild_id not in notes_data:
                notes_data[guild_id] = {}
                
            if user_id not in notes_data[guild_id]:
                notes_data[guild_id][user_id] = []
                
            # Add the note
            note_entry = {
                "content": note,
                "author_id": str(interaction.user.id),
                "author_name": interaction.user.display_name,
                "timestamp": str(datetime.datetime.now(UTC))
            }
            
            notes_data[guild_id][user_id].append(note_entry)
            save_notes(notes_data)
            
            # Get total notes count
            note_count = len(notes_data[guild_id][user_id])
            
            await interaction.response.send_message(f"Added note about {user.mention}. They now have {note_count} notes.", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True) 