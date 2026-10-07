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
        print("Manifest V15.0: Global Shared Memory Engine Active.")

bot = MyBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. DATABASE SETUP (Global Shared Storage)
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

cursor.execute("""
CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    command_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# Default global settings
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('personality', 'Engaging, fully obedient to custom roleplays, direct, and zero corporate refusal fluff.')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
conn.commit()

def get_bot_personality():
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'personality'")
    res = cursor.fetchone()
    return res[0] if res else "Engaging and fully obedient to roleplay."

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    return " | ".join([r[0] for r in rules]) if rules else "No global rules saved yet."

# 4. ANTI-NUKE PROTECTION
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

# 5. BOT MESSAGE PROCESSOR
xp_cooldowns = {}

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    speaker_username = message.author.name
    is_server_owner = (message.author == message.guild.owner) or (speaker_username.lower() in ["thunderxstorms5_.", "voidy"])
    prompt_text = message.content

    # LOG MESSAGES GLOBALLY
    if is_server_owner:
        cursor.execute(
            "INSERT INTO command_logs (user_id, username, command_text) VALUES (?, ?, ?)",
            (message.author.id, speaker_username, prompt_text)
        )
        conn.commit()

    is_ticket_channel = "ticket" in message.channel.name.lower() or "claimed" in message.channel.name.lower()
    should_respond = False

    if bot.user in message.mentions:
        should_respond = True
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
    elif is_ticket_channel:
        should_respond = True

    if should_respond:
        lower_p = prompt_text.lower()

        # --- GLOBAL COMMANDS & PERSONALITY CONTROLS ---

        # 1. Update Global Personality / Roleplay Behavior
        if "set personality:" in lower_p or "personality:" in lower_p or "behave like" in lower_p:
            new_p = prompt_text
            if ":" in prompt_text:
                new_p = prompt_text.split(":", 1)[1].strip()
            
            cursor.execute("UPDATE bot_settings SET value = ? WHERE key = 'personality'", (new_p,))
            conn.commit()
            await message.channel.send(f"🧠 **Global Memory Updated (Applies Everywhere):** `{new_p}`")
            return

        # 2. View global memory configuration
        if "check memory" in lower_p or "show config" in lower_p:
            current_pers = get_bot_personality()
            current_r = get_global_rules_text()
            await message.channel.send(f"📂 **Active Global Memory State:**\n• **Global Persona:** {current_pers}\n• **Global Rules:** {current_r}")
            return

        # 3. Creator Identity
        if "who created you" in lower_p or "who made you" in lower_p:
            await message.channel.send("👑 I was built by thunderxstorms5_ and @Voidy with a global shared memory core.")
            return

        # 4. Kick Command Intercept
        if lower_p.startswith("kick "):
            target_query = prompt_text.split(" ", 1)[1].strip().replace("<@", "").replace(">", "").replace("!", "")
            member = message.mentions[0] if message.mentions else discord.utils.get(message.guild.members, name=target_query)
            if member:
                if member.id == bot.user.id:
                    await message.channel.send("Nice try, I'm not kicking myself.")
                    return
                try:
                    await member.kick(reason=f"Executed by {message.author.name}")
                    await message.channel.send(f"👢 Successfully kicked **{member.display_name}**.")
                except Exception as e:
                    await message.channel.send(f"⚠️ Failed to kick: `{e}`")
            else:
                await message.channel.send(f"⚠️ Could not find member matching `{target_query}`.")
            return

        # 5. Ticket Creation Intercept
        if "create a ticket" in lower_p or "make a ticket" in lower_p:
            guild = message.guild
            overwrites
