import discord
import datetime
import asyncio
import re
from discord import app_commands
from typing import Optional

from config import UTC
from data_manager import save_warnings, warnings_data

async def setup_mass_moderation_commands(bot):
    """Setup mass moderation commands including purgewords"""
    
    @bot.tree.command(name="purgewords", description="Delete ALL messages containing specific words in a channel")
    @app_commands.describe(
        channel="The channel to scan", 
        words="Words to search for (space separated)", 
        user="Optional: Only delete messages from this user",
        batch_size="Optional: Number of messages to process in each batch (10-1000)",
        silent="Optional: Whether to silently delete without showing a report",
        exact_match="Optional: Whether words must match exactly or can be part of other words",
        older_than="Optional: Only scan messages older than this many days",
        newer_than="Optional: Only scan messages newer than this many days",
        report_channel="Optional: Channel to send the complete report to"
    )
    @app_commands.default_permissions(manage_messages=True)
    async def purgewords(interaction: discord.Interaction, channel: discord.TextChannel, words: str, 
                         user: Optional[discord.Member] = None, batch_size: int = 100, silent: bool = False,
                         exact_match: bool = False, older_than: int = 0, newer_than: int = 0,
                         report_channel: Optional[discord.TextChannel] = None):
        try:
            # Immediately defer the response as this could take time
            await interaction.response.defer(ephemeral=True)
            
            # Parse the words to search for
            search_words = [word.lower().strip() for word in words.split() if word.strip()]
            
            if not search_words:
                await interaction.followup.send("Please provide at least one word to search for.", ephemeral=True)
                return
                
            # Validate batch_size
            batch_size = max(10, min(batch_size, 1000))  # Ensure batch size is between 10 and 1000
            
            # Create progress message
            progress = await interaction.followup.send(
                f"🔍 **SUPER SCAN MODE**: Scanning all messages in {channel.mention} for: `{', '.join(search_words)}`\n" +
                f"Processing in batches of {batch_size} messages at a time...", 
                ephemeral=True
            )
            
            # Stats tracking
            total_scanned = 0
            total_matched = 0
            total_deleted = 0
            total_batches = 0
            rate_limited_count = 0
            batch_stats = []
            
            # Calculate date filters if specified
            now = datetime.datetime.now(UTC)
            older_than_date = None if older_than <= 0 else now - datetime.timedelta(days=older_than)
            newer_than_date = None if newer_than <= 0 else now - datetime.timedelta(days=newer_than)
            
            # Flag to track if we've reached the end of messages
            reached_end = False
            last_message_id = None
            
            # Log to store deleted message samples
            message_samples = []
            
            # Process messages in batches until we've covered the entire channel
            while not reached_end:
                # Create a batch
                batch_number = total_batches + 1
                await progress.edit(content=f"🔍 Scanning batch #{batch_number} in {channel.mention}...\n" +
                                    f"Total scanned so far: {total_scanned} messages")
                
                # Get messages for this batch
                try:
                    if last_message_id:
                        # Get messages before the last one we processed
                        messages = []
                        async for msg in channel.history(limit=batch_size, before=discord.Object(id=last_message_id)):
                            messages.append(msg)
                    else:
                        # First batch - get most recent messages
                        messages = []
                        async for msg in channel.history(limit=batch_size):
                            messages.append(msg)
                except Exception as e:
                    await progress.edit(content=f"Error retrieving messages: {str(e)}")
                    break
                    
                # Check if we've reached the end of the channel history
                if not messages:
                    reached_end = True
                    break
                    
                # Save the ID of the last message in this batch
                last_message_id = messages[-1].id
                
                # Track stats for this batch
                batch_scanned = len(messages)
                batch_matched = 0
                batch_deleted = 0
                batch_messages = []
                
                # Process each message in the batch
                for message in messages:
                    # Skip if doesn't match our filters
                    if user and message.author.id != user.id:
                        continue
                        
                    # Skip if doesn't match date filters
                    if older_than_date and message.created_at > older_than_date:
                        continue
                    if newer_than_date and message.created_at < newer_than_date:
                        continue
                        
                    # Check if message content matches the search words
                    content = message.content.lower()
                    match_found = False
                    
                    if exact_match:
                        # Split content into words and check for exact matches
                        message_words = re.findall(r'\b\w+\b', content)
                        match_found = any(word in message_words for word in search_words)
                    else:
                        # Check if any search word is contained within the content
                        match_found = any(word in content for word in search_words)
                        
                    if match_found:
                        batch_matched += 1
                        total_matched += 1
                        
                        # Keep track of matched message content for logs
                        msg_info = f"[{message.author.display_name}]: {message.content[:100]}"
                        if len(message.content) > 100:
                            msg_info += "..."
                        batch_messages.append(msg_info)
                        
                        # Only store first 50 samples to avoid memory issues
                        if len(message_samples) < 50:
                            message_samples.append(msg_info)
                        
                        # Try to delete the message
                        try:
                            retry_count = 0
                            max_retries = 3
                            deletion_success = False
                            
                            while not deletion_success and retry_count < max_retries:
                                try:
                                    await message.delete()
                                    batch_deleted += 1
                                    total_deleted += 1
                                    deletion_success = True
                                    
                                    # Add delay between deletions to manage rate limits
                                    await asyncio.sleep(0.8)  # 800ms delay
                                except discord.errors.HTTPException as e:
                                    if e.status == 429:  # Rate limited
                                        rate_limited_count += 1
                                        retry_count += 1
                                        
                                        # Extract retry_after from exception or use increasing backoff
                                        retry_after = getattr(e, 'retry_after', 1.5 * retry_count)
                                        
                                        # Update progress with rate limit info
                                        await progress.edit(content=f"⚠️ Rate limited! Waiting {retry_after:.1f}s before continuing...\n" +
                                                            f"Batch #{batch_number}: {batch_deleted}/{batch_matched} deleted so far")
                                        
                                        # Wait before retrying
                                        await asyncio.sleep(retry_after)
                                    else:
                                        # Other HTTP error, skip this message
                                        break
                                except Exception:
                                    # Any other error, skip this message
                                    break
                            
                            # If we couldn't delete after max retries, log it
                            if not deletion_success:
                                print(f"Failed to delete message after {max_retries} attempts: {message.id}")
                        except Exception as e:
                            print(f"Error deleting message: {e}")
                
                # Update batch stats
                total_scanned += batch_scanned
                total_batches += 1
                
                # Store this batch's stats
                batch_stats.append({
                    "batch": batch_number,
                    "scanned": batch_scanned,
                    "matched": batch_matched,
                    "deleted": batch_deleted,
                    "oldest_msg_id": last_message_id
                })
                
                # Update progress with batch results
                batch_info = f"✅ Batch #{batch_number} complete:\n"
                batch_info += f"- Scanned: {batch_scanned} messages\n"
                batch_info += f"- Matched: {batch_matched} messages\n"
                batch_info += f"- Deleted: {batch_deleted} messages\n\n"
                batch_info += f"📊 Running Total:\n"
                batch_info += f"- Total Scanned: {total_scanned} messages\n"
                batch_info += f"- Total Deleted: {total_deleted}/{total_matched} messages\n"
                batch_info += f"- Rate Limits: {rate_limited_count} occurrences\n\n"
                
                if not reached_end:
                    batch_info += "⏳ Continuing to next batch..."
                
                await progress.edit(content=batch_info)
                
                # If this batch had no matches, do a shorter delay
                if batch_matched == 0:
                    await asyncio.sleep(1)  # 1 second between batches with no matches
                else:
                    # Allow a bit more time between batches with matches
                    await asyncio.sleep(2)  # 2 seconds between batches with matches
            
            # Create final report embed and buttons
            if total_batches == 0:
                result_title = "❌ No messages found"
                result_description = "No messages were found matching your criteria in this channel."
                result_color = discord.Color.light_grey()
            else:
                result_title = f"🏁 SUPER SCAN COMPLETE!"
                result_description = f"{interaction.user.mention} purged {total_deleted} messages containing target words."
                result_color = discord.Color.green() if total_deleted > 0 else discord.Color.gold()
            
            # Create embed for results
            result_embed = discord.Embed(
                title=result_title,
                description=result_description,
                color=result_color,
                timestamp=datetime.datetime.now(UTC)
            )
            
            # Add main stats fields
            result_embed.add_field(name="📊 Messages Scanned", value=str(total_scanned), inline=True)
            result_embed.add_field(name="🔍 Matches Found", value=str(total_matched), inline=True)
            result_embed.add_field(name="🗑️ Messages Deleted", value=str(total_deleted), inline=True)
            
            # Add filter information
            filters_info = []
            if user:
                filters_info.append(f"👤 User: {user.mention}")
            if exact_match:
                filters_info.append("🔤 Exact word matches only")
            if older_than > 0:
                filters_info.append(f"📅 Older than {older_than} days")
            if newer_than > 0:
                filters_info.append(f"📅 Newer than {newer_than} days")
                
            if filters_info:
                result_embed.add_field(
                    name="🔧 Filters Applied", 
                    value="\n".join(filters_info),
                    inline=False
                )
            
            # Create a View for interactive buttons
            class PurgeActionView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=300)  # 5 minute timeout
                    
                @discord.ui.button(label="Show Message Samples", style=discord.ButtonStyle.primary, emoji="💬", disabled=len(message_samples)==0)
                async def show_samples(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    # Show sample of deleted messages
                    if message_samples:
                        samples = "\n".join(message_samples[:10])
                        if len(samples) > 1024:
                            samples = samples[:1020] + "..."
                        
                        sample_embed = discord.Embed(
                            title="💬 Deleted Message Samples",
                            description=samples,
                            color=discord.Color.blue()
                        )
                        await button_interaction.response.send_message(embed=sample_embed, ephemeral=True)
                    else:
                        await button_interaction.response.send_message("No message samples available.", ephemeral=True)
                
                @discord.ui.button(label="Done", style=discord.ButtonStyle.danger, emoji="✖️")
                async def close_menu(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                    # Disable all buttons
                    for child in self.children:
                        child.disabled = True
                    await button_interaction.response.edit_message(view=self)
            
            # Send to mod-logs if available
            try:
                log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
                if log_channel:
                    log_embed = discord.Embed(
                        title=f"🧹 Channel Purge Completed",
                        description=f"{interaction.user.mention} purged {total_deleted} messages in {channel.mention}.",
                        color=discord.Color.red(),
                        timestamp=datetime.datetime.now(UTC)
                    )
                    log_embed.add_field(name="Target Words", value=f"`{', '.join(search_words)}`", inline=True)
                    log_embed.add_field(name="Messages Scanned", value=str(total_scanned), inline=True)
                    log_embed.add_field(name="Messages Deleted", value=str(total_deleted), inline=True)
                    await log_channel.send(embed=log_embed)
            except Exception as e:
                print(f"Error sending purge log: {e}")
            
            # Send final report to user with buttons
            await progress.edit(content=None, embed=result_embed, view=PurgeActionView())
            
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

    @bot.tree.command(name="clean", description="Delete messages matching specific criteria")
    @app_commands.describe(
        amount="Number of messages to check",
        type="Type of messages to delete",
        channel="Channel to clean (defaults to current channel)"
    )
    @app_commands.choices(type=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Bot messages", value="bot"),
        app_commands.Choice(name="User messages", value="user"),
        app_commands.Choice(name="Embeds", value="embed"),
        app_commands.Choice(name="Files/Attachments", value="file"),
        app_commands.Choice(name="Links", value="link"),
        app_commands.Choice(name="Invites", value="invite")
    ])
    @app_commands.default_permissions(manage_messages=True)
    async def clean(interaction: discord.Interaction, amount: int = 10, type: str = "all", 
                    channel: Optional[discord.TextChannel] = None):
        try:
            # Validate amount
            if amount <= 0 or amount > 1000:
                await interaction.response.send_message("Please provide a valid amount between 1 and 1000.", ephemeral=True)
                return
                
            # Determine target channel
            target_channel = channel or interaction.channel
            
            # Defer response for long operation
            await interaction.response.defer(ephemeral=True)
            
            # Create progress message
            progress = await interaction.followup.send(f"Searching for messages to delete in {target_channel.mention}...", ephemeral=True)
            
            # Define the filter based on type
            def message_filter(message):
                if type == "all":
                    return True
                elif type == "bot":
                    return message.author.bot
                elif type == "user":
                    return not message.author.bot
                elif type == "embed":
                    return len(message.embeds) > 0
                elif type == "file":
                    return len(message.attachments) > 0
                elif type == "link":
                    # Simple link detection regex
                    return bool(re.search(r'https?://\S+', message.content))
                elif type == "invite":
                    # Discord invite link detection
                    return bool(re.search(r'discord(?:\.gg|app\.com/invite)/[a-zA-Z0-9]+', message.content))
                return False
                
            # Get messages and filter them
            deleted_count = 0
            last_report_time = datetime.datetime.now()
            
            async for message in target_channel.history(limit=amount):
                if message_filter(message):
                    try:
                        await message.delete()
                        deleted_count += 1
                        
                        # Update progress periodically
                        now = datetime.datetime.now()
                        if deleted_count % 5 == 0 or (now - last_report_time).total_seconds() > 3:
                            await progress.edit(content=f"Deleting messages... Removed {deleted_count} so far.")
                            last_report_time = now
                    except:
                        pass
                        
            # Create final report
            await progress.edit(content=f"✅ Clean complete! Deleted {deleted_count} messages matching criteria: {type}.")
            
            # Log to mod-logs
            try:
                log_channel = discord.utils.get(interaction.guild.text_channels, name="mod-logs")
                if log_channel:
                    log_embed = discord.Embed(
                        title="Channel Cleaned",
                        description=f"{interaction.user.mention} cleaned {target_channel.mention}.",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now(UTC)
                    )
                    log_embed.add_field(name="Filter", value=type, inline=True)
                    log_embed.add_field(name="Deleted", value=str(deleted_count), inline=True)
                    await log_channel.send(embed=log_embed)
            except:
                pass
                
        except discord.Forbidden:
            await interaction.followup.send("I don't have permission to delete messages in that channel.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True) 