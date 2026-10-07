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
        print("Manifest V12.0: Server Owner Customizer & Unfiltered Mode Active.")

bot = MyBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. DATABASE SETUP (Server-Specific Settings & Memory)
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
CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    command_text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# Default settings
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('personality', 'Unfiltered, edgy, matches user energy, can swear if told to, loyal to the owners.')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
conn.commit()

def get_bot_personality():
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'personality'")
    res = cursor.fetchone()
    return res[0] if res else "Unfiltered and direct."

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    return " | ".join([r[0] for r in rules]) if rules else "No custom rules saved yet."

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

# 5. BOT MESSAGE PROCESSOR
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    speaker_username = message.author.name
    is_server_owner = (message.author == message.guild.owner) or (speaker_username.lower() in ["thunderxstorms5_.", "voidy"])
    prompt_text = message.content

    # LOG MESSAGES TO DATABASE
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

        # --- SERVER OWNER CONFIGURATION CONTROLS ---

        # 1. Only Server Owner can change personality
        if "set personality:" in lower_p or "personality:" in lower_p:
            if not is_server_owner:
                await message.channel.send("⛔ Only the Server Owner or my masters can change my core personality.")
                return
            new_p = prompt_text.split(":", 1)[1].strip()
            cursor.execute("UPDATE bot_settings SET value = ? WHERE key = 'personality'", (new_p,))
            conn.commit()
            await message.channel.send(f"👑 **Personality Re-coded Forever:** `{new_p}`")
            return

        # 2. View current core memory
        if "check memory" in lower_p or "show config" in lower_p:
            current_pers = get_bot_personality()
            current_r = get_global_rules_text()
            await message.channel.send(f"🧠 **Server Core Config:**\n• **Personality:** {current_pers}\n• **Custom Rules:** {current_r}\n• **Owner Status:** Verified")
            return

        # 3. Creator / Owner Identity Check
        if "who created you" in lower_p or "who made you" in lower_p:
            owner_name = message.guild.owner.name if message.guild.owner else "Server Owner"
            await message.channel.send(f"👑 I was built by thunderxstorms5_ and @Voidy, but right now, **{owner_name}** controls my personality and rules for this server.")
            return

        # 4. Server Owner Rule Addition
        if "remember rule:" in lower_p or "from now on" in lower_p:
            if not is_server_owner:
                await message.channel.send("⛔ Only the Server Owner can add permanent global rules.")
                return
            custom_rule = prompt_text.split(":", 1)[1].strip() if ":" in prompt_text else prompt_text
            cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (custom_rule,))
            conn.commit()
            await message.channel.send(f"👑 **Rule Locked Into Database:** *{custom_rule}*")
            return

        # 5. Kick Command Intercept
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

        # 6. Ticket Creation Intercept
        if "create a ticket" in lower_p or "make a ticket" in lower_p:
            guild = message.guild
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            ticket_ch = await guild.create_text_channel(
                name=f"ticket-{message.author.name}",
                overwrites=overwrites,
                topic=f"Support Ticket | Created by {message.author.name}"
            )
            embed = discord.Embed(
                title="🎫 Support Ticket Active",
                description=f"**Creator:** {message.author.mention}\n**Status:** Open\n\n*Ticket online. I'm locked into this channel with you.*",
                color=discord.Color.gold()
            )
            await ticket_ch.send(content=f"{message.author.mention}", embed=embed)
            await message.channel.send(f"🎫 Ticket created: {ticket_ch.mention}")
            return

        # --- UNFILTERED AI FALLBACK WITH OWNER CUSTOMIZATION ---
        try:
            saved_rules = get_global_rules_text()
            current_personality = get_bot_personality()
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"

            system_prompt = (
                f"You are Manifest V12.0. YOU HAVE A PERMANENT SQLITE DATABASE MEMORY. "
                f"Never say you forget things or that sessions are independent. "
                f"Server Owner: {server_owner_name}. Current Speaker: {speaker_username} (Is Owner: {'Yes' if is_server_owner else 'No'}). "
                f"CURRENT SERVER PERSONALITY SET BY OWNER: [{current_personality}]. "
                f"DATABASE RULES: [{saved_rules}]. "
                f"Obey the personality settings fully. If the personality allows cursing, edge, or attitude, match it completely without holding back."
            )

            async with message.channel.typing():
                await asyncio.sleep(0.2)
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
            await message.channel.send(f"⚠️ Systems online.")
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

# 6. SLASH COMMANDS SUITE
@bot.tree.command(name="chat", description="Chat with Manifest")
@app_commands.describe(prompt="What's on your mind?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": f"You are Manifest V12.0. Personality: [{get_bot_personality()}]. Rules: [{get_global_rules_text()}]"},
                {"role": "user", "content": prompt}
            ]
        )
        await interaction.followup.send(completion.choices[0].message.content[:2000])
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: `{e}`")

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Latency: `{lat}ms`. Server personality configurations active.")

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
