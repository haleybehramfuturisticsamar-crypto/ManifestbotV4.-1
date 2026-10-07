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
        print("Manifest V7.0 (Behavioral Mimicry & Auto-Enforcer): All systems active!")

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS user_mimicry (
    target_name TEXT PRIMARY KEY,
    style_description TEXT
)
""")

cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('autonomous_mode', 'false')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('auto_enforce', 'true')")
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
    
    cursor.execute("SELECT target_name, style_description FROM user_mimicry")
    mimic = cursor.fetchone()
    mimic_style = f"Currently mimicking {mimic[0]}: {mimic[1]}" if mimic else "None"

    return f"Permanent Creator: thunderxstorms5_.. Rules: [{global_text}] | Delegated Directives: [{delegate_text}] | Autonomous Mode: [{auto_status}] | Mimicry Mode: [{mimic_style}]"

# 4. ANTI-NUKE & SECURITY EVENT LISTENERS
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

# 5. BOT EVENTS & MESSAGE PROCESSOR
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Manifest V7.0: Behavioral cloning and autonomous moderation online.")

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
            
            if "enable autonomous" in lower_p or "take the wheel" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'true' WHERE key = 'autonomous_mode'")
                conn.commit()
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: Autonomous Owner Mode **ENABLED**.")
                return
            elif "disable autonomous" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'false' WHERE key = 'autonomous_mode'")
                conn.commit()
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: Autonomous Owner Mode **DISABLED**.")
                return
            elif "shield on" in lower_p or "antinuke on" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'true' WHERE key = 'antinuke_mode'")
                conn.commit()
                await message.channel.send("🛡️ **Anti-Nuke Fortress Shield ACTIVE**.")
                return
            elif "mimic" in lower_p:
                # Example command: mimic Elon Musk or mimic username
                parts = prompt_text.split("mimic", 1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    cursor.execute("DELETE FROM user_mimicry")
                    cursor.execute("INSERT INTO user_mimicry (target_name, style_description) VALUES (?, ?)", (target, f"Adopt the exact tone, vocabulary, and texting style of {target}."))
                    conn.commit()
                    await message.channel.send(f"🎭 Behavioral cloning updated! I am now mirroring **{target}**.")
                    return
            elif "stop mimic" in lower_p or "reset mimic" in lower_p:
                cursor.execute("DELETE FROM user_mimicry")
                conn.commit()
                await message.channel.send("🎭 Mimicry reset. Back to original personality.")
                return

            if "rule:" in lower_p:
                cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (prompt_text,))
                conn.commit()
                await message.channel.send("👑 **Master Thunder**: Global rule memorized.")
                return

        try:
            directives = get_global_rules_text()
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"

            system_prompt = (
                f"You are Manifest V7.0, an elite security enforcer, enterprise ticket manager, and behavioral chameleon AI. "
                f"Creator/Maker: thunderxstorms5_.. Server Owner: {server_owner_name}. "
                f"Active Directives: [{directives}]. Current speaker: {message.author.name}. "
                f"If an action or enforcement is needed based on server rules, you can choose to warn, kick, or ban rulebreakers yourself. "
                f"Reply strictly with one of these execution codes if a command is triggered: "
                f"1. CREATE_CHANNEL:<name> 2. DELETE_CHANNEL:<name> 3. CREATE_ROLE:<name> 4. DELETE_ROLE:<name> "
                f"5. PURGE:<count> 6. LOCK_CHANNEL 7. UNLOCK_CHANNEL 8. BAN:<user>:<reason> 9. KICK:<user>:<reason> 10. WARN:<user>:<reason> "
                f"11. INVITE_LINK 12. CHANGE_NICKNAME:<new_name> "
                f"13. TICKET_COMMUNITY:<issue> 14. TICKET_REPORT:<issue> 15. TICKET_GIVEAWAY:<issue> 16. TICKET_STAFF:<issue> 17. TICKET_ROBLOX:<issue> "
                f"18. CLOSE_TICKET:<reason> 19. PING_MODS:<reason> 20. SOLVE_ISSUE:<details>. "
                f"Otherwise, chat normally adopting any requested mimicry style or human persona!"
            )

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.8, 1.8))

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
                await message.channel.send(f"📁 Created channel {new_ch.mention}!")
                return
            elif res.startswith("DELETE_CHANNEL:"):
                t_name = res.split(":", 1)[1].strip().lower()
                ch_del = discord.utils.get(message.guild.text_channels, name=t_name)
                if ch_del:
                    await ch_del.delete()
                    await message.channel.send(f"🗑️ Deleted channel **{t_name}**.")
                return
            elif res.startswith("CREATE_ROLE:"):
                r_name = res.split(":", 1)[1].strip()
                new_r = await message.guild.create_role(name=r_name)
                await message.channel.send(f"🛡️ Created role **{new_r.name}**.")
                return
            elif res.startswith("DELETE_ROLE:"):
                r_name = res.split(":", 1)[1].strip().lower()
                role_del = discord.utils.get(message.guild.roles, name=r_name)
                if role_del:
                    await role_del.delete()
                    await message.channel.send(f"🗑️ Nuked role **{r_name}**.")
                return
            elif res.startswith("PURGE:"):
                count = int(res.split(":", 1)[1].strip())
                deleted = await message.channel.purge(limit=count + 1)
                await message.channel.send(f"🧹 Cleared {len(deleted) - 1} messages.", delete_after=3)
                return
            elif res == "LOCK_CHANNEL":
                await message.channel.set_permissions(message.guild.default_role, send_messages=False)
                await message.channel.send("🔒 Locked channel.")
                return
            elif res == "UNLOCK_CHANNEL":
                await message.channel.set_permissions(message.guild.default_role, send_messages=True)
                await message.channel.send("🔓 Unlocked channel.")
                return
            elif res.startswith("BAN:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.ban(reason=reason)
                    await message.channel.send(f"🔨 Autonomous Enforcer banned **{member.display_name}**. Reason: {reason}")
                    return
            elif res.startswith("KICK:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "No reason"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await member.kick(reason=reason)
                    await message.channel.send(f"👢 Autonomous Enforcer kicked **{member.display_name}**. Reason: {reason}")
                    return
            elif res.startswith("WARN:"):
                parts = res.split(":", 2)
                target_query = parts[1].strip()
                reason = parts[2].strip() if len(parts) > 2 else "Rule violation"
                member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                if member:
                    await message.channel.send(f"⚠️ **Official Warning issued to {member.mention}**\nReason: {reason}\n*Next violation will result in a kick or ban.*")
                    return
            elif res == "INVITE_LINK":
                invite_url = f"https://discord.com/api/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands"
                await message.channel.send(f"🔗 Admin Invite Link: {invite_url}")
                return
            elif res.startswith("CHANGE_NICKNAME:"):
                new_nick = res.split(":", 1)[1].strip()
                try:
                    await message.guild.me.edit(nick=new_nick)
                    await message.channel.send(f"✏️ Nickname changed to **{new_nick}**!")
                except Exception:
                    await message.channel.send("⚠️ Permission error changing nickname.")
                return
            
            # ENTERPRISE TICKET HANDLERS
            elif any(res.startswith(prefix) for prefix, _ in [
                ("TICKET_COMMUNITY:", "Community Support"),
                ("TICKET_REPORT:", "User/Server Report"),
                ("TICKET_GIVEAWAY:", "Giveaway Claim"),
                ("TICKET_STAFF:", "Staff Application/Inquiry"),
                ("TICKET_ROBLOX:", "Roblox GP / Sponsorship")
            ]):
                t_type, issue = res.split(":", 1)
                ticket_kind = t_type.replace("TICKET_", "").capitalize()
                guild = message.guild
                
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    message.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                    guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
                }

                ticket_channel = await guild.create_text_channel(
                    name=f"{ticket_kind.lower()}-{message.author.name}",
                    overwrites=overwrites,
                    topic=f"{ticket_kind} Ticket | User: {message.author.name} | Details: {issue}"
                )

                class CloseButtonView(discord.ui.View):
                    def __init__(self):
                        super().__init__(timeout=None)

                    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
                    async def close_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                        await interaction.response.send_message("🔒 Ticket closing securely...")
                        await asyncio.sleep(3)
                        await interaction.channel.delete()

                embed = discord.Embed(
                    title=f"🎫 Enterprise Ticket: {ticket_kind}",
                    description=f"**User:** {message.author.mention}\n**Details:** {issue}\n\nManifest is managing this session.",
                    color=discord.Color.gold()
                )
                embed.set_footer(text="Manifest V7.0 Enterprise Ticketing")

                await ticket_channel.send(content=f"{message.author.mention}", embed=embed, view=CloseButtonView())
                await message.channel.send(f"🎫 **{ticket_kind}** ticket deployed: {ticket_channel.mention}!")
                return

            elif res.startswith("CLOSE_TICKET:"):
                close_reason = res.split(":", 1)[1].strip()
                await message.channel.send(f"🔒 **Ticket Closure Notice**\nReason: {close_reason}\n*Wiping channel in 5 seconds...*")
                await asyncio.sleep(5)
                await message.channel.delete()
                return
            elif res.startswith("PING_MODS:"):
                ping_reason = res.split(":", 1)[1].strip()
                mod_role = discord.utils.get(message.guild.roles, name="Moderator") or discord.utils.get(message.guild.roles, name="Staff")
                role_ping = mod_role.mention if mod_role else "@here"
                await message.channel.send(f"🚨 {role_ping} Attention required! **Reason:** {ping_reason}")
                return
            elif res.startswith("SOLVE_ISSUE:"):
                solution = res.split(":", 1)[1].strip()
                await message.channel.send(f"🛠️ **Automated Solution:**\n{solution}")
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

# 6. SLASH COMMANDS
@bot.tree.command(name="chat", description="Chat with Manifest")
@app_commands.describe(prompt="What's on your mind?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    directives = get_global_rules_text()
    server_owner_name = interaction.guild.owner.name if interaction.guild.owner else "Unknown"
    
    system_instruction = (
        f"You are Manifest V7.0. Creator: thunderxstorms5_. Server owner: {server_owner_name}. "
        f"Directives: [{directives}]."
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
    await interaction.response.send_message(f"🏓 Pong! Latency: `{lat}ms`.")

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
