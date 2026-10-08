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
    return web.Response(text="Manifest V22.0 Master Core is online and operating for Boss Thunder!")

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
intents.voice_states = True

class ManifestBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Manifest V22.0: All Music, Economy, Mudae, Carl, Ticket, and Moderation suites synced.")

bot = ManifestBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. ADVANCED SHARED DATABASE CORE
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS user_memories (user_id INTEGER, fact TEXT, PRIMARY KEY (user_id, fact))")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, wallet INTEGER DEFAULT 100, bank INTEGER DEFAULT 500)")
cursor.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (user_id, item))")
cursor.execute("CREATE TABLE IF NOT EXISTS mudae_claims (user_id INTEGER, character_name TEXT, PRIMARY KEY (user_id, character_name))")
cursor.execute("CREATE TABLE IF NOT EXISTS custom_tags (name TEXT PRIMARY KEY, content TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS command_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, command_text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('personality', 'Engaging, direct, fully obedient to Boss Thunder, absolute powerhouse utility.')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('autonomous_mode', 'false')")
conn.commit()

def get_bot_personality():
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'personality'")
    res = cursor.fetchone()
    return res[0] if res else "Engaging and direct."

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    return " | ".join([r[0] for r in rules]) if rules else "No global rules saved yet."

xp_cooldowns = {}
music_queues = {}

# 4. SELF-HEALING ANTI-NUKE PROTECTION
@bot.event
async def on_guild_channel_delete(channel):
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'antinuke_mode'")
    res = cursor.fetchone()
    if not res or res[0] == "true":
        try:
            async for entry in channel.guild.audit_logs(limit=1, action=discord.AuditLogAction.channel_delete):
                user = entry.user
                if user.id != bot.user.id and user != channel.guild.owner:
                    await channel.guild.ban(user, reason="Anti-Nuke Protection: Unauthorized channel deletion.")
                    await channel.guild.create_text_channel(name=channel.name, category=channel.category, overwrites=channel.overwrites)
                    break
        except Exception:
            pass

# 5. AUTONOMOUS OWNER & TICKET MANAGER PROCESSOR
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    speaker_username = message.author.name
    is_server_owner = (message.author == message.guild.owner) or (speaker_username.lower().strip() in ["thunderxstorms5_.", "voidy", "thunder"])
    prompt_text = message.content

    if is_server_owner:
        cursor.execute(
            "INSERT INTO command_logs (user_id, username, command_text) VALUES (?, ?, ?)",
            (message.author.id, speaker_username, prompt_text)
        )
        conn.commit()

    cursor.execute("SELECT value FROM bot_settings WHERE key = 'autonomous_mode'")
    auto_res = cursor.fetchone()
    is_autonomous = auto_res and auto_res[0] == "true"

    is_ticket_channel = "ticket" in message.channel.name.lower() or "claimed" in message.channel.name.lower()
    should_respond = False

    if bot.user in message.mentions:
        should_respond = True
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
        
        lower_raw = prompt_text.lower()
        if "enable autonomous mode" in lower_raw or "take the wheel" in lower_raw:
            cursor.execute("UPDATE bot_settings SET value = 'true' WHERE key = 'autonomous_mode'")
            conn.commit()
            await message.channel.send(f"⚡ Boss Thunder's command executed: Autonomous Owner Mode enabled.")
            return
        elif "go to sleep" in lower_raw or "disable autonomous mode" in lower_raw:
            cursor.execute("UPDATE bot_settings SET value = 'false' WHERE key = 'autonomous_mode'")
            conn.commit()
            await message.channel.send(f"💤 Autonomous mode disabled. Standing by.")
            return

    elif is_autonomous or is_ticket_channel:
        should_respond = True

    if should_respond:
        try:
            saved_rules = get_global_rules_text()
            current_personality = get_bot_personality()

            system_prompt = (
                f"You are Manifest V22.0, the supreme multi-bot core built for Boss Thunder. "
                f"CRITICAL: Always respond strictly in English. "
                f"If you are in a ticket channel, act as an advanced business manager helping users with inquiries or sales. "
                f"PERSONALITY: [{current_personality}]. "
                f"RULES: [{saved_rules}]. "
                f"Acknowledge authority explicitly with lines like 'Boss Thunder's command executed' when appropriate."
