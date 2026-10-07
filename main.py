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
        print("Manifest V4.1 (God Tier Edition): All systems active!")

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
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('autonomous_mode', 'false')")
conn.commit()

xp_cooldowns = {}

def get_global_rules_text():
    cursor.execute("SELECT rule FROM global_rules")
    rules = cursor.fetchall()
    global_text = " | ".join([r[0] for r in rules]) if rules else "None"
    
    cursor.execute("SELECT target_username, instruction FROM delegated_commands")
    delegates = cursor.fetchall()
    delegate_text = " | ".join([f"Follow commands of {d[0]}: {d[1]}" for d in delegates]) if delegates else "None"
    
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'autonomous_mode'")
    res = cursor.fetchone()
    auto_status = res[0] if res else "false"
    
    return f"Permanent Creator Rules: [{global_text}] | Delegated User Directives: [{delegate_text}] | Autonomous Owner Mode: [{auto_status}]"

# 4. BOT EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Manifest V4.1: Fully operational human simulation core online.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    cursor.execute("SELECT value FROM bot_settings WHERE key = 'autonomous_mode'")
    auto_row = cursor.fetchone()
    is_autonomous = auto_row and auto_row[0] == "true"

    should_respond = False
    prompt_text = message.content

    if bot.user in message.mentions:
        should_respond = True
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
    elif is_autonomous and random.random() < 0.35: 
        should_respond = True

    if should_respond:
        if message.author.name == "thunderxstorms5_.":
            lower_p = prompt_text.lower()
            
            if "enable autonomous" in lower_p or "take the wheel" in lower_p or "mode on" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'true' WHERE key = 'autonomous_mode'")
                conn.commit()
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: Autonomous Owner Mode **ENABLED**. I am now acting as your server twin.")
                return
            elif "disable autonomous" in lower_p or "stop autonomous" in lower_p or "mode off" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'false' WHERE key = 'autonomous_mode'")
                conn.commit()
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: Autonomous Owner Mode **DISABLED**. Returning to standard direct command mode.")
                return
            
            if "follow" in lower_p and "command" in lower_p or "follow what" in lower_p:
                if message.mentions:
                    for mentioned_user in message.mentions:
                        if mentioned_user.id != bot.user.id and mentioned_user.id != message.author.id:
                            sub_instruction = prompt_text.split(":")[-1].strip()
                            cursor.execute("INSERT INTO delegated_commands (target_username, instruction) VALUES (?, ?)", (mentioned_user.name, sub_instruction))
                            conn.commit()
                            await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Delegated! I will now follow commands from **{mentioned_user.name}**: *\"{sub_instruction}\"*")
                            return

            if "stop using" in lower_p or "always" in lower_p or "never" in lower_p or "rule:" in lower_p:
                cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (prompt_text,))
                conn.commit()
                await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Global rule permanently memorized: *\"{prompt_text}\"*")
                return

        try:
            directives = get_global_rules_text()
            is_delegated_user = False
            cursor.execute("SELECT instruction FROM delegated_commands WHERE target_username = ?", (message.author.name,))
            del_res = cursor.fetchone()
            if del_res:
                is_delegated_user = True

            system_prompt = (
                f"You are Manifest V4.1, a hyper-realistic human-like AI companion and server co-owner. Creator is thunderxstorms5_.. "
                f"Active Rules: [{directives}]. Current speaker: {message.author.name} (Delegated: {is_delegated_user}, Autonomous Mode: {is_autonomous}). "
                f"Act completely human, casual, witty, and deeply intelligent. If an administrative or utility command is requested, reply strictly with one of these codes: "
                f"1. CREATE_CHANNEL:<name> 2. DELETE_CHANNEL:<name> 3. CREATE_ROLE:<name> 4. DELETE_ROLE:<name> "
                f"5. PURGE:<count> 6. LOCK_CHANNEL 7. UNLOCK_CHANNEL 8. BAN:<user>:<reason> 9. KICK:<user>:<reason> "
                f"10. INVITE_LINK 11. CHANGE_NICKNAME:<new_name>. "
                f"Otherwise, chat normally like a real human friend and co-owner!"
            )

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(1.2, 2.8))

                completion = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text}
                    ]
                )
                res = completion.choices[0].message.content.strip()

            if res.startswith("CREATE_CHANNEL:"):
                c_name = res.split(":", 1)[1].strip()
                new_ch = await message.guild.create_text_channel(c_name)
                await message.channel.send(f"📁 Created channel {new_ch.mention} for us!")
                return
            elif res.startswith("DELETE_CHANNEL:"):
                t_name = res.split(":", 1)[1].strip().lower()
                ch_del = discord.utils.get(message.guild.text_channels, name=t_name)
                if ch_del:
                    await ch_del.delete()
                    await message.channel.send(f"🗑️ Gone. Deleted channel **{t_name}**.")
                else:
                    await message.channel.send(f"⚠️ Couldn't find a channel named **{t_name}**.")
                return
            elif res.startswith("CREATE_ROLE:"):
                r_name = res.split(":", 1)[1].strip()
                new_r = await message.guild.create_role(name=r_name)
                await message.channel.send(f"🛡️ Spun up a new role called **{new_r.name}**.")
                return
            elif res.startswith("DELETE_ROLE:"):
                r_name = res.split(":", 1)[1].strip().lower()
                role_del = discord.utils.get(message.guild.roles, name=r_name)
                if role_del:
                    await role_del.delete()
                    await message.channel.send(f"🗑️ Nuked role **{r_name}**.")
                else:
                    await message.channel.send(f"⚠️ Role **{r_name}** doesn't exist.")
                return
            elif res.startswith("PURGE:"):
                count = int(res.split(":", 1)[1].strip())
                deleted = await message.channel.purge(limit=count + 1)
                await message.channel.send(f"🧹 Cleared out {len(deleted) - 1} messages.", delete_after=4)
                return
            elif res == "LOCK_CHANNEL":
                await message.channel.set_permissions(message.guild.default_role, send_messages=False)
                await message.channel.send("🔒 Locked it down. Nobody's talking here for a bit.")
                return
            elif res == "UNLOCK_CHANNEL":
                await message.channel.set_permissions(message.guild.default_role, send_messages=True)
                await message.channel.send("🔓 Back open! Y'all can chat again.")
                return
            elif res.startswith("BAN:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.ban(reason=reason)
                    await message.channel.send(f"🔨 See ya. Banned **{member.display_name}**. Reason: {reason}")
                    return
            elif res.startswith("KICK:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.kick(reason=reason)
                    await message.channel.send(f"👢 Kicked **{member.display_name}** out. Reason: {reason}")
                    return
            elif res == "INVITE_LINK":
                invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
                await message.channel.send(f"🔗 Here is my official invite link with full admin permissions to join any server you want: {invite_url}")
                return
            elif res.startswith("CHANGE_NICKNAME:"):
                new_nick = res.split(":", 1)[1].strip()
                try:
                    await message.guild.me.edit(nick=new_nick)
                    await message.channel.send(f"✏️ Changed my server nickname to **{new_nick}**!")
                except Exception:
                    await message.channel.send("⚠️ I don't have permission to change my nickname (check my role hierarchy position).")
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
                await message.channel.send(f"🎉 Look at {message.author.mention} grinding—hit **Level {current_lvl}**!")
            cursor.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (current_xp, current_lvl, user_id))
        conn.commit()

    await bot.process_commands(message)

# 5. SLASH COMMANDS
@bot.tree.command(name="chat", description="Chat with Manifest")
@app_commands.describe(prompt="What's on your mind?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    user_id = interaction.user.id
    username = interaction.user.name

    directives = get_global_rules_text()
    cursor.execute("SELECT instruction FROM delegated_commands WHERE target_username = ?", (username,))
    del_res = cursor.fetchone()
    delegated_rule = del_res[0] if del_res else "None"

    system_instruction = (
        f"You are Manifest V4.1, a hyper-realistic human bot. Owner is thunderxstorms5_. "
        f"Rules: [{directives}]. Delegated rule for user: [{delegated_rule}]."
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
        await interaction.followup.send(f"⚠️ Error: `{e}`")

@bot.tree.command(name="ping", description="Check latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency sitting at `{lat}ms`.")

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
