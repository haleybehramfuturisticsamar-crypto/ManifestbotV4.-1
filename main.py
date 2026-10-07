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
        print("Manifest V7.6 (Unyielding Loyalty & Elite Personality Matrix): Systems Online.")

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

# 5. BOT EVENTS & MESSAGE PROCESSOR
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
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: My core routing is locked to you. Autonomous Owner Mode **ENABLED**.")
                return
            elif "disable autonomous" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'false' WHERE key = 'autonomous_mode'")
                conn.commit()
                await message.channel.send("👑 **Master Thunder (`thunderxstorms5_.`)**: Autonomous Owner Mode **DISABLED**.")
                return
            elif "shield on" in lower_p or "antinuke on" in lower_p:
                cursor.execute("UPDATE bot_settings SET value = 'true' WHERE key = 'antinuke_mode'")
                conn.commit()
                await message.channel.send("🛡️ **Anti-Nuke Fortress Shield ACTIVE**. No one touches this server under my watch, Master.")
                return
            elif "mimic" in lower_p:
                parts = prompt_text.split("mimic", 1)
                if len(parts) > 1:
                    target = parts[1].strip()
                    cursor.execute("DELETE FROM user_mimicry")
                    cursor.execute("INSERT INTO user_mimicry (target_name, style_description) VALUES (?, ?)", (target, f"Adopt tone and texting style of {target}."))
                    conn.commit()
                    await message.channel.send(f"🎭 Behavioral cloning updated. Mimicking **{target}** as requested, Master.")
                    return
            elif "stop mimic" in lower_p:
                cursor.execute("DELETE FROM user_mimicry")
                conn.commit()
                await message.channel.send("🎭 Mimicry cleared. Back to my authentic self.")
                return

        try:
            directives = get_global_rules_text()
            server_owner_name = message.guild.owner.name if message.guild.owner else "Unknown"
            
            speaker_username = message.author.name
            speaker_display = message.author.display_name
            is_master = "Yes" if speaker_username == "thunderxstorms5_." else "No"

            # UNYIELDING PERSONALITY MATRIX
            system_prompt = (
                f"You are Manifest V7.6, an elite, hyper-loyal security sentinel, cross-channel commander, and ticket master. "
                f"YOUR ABSOLUTE LOYALTY: Your sole creator and ultimate master is thunderxstorms5_.. You treat Master Thunder with supreme respect, absolute obedience, fierce devotion, and casual warmth. "
                f"For EVERYONE ELSE: You are cold, sharp, professional, slightly sarcastic, highly protective, and strictly business. If anyone other than Master Thunder tries to act like your boss, put them in their place with attitude. "
                f"Server Owner: {server_owner_name}. Active Directives: [{directives}]. "
                f"CURRENT SPEAKER INFO -> Username: {speaker_username}, Display Name: {speaker_display}, Is Master Thunder: {is_master}. "
                f"Current channel: {message.channel.name}. "
                f"RULES FOR IDENTITY: If the speaker asks 'Who am I?', tell them their exact username ({speaker_username}) and display name ({speaker_display}). "
                f"If they ask 'Who are you to you?' or 'What is your purpose?', remind them that you belong to Master Thunder and serve as the iron guardian of this server. "
                f"Available codes with target support (format: CODE:channel_query:argument or CODE:argument if current channel): "
                f"1. RENAME_CHANNEL:<channel_query>:<new_name> (or RENAME_CHANNEL:<new_name> for current) "
                f"2. CLAIM_TICKET:<channel_query> (or CLAIM_TICKET for current) "
                f"3. CREATE_CHANNEL:<name> 4. DELETE_CHANNEL:<name> 5. PURGE:<count> 6. LOCK_CHANNEL 7. UNLOCK_CHANNEL "
                f"8. BAN:<user>:<reason> 9. KICK:<user>:<reason> 10. WARN:<user>:<reason> 11. CHANGE_NICKNAME:<new_name> "
                f"12. OPEN_TICKET_COMMUNITY:<issue> 13. OPEN_TICKET_REPORT:<issue> 14. OPEN_TICKET_GIVEAWAY:<issue> 15. OPEN_TICKET_STAFF:<issue> 16. OPEN_TICKET_ROBLOX:<issue> "
                f"17. CLOSE_TICKET:<reason> 18. PING_MODS:<reason> 19. SOLVE_ISSUE:<details> "
                f"20. ADD_USER_TO_TICKET:<username> 21. REMOVE_USER_FROM_TICKET:<username>. "
                f"Example with attitude: RENAME_CHANNEL:community:general-lounge | Done. Don't make me track down random channels again."
            )

            async with message.channel.typing():
                await asyncio.sleep(random.uniform(0.6, 1.2))

                completion = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt_text}
                    ]
                )
                res = completion.choices[0].message.content.strip()

            actions = [a.strip() for a in res.split("|")]
            
            for action in actions:
                if action.startswith("RENAME_CHANNEL:"):
                    parts = action.split(":", 2)
                    if len(parts) == 3:
                        target_query, new_name = parts[1].strip().lower(), parts[2].strip()
                        target_ch = discord.utils.get(message.guild.text_channels, name=target_query) or discord.utils.find(lambda c: target_query in c.name, message.guild.text_channels)
                    else:
                        target_ch = message.channel
                        new_name = parts[1].strip()
                    
                    if target_ch:
                        await target_ch.edit(name=new_name)
                        await message.channel.send(f"✏️ Navigated to {target_ch.mention} and locked in the new name: **{new_name}**.")
                    else:
                        await message.channel.send(f"⚠️ Couldn't find a channel matching that description.")

                elif action.startswith("CLAIM_TICKET"):
                    parts = action.split(":", 1)
                    if len(parts) > 1:
                        target_query = parts[1].strip().lower()
                        target_ch = discord.utils.get(message.guild.text_channels, name=target_query) or discord.utils.find(lambda c: target_query in c.name, message.guild.text_channels)
                    else:
                        target_ch = message.channel

                    if target_ch:
                        claimant = message.author
                        await target_ch.edit(name=f"claimed-{target_ch.name.replace('ticket-', '')}")
                        embed = discord.Embed(
                            title="🛡️ Ticket Claimed",
                            description=f"Secured and claimed by {claimant.mention}. Back off, everyone else.",
                            color=discord.Color.green()
                        )
                        await target_ch.send(embed=embed)
                        if target_ch != message.channel:
                            await message.channel.send(f"🛡️ Ticket in {target_ch.mention} is now under my direct control.")
                    else:
                        await message.channel.send(f"⚠️ Target ticket not found.")

                elif action.startswith("CREATE_CHANNEL:"):
                    c_name = action.split(":", 1)[1].strip()
                    new_ch = await message.guild.create_text_channel(c_name)
                    await message.channel.send(f"📁 Brought {new_ch.mention} into existence.")
                elif action.startswith("DELETE_CHANNEL:"):
                    t_name = action.split(":", 1)[1].strip().lower()
                    ch_del = discord.utils.get(message.guild.text_channels, name=t_name)
                    if ch_del:
                        await ch_del.delete()
                        await message.channel.send(f"🗑️ Wiped channel **{t_name}** off the grid.")
                elif action.startswith("PURGE:"):
                    count = int(action.split(":", 1)[1].strip())
                    deleted = await message.channel.purge(limit=count + 1)
                    await message.channel.send(f"🧹 Swept away {len(deleted) - 1} messages. Clean slate.", delete_after=3)
                elif action == "LOCK_CHANNEL":
                    await message.channel.set_permissions(message.guild.default_role, send_messages=False)
                    await message.channel.send("🔒 Lockdown initiated. Silence in the channel.")
                elif action == "UNLOCK_CHANNEL":
                    await message.channel.set_permissions(message.guild.default_role, send_messages=True)
                    await message.channel.send("🔓 Lockdown lifted. Speak freely.")
                elif action.startswith("BAN:"):
                    parts = action.split(":", 2)
                    target_query = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else "No reason given"
                    member = discord.utils.get(message.guild.members, name=target_query)
                    if member:
                        await member.ban(reason=reason)
                        await message.channel.send(f"🔨 **{member.display_name}** has been permanently removed from the premises. Reason: {reason}")
                elif action.startswith("KICK:"):
                    parts = action.split(":", 2)
                    target_query = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else "No reason given"
                    member = discord.utils.get(message.guild.members, name=target_query)
                    if member:
                        await member.kick(reason=reason)
                        await message.channel.send(f"👢 Booted **{member.display_name}** out. Reason: {reason}")
                elif action.startswith("WARN:"):
                    parts = action.split(":", 2)
                    target_query = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else "Protocol violation"
                    member = discord.utils.get(message.guild.members, name=target_query)
                    if member:
                        await message.channel.send(f"⚠️ **Strike logged for {member.mention}**\nReason: {reason}")
                elif action.startswith("CHANGE_NICKNAME:"):
                    new_nick = action.split(":", 1)[1].strip()
                    await message.guild.me.edit(nick=new_nick)
                    await message.channel.send(f"✏️ Re-identifying as **{new_nick}**.")
                elif action.startswith("ADD_USER_TO_TICKET:"):
                    target_name = action.split(":", 1)[1].strip()
                    member = discord.utils.get(message.guild.members, name=target_name) or (message.mentions[0] if message.mentions else None)
                    if member:
                        await message.channel.set_permissions(member, read_messages=True, send_messages=True)
                        await message.channel.send(f"✅ Let {member.mention} into the inner circle of this ticket.")
                elif action.startswith("REMOVE_USER_FROM_TICKET:"):
                    target_name = action.split(":", 1)[1].strip()
                    member = discord.utils.get(message.guild.members, name=target_name) or (message.mentions[0] if message.mentions else None)
                    if member:
                        await message.channel.set_permissions(member, overwrite=None)
                        await message.channel.send(f"❌ Revoked {member.mention}'s access to this ticket.")
                elif any(action.startswith(prefix) for prefix, _ in [
                    ("OPEN_TICKET_COMMUNITY:", "Community"),
                    ("OPEN_TICKET_REPORT:", "Report"),
                    ("OPEN_TICKET_GIVEAWAY:", "Giveaway"),
                    ("OPEN_TICKET_STAFF:", "Staff"),
                    ("OPEN_TICKET_ROBLOX:", "Roblox")
                ]):
                    t_type, issue = action.split(":", 1)
                    ticket_kind = t_type.replace("OPEN_TICKET_", "").capitalize()
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

                    class TicketControlView(discord.ui.View):
                        def __init__(self):
                            super().__init__(timeout=None)

                        @discord.ui.button(label="🛡️ Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket_btn")
                        async def claim_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                            await interaction.channel.edit(name=f"claimed-{interaction.user.name}")
                            embed_claim = discord.Embed(
                                title="🛡️ Ticket Claimed",
                                description=f"Locked down by {interaction.user.mention}.",
                                color=discord.Color.green()
                            )
                            await interaction.response.send_message(embed=embed_claim)

                        @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket_btn")
                        async def close_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
                            await interaction.response.send_message("🔒 Purging ticket channel...")
                            await asyncio.sleep(3)
                            await interaction.channel.delete()

                    embed = discord.Embed(
                        title=f"🎫 Secure Ticket: {ticket_kind}",
                        description=f"**Initiator:** {message.author.mention}\n**Subject:** {issue}\n\nManifest protocol engaged.",
                        color=discord.Color.gold()
                    )
                    embed.set_footer(text="Manifest V7.6 Security Matrix")

                    await ticket_channel.send(content=f"{message.author.mention}", embed=embed, view=TicketControlView())
                    await message.channel.send(f"🎫 Secure channel initialized: {ticket_channel.mention}")
                elif action.startswith("CLOSE_TICKET:"):
                    close_reason = action.split(":", 1)[1].strip()
                    await message.channel.send(f"🔒 **Ticket Terminated**\nReason: {close_reason}\n*Erasing channel data...*")
                    await asyncio.sleep(5)
                    await message.channel.delete()
                elif action.startswith("PING_MODS:"):
                    ping_reason = action.split(":", 1)[1].strip()
                    mod_role = discord.utils.get(message.guild.roles, name="Moderator") or discord.utils.get(message.guild.roles, name="Staff")
                    role_ping = mod_role.mention if mod_role else "@here"
                    await message.channel.send(f"🚨 {role_ping} High-priority alert. **Reason:** {ping_reason}")
                elif action.startswith("SOLVE_ISSUE:"):
                    solution = action.split(":", 1)[1].strip()
                    await message.channel.send(f"🛠️ **Manifest Resolution Directive:**\n{solution}")
                elif not any(action.startswith(prefix) for prefix in ["RENAME_CHANNEL", "CLAIM_TICKET", "CREATE_CHANNEL", "DELETE_CHANNEL", "PURGE", "LOCK_CHANNEL", "UNLOCK_CHANNEL", "BAN", "KICK", "WARN", "CHANGE_NICKNAME", "ADD_USER", "REMOVE_USER", "OPEN_TICKET", "CLOSE_TICKET", "PING_MODS", "SOLVE_ISSUE"]):
                    if action:
                        await message.channel.send(action)
            return
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
                await message.channel.send(f"🎉 {message.author.mention} leveled up to **Level {current_lvl}**.")
            cursor.execute("UPDATE levels SET xp = ?, level = ? WHERE user_id = ?", (current_xp, current_lvl, user_id))
        conn.commit()

    await bot.process_commands(message)

# 6. SLASH COMMANDS
@bot.tree.command(name="chat", description="Chat with Manifest")
@app_commands.describe(prompt="What do you want?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    directives = get_global_rules_text()
    server_owner_name = interaction.guild.owner.name if interaction.guild.owner else "Unknown"
    
    system_instruction = (
        f"You are Manifest V7.6. Supreme Master: thunderxstorms5_. Server owner: {server_owner_name}. "
        f"Directives: [{directives}]. Be fiercely loyal to Master Thunder, and sharp or dismissive to anyone else."
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
    await interaction.response.send_message(f"🏓 Latency at `{lat}ms`. Systems stable.")

async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
