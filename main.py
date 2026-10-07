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
                    "You are Manifest V7.9 acting as an Autonomous Ticket Support Agent. "
                    "No human moderator has answered yet, so you must help the user resolve their issue completely. "
                    "Be sharp, helpful, technical, and polite. Walk them through troubleshooting steps step-by-step. "
                    f"Creator: thunderxstorms5_. Current User: {speaker_username} ({speaker_display})."
                )
            else:
                system_prompt = (
                    "You are Manifest V7.9, an elite security sentinel and assistant. "
                    f"Creator/Master: thunderxstorms5_. Server Owner: {server_owner_name}. "
                    f"CURRENT SPEAKER -> Username: {speaker_username}, Display Name: {speaker_display}, Is Master Thunder: {'Yes' if is_master else 'No'}. "
                    "Be confident, concise, and smart. Reply directly to the user."
                )

            async with message.channel.typing():
                completion = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text}
                    ]
                )
                res = completion.choices[0].message.content.strip()

            if res:
                await message.channel.send(res)
            return

        except Exception as e:
            await message.channel.send(f"⚠️ System handled smoothly.")
            return

    # XP System Handler
    user_id = message.author.id
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    if user_id not in xp_cooldowns or now - xp_cooldowns[user_id] > 60:
        xp_cooldowns[user_id] = now
        cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if result is None:
            cursor.execute("INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)", (user_id, 15, 0))
        else:
            current_xp, current_lvl = result
            current_xp += random.randint(15, 25)
            if current_xp >= (current_lvl + 1) * 100:
                current_lvl += 1
                await message.channel.send(f"⚡ {message.author.mention} advanced to **Level {current_lvl}**.")
            cursor.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (current_xp, current_lvl, user_id))
        conn.commit()

    await bot.process_commands(message)

# 6. FULL SLASH COMMAND SUITE
@bot.tree.command(name="chat", description="Chat with Manifest")
@app_commands.describe(prompt="What's on your mind?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are Manifest V7.9, an elite security bot created by thunderxstorms5_."},
                {"role": "user", "content": prompt}
            ]
        )
        await interaction.followup.send(completion.choices[0].message.content[:2000])
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: `{e}`")

@bot.tree.command(name="ping", description="Check bot status and latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Latency: `{lat}ms`. Systems fully operational.")

@bot.tree.command(name="lock", description="Lock the current channel down")
async def lock(interaction: discord.Interaction):
    if interaction.user.guild_permissions.manage_channels:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message("🔒 Channel locked down successfully.")
    else:
        await interaction.response.send_message("⚠️ You lack permissions to lock channels.", ephemeral=True)

@bot.tree.command(name="unlock", description="Unlock the current channel")
async def unlock(interaction: discord.Interaction):
    if interaction.user.guild_permissions.manage_channels:
        await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message("🔓 Channel unlocked.")
    else:
        await interaction.response.send_message("⚠️ You lack permissions to unlock channels.", ephemeral=True)

@bot.tree.command(name="purge", description="Clear a specified number of messages")
@app_commands.describe(count="Number of messages to clear")
async def purge(interaction: discord.Interaction, count: int):
    if interaction.user.guild_permissions.manage_messages:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=count)
        await interaction.followup.send(f"🧹 Swept away {len(deleted)} messages.", ephemeral=True)
    else:
        await interaction.response.send_message("⚠️ You lack permission to manage messages.", ephemeral=True)

@bot.tree.command(name="ticket", description="Open a support ticket channel")
@app_commands.describe(issue="Brief description of your issue")
async def ticket(interaction: discord.Interaction, issue: str):
    guild = interaction.guild
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    ticket_ch = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name}",
        overwrites=overwrites,
        topic=f"Support Ticket | User: {interaction.user.name} | Issue: {issue}"
    )
    embed = discord.Embed(
        title="🎫 Secure Support Ticket",
        description=f"**User:** {interaction.user.mention}\n**Issue:** {issue}\n\n*If staff are unavailable, I will personally assist you here.*",
        color=discord.Color.gold()
    )
    await ticket_ch.send(content=f"{interaction.user.mention}", embed=embed)
    await interaction.response.send_message(f"🎫 Ticket deployed: {ticket_ch.mention}", ephemeral=True)

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
