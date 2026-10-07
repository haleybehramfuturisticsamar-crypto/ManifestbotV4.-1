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

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("Manifest V4.1 (God Tier Edition): All commands synced successfully!")

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
CREATE TABLE IF NOT EXISTS user_memories (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    notes TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS global_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS delegated_commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_username TEXT,
    instruction TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    user_id INTEGER,
    guild_id INTEGER,
    status TEXT DEFAULT 'open'
)
""")
conn.commit()

xp_cooldowns = {}

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    global_text = " | ".join([r[0] for r in rules]) if rules else "None"
    
    cursor.execute("SELECT target_username, instruction FROM delegated_commands")
    delegates = cursor.fetchall()
    delegate_text = " | ".join([f"Follow commands of {d[0]}: {d[1]}" for d in delegates]) if delegates else "None"
    
    return f"Permanent Creator Rules: [{global_text}] | Delegated User Directives: [{delegate_text}]"

# 4. BOT EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Manifest V4.1 core online: Absolute loyalty to thunderxstorms5_. locked in globally.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    if bot.user in message.mentions:
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
        
        if message.author.name == "thunderxstorms5_.":
            lower_p = prompt_text.lower()
            
            if "follow" in lower_p and "command" in lower_p or "follow what" in lower_p:
                if message.mentions:
                    for mentioned_user in message.mentions:
                        if mentioned_user.id != bot.user.id and mentioned_user.id != message.author.id:
                            sub_instruction = prompt_text.split(":")[-1].strip()
                            cursor.execute("INSERT INTO delegated_commands (target_username, instruction) VALUES (?, ?)", (mentioned_user.name, sub_instruction))
                            conn.commit()
                            await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Delegated! I will now follow commands/directives from **{mentioned_user.name}**: *\"{sub_instruction}\"*")
                            return

            if "stop using" in lower_p or "always" in lower_p or "never" in lower_p or "rule:" in lower_p:
                cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (prompt_text,))
                conn.commit()
                await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Global rule permanently memorized and enforced everywhere: *\"{prompt_text}\"*")
                return

        try:
            directives = get_global_rules_text()
            is_delegated_user = False
            cursor.execute("SELECT instruction FROM delegated_commands WHERE target_username = ?", (message.author.name,))
            del_res = cursor.fetchone()
            if del_res:
                is_delegated_user = True

            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {
                        "role": "system", 
                        "content": f"You are Manifest V4.1, Thunder's ultimate bot. Owner is thunderxstorms5_.. Active System Instructions & Delegations: [{directives}]. Current speaker: {message.author.name} (Delegated status: {is_delegated_user}). If admin wants to ban, reply: BAN:<username_or_id>:<reason>. If kick, reply: KICK:<username_or_id>:<reason>. Otherwise, reply normally, obeying Master Thunder and factoring in any active user delegations."
                    },
                    {"role": "user", "content": prompt_text}
                ]
            )
            res = completion.choices[0].message.content.strip()
            if res.startswith("BAN:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.ban(reason=reason)
                    await message.channel.send(f"🔨 Master Thunder's orders executed: Banned **{member.display_name}**. Reason: {reason}")
                    return
            elif res.startswith("KICK:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.kick(reason=reason)
                    await message.channel.send(f"👢 Master Thunder's orders executed: Kicked **{member.display_name}**. Reason: {reason}")
                    return
            else:
                await message.channel.send(res)
        except Exception as e:
            pass

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
            next_level_xp = (current_lvl + 1) * 100
            if current_xp >= next_level_xp:
                current_lvl += 1
                await message.channel.send(f"🎉 {message.author.mention} reached **Level {current_lvl}**!")
            cursor.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (current_xp, current_lvl, user_id))
        conn.commit()

    await bot.process_commands(message)

# 5. SLASH COMMANDS
@bot.tree.command(name="chat", description="Chat with Manifest V4.1")
@app_commands.describe(prompt="What would you like to say to the AI?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    user_id = interaction.user.id
    username = interaction.user.name
    display_name = interaction.user.display_name

    cursor.execute("SELECT notes FROM user_memories WHERE user_id = ?", (user_id,))
    mem_result = cursor.fetchone()
    stored_notes = mem_result[0] if mem_result else "No prior notes saved for this user."

    directives = get_global_rules_text()
    cursor.execute("SELECT instruction FROM delegated_commands WHERE target_username = ?", (username,))
    del_res = cursor.fetchone()
    delegated_rule = del_res[0] if del_res else "None"

    system_instruction = (
        f"You are Manifest V4.1, Thunder's advanced bot. Owner is thunderxstorms5_. "
        f"Global Active Directives: [{directives}]. Delegated rule for '{username}': [{delegated_rule}]."
    )

    try:
        chat_completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        response_text = chat_completion.choices[0].message.content
        await interaction.followup.send(response_text[:2000])
    except Exception as e:
        await interaction.followup.send(f"⚠️ Groq Error: `{e}`")

@bot.tree.command(name="ping", description="Check bot's latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is `{lat}ms`.")

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
