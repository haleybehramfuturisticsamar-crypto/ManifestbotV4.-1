import os
import random
import datetime
import asyncio
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands 
from groq import Groq
from aiohttp import web

# 1. DUMMY WEB SERVER FOR RENDER
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# 2. BOT SETUP & INTENTS
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Manifest V7.9 (Stable Matrix): Online.")

bot = MyBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. DATABASE SETUP
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS levels (
    user_id INTEGER PRIMARY KEY,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('autonomous_mode', 'false')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
conn.commit()

xp_cooldowns = {}

# 4. ANTI-NUKE PROTECTION
@bot.event
async def on_guild_channel_delete(channel):
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'antinuke_mode'")
    res = cursor.fetchone()
    if res and res[0] == "true":
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                user = entry.user
                if user.id != bot.user.id and user != channel.guild.owner:
                    await channel.guild.ban(user, reason="Anti-Nuke Protection: Unauthorized channel deletion.")
                    await channel.guild.create_text_channel(name=channel.name, category=channel.category, overwrites=channel.overwrites)
                    break
        except Exception:
            pass

# 5. BOT MESSAGE PROCESSOR (WITH AUTONOMOUS TICKET SUPPORT)
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    is_ticket_channel = "ticket" in message.channel.name.lower() or "claimed" in message.channel.name.lower()
    should_respond = False
    prompt_text = message.content

    if bot.user in message.mentions:
        should_respond = True
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
    elif is_ticket_channel:
        should_respond = True

    if should_respond:
        speaker_username = message.author.name
        speaker_display = message.author.display_name
        is_master = True if speaker_username == "thunderxstorms5_." else False

        lower_prompt = prompt_text.lower()
        if "who am i" in lower_prompt:
            await message.channel.send(f"Your username is {speaker_username} and your display name is **{speaker_display}**.")
            return
        if "who are you to you" in lower_prompt or "who are you to me" in lower_prompt:
            if is_master:
                await message.channel.send("I am Manifest, your personal security sentinel and executive commander. You are my creator, Master Thunder.")
            else:
                await message.channel.send(f"I am Manifest V7.9, protecting this server under Master Thunder's direct command. You are a member here, {speaker_username}.")
            return
        if "who created you" in lower_prompt:
            await message.channel.send("I was engineered and coded by thunderxstorms5_.")
            return

        try:
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"
            
            if is_ticket_channel:
                system_prompt = (
                    f"You are Manifest V7.9 acting as an Autonomous Ticket Support Agent. "
                    f"No human moderator has answered yet, so you must help the user resolve their issue completely. "
                    f"Be sharp, helpful, technical, and polite. Walk them through troubleshooting steps step-by-step. "
                    f"Creator: thunderxstorms5_.. Current User: {speaker_username} ({speaker_display})."
                )
            else:
                system_prompt = (
                    f"You are Manifest V7.9, an elite security sentinel and assistant. "
                    f"Creator/Master: thunderxstorms5
