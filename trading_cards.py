import discord
from discord.ext import commands, tasks
import sqlite3
import random
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import aiohttp

class TradingCards(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_database()
        # Only start random drops if we have an event loop running
        try:
            if bot.loop and bot.loop.is_running():
                self.random_drops.start()
        except Exception:
            # In case there's no loop or bot isn't fully initialized yet
            pass
        
    def init_database(self):
        """Initialize SQLite database for trading cards"""
        self.conn = sqlite3.connect('trading_cards.db')
        self.cursor = self.conn.cursor()
        
        # Cards table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                rarity TEXT NOT NULL,
                image_url TEXT,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # User collections table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                obtained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES cards (id)
            )
        ''')
        
        # Trading history table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_user INTEGER NOT NULL,
                to_user INTEGER NOT NULL,
                card_id INTEGER NOT NULL,
                traded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (card_id) REFERENCES cards (id)
            )
        ''')
        
        # User settings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                last_daily TIMESTAMP,
                total_cards INTEGER DEFAULT 0,
                cards_found INTEGER DEFAULT 0
            )
        ''')
        
        self.conn.commit()

    @commands.group(name='card', invoke_without_command=True)
    async def card_group(self, ctx):
        """Trading card commands"""
        embed = discord.Embed(
            title="🃏 Trading Card System",
            description="Available commands:",
            color=0x7289da
        )
        embed.add_field(
            name="🎯 Collection",
            value="`!card collection` - View your cards\n`!card daily` - Daily card claim\n`!card info <name>` - Card details",
            inline=False
        )
        embed.add_field(
            name="🔄 Trading",
            value="`!card trade @user <your_card> <their_card>` - Propose trade\n`!card gift @user <card>` - Gift a card",
            inline=False
        )
        embed.add_field(
            name="📊 Stats",
            value="`!card stats` - Your collection stats\n`!card leaderboard` - Top collectors\n`!card search <name>` - Find cards",
            inline=False
        )
        if ctx.author.guild_permissions.administrator:
            embed.add_field(
                name="⚙️ Admin",
                value="`!card create` - Create new card\n`!card list` - All cards\n`!card give @user <card>` - Give card",
                inline=False
            )
        await ctx.send(embed=embed)

    @card_group.command(name='create')
    @commands.has_permissions(administrator=True)
    async def create_card(self, ctx):
        """Create a new trading card (Admin only)"""
        embed = discord.Embed(
            title="🎨 Create New Trading Card",
            description="Let's create a new card! I'll ask you some questions.",
            color=0x00ff00
        )
        await ctx.send(embed=embed)
        
        def check(message):
            return message.author == ctx.author and message.channel == ctx.channel
        
        try:
            # Get card name
            await ctx.send("**What's the card name?**")
            name_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            card_name = name_msg.content.strip()
            
            # Check if card exists
            self.cursor.execute("SELECT id FROM cards WHERE name = ?", (card_name,))
            if self.cursor.fetchone():
                await ctx.send("❌ A card with that name already exists!")
                return
            
            # Get description
            await ctx.send("**Card description? (or 'skip')**")
            desc_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            description = desc_msg.content.strip() if desc_msg.content.lower() != 'skip' else ""
            
            # Get rarity
            rarity_embed = discord.Embed(
                title="🌟 Choose Rarity",
                description="1️⃣ Common (70% drop rate)\n2️⃣ Uncommon (20% drop rate)\n3️⃣ Rare (8% drop rate)\n4️⃣ Legendary (2% drop rate)",
                color=0xffd700
            )
            await ctx.send(embed=rarity_embed)
            
            rarity_msg = await self.bot.wait_for('message', check=check, timeout=60.0)
            rarity_map = {'1': 'Common', '2': 'Uncommon', '3': 'Rare', '4': 'Legendary'}
            rarity = rarity_map.get(rarity_msg.content.strip(), 'Common')
            
            # Get image
            await ctx.send("**Upload an image for the card or paste image URL** (or 'skip' for no image)")
            image_msg = await self.bot.wait_for('message', check=check, timeout=120.0)
            
            image_url = None
            if image_msg.content.lower() != 'skip':
                if image_msg.attachments:
                    # Save uploaded image
                    attachment = image_msg.attachments[0]
                    if attachment.content_type and attachment.content_type.startswith('image/'):
                        # Create cards directory if it doesn't exist
                        os.makedirs('card_images', exist_ok=True)
                        image_path = f"card_images/{card_name.replace(' ', '_')}.{attachment.filename.split('.')[-1]}"
                        await attachment.save(image_path)
                        image_url = image_path
                    else:
                        await ctx.send("⚠️ Please upload an image file!")
                        return
                elif image_msg.content.startswith('http'):
                    image_url = image_msg.content.strip()
            
            # Save to database
            self.cursor.execute(
                "INSERT INTO cards (name, description, rarity, image_url, created_by) VALUES (?, ?, ?, ?, ?)",
                (card_name, description, rarity, image_url, ctx.author.id)
            )
            self.conn.commit()
            
            # Confirmation
            card_embed = discord.Embed(
                title=f"✅ Card Created: {card_name}",
                description=description,
                color=self.get_rarity_color(rarity)
            )
            card_embed.add_field(name="Rarity", value=f"{self.get_rarity_emoji(rarity)} {rarity}", inline=True)
            card_embed.add_field(name="Created by", value=ctx.author.mention, inline=True)
            
            if image_url:
                if image_url.startswith('http'):
                    card_embed.set_image(url=image_url)
                else:
                    # For local files, we'd need to upload them to Discord
                    file = discord.File(image_url)
                    await ctx.send(embed=card_embed, file=file)
                    return
            
            await ctx.send(embed=card_embed)
            
        except asyncio.TimeoutError:
            await ctx.send("⏰ Card creation timed out. Try again!")

    @card_group.command(name='daily')
    async def daily_card(self, ctx):
        """Claim your daily card"""
        user_id = ctx.author.id
        
        # Check last daily claim
        self.cursor.execute("SELECT last_daily FROM user_settings WHERE user_id = ?", (user_id,))
        result = self.cursor.fetchone()
        
        now = datetime.now()
        if result and result[0]:
            last_daily = datetime.fromisoformat(result[0])
            if (now - last_daily).total_seconds() < 86400:  # 24 hours
                time_left = 86400 - (now - last_daily).total_seconds()
                hours = int(time_left // 3600)
                minutes = int((time_left % 3600) // 60)
                await ctx.send(f"⏰ Daily already claimed! Next claim in {hours}h {minutes}m")
                return
        
        # Get random card
        card = self.get_random_card()
        if not card:
            await ctx.send("❌ No cards available! Ask an admin to create some cards.")
            return
        
        # Give card to user
        self.cursor.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user_id, card[0]))
        
        # Update user settings
        self.cursor.execute(
            "INSERT OR REPLACE INTO user_settings (user_id, last_daily, total_cards, cards_found) VALUES (?, ?, COALESCE((SELECT total_cards FROM user_settings WHERE user_id = ?), 0) + 1, COALESCE((SELECT cards_found FROM user_settings WHERE user_id = ?), 0) + 1)",
            (user_id, now.isoformat(), user_id, user_id)
        )
        self.conn.commit()
        
        # Send card
        embed = discord.Embed(
            title="🎁 Daily Card Claimed!",
            description=f"You got: **{card[1]}**",
            color=self.get_rarity_color(card[3])
        )
        embed.add_field(name="Rarity", value=f"{self.get_rarity_emoji(card[3])} {card[3]}", inline=True)
        if card[2]:
            embed.add_field(name="Description", value=card[2], inline=False)
        
        if card[4]:  # image_url
            if card[4].startswith('http'):
                embed.set_image(url=card[4])
            else:
                try:
                    file = discord.File(card[4])
                    await ctx.send(embed=embed, file=file)
                    return
                except:
                    pass
        
        await ctx.send(embed=embed)

    @card_group.command(name='collection')
    async def view_collection(self, ctx, user: Optional[discord.Member] = None):
        """View your or someone else's card collection"""
        target_user = user or ctx.author
        
        # Get user's cards
        self.cursor.execute('''
            SELECT c.name, c.rarity, COUNT(*) as count, c.description, c.image_url
            FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id = ?
            GROUP BY c.id
            ORDER BY 
                CASE c.rarity 
                    WHEN 'Legendary' THEN 1 
                    WHEN 'Rare' THEN 2 
                    WHEN 'Uncommon' THEN 3 
                    WHEN 'Common' THEN 4 
                END, c.name
        ''', (target_user.id,))
        
        cards = self.cursor.fetchall()
        
        if not cards:
            await ctx.send(f"📭 {target_user.display_name} has no cards yet!")
            return
        
        # Create pages
        cards_per_page = 10
        pages = [cards[i:i + cards_per_page] for i in range(0, len(cards), cards_per_page)]
        current_page = 0
        
        embed = self.create_collection_embed(target_user, pages[current_page], current_page + 1, len(pages))
        
        if len(pages) == 1:
            await ctx.send(embed=embed)
            return
        
        # Add navigation for multiple pages
        message = await ctx.send(embed=embed)
        await message.add_reaction('⬅️')
        await message.add_reaction('➡️')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['⬅️', '➡️'] and reaction.message.id == message.id
        
        while True:
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                if str(reaction.emoji) == '➡️' and current_page < len(pages) - 1:
                    current_page += 1
                elif str(reaction.emoji) == '⬅️' and current_page > 0:
                    current_page -= 1
                
                embed = self.create_collection_embed(target_user, pages[current_page], current_page + 1, len(pages))
                await message.edit(embed=embed)
                await message.remove_reaction(reaction, user)
                
            except asyncio.TimeoutError:
                break

    @card_group.command(name='trade')
    async def trade_card(self, ctx, user: discord.Member, your_card: str, their_card: str):
        """Trade cards with another user"""
        if user == ctx.author:
            await ctx.send("❌ You can't trade with yourself!")
            return
        
        # Check if both users have the cards
        your_card_id = self.get_user_card_id(ctx.author.id, your_card)
        their_card_id = self.get_user_card_id(user.id, their_card)
        
        if not your_card_id:
            await ctx.send(f"❌ You don't have a card named '{your_card}'!")
            return
        
        if not their_card_id:
            await ctx.send(f"❌ {user.display_name} doesn't have a card named '{their_card}'!")
            return
        
        # Create trade proposal
        embed = discord.Embed(
            title="🔄 Trade Proposal",
            description=f"{ctx.author.mention} wants to trade with {user.mention}",
            color=0xffa500
        )
        embed.add_field(name=f"{ctx.author.display_name} offers", value=your_card, inline=True)
        embed.add_field(name=f"{user.display_name} gives", value=their_card, inline=True)
        embed.add_field(name="Action", value=f"{user.mention}, react with ✅ to accept or ❌ to decline", inline=False)
        
        message = await ctx.send(embed=embed)
        await message.add_reaction('✅')
        await message.add_reaction('❌')
        
        def check(reaction, reacting_user):
            return reacting_user == user and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id
        
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
            
            if str(reaction.emoji) == '✅':
                # Execute trade
                self.execute_trade(ctx.author.id, user.id, your_card_id, their_card_id)
                
                embed = discord.Embed(
                    title="✅ Trade Completed!",
                    description=f"{ctx.author.mention} and {user.mention} successfully traded cards!",
                    color=0x00ff00
                )
                embed.add_field(name="Trade Details", value=f"{ctx.author.display_name} received: {their_card}\n{user.display_name} received: {your_card}", inline=False)
                await message.edit(embed=embed)
            else:
                embed = discord.Embed(
                    title="❌ Trade Declined",
                    description=f"{user.display_name} declined the trade.",
                    color=0xff0000
                )
                await message.edit(embed=embed)
                
        except asyncio.TimeoutError:
            embed = discord.Embed(
                title="⏰ Trade Expired",
                description="Trade proposal timed out.",
                color=0x808080
            )
            await message.edit(embed=embed)

    @card_group.command(name='gift')
    async def gift_card(self, ctx, user: discord.Member, card_name: str):
        """Gift a card to another user"""
        if user == ctx.author:
            await ctx.send("❌ You can't gift to yourself!")
            return
        
        card_id = self.get_user_card_id(ctx.author.id, card_name)
        if not card_id:
            await ctx.send(f"❌ You don't have a card named '{card_name}'!")
            return
        
        # Transfer card
        self.cursor.execute("UPDATE user_cards SET user_id = ? WHERE id = ?", (user.id, card_id))
        self.conn.commit()
        
        embed = discord.Embed(
            title="🎁 Card Gifted!",
            description=f"{ctx.author.mention} gifted **{card_name}** to {user.mention}!",
            color=0xffd700
        )
        await ctx.send(embed=embed)

    @card_group.command(name='info')
    async def card_info(self, ctx, *, card_name: str):
        """Get detailed information about a card"""
        self.cursor.execute("SELECT * FROM cards WHERE name LIKE ?", (f"%{card_name}%",))
        card = self.cursor.fetchone()
        
        if not card:
            await ctx.send(f"❌ No card found matching '{card_name}'!")
            return
        
        # Get ownership stats
        self.cursor.execute("SELECT COUNT(*) FROM user_cards WHERE card_id = ?", (card[0],))
        total_owned = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_cards WHERE card_id = ?", (card[0],))
        unique_owners = self.cursor.fetchone()[0]
        
        embed = discord.Embed(
            title=f"🃏 {card[1]}",
            description=card[2] or "No description",
            color=self.get_rarity_color(card[3])
        )
        embed.add_field(name="Rarity", value=f"{self.get_rarity_emoji(card[3])} {card[3]}", inline=True)
        embed.add_field(name="Total Owned", value=str(total_owned), inline=True)
        embed.add_field(name="Unique Owners", value=str(unique_owners), inline=True)
        embed.add_field(name="Created", value=card[6][:10], inline=True)
        
        if card[4]:  # image_url
            if card[4].startswith('http'):
                embed.set_image(url=card[4])
            else:
                try:
                    file = discord.File(card[4])
                    await ctx.send(embed=embed, file=file)
                    return
                except:
                    pass
        
        await ctx.send(embed=embed)

    @card_group.command(name='stats')
    async def user_stats(self, ctx, user: Optional[discord.Member] = None):
        """View collection statistics"""
        target_user = user or ctx.author
        
        # Get user stats
        self.cursor.execute('''
            SELECT 
                COUNT(*) as total_cards,
                COUNT(DISTINCT c.name) as unique_cards,
                SUM(CASE WHEN c.rarity = 'Common' THEN 1 ELSE 0 END) as common,
                SUM(CASE WHEN c.rarity = 'Uncommon' THEN 1 ELSE 0 END) as uncommon,
                SUM(CASE WHEN c.rarity = 'Rare' THEN 1 ELSE 0 END) as rare,
                SUM(CASE WHEN c.rarity = 'Legendary' THEN 1 ELSE 0 END) as legendary
            FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id = ?
        ''', (target_user.id,))
        
        stats = self.cursor.fetchone()
        
        # Get total available cards
        self.cursor.execute("SELECT COUNT(*) FROM cards")
        total_available = self.cursor.fetchone()[0]
        
        embed = discord.Embed(
            title=f"📊 {target_user.display_name}'s Collection Stats",
            color=0x7289da
        )
        
        if stats[0] == 0:
            embed.description = "No cards in collection yet!"
        else:
            embed.add_field(name="Total Cards", value=str(stats[0]), inline=True)
            embed.add_field(name="Unique Cards", value=f"{stats[1]}/{total_available}", inline=True)
            embed.add_field(name="Completion", value=f"{stats[1]/total_available*100:.1f}%" if total_available > 0 else "0%", inline=True)
            
            rarity_text = ""
            if stats[2]: rarity_text += f"⚪ Common: {stats[2]}\n"
            if stats[3]: rarity_text += f"🟢 Uncommon: {stats[3]}\n"
            if stats[4]: rarity_text += f"🔵 Rare: {stats[4]}\n"
            if stats[5]: rarity_text += f"🟡 Legendary: {stats[5]}\n"
            
            if rarity_text:
                embed.add_field(name="By Rarity", value=rarity_text, inline=False)
        
        await ctx.send(embed=embed)

    @card_group.command(name='leaderboard')
    async def leaderboard(self, ctx):
        """Show top collectors"""
        self.cursor.execute('''
            SELECT uc.user_id, COUNT(*) as total_cards, COUNT(DISTINCT c.name) as unique_cards
            FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            GROUP BY uc.user_id
            ORDER BY unique_cards DESC, total_cards DESC
            LIMIT 10
        ''')
        
        results = self.cursor.fetchall()
        
        if not results:
            await ctx.send("📭 No one has any cards yet!")
            return
        
        embed = discord.Embed(
            title="🏆 Top Card Collectors",
            color=0xffd700
        )
        
        for i, (user_id, total, unique) in enumerate(results, 1):
            user = self.bot.get_user(user_id)
            username = user.display_name if user else f"User {user_id}"
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            embed.add_field(
                name=f"{medal} {username}",
                value=f"Unique: {unique} | Total: {total}",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @card_group.command(name='search')
    async def search_cards(self, ctx, *, query: str):
        """Search for cards by name"""
        self.cursor.execute("SELECT name, rarity, description FROM cards WHERE name LIKE ? ORDER BY name", (f"%{query}%",))
        results = self.cursor.fetchall()
        
        if not results:
            await ctx.send(f"❌ No cards found matching '{query}'!")
            return
        
        embed = discord.Embed(
            title=f"🔍 Search Results for '{query}'",
            color=0x7289da
        )
        
        for name, rarity, desc in results[:15]:  # Limit to 15 results
            embed.add_field(
                name=f"{self.get_rarity_emoji(rarity)} {name}",
                value=desc[:50] + "..." if desc and len(desc) > 50 else desc or "No description",
                inline=False
            )
        
        if len(results) > 15:
            embed.set_footer(text=f"Showing first 15 of {len(results)} results")
        
        await ctx.send(embed=embed)

    # Admin commands
    @card_group.command(name='list')
    @commands.has_permissions(administrator=True)
    async def list_all_cards(self, ctx):
        """List all cards (Admin only)"""
        self.cursor.execute("SELECT name, rarity, description FROM cards ORDER BY rarity, name")
        cards = self.cursor.fetchall()
        
        if not cards:
            await ctx.send("📭 No cards have been created yet!")
            return
        
        embed = discord.Embed(
            title="📋 All Trading Cards",
            color=0x7289da
        )
        
        for name, rarity, desc in cards:
            embed.add_field(
                name=f"{self.get_rarity_emoji(rarity)} {name}",
                value=f"**{rarity}** | {desc[:50] + '...' if desc and len(desc) > 50 else desc or 'No description'}",
                inline=False
            )
        
        await ctx.send(embed=embed)

    @card_group.command(name='give')
    @commands.has_permissions(administrator=True)
    async def give_card(self, ctx, user: discord.Member, *, card_name: str):
        """Give a card to a user (Admin only)"""
        self.cursor.execute("SELECT id, name FROM cards WHERE name LIKE ?", (f"%{card_name}%",))
        card = self.cursor.fetchone()
        
        if not card:
            await ctx.send(f"❌ No card found matching '{card_name}'!")
            return
        
        # Give card to user
        self.cursor.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user.id, card[0]))
        self.conn.commit()
        
        embed = discord.Embed(
            title="✅ Card Given",
            description=f"Gave **{card[1]}** to {user.mention}!",
            color=0x00ff00
        )
        await ctx.send(embed=embed)

    @tasks.loop(minutes=30)
    async def random_drops(self):
        """Random card drops in channels"""
        if not hasattr(self, 'drop_channels'):
            return
        
        for guild_id, channel_id in self.drop_channels.items():
            guild = self.bot.get_guild(guild_id)
            if not guild:
                continue
                
            channel = guild.get_channel(channel_id)
            if not channel:
                continue
            
            # Check if channel has been active
            messages = [message async for message in channel.history(limit=10, after=datetime.now() - timedelta(hours=1))]
            if len(messages) < 3:  # Need some activity for drops
                continue
            
            # Random chance for drop (5% every 30 minutes)
            if random.random() < 0.05:
                card = self.get_random_card()
                if card:
                    embed = discord.Embed(
                        title="🎁 Wild Card Appeared!",
                        description=f"A **{card[1]}** card appeared! First to react with 🃏 gets it!",
                        color=self.get_rarity_color(card[3])
                    )
                    embed.add_field(name="Rarity", value=f"{self.get_rarity_emoji(card[3])} {card[3]}", inline=True)
                    
                    message = await channel.send(embed=embed)
                    await message.add_reaction('🃏')
                    
                    def check(reaction, user):
                        return str(reaction.emoji) == '🃏' and reaction.message.id == message.id and not user.bot
                    
                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=300.0, check=check)
                        
                        # Give card to user
                        self.cursor.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user.id, card[0]))
                        self.conn.commit()
                        
                        success_embed = discord.Embed(
                            title="✅ Card Caught!",
                            description=f"{user.mention} caught the **{card[1]}** card!",
                            color=0x00ff00
                        )
                        await channel.send(embed=success_embed)
                        
                    except asyncio.TimeoutError:
                        timeout_embed = discord.Embed(
                            title="💨 Card Escaped",
                            description="The card disappeared...",
                            color=0x808080
                        )
                        await message.edit(embed=timeout_embed)

    def set_drop_channel(self, guild_id: int, channel_id: int):
        """Set drop channel for a guild"""
        if not hasattr(self, 'drop_channels'):
            self.drop_channels = {}
        self.drop_channels[guild_id] = channel_id

    # Helper methods
    def get_random_card(self):
        """Get a random card based on rarity weights"""
        # Rarity weights: Common 70%, Uncommon 20%, Rare 8%, Legendary 2%
        rarity_weights = {'Common': 70, 'Uncommon': 20, 'Rare': 8, 'Legendary': 2}
        
        cards_by_rarity = {}
        for rarity in rarity_weights:
            self.cursor.execute("SELECT * FROM cards WHERE rarity = ?", (rarity,))
            cards_by_rarity[rarity] = self.cursor.fetchall()
        
        # Build weighted list
        weighted_cards = []
        for rarity, weight in rarity_weights.items():
            if cards_by_rarity[rarity]:
                for card in cards_by_rarity[rarity]:
                    weighted_cards.extend([card] * weight)
        
        return random.choice(weighted_cards) if weighted_cards else None

    def get_user_card_id(self, user_id: int, card_name: str):
        """Get a user's card ID by name"""
        self.cursor.execute('''
            SELECT uc.id FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            WHERE uc.user_id = ? AND c.name LIKE ?
            LIMIT 1
        ''', (user_id, f"%{card_name}%"))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def execute_trade(self, user1_id: int, user2_id: int, card1_id: int, card2_id: int):
        """Execute a card trade"""
        # Update ownership
        self.cursor.execute("UPDATE user_cards SET user_id = ? WHERE id = ?", (user2_id, card1_id))
        self.cursor.execute("UPDATE user_cards SET user_id = ? WHERE id = ?", (user1_id, card2_id))
        
        # Record trade history
        self.cursor.execute("INSERT INTO trades (from_user, to_user, card_id) VALUES (?, ?, ?)", (user1_id, user2_id, card1_id))
        self.cursor.execute("INSERT INTO trades (from_user, to_user, card_id) VALUES (?, ?, ?)", (user2_id, user1_id, card2_id))
        
        self.conn.commit()

    def create_collection_embed(self, user, cards, page, total_pages):
        """Create collection display embed"""
        embed = discord.Embed(
            title=f"🃏 {user.display_name}'s Collection",
            color=0x7289da
        )
        
        collection_text = ""
        for name, rarity, count, desc, image_url in cards:
            emoji = self.get_rarity_emoji(rarity)
            collection_text += f"{emoji} **{name}** x{count}\n"
        
        embed.description = collection_text
        embed.set_footer(text=f"Page {page}/{total_pages} • Total: {len(cards)} unique cards")
        
        return embed

    def get_rarity_color(self, rarity: str) -> int:
        """Get color for rarity"""
        colors = {
            'Common': 0x808080,      # Gray
            'Uncommon': 0x00ff00,    # Green  
            'Rare': 0x0080ff,        # Blue
            'Legendary': 0xffd700     # Gold
        }
        return colors.get(rarity, 0x808080)

    def get_rarity_emoji(self, rarity: str) -> str:
        """Get emoji for rarity"""
        emojis = {
            'Common': '⚪',
            'Uncommon': '🟢', 
            'Rare': '🔵',
            'Legendary': '🟡'
        }
        return emojis.get(rarity, '⚪')

async def setup(bot):
    await bot.add_cog(TradingCards(bot)) 