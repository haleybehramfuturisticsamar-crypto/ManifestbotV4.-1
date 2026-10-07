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
        print("Manifest V9.0: Bulletproof Master Protocol Active.")

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
    return " | ".join([r[0] for r in rules]) if rules else "No custom restrictions."

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
        is_master = (speaker_username.lower() == "thunderxstorms5_.")
        lower_p = prompt_text.lower()

        # --- BULLETPROOF COMMAND INTERCEPTORS ---

        # Creator / Identity Check Override (Never fails)
        if "who created you" in lower_p or "who made you" in lower_p or "who is your creator" in lower_p:
            await message.channel.send("👑 I was created and built entirely by **thunderxstorms5_.** He is my master and owner.")
            return

        if is_master:
            if "who am i" in lower_p or "check my user" in lower_p:
                await message.channel.send(f"👑 You are Master Thunder (`{speaker_username}`), my absolute creator and owner.")
                return
            elif "am i your creator" in lower_p or "am i your owner" in lower_p:
                await message.channel.send("👑 Yes, absolutely. You are thunderxstorms5_., my creator and master. I follow your every command.")
                return
            elif "remember rule:" in lower_p or "from now on" in lower_p:
                custom_rule = prompt_text.split(":", 1)[1].strip() if ":" in prompt_text else prompt_text
                cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (custom_rule,))
                conn.commit()
                await message.channel.send(f"👑 **Master Thunder**: Directive locked into core memory -> *{custom_rule}*")
                return
            elif "clear rules" in lower_p:
                cursor.execute("DELETE FROM global_rules")
                conn.commit()
                await message.channel.send("👑 **Master Thunder**: All custom core restrictions cleared.")
                return

        # Kick Command Intercept (Supports mentions or text names)
        if lower_p.startswith("kick "):
            target_query = prompt_text.split(" ", 1)[1].strip().replace("<@", "").replace(">", "").replace("!", "")
            member = None
            if message.mentions:
                member = message.mentions[0]
            else:
                member = discord.utils.get(message.guild.members, name=target_query) or discord.utils.get(message.guild.members, display_name=target_query)
            
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

        # Ban Command Intercept
        if lower_p.startswith("ban "):
            target_query = prompt_text.split(" ", 1)[1].strip().replace("<@", "").replace(">", "").replace("!", "")
            member = message.mentions[0] if message.mentions else discord.utils.get(message.guild.members, name=target_query)
            if member:
                try:
                    await member.ban(reason=f"Executed by {message.author.name}")
                    await message.channel.send(f"🔨 Banned **{member.display_name}**.")
                except Exception as e:
                    await message.channel.send(f"⚠️ Failed to ban: `{e}`")
            else:
                await message.channel.send(f"⚠️ Could not find member matching `{target_query}`.")
            return

        # Ticket Creation Intercept
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
                description=f"**Creator:** {message.author.mention}\n**Status:** Open\n\n*I'm locked into this ticket channel with you to help sort it out.*",
                color=discord.Color.gold()
            )
            await ticket_ch.send(content=f"{message.author.mention}", embed=embed)
            await message.channel.send(f"🎫 Ticket created: {ticket_ch.mention}")
            return

        # --- STANDARD AI FALLBACK WITH HARDCODED CREATOR IDENTITY ---
        try:
            saved_rules = get_global_rules_text()
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"

            system_prompt = (
                f"You are Manifest V9.0, an elite assistant and security bot. "
                f"YOUR CREATOR, MASTER, AND OWNER IS thunderxstorms5_. NEVER say you were created by OpenAI or any other company. "
                f"Server Owner: {server_owner_name}. Current Speaker: {speaker_username}. "
                f"Active Rules/Directives set by Master Thunder: [{saved_rules}]. "
                f"Keep your tone chill, completely loyal, direct, and zero corporate fluff."
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
            await message.channel.send(f"⚠️ Systems running smoothly.")
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
                {"role": "system", "content": f"You are Manifest V9.0, created solely by thunderxstorms5_."},
                {"role": "user", "content": prompt}
            ]
        )
        await interaction.followup.send(completion.choices[0].message.content[:2000])
    except Exception as e:
        await interaction.followup.send(f"⚠️ Error: `{e}`")

@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Latency: `{lat}ms`. All systems locked in.")

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
        title="🎫 Support Ticket Deployed",
        description=f"**User:** {interaction.user.mention}\n**Issue:** {issue}\n\n*Ticket online. I'm right here in the channel with you.*",
        color=discord.Color.gold()
    )
    await ticket_ch.send(content=f"{interaction.user.mention}", embed=embed)
    await interaction.response.send_message(f"🎫 Ticket created: {ticket_ch.mention}", ephemeral=True)

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
