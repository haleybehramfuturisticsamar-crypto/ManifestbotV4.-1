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
        print("Manifest V8.0: Supreme Master Protocol Active.")

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
CREATE TABLE IF NOT EXISTS global_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT
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

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    return " | ".join([r[0] for r in rules]) if rules else "No custom restrictions yet."

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

# 5. BOT MESSAGE PROCESSOR WITH UNYIELDING LOYALTY & COMMAND INTERCEPTION
@bot.event
