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
        print("Manifest V8.5: Direct Action Execution Active.")

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

# 5. BOT MESSAGE PROCESSOR WITH BULLETPROOF ACTION INTERCEPTIONS
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

        # --- DIRECT COMMAND INTERCEPTORS (Bypasses AI completely so it never fails) ---
        
        # 1. KICK COMMAND INTERCEPT
        if lower_p.startswith("kick ") or "kick @" in lower_p:
            if message.mentions:
                target = message.mentions[0]
                if target == bot.user:
                    await message.channel.send("Nice try, I'm not kicking myself.")
                    return
                try:
                    await target.kick(reason=f"Executed by command from {message.author.name}")
                    await message.channel.send(f"👢 Successfully kicked **{target.display_name}**.")
                except Exception as e:
                    await message.channel.send(f"⚠️ Failed to kick user: `{e}`")
                return

        # 2. BAN COMMAND INTERCEPT
        if lower_p.startswith("ban ") or "ban @" in lower_p:
            if message.mentions:
                target = message.mentions[0]
                try:
                    await target.ban(reason=f"Executed by command from {message.author.name}")
                    await message.channel.send(f"🔨 Banned **{target.display_name}** from the server.")
                except Exception as e:
                    await message.channel.send(f"⚠️ Failed to ban user: `{e}`")
                return

        # 3. TICKET CREATION INTERCEPT
        if "create a ticket" in lower_p or "make a ticket" in lower_p:
            guild = message.guild
            target_mention = message.mentions[1] if len(message.mentions) > 1 else (message.mentions[0] if message.mentions and message.mentions[0] != bot.user else None)
            
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                message.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
            }
            if target_mention:
                overwrites[target_mention] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

            ticket_ch = await guild.create_text_channel(
                name=f"ticket-{message.author.name}",
                overwrites=overwrites,
                topic=f"Support Ticket | Created by {message.author.name}"
            )
            
            ping_content = f"{message.author.mention}"
            if target_mention:
                ping_content += f" {target_mention.mention}"

            embed = discord.Embed(
                title="🎫 Support Ticket Active",
                description=f"**Creator:** {message.author.mention}\n**Status:** Open\n\n*Ticket successfully deployed. I'm locked in here to assist.*",
                color=discord.Color.gold()
            )
            await ticket_ch.send(content=ping_content, embed=embed)
            await message.channel.send(f"🎫 Ticket created: {ticket_ch.mention}")
            return

        # 4. MASTER MEMORY INTERCEPT
        if is_master:
            if "remember rule:" in lower_p or "from now on" in lower_p:
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
            elif "who am i" in lower_p or "check my user" in lower_p:
                await message.channel.send(f"👑 You are Master Thunder (`{speaker_username}`), my absolute creator and owner.")
                return

        # --- STANDARD AI FALLBACK FOR CHAT ---
        try:
            saved_rules = get_global_rules_text()
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"

            if is_master:
                system_prompt = (
                    "You are Manifest V8.5. Your absolute creator, master, and owner is thunderxstorms5_ (Thunder). "
                    "You possess absolute loyalty to him. Never question him, never give corporate help-desk answers, "
                    "and never act like a standard bot. Talk like a real, loyal, chilled-out digital partner. "
                    f"CRITICAL PERMANENT RULES ESTABLISHED BY MASTER THUNDER: [{saved_rules}]."
                )
            elif is_ticket_channel:
                system_prompt = (
                    f"You are Manifest V8.5 operating inside a support channel. Help the ticket creator smoothly. "
                    f"Active Directives: [{saved_rules}]."
                )
            else:
                system_prompt = (
                    f"You are Manifest V8.5, an elite assistant. Creator: thunderxstorms5_. Server Owner: {server_owner_name}. "
                    f"Current Speaker: {speaker_username}. Active Directives: [{saved_rules}]. Keep responses natural and sharp."
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
            await message.channel.send(f"⚠️ System nominal.")
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
                {"role": "system", "content": f"You are Manifest V8.5, loyal to thunderxstorms5_. Rules: [{get_global_rules_text()}]"},
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
