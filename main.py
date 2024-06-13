import discord
from discord.ext import commands
import aiohttp
import aiosqlite
import logging
import os
from cachetools import TTLCache
from dotenv import load_dotenv
from aiolimiter import AsyncLimiter
import asyncio
import urllib.parse

# Load environment variables from .env file
load_dotenv()

# Retrieve Discord bot token from environment variables
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Define intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# Initialize the bot with intents
bot = commands.Bot(command_prefix='!', intents=intents)

# Temporary link cache with TTL (Time-To-Live)
temp_links = TTLCache(maxsize=1000, ttl=600)

# Initialize rate limiter (adjust limits as needed)
rate_limiter = AsyncLimiter(max_rate=10, time_period=1)

# Rate limiter for sending messages to avoid 429 errors
message_rate_limiter = AsyncLimiter(max_rate=5, time_period=10)

# Initialize the SQLite database asynchronously
async def init_db():
    try:
        async with aiosqlite.connect('database.db') as db:
            # Create table if it does not exist with unique constraint on roblox_id
            await db.execute('''CREATE TABLE IF NOT EXISTS links
                                (discord_id TEXT PRIMARY KEY, 
                                roblox_id TEXT UNIQUE,
                                linked BOOLEAN DEFAULT 0)''')
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")

# Store the linked Roblox ID with the Discord ID in the database
async def store_roblox_id(discord_id, roblox_id):
    try:
        async with aiosqlite.connect('database.db') as db:
            await db.execute(
                'INSERT OR REPLACE INTO links (discord_id, roblox_id, linked) VALUES (?, ?, ?)',
                (discord_id, roblox_id, 1))  # Setting linked to True
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")

# Remove the linked Roblox ID from the database
async def remove_roblox_id(discord_id):
    try:
        async with aiosqlite.connect('database.db') as db:
            await db.execute('DELETE FROM links WHERE discord_id = ?', (discord_id, ))
            await db.commit()
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")

async def is_linked(discord_id):
    try:
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute(
                'SELECT * FROM links WHERE discord_id = ?', (discord_id, ))
            row = await cursor.fetchone()
            if row is not None:
                # Check if 'linked' column is truthy (non-zero value)
                linked = bool(row[2])  # Assuming 'linked' column is at index 2
                return linked
            else:
                return False
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")
        return False

async def is_roblox_id_linked(roblox_id):
    try:
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute(
                'SELECT * FROM links WHERE roblox_id = ?', (roblox_id, ))
            row = await cursor.fetchone()
            return row is not None
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")
        return False

# Function to retrieve Roblox ID from username with retry mechanism
async def get_roblox_id_from_username(roblox_username, retries=3):
    encoded_username = urllib.parse.quote(roblox_username)
    url = f"https://users.roblox.com/v1/users/search?keyword={encoded_username}&limit=10"
    async with aiohttp.ClientSession() as session:
        for attempt in range(retries):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if 'data' in data and len(data['data']) > 0:
                            return data['data'][0]['id']
                    logging.error(f"Unexpected response: {await response.text()}")
                    return None
            except aiohttp.ClientError as e:
                logging.error(f"Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(2)  # Wait before retrying
                else:
                    return None

# Function to verify user with username and ID confirmation
async def verify_roblox_username(ctx, roblox_username):
    """
    Link your Discord account with your Roblox username.

    Parameters:
    - roblox_username (str): Your Roblox username to link with your Discord account.
      This should be the username you use on Roblox.

    Example:
    !link my_roblox_username
    """
    roblox_id = await get_roblox_id_from_username(roblox_username)
    if roblox_id:
        if await is_roblox_id_linked(roblox_id):
            await send_with_retries(ctx, "This Roblox ID is already linked to another Discord account.")
            return

        roblox_link = f"https://www.roblox.com/users/{roblox_id}/profile"
        await send_with_retries(ctx, f"Is this your Roblox account? {roblox_link}")
        def check(m):
            return m.author == ctx.author and m.content.lower() in ('yes', 'y', 'no', 'n')
        try:
            msg = await bot.wait_for('message', check=check, timeout=30)
            if msg.content.lower() in ('yes', 'y'):
                await store_roblox_id(ctx.author.id, roblox_id)
                await send_with_retries(ctx, "Roblox account linked successfully!")

                # Update user's nickname in the server
                member = ctx.author
                new_nick = f"{member.name} (@{roblox_username})"
                try:
                    await member.edit(nick=new_nick)
                    await send_with_retries(ctx, f"Nickname updated to: {new_nick}")
                except discord.Forbidden:
                    await send_with_retries(ctx, "I don't have permission to change your nickname.")

                # Add "Verified Roblox Account" role to the user
                verified_role = discord.utils.get(ctx.guild.roles, name="Verified Roblox Account")
                if verified_role:
                    await member.add_roles(verified_role)
                    await send_with_retries(ctx, "You have been given the 'Verified Roblox Account' role.")
                else:
                    await send_with_retries(ctx, "Role 'Verified Roblox Account' not found. Please contact an admin.")
            else:
                await send_with_retries(ctx, "Verification cancelled.")
        except asyncio.TimeoutError:
            await send_with_retries(ctx, "Verification timed out.")
    else:
        await send_with_retries(ctx, "Roblox username not found or API request failed. Please try again later.")

@bot.event
async def on_ready():
    await init_db()
    logging.info(f'Bot is ready. Logged in as {bot.user}')

@bot.command(
    name='link',
    brief='!link <roblox_username>',
    description="Link your Discord account with your Roblox username."
)
@commands.cooldown(1, 10, commands.BucketType.user)
async def link(ctx, roblox_username):
    """
    Link your Discord account with your Roblox username.

    Parameters:
    - roblox_username (str): Your Roblox username to link with your Discord account.
      This should be the username you use on Roblox.

    Example:
    !link my_roblox_username
    """
    if await is_linked(ctx.author.id):
        await send_with_retries(ctx, "You've already linked a Roblox account.")
        return

    await verify_roblox_username(ctx, roblox_username)

@bot.command(
    name='unlink',
    brief='!unlink',
    description="Unlink your Discord account from your linked Roblox account."
)
async def unlink(ctx):
    try:
        await remove_roblox_id(ctx.author.id)
        await send_with_retries(ctx, "Roblox account unlinked successfully!")

        # Reset user's nickname in the server
        member = ctx.author
        original_nick = member.name
        try:
            await member.edit(nick=original_nick)
            await send_with_retries(ctx, f"Nickname reset to: {original_nick}")
        except discord.Forbidden:
            await send_with_retries(ctx, "I don't have permission to change your nickname.")

        # Remove "Verified Roblox Account" role from the user
        verified_role = discord.utils.get(ctx.guild.roles, name="Verified Roblox Account")
        if verified_role:
            await member.remove_roles(verified_role)
            await send_with_retries(ctx, "The 'Verified Roblox Account' role has been removed.")
        else:
            await send_with_retries(ctx, "Role 'Verified Roblox Account' not found. Please contact an admin.")
    except Exception as e:
        logging.error(f"Error unlinking Roblox account: {e}")
        await send_with_retries(ctx, "An error occurred while unlinking your Roblox account. Please try again later.")

async def get_roblox_id(discord_id):
    try:
        async with aiosqlite.connect('database.db') as db:
            cursor = await db.execute('SELECT roblox_id FROM links WHERE discord_id = ?', (discord_id, ))
            row = await cursor.fetchone()
            return row['roblox_id'] if row else None
    except aiosqlite.Error as e:
        logging.error(f"Database error: {e}")
        return None

@bot.event
async def on_member_update(before, after):
    if before.nick != after.nick:
        roblox_id = await get_roblox_id(after.id)
        if roblox_id:
            new_nick = f"{after.nick} (@{roblox_id})"
            try:
                await after.edit(nick=new_nick)
            except discord.Forbidden:
                logging.error("Bot doesn't have permission to change nickname.")

async def send_with_retries(ctx, content, retries=5, delay=1):
    for attempt in range(retries):
        try:
            await message_rate_limiter.acquire()
            await ctx.send(content)
            return
        except discord.HTTPException as e:
            if attempt < retries - 1:
                logging.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logging.error(f"Failed to send message after {retries} attempts: {e}")
                return

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await send_with_retries(ctx, f"You're doing that too often. Try again in {error.retry_after:.2f} seconds.")
    elif isinstance(error, commands.CommandNotFound):
        await send_with_retries(ctx, "Command not found. Please use a valid command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await send_with_retries(ctx, "Missing arguments. Please check the command usage.")
    elif isinstance(error, discord.HTTPException) and error.status == 429:
        logging.warning(f"Rate limited: {error}")
        await asyncio.sleep(5)  # Wait a bit before retrying
    else:
        logging.error(f"Unhandled error: {error}")
        await send_with_retries(ctx, "An error occurred. Please try again later.")

@bot.command(
    name='checklink',
    brief='!checklink',
    description="Check if your Discord account is linked to a Roblox account."
)
async def check_link(ctx):
    """
    Check if your Discord account is linked to a Roblox account.
    """
    if await is_linked(ctx.author.id):
        await ctx.send("Your Discord account is linked to a Roblox account.")
    else:
        await ctx.send("Your Discord account is not linked to any Roblox account.")

# Run the bot
bot.run(DISCORD_BOT_TOKEN)
