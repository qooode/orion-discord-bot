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

class CollectionView(discord.ui.View):
    def __init__(self, user, cards, trading_cards_cog):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.user = user
        self.cards = cards
        self.trading_cards = trading_cards_cog
        self.current_index = 0
        
        # Update button states
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current position"""
        # Previous button
        self.previous_button.disabled = self.current_index == 0
        
        # Next button  
        self.next_button.disabled = self.current_index >= len(self.cards) - 1
        
        # Update labels with current position
        self.previous_button.label = f"← Previous"
        self.next_button.label = f"Next →"
        self.info_button.label = f"Card {self.current_index + 1}/{len(self.cards)}"
    
    def create_card_embed(self, index):
        """Create beautiful embed for current card"""
        if index >= len(self.cards):
            index = 0
        
        card = self.cards[index]
        card_id, name, description, rarity, image_url, created_at, count = card
        
        # Create gorgeous collection card embed
        embed = discord.Embed(
            title=f"🃏 {self.user.display_name}'s Collection",
            color=self.trading_cards.get_rarity_color(rarity)
        )
        
        # Beautiful card display
        rarity_stars = {
            'Common': "⭐",
            'Uncommon': "⭐⭐", 
            'Rare': "⭐⭐⭐",
            'Legendary': "⭐⭐⭐⭐"
        }
        
        card_display = f"**{name}**\n{rarity_stars.get(rarity, '⭐')} {self.trading_cards.get_rarity_emoji(rarity)} {rarity}"
        if description:
            card_display += f"\n\n*{description}*"
        
        embed.description = card_display
        
        # Add essential info
        embed.add_field(name="🔢 Owned", value=f"x{count}", inline=True)
        embed.add_field(name="🆔 ID", value=f"#{card_id}", inline=True)
        embed.add_field(name="📊 Rarity", value=f"{rarity} ({self.get_rarity_rate(rarity)})", inline=True)
        
        # Handle image display
        if image_url:
            if image_url.startswith('http'):
                embed.set_image(url=image_url)
            elif os.path.exists(image_url):
                # For local files, we'll handle this in the interaction response
                pass
        
        embed.set_footer(text=f"Card {index + 1} of {len(self.cards)} in collection")
        embed.timestamp = datetime.now()
        
        return embed
    
    def get_rarity_rate(self, rarity):
        """Get drop rate for rarity"""
        rates = {
            'Common': '70%',
            'Uncommon': '20%',
            'Rare': '8%',
            'Legendary': '2%'
        }
        return rates.get(rarity, 'Unknown')
    
    @discord.ui.button(label='← Previous', style=discord.ButtonStyle.secondary, emoji='⬅️')
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("❌ This is not your collection!", ephemeral=True)
            return
            
        if self.current_index > 0:
            self.current_index -= 1
            self.update_buttons()
            embed = self.create_card_embed(self.current_index)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label='Card 1/X', style=discord.ButtonStyle.primary, emoji='📊')
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("❌ This is not your collection!", ephemeral=True)
            return
            
        # Show quick stats
        card = self.cards[self.current_index]
        card_id = card[0]
        name = card[1]
        
        embed = discord.Embed(
            title=f"📈 Quick Stats - {name}",
            color=0x7289da
        )
        
        # Get additional stats for this card
        self.trading_cards.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_cards WHERE card_id = ?", (card_id,))
        total_collectors = self.trading_cards.cursor.fetchone()[0]
        
        embed.add_field(name="👥 Total Collectors", value=str(total_collectors), inline=True)
        embed.add_field(name="🔢 You Own", value=f"x{card[6]}", inline=True)
        embed.add_field(name="🎯 Collection", value=f"{self.current_index + 1}/{len(self.cards)}", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label='Next →', style=discord.ButtonStyle.secondary, emoji='➡️')
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("❌ This is not your collection!", ephemeral=True)
            return
            
        if self.current_index < len(self.cards) - 1:
            self.current_index += 1
            self.update_buttons()
            embed = self.create_card_embed(self.current_index)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @discord.ui.button(label='🎲 Random', style=discord.ButtonStyle.success, emoji='🎲')
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != interaction.message.interaction.user:
            await interaction.response.send_message("❌ This is not your collection!", ephemeral=True)
            return
            
        # Jump to random card
        import random
        self.current_index = random.randint(0, len(self.cards) - 1)
        self.update_buttons()
        embed = self.create_card_embed(self.current_index)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True

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
            title="🃏 Trading Card System - Complete Guide",
            description="Your server's complete trading card collection system!",
            color=0x7289da
        )
        
        # Basic Collection Commands
        embed.add_field(
            name="🎯 Collection & Claims",
            value="`!card daily` - Claim your daily free card (24h cooldown)\n`!card collection [@user]` - View card collection\n`!card info <card name>` - Get detailed card information\n`!card search <text>` - Search for cards by name",
            inline=False
        )
        
        # Trading & Social Commands  
        embed.add_field(
            name="🔄 Trading & Gifts",
            value="`!card trade @user <your card> <their card>` - Propose a trade\n`!card gift @user <card name>` - Gift a card to someone\n`!card leaderboard` - View top collectors",
            inline=False
        )
        
        # Statistics & Information
        embed.add_field(
            name="📊 Statistics & Info",
            value="`!card stats [@user]` - View collection statistics\n`!card rarity` - Learn about the rarity system\n`!card leaderboard` - Top card collectors",
            inline=False
        )
        
        # Rarity Quick Reference
        embed.add_field(
            name="🌟 Rarity System Quick Reference",
            value="⚪ **Common** (70%) - Server memes, inside jokes\n🟢 **Uncommon** (20%) - Special moments\n🔵 **Rare** (8%) - Significant events\n🟡 **Legendary** (2%) - Epic milestones",
            inline=False
        )
        
        # How to Get Cards
        embed.add_field(
            name="💡 How to Get Cards",
            value="• **Daily Claims**: `!card daily` every 24 hours\n• **Random Drops**: React 🃏 to wild cards in chat\n• **Trading**: Exchange with other users\n• **Gifts**: Receive from generous users",
            inline=False
        )
        
        # Admin Commands (only show if user is admin)
        if ctx.author.guild_permissions.administrator:
            embed.add_field(
                name="⚙️ Admin - Card Management",
                value="`!card create` - Create new card (interactive)\n`!card list` - View all created cards\n`!card give @user <card>` - Give card to user\n`!card delete <card>` - Delete card permanently",
                inline=False
            )
            
            embed.add_field(
                name="🛠️ Admin - System Configuration",
                value="`!card config` - View system settings & stats\n`!card systemstats` - Detailed system statistics\n`!card dropchannel #channel` - Set random drop channel\n`!card drop [#channel] [card]` - Manual card drop\n`!card backup` - Export database backup\n`!card restore` - Import database backup",
                inline=False
            )
            
            embed.add_field(
                name="📈 Admin - Drop System",
                value="• **Random Drops**: Every 30 minutes, 5% chance\n• **Manual Drops**: `!card drop` for events\n• **Requirements**: 3+ messages in last hour\n• **Timeout**: 5-10 minutes to claim",
                inline=False
            )
        
        # Footer with tips
        embed.set_footer(text="💡 Tip: Use !card rarity to learn about drop rates and trading strategies!")
        
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
        embed = self.create_card_embed(card, "daily")
        await ctx.send(embed=embed)

    @card_group.command(name='collection')
    async def view_collection(self, ctx, user: Optional[discord.Member] = None):
        """View your or someone else's card collection - Interactive with buttons!"""
        target_user = user or ctx.author
        
        # Get user's cards with full details
        self.cursor.execute('''
            SELECT c.id, c.name, c.description, c.rarity, c.image_url, c.created_at, COUNT(*) as count
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
            embed = discord.Embed(
                title=f"📭 {target_user.display_name}'s Collection",
                description="No cards in collection yet!\n\nUse `!card daily` to get your first card!",
                color=0x808080
            )
            await ctx.send(embed=embed)
            return
        
        # Create interactive collection view
        view = CollectionView(target_user, cards, self)
        embed = view.create_card_embed(0)  # Start with first card
        
        await ctx.send(embed=embed, view=view)

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
        """Get detailed information about a card - Beautiful showcase!"""
        self.cursor.execute("SELECT * FROM cards WHERE name LIKE ?", (f"%{card_name}%",))
        card = self.cursor.fetchone()
        
        if not card:
            await ctx.send(f"❌ No card found matching '{card_name}'!")
            return
        
        # Get basic stats
        self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_cards WHERE card_id = ?", (card[0],))
        unique_owners = self.cursor.fetchone()[0]
        
        # Create beautiful minimal showcase embed
        embed = self.create_card_embed(card, "showcase")
        
        # Add minimal essential info only
        embed.add_field(name="👥 Collectors", value=str(unique_owners), inline=True)
        embed.add_field(name="🆔 ID", value=f"#{card[0]}", inline=True)
        
        # Handle image display beautifully
        image_url = card[4]
        discord_file = None
        
        if image_url:
            if image_url.startswith('http'):
                embed.set_image(url=image_url)
            elif os.path.exists(image_url):
                try:
                    discord_file = discord.File(image_url, filename=f"card_{card[0]}.jpg")
                    embed.set_image(url=f"attachment://card_{card[0]}.jpg")
                except Exception as e:
                    print(f"Error loading image file {image_url}: {e}")
        
        # Send with proper image handling
        if discord_file:
            await ctx.send(embed=embed, file=discord_file)
        else:
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

    @card_group.command(name='delete')
    @commands.has_permissions(administrator=True)
    async def delete_card(self, ctx, *, card_name: str):
        """Delete a card permanently (Admin only)"""
        # Find the card
        self.cursor.execute("SELECT id, name, rarity FROM cards WHERE name LIKE ?", (f"%{card_name}%",))
        card = self.cursor.fetchone()
        
        if not card:
            await ctx.send(f"❌ No card found matching '{card_name}'!")
            return
        
        card_id, exact_name, rarity = card
        
        # Get stats before deletion
        self.cursor.execute("SELECT COUNT(*) FROM user_cards WHERE card_id = ?", (card_id,))
        total_owned = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_cards WHERE card_id = ?", (card_id,))
        unique_owners = self.cursor.fetchone()[0]
        
        # Confirmation embed
        confirm_embed = discord.Embed(
            title="⚠️ Confirm Card Deletion",
            description=f"Are you sure you want to **permanently delete** this card?",
            color=0xff6b35
        )
        confirm_embed.add_field(name="Card", value=f"**{exact_name}**", inline=True)
        confirm_embed.add_field(name="Rarity", value=f"{self.get_rarity_emoji(rarity)} {rarity}", inline=True)
        confirm_embed.add_field(name="Impact", value=f"Will remove {total_owned} copies from {unique_owners} users", inline=False)
        confirm_embed.add_field(name="⚠️ Warning", value="This action cannot be undone!", inline=False)
        confirm_embed.set_footer(text="React with ✅ to confirm or ❌ to cancel (30 seconds)")
        
        message = await ctx.send(embed=confirm_embed)
        await message.add_reaction('✅')
        await message.add_reaction('❌')
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id
        
        try:
            reaction, _ = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
            
            if str(reaction.emoji) == '✅':
                # Delete all user instances first
                self.cursor.execute("DELETE FROM user_cards WHERE card_id = ?", (card_id,))
                
                # Delete from trades history
                self.cursor.execute("DELETE FROM trades WHERE card_id = ?", (card_id,))
                
                # Delete the card itself
                self.cursor.execute("DELETE FROM cards WHERE id = ?", (card_id,))
                
                self.conn.commit()
                
                # Success message
                success_embed = discord.Embed(
                    title="🗑️ Card Deleted Successfully",
                    description=f"**{exact_name}** has been permanently removed from the system.",
                    color=0xff0000
                )
                success_embed.add_field(name="Removed", value=f"{total_owned} copies from {unique_owners} users", inline=True)
                success_embed.add_field(name="Deleted by", value=ctx.author.mention, inline=True)
                success_embed.set_footer(text="This action cannot be undone")
                
                await message.edit(embed=success_embed)
                
                print(f"Card '{exact_name}' deleted by {ctx.author.name} - removed {total_owned} copies from {unique_owners} users")
                
            else:
                # Cancelled
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description=f"**{exact_name}** was not deleted.",
                    color=0x808080
                )
                await message.edit(embed=cancel_embed)
                
        except asyncio.TimeoutError:
            # Timeout
            timeout_embed = discord.Embed(
                title="⏰ Deletion Timed Out",
                description=f"Card deletion was cancelled due to timeout.",
                color=0x808080
            )
            await message.edit(embed=timeout_embed)

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
                    embed = self.create_card_embed(card, "drop")
                    message = await channel.send(embed=embed)
                    await message.add_reaction('🃏')
                    
                    def check(reaction, user):
                        return str(reaction.emoji) == '🃏' and reaction.message.id == message.id and not user.bot
                    
                    try:
                        reaction, user = await self.bot.wait_for('reaction_add', timeout=300.0, check=check)
                        
                        # Give card to user
                        self.cursor.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user.id, card[0]))
                        self.conn.commit()
                        
                        success_embed = self.create_card_embed(card, "claimed", {"user": user})
                        await channel.send(embed=success_embed)
                        
                    except asyncio.TimeoutError:
                        timeout_embed = self.create_card_embed(card, "claimed", {"status": "escaped"})
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

    def create_card_embed(self, card, context_type="display", extra_info=None):
        """Create a beautiful card display embed"""
        # Handle different card tuple formats
        if len(card) == 7 and context_type == "collection":
            # Collection format: (id, name, description, rarity, image_url, created_at, count)
            card_id, name, description, rarity, image_url, created_at, count = card
            created_by = None
        elif len(card) == 7:
            # Standard format: (id, name, description, rarity, image_url, created_by, created_at)
            card_id, name, description, rarity, image_url, created_by, created_at = card
            count = None
        else:
            # Handle any other formats gracefully
            card_id, name, description, rarity = card[:4]
            image_url = card[4] if len(card) > 4 else None
            created_by = card[5] if len(card) > 5 else None
            created_at = card[6] if len(card) > 6 else None
            count = None
        
        # Different titles based on context
        title_prefixes = {
            "daily": "🎁 Daily Card Claimed!",
            "drop": "🎁 Wild Card Appeared!",
            "admin_drop": "🎯 Admin Card Drop!",
            "claimed": "✅ Card Caught!",
            "escaped": "💨 Card Escaped!",
            "info": "🃏 Card Information",
            "showcase": "✨ Card Showcase",
            "display": "🃏 Trading Card"
        }
        
        # Handle special escaped context
        if extra_info and extra_info.get("status") == "escaped":
            context_type = "escaped"
        
        title = title_prefixes.get(context_type, "🃏 Trading Card")
        
        # Create the embed with rarity-based styling
        embed_color = self.get_rarity_color(rarity)
        if context_type == "escaped":
            embed_color = 0x808080  # Gray for escaped cards
            
        embed = discord.Embed(
            title=title,
            color=embed_color
        )
        
        # Card name as main description with rarity styling
        rarity_stars = {
            'Common': "⭐",
            'Uncommon': "⭐⭐", 
            'Rare': "⭐⭐⭐",
            'Legendary': "⭐⭐⭐⭐"
        }
        
        # Special handling for different contexts
        if context_type == "escaped":
            card_display = f"**{name}** vanished into the void...\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
            card_display += "\n\n💨 *No one claimed it in time!*"
        elif context_type == "claimed" and extra_info and "user" in extra_info:
            user = extra_info["user"]
            card_display = f"**{name}**\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
            card_display += f"\n\n🎉 **Caught by {user.mention}!**"
        elif context_type == "drop":
            card_display = f"**{name}** appeared!\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
            card_display += "\n\n⚡ **React 🃏 to claim!**"
        elif context_type == "admin_drop":
            card_display = f"**{name}** was dropped!\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
            card_display += "\n\n⚡ **React 🃏 to claim!**"
        elif context_type == "showcase":
            card_display = f"**{name}**\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
        else:
            card_display = f"**{name}**\n{rarity_stars.get(rarity, '⭐')} {self.get_rarity_emoji(rarity)} {rarity}"
            if description:
                card_display += f"\n\n*{description}*"
                
        embed.description = card_display
        
        # Add beautiful fields based on context
        if context_type == "daily":
            embed.add_field(name="🎯 Daily Claim", value="✅ Claimed", inline=True)
        elif context_type in ["drop", "admin_drop"]:
            embed.add_field(name="🎲 How to Claim", value="React with 🃏", inline=True)
        elif context_type == "claimed":
            embed.add_field(name="🎊 Status", value="Successfully Caught!", inline=True)
        elif context_type == "escaped":
            embed.add_field(name="💸 Status", value="Escaped", inline=True)
        
        # Only show rarity info for non-escaped cards
        if context_type != "escaped":
            rarity_info = {
                'Common': "70% drop rate",
                'Uncommon': "20% drop rate", 
                'Rare': "8% drop rate",
                'Legendary': "2% drop rate"
            }
            embed.add_field(name="📊 Rarity", value=rarity_info.get(rarity, "Unknown"), inline=True)
        
        # Add extra context-specific info
        if extra_info:
            for field_name, field_value in extra_info.items():
                if field_name not in ["status", "user", "dropped_by", "time_taken"]:  # Skip already handled fields
                    embed.add_field(name=field_name, value=field_value, inline=True)
        
        # Handle images beautifully
        if image_url:
            if image_url.startswith('http'):
                embed.set_image(url=image_url)
            else:
                # For local files, we'll handle this in the calling function
                pass
        
        # Beautiful footer with card ID and creation info
        if created_at:
            try:
                # Parse the timestamp
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                embed.set_footer(text=f"Card ID: {card_id} • Created {created_date.strftime('%B %d, %Y')}")
            except:
                embed.set_footer(text=f"Card ID: {card_id}")
        else:
            embed.set_footer(text=f"Card ID: {card_id}")
        
        # Add timestamp for certain contexts
        if context_type in ["daily", "claimed"]:
            embed.timestamp = datetime.now()
            
        return embed

    @card_group.command(name='config')
    @commands.has_permissions(administrator=True)
    async def config_system(self, ctx):
        """View and configure trading card system settings (Admin only)"""
        # Get current stats
        self.cursor.execute("SELECT COUNT(*) FROM cards")
        total_cards = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT rarity, COUNT(*) FROM cards GROUP BY rarity ORDER BY COUNT(*) DESC")
        rarity_stats = self.cursor.fetchall()
        
        self.cursor.execute("SELECT COUNT(*) FROM user_cards")
        total_owned = self.cursor.fetchone()[0]
        
        embed = discord.Embed(
            title="⚙️ Trading Card System Configuration",
            description="Current system settings and statistics",
            color=0x7289da
        )
        
        # Current drop rates
        embed.add_field(
            name="🎲 Drop Probabilities", 
            value="⚪ Common: 70%\n🟢 Uncommon: 20%\n🔵 Rare: 8%\n🟡 Legendary: 2%",
            inline=True
        )
        
        # Random drop settings
        embed.add_field(
            name="🔄 Random Drops",
            value="Every 30 minutes\n5% chance per check\nRequires 3+ recent messages",
            inline=True
        )
        
        # System stats
        card_breakdown = "\n".join([f"{self.get_rarity_emoji(rarity)} {rarity}: {count}" for rarity, count in rarity_stats])
        embed.add_field(
            name="📊 System Stats",
            value=f"Total Cards: {total_cards}\nTotal Owned: {total_owned}\n\n{card_breakdown or 'No cards created yet'}",
            inline=False
        )
        
        # Available config commands
        embed.add_field(
            name="🛠️ Configuration Commands",
            value="`!card dropchannel #channel` - Set drop channel\n`!card droprate <1-100>` - Set random drop chance\n`!card info system` - Detailed system info",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @card_group.command(name='dropchannel')
    @commands.has_permissions(administrator=True)
    async def set_drop_channel(self, ctx, channel: discord.TextChannel = None):
        """Set the channel for random card drops (Admin only)"""
        if not channel:
            channel = ctx.channel
        
        # Set the drop channel
        self.set_drop_channel(ctx.guild.id, channel.id)
        
        embed = discord.Embed(
            title="📍 Drop Channel Set",
            description=f"Random card drops will now appear in {channel.mention}",
            color=0x00ff00
        )
        embed.add_field(name="Drop Settings", value="Every 30 minutes\n5% chance if channel is active", inline=True)
        embed.set_footer(text="Cards will only drop if there are 3+ messages in the last hour")
        
        await ctx.send(embed=embed)

    @card_group.command(name='drop')
    @commands.has_permissions(administrator=True)
    async def manual_drop(self, ctx, channel: discord.TextChannel = None, *, card_name: str = None):
        """Manually drop a card in a channel (Admin only)"""
        if not channel:
            channel = ctx.channel
        
        # If specific card name provided, try to find it
        if card_name:
            self.cursor.execute("SELECT * FROM cards WHERE name LIKE ?", (f"%{card_name}%",))
            card = self.cursor.fetchone()
            if not card:
                await ctx.send(f"❌ No card found matching '{card_name}'!")
                return
        else:
            # Get random card if no specific card requested
            card = self.get_random_card()
            if not card:
                await ctx.send("❌ No cards available to drop!")
                return
        
        # Create the drop embed
        embed = self.create_card_embed(card, "admin_drop", {"dropped_by": ctx.author.mention})
        
        # Send to target channel
        message = await channel.send(embed=embed)
        await message.add_reaction('🃏')
        
        # Confirm to admin
        confirm_embed = discord.Embed(
            title="✅ Card Dropped Successfully",
            description=f"Dropped **{card[1]}** in {channel.mention}",
            color=0x00ff00
        )
        await ctx.send(embed=confirm_embed)
        
        # Wait for someone to claim it
        def check(reaction, user):
            return str(reaction.emoji) == '🃏' and reaction.message.id == message.id and not user.bot
        
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=600.0, check=check)
            
            # Give card to user
            self.cursor.execute("INSERT INTO user_cards (user_id, card_id) VALUES (?, ?)", (user.id, card[0]))
            self.conn.commit()
            
            # Success message
            success_embed = self.create_card_embed(card, "claimed", {"user": user})
            await channel.send(embed=success_embed)
            
            print(f"Manual drop: {user.name} claimed {card[1]} in {channel.name} (dropped by {ctx.author.name})")
            
        except asyncio.TimeoutError:
            # Timeout - card escaped
            timeout_embed = self.create_card_embed(card, "claimed", {"status": "escaped"})
            await message.edit(embed=timeout_embed)

    @card_group.command(name='droprate')
    @commands.has_permissions(administrator=True)
    async def set_drop_rate(self, ctx, rate: int):
        """Set random drop chance percentage (1-100) (Admin only)"""
        if not 1 <= rate <= 100:
            await ctx.send("❌ Drop rate must be between 1 and 100!")
            return
        
        # This would require modifying the random_drops method, for now just show current
        embed = discord.Embed(
            title="⚠️ Drop Rate Configuration",
            description="Drop rate configuration is currently hardcoded to 5%",
            color=0xffa500
        )
        embed.add_field(name="Requested Rate", value=f"{rate}%", inline=True)
        embed.add_field(name="Current Rate", value="5% (hardcoded)", inline=True)
        embed.add_field(name="Note", value="This feature requires code modification to make dynamic", inline=False)
        
        await ctx.send(embed=embed)

    @card_group.command(name='systemstats', aliases=['adminstats'])
    @commands.has_permissions(administrator=True)
    async def system_stats(self, ctx):
        """View detailed system statistics (Admin only)"""
        # Get comprehensive stats
        self.cursor.execute("SELECT COUNT(*) FROM cards")
        total_cards = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_cards")
        unique_collectors = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM user_cards")
        total_cards_owned = self.cursor.fetchone()[0]
        
        self.cursor.execute("SELECT COUNT(*) FROM trades")
        total_trades = self.cursor.fetchone()[0]
        
        # Rarity breakdown
        self.cursor.execute('''
            SELECT c.rarity, COUNT(DISTINCT c.id) as unique_cards, COUNT(uc.id) as total_owned
            FROM cards c
            LEFT JOIN user_cards uc ON c.id = uc.card_id
            GROUP BY c.rarity
            ORDER BY 
                CASE c.rarity 
                    WHEN 'Legendary' THEN 1 
                    WHEN 'Rare' THEN 2 
                    WHEN 'Uncommon' THEN 3 
                    WHEN 'Common' THEN 4 
                END
        ''')
        rarity_breakdown = self.cursor.fetchall()
        
        # Top collectors
        self.cursor.execute('''
            SELECT uc.user_id, COUNT(DISTINCT c.name) as unique_cards, COUNT(*) as total_cards
            FROM user_cards uc
            JOIN cards c ON uc.card_id = c.id
            GROUP BY uc.user_id
            ORDER BY unique_cards DESC, total_cards DESC
            LIMIT 5
        ''')
        top_collectors = self.cursor.fetchall()
        
        embed = discord.Embed(
            title="📈 Trading Card System Statistics",
            color=0x7289da
        )
        
        # Overall stats
        embed.add_field(
            name="🎯 Overview",
            value=f"Total Cards Created: {total_cards}\nUnique Collectors: {unique_collectors}\nCards in Circulation: {total_cards_owned}\nTotal Trades: {total_trades}",
            inline=True
        )
        
        # Rarity breakdown
        rarity_text = ""
        for rarity, unique, owned in rarity_breakdown:
            emoji = self.get_rarity_emoji(rarity)
            rarity_text += f"{emoji} {rarity}: {unique} cards ({owned} owned)\n"
        
        if rarity_text:
            embed.add_field(
                name="🎨 By Rarity",
                value=rarity_text,
                inline=True
            )
        
        # Top collectors
        if top_collectors:
            collector_text = ""
            for i, (user_id, unique, total) in enumerate(top_collectors, 1):
                user = self.bot.get_user(user_id)
                name = user.display_name if user else f"User {user_id}"
                collector_text += f"{i}. {name}: {unique} unique ({total} total)\n"
            
            embed.add_field(
                name="🏆 Top Collectors",
                value=collector_text,
                inline=False
            )
        
        # Activity stats
        self.cursor.execute("SELECT COUNT(*) FROM user_settings WHERE last_daily IS NOT NULL")
        active_daily_users = self.cursor.fetchone()[0]
        
        embed.add_field(
            name="📊 Activity",
            value=f"Users with Daily Claims: {active_daily_users}",
            inline=True
        )
        
        embed.set_footer(text="Use !card config for system configuration options")
        
        await ctx.send(embed=embed)

    @card_group.command(name='rarity')
    async def explain_rarity(self, ctx):
        """Explain the rarity system"""
        embed = discord.Embed(
            title="🌟 Trading Card Rarity System",
            description="Understanding card rarities and drop rates",
            color=0xffd700
        )
        
        embed.add_field(
            name="⚪ Common Cards",
            value="**70% drop chance**\nEasiest to find\nOften server memes or inside jokes",
            inline=True
        )
        
        embed.add_field(
            name="🟢 Uncommon Cards", 
            value="**20% drop chance**\nModerately rare\nSpecial moments or popular content",
            inline=True
        )
        
        embed.add_field(
            name="🔵 Rare Cards",
            value="**8% drop chance**\nHard to find\nSignificant server events",
            inline=True
        )
        
        embed.add_field(
            name="🟡 Legendary Cards",
            value="**2% drop chance**\nExtremely rare\nServer milestones, founder cards",
            inline=True
        )
        
        embed.add_field(
            name="🎲 How Drops Work",
            value="• Daily claims: Random card based on rarity weights\n• Random drops: 5% chance every 30 minutes in active channels\n• Trading: Get specific cards from other users",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Trade common cards for rarer ones\n• Check daily for your free card\n• Be active in chat for random drops\n• Use `!card collection` to see what you have",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @card_group.command(name='backup')
    @commands.has_permissions(administrator=True)
    async def backup_database(self, ctx):
        """Export trading card database as downloadable file (Admin only)"""
        try:
            # Create backup data structure
            backup_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "1.0",
                "bot_info": "Orion Trading Cards System",
                "cards": [],
                "user_cards": [],
                "trades": [],
                "user_settings": []
            }
            
            # Export all cards
            self.cursor.execute("SELECT * FROM cards")
            cards = self.cursor.fetchall()
            for card in cards:
                backup_data["cards"].append({
                    "id": card[0],
                    "name": card[1],
                    "description": card[2],
                    "rarity": card[3],
                    "image_url": card[4],
                    "created_by": card[5],
                    "created_at": card[6]
                })
            
            # Export all user cards
            self.cursor.execute("SELECT * FROM user_cards")
            user_cards = self.cursor.fetchall()
            for user_card in user_cards:
                backup_data["user_cards"].append({
                    "id": user_card[0],
                    "user_id": user_card[1],
                    "card_id": user_card[2],
                    "obtained_at": user_card[3]
                })
            
            # Export all trades
            self.cursor.execute("SELECT * FROM trades")
            trades = self.cursor.fetchall()
            for trade in trades:
                backup_data["trades"].append({
                    "id": trade[0],
                    "from_user": trade[1],
                    "to_user": trade[2],
                    "card_id": trade[3],
                    "traded_at": trade[4]
                })
            
            # Export user settings
            self.cursor.execute("SELECT * FROM user_settings")
            settings = self.cursor.fetchall()
            for setting in settings:
                backup_data["user_settings"].append({
                    "user_id": setting[0],
                    "last_daily": setting[1],
                    "total_cards": setting[2],
                    "cards_found": setting[3]
                })
            
            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"trading_cards_backup_{timestamp}.json"
            
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(backup_data, f, indent=2)
                temp_path = f.name
            
            # Create embed
            embed = discord.Embed(
                title="📦 Trading Cards Database Backup",
                description="Your complete trading card system backup is ready!",
                color=0x00ff00
            )
            embed.add_field(name="📊 Backup Contents", value=f"🃏 Cards: {len(backup_data['cards'])}\n👥 User Collections: {len(backup_data['user_cards'])}\n🔄 Trade History: {len(backup_data['trades'])}\n⚙️ User Settings: {len(backup_data['user_settings'])}", inline=True)
            embed.add_field(name="📅 Created", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
            embed.add_field(name="💾 File Size", value=f"{os.path.getsize(temp_path) / 1024:.1f} KB", inline=True)
            embed.add_field(name="🔄 Restore", value="Use `!card restore` and upload this file to restore your data", inline=False)
            embed.set_footer(text="Keep this file safe! It contains your entire trading card system.")
            
            # Send file
            with open(temp_path, 'rb') as f:
                discord_file = discord.File(f, filename=filename)
                await ctx.send(embed=embed, file=discord_file)
            
            # Clean up temp file
            os.unlink(temp_path)
            
            print(f"Trading cards backup created by {ctx.author.name}: {len(backup_data['cards'])} cards, {len(backup_data['user_cards'])} user cards")
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Backup Failed",
                description=f"Failed to create backup: {str(e)}",
                color=0xff0000
            )
            await ctx.send(embed=error_embed)
            print(f"Backup error: {e}")

    @card_group.command(name='restore')
    @commands.has_permissions(administrator=True)
    async def restore_database(self, ctx):
        """Restore trading card database from uploaded file (Admin only)"""
        if not ctx.message.attachments:
            embed = discord.Embed(
                title="📥 Restore Trading Cards Database",
                description="Upload a trading cards backup file to restore your data.",
                color=0xffa500
            )
            embed.add_field(name="📋 Instructions", value="1. Run this command\n2. Attach your backup .json file\n3. Confirm the restore operation", inline=False)
            embed.add_field(name="⚠️ Warning", value="This will REPLACE all current trading card data!", inline=False)
            embed.add_field(name="💡 Tip", value="Create a backup first with `!card backup`", inline=False)
            await ctx.send(embed=embed)
            return
        
        attachment = ctx.message.attachments[0]
        
        # Validate file
        if not attachment.filename.endswith('.json'):
            await ctx.send("❌ Please upload a .json backup file!")
            return
        
        if attachment.size > 50 * 1024 * 1024:  # 50MB limit
            await ctx.send("❌ File too large! Maximum size is 50MB.")
            return
        
        try:
            # Download and parse file
            backup_data = json.loads(await attachment.read())
            
            # Validate backup structure
            required_keys = ["cards", "user_cards", "trades", "user_settings"]
            if not all(key in backup_data for key in required_keys):
                await ctx.send("❌ Invalid backup file format!")
                return
            
            # Show preview
            preview_embed = discord.Embed(
                title="🔍 Backup File Preview",
                description="Found valid trading cards backup. Review before restoring:",
                color=0xffa500
            )
            preview_embed.add_field(name="📊 Contents", value=f"🃏 Cards: {len(backup_data['cards'])}\n👥 User Collections: {len(backup_data['user_cards'])}\n🔄 Trade History: {len(backup_data['trades'])}\n⚙️ User Settings: {len(backup_data['user_settings'])}", inline=True)
            
            if "timestamp" in backup_data:
                try:
                    backup_time = datetime.fromisoformat(backup_data["timestamp"])
                    preview_embed.add_field(name="📅 Backup Date", value=f"<t:{int(backup_time.timestamp())}:F>", inline=True)
                except:
                    pass
            
            preview_embed.add_field(name="⚠️ WARNING", value="This will COMPLETELY REPLACE your current trading card database!\n\nReact with ✅ to confirm or ❌ to cancel.", inline=False)
            
            message = await ctx.send(embed=preview_embed)
            await message.add_reaction('✅')
            await message.add_reaction('❌')
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id
            
            try:
                reaction, _ = await self.bot.wait_for('reaction_add', timeout=60.0, check=check)
                
                if str(reaction.emoji) == '✅':
                    # Perform restore
                    await self.perform_restore(ctx, backup_data, message)
                else:
                    cancel_embed = discord.Embed(
                        title="❌ Restore Cancelled",
                        description="Database restore was cancelled.",
                        color=0x808080
                    )
                    await message.edit(embed=cancel_embed)
                    
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Restore Timed Out",
                    description="Restore confirmation timed out.",
                    color=0x808080
                )
                await message.edit(embed=timeout_embed)
                
        except json.JSONDecodeError:
            await ctx.send("❌ Invalid JSON file! Please upload a valid backup file.")
        except Exception as e:
            await ctx.send(f"❌ Error reading backup file: {str(e)}")

    async def perform_restore(self, ctx, backup_data, message):
        """Perform the actual database restore"""
        try:
            # Create progress embed
            progress_embed = discord.Embed(
                title="🔄 Restoring Database...",
                description="Please wait while the database is restored.",
                color=0xffa500
            )
            await message.edit(embed=progress_embed)
            
            # Clear existing data
            self.cursor.execute("DELETE FROM user_cards")
            self.cursor.execute("DELETE FROM trades") 
            self.cursor.execute("DELETE FROM user_settings")
            self.cursor.execute("DELETE FROM cards")
            
            # Reset auto-increment
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('cards', 'user_cards', 'trades')")
            
            # Restore cards
            cards_added = 0
            for card_data in backup_data["cards"]:
                self.cursor.execute(
                    "INSERT INTO cards (name, description, rarity, image_url, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                    (card_data["name"], card_data["description"], card_data["rarity"], 
                     card_data["image_url"], card_data["created_by"], card_data["created_at"])
                )
                cards_added += 1
            
            # Create card ID mapping (old ID -> new ID)
            self.cursor.execute("SELECT id, name FROM cards ORDER BY id")
            new_cards = {card_data["name"]: new_id for new_id, _ in self.cursor.fetchall() for card_data in backup_data["cards"] if card_data["name"] == _}
            
            # Restore user cards
            user_cards_added = 0
            for user_card_data in backup_data["user_cards"]:
                # Find the new card ID
                old_card_id = user_card_data["card_id"]
                card_name = None
                for card_data in backup_data["cards"]:
                    if card_data["id"] == old_card_id:
                        card_name = card_data["name"]
                        break
                
                if card_name and card_name in new_cards:
                    new_card_id = new_cards[card_name]
                    self.cursor.execute(
                        "INSERT INTO user_cards (user_id, card_id, obtained_at) VALUES (?, ?, ?)",
                        (user_card_data["user_id"], new_card_id, user_card_data["obtained_at"])
                    )
                    user_cards_added += 1
            
            # Restore trades
            trades_added = 0
            for trade_data in backup_data["trades"]:
                old_card_id = trade_data["card_id"]
                card_name = None
                for card_data in backup_data["cards"]:
                    if card_data["id"] == old_card_id:
                        card_name = card_data["name"]
                        break
                
                if card_name and card_name in new_cards:
                    new_card_id = new_cards[card_name]
                    self.cursor.execute(
                        "INSERT INTO trades (from_user, to_user, card_id, traded_at) VALUES (?, ?, ?, ?)",
                        (trade_data["from_user"], trade_data["to_user"], new_card_id, trade_data["traded_at"])
                    )
                    trades_added += 1
            
            # Restore user settings
            settings_added = 0
            for setting_data in backup_data["user_settings"]:
                self.cursor.execute(
                    "INSERT INTO user_settings (user_id, last_daily, total_cards, cards_found) VALUES (?, ?, ?, ?)",
                    (setting_data["user_id"], setting_data["last_daily"], 
                     setting_data["total_cards"], setting_data["cards_found"])
                )
                settings_added += 1
            
            self.conn.commit()
            
            # Success embed
            success_embed = discord.Embed(
                title="✅ Database Restored Successfully!",
                description="Your trading card database has been completely restored.",
                color=0x00ff00
            )
            success_embed.add_field(name="📊 Restored", value=f"🃏 Cards: {cards_added}\n👥 User Collections: {user_cards_added}\n🔄 Trade History: {trades_added}\n⚙️ User Settings: {settings_added}", inline=True)
            success_embed.add_field(name="✨ Status", value="All data restored successfully!\nTrading card system is ready.", inline=True)
            success_embed.set_footer(text="Database restore completed")
            
            await message.edit(embed=success_embed)
            
            print(f"Trading cards database restored by {ctx.author.name}: {cards_added} cards, {user_cards_added} user cards")
            
        except Exception as e:
            error_embed = discord.Embed(
                title="❌ Restore Failed",
                description=f"Failed to restore database: {str(e)}",
                color=0xff0000
            )
            await message.edit(embed=error_embed)
            print(f"Restore error: {e}")

async def setup(bot):
    await bot.add_cog(TradingCards(bot)) 