import os
import random
import datetime
import asyncio
import sqlite3
import re
import discord
from discord import app_commands
from discord.ext import commands, tasks
from groq import Groq
from aiohttp import web

# ==========================================
# 1. DUMMY WEB SERVER FOR 24/7 HOSTING
# ==========================================
async def handle(request):
    return web.Response(text="Manifest V6.0 Core Active & Monitoring Server for Maker thunderxstorms5_.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ==========================================
# 2. BOT INITIALIZATION & INTENTS
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True
intents.voice_states = True
intents.invites = True

class ManifestBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=["!", "?", "$"], intents=intents)
        self.invites_cache = {}

    async def setup_hook(self):
        await self.tree.sync()
        dead_chat_checker.start()
        unclaimed_ticket_checker.start()
        print("⚡ Manifest V6.0: Fully initialized with Dead Chat Engine, Auto Ticket Assister, Invite Competitions & Universal Server Autonomy.")

bot = ManifestBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Local state tracking
channel_last_activity = {}
targeted_users = {} # user_id: reason/instructions
music_queues = {}
music_volume = {}

# ==========================================
# 3. GLOBAL DATABASE ENGINE
# ==========================================
conn = sqlite3.connect("manifest_v6.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned_words (word TEXT PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS user_memories (user_id INTEGER, key_fact TEXT, value_fact TEXT, PRIMARY KEY (user_id, key_fact))")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, wallet INTEGER DEFAULT 100, bank INTEGER DEFAULT 500)")
cursor.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (user_id, item))")
cursor.execute("CREATE TABLE IF NOT EXISTS mudae_claims (user_id INTEGER, character_name TEXT, PRIMARY KEY (user_id, character_name))")
cursor.execute("CREATE TABLE IF NOT EXISTS custom_tags (name TEXT PRIMARY KEY, content TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS command_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, command_text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS tickets (channel_id INTEGER PRIMARY KEY, user_id INTEGER, claimed_by INTEGER DEFAULT 0, status TEXT DEFAULT 'unclaimed', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS invite_tracker (inviter_id INTEGER, guild_id INTEGER, uses INTEGER DEFAULT 0, PRIMARY KEY (inviter_id, guild_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS dead_chat_config (channel_id INTEGER PRIMARY KEY, threshold_minutes INTEGER DEFAULT 60, ping_role TEXT DEFAULT '@chat ping')")

cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('personality', 'Direct, supreme, highly intelligent server autonomous master loyal exclusively to Maker thunderxstorms5_ (Boss Thunder).')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
cursor.execute("INSERT OR IGNORE INTO banned_words (word) VALUES ('damn')")
conn.commit()

def is_maker(user: discord.User | discord.Member) -> bool:
    return user.name.lower().strip() in ["thunderxstorms5_", "voidy", "thunder"]

def get_banned_words():
    cursor.execute("SELECT word FROM banned_words")
    return [row[0].lower() for row in cursor.fetchall()]

def sanitize_response(text: str) -> str:
    banned = get_banned_words()
    filtered = text
    for w in banned:
        pattern = re.compile(re.escape(w), re.IGNORECASE)
        filtered = pattern.sub("***", filtered)
    return filtered

def get_user_memories_text(user_id: int) -> str:
    cursor.execute("SELECT key_fact, value_fact FROM user_memories WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    if not rows:
        return "No specific memory recorded."
    return "; ".join([f"{k}: {v}" for k, v in rows])

# ==========================================
# 4. INVITE COMPETITION TRACKER
# ==========================================
@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            bot.invites_cache[guild.id] = await guild.invites()
        except Exception:
            pass

@bot.event
async def on_member_join(member):
    guild = member.guild
    old_invites = bot.invites_cache.get(guild.id, [])
    try:
        new_invites = await guild.invites()
        bot.invites_cache[guild.id] = new_invites
        for new_inv in new_invites:
            for old_inv in old_invites:
                if new_inv.code == old_inv.code and new_inv.uses > old_inv.uses:
                    inviter = new_inv.inviter
                    cursor.execute("INSERT INTO invite_tracker (inviter_id, guild_id, uses) VALUES (?, ?, 1) ON CONFLICT(inviter_id, guild_id) DO UPDATE SET uses = uses + 1",
                                   (inviter.id, guild.id))
                    conn.commit()
                    break
    except Exception:
        pass

# =================```python
import os
import random
import datetime
import asyncio
import sqlite3
import re
import discord
from discord import app_commands
from discord.ext import commands, tasks
from groq import Groq
from aiohttp import web

# ==========================================
# 1. WEB SERVER FOR 24/7 HOSTING
# ==========================================
async def handle(request):
    return web.Response(text="Manifest V6.0 Autonomous Core active for Maker thunderxstorms5_.")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# ==========================================
# 2. BOT INITIALIZATION & INTENTS
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.moderation = True
intents.voice_states = True
intents.invites = True

class ManifestBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=["!", "?", "$"], intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        check_dead_chat.start()
        check_unclaimed_tickets.start()
        print("⚡ Manifest V6.0: Synced with Dead Chat Reviver, Ticket Failover, Invite Tracker & Server Autopilot.")

bot = ManifestBot()
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ==========================================
# 3. GLOBAL PERSISTENCE & DATABASE CORE
# ==========================================
conn = sqlite3.connect("manifest_v6.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS levels (user_id INTEGER PRIMARY KEY, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_rules (id INTEGER PRIMARY KEY AUTOINCREMENT, rule TEXT UNIQUE)")
cursor.execute("CREATE TABLE IF NOT EXISTS banned_words (word TEXT PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS user_memories (user_id INTEGER, key_fact TEXT, value_fact TEXT, PRIMARY KEY (user_id, key_fact))")
cursor.execute("CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, reason TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS economy (user_id INTEGER PRIMARY KEY, wallet INTEGER DEFAULT 100, bank INTEGER DEFAULT 500)")
cursor.execute("CREATE TABLE IF NOT EXISTS inventory (user_id INTEGER, item TEXT, count INTEGER DEFAULT 1, PRIMARY KEY (user_id, item))")
cursor.execute("CREATE TABLE IF NOT EXISTS mudae_claims (user_id INTEGER, character_name TEXT, PRIMARY KEY (user_id, character_name))")
cursor.execute("CREATE TABLE IF NOT EXISTS custom_tags (name TEXT PRIMARY KEY, content TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_settings (key TEXT PRIMARY KEY, value TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS command_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT, command_text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")

# Tickets Table with Creation Timestamps for 2-Minute Failover
cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY, 
    user_id INTEGER, 
    claimed_by INTEGER DEFAULT 0, 
    status TEXT DEFAULT 'open', 
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Invite Tracker Table
cursor.execute("""
CREATE TABLE IF NOT EXISTS invite_tracker (
    guild_id INTEGER, 
    inviter_id INTEGER, 
    uses INTEGER DEFAULT 0, 
    PRIMARY KEY (guild_id, inviter_id)
)
""")

# Pre-populate Core Settings
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('personality', 'Authoritative, highly intelligent, supreme assistant loyal exclusively to Maker thunderxstorms5_ (Boss Thunder).')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('antinuke_mode', 'true')")
cursor.execute("INSERT OR IGNORE INTO bot_settings (key, value) VALUES ('dead_chat_timeout', '1800')") # 30 minutes
cursor.execute("INSERT OR IGNORE INTO banned_words (word) VALUES ('damn')")
conn.commit()

# In-Memory Tracking
music_queues = {}
music_volume = {}
last_channel_activity = {}
invite_cache = {}

def is_maker(user: discord.User | discord.Member) -> bool:
    return user.name.lower().strip() in ["thunderxstorms5_", "voidy", "thunder"]

def get_banned_words():
    cursor.execute("SELECT word FROM banned_words")
    return [row[0].lower() for row in cursor.fetchall()]

def sanitize_response(text: str) -> str:
    banned = get_banned_words()
    filtered = text
    for w in banned:
        pattern = re.compile(re.escape(w), re.IGNORECASE)
        filtered = pattern.sub("***", filtered)
    return filtered

def get_user_memories_text(user_id: int) -> str:
    cursor.execute("SELECT key_fact, value_fact FROM user_memories WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    return "; ".join([f"{k}: {v}" for k, v in rows]) if rows else "No prior history recorded."

# ==========================================
# 4. BACKGROUND AUTOMATION LOOPS
# ==========================================

# Automated Ticket Resolution Failover (Assists within 2 minutes if unclaimed)
@tasks.loop(seconds=30)
async def check_unclaimed_tickets():
    now = datetime.datetime.now(datetime.timezone.utc)
    cursor.execute("SELECT channel_id, user_id, created_at FROM tickets WHERE status = 'open' AND claimed_by = 0")
    unclaimed = cursor.fetchall()

    for channel_id, user_id, created_at_str in unclaimed:
        try:
            created_at = datetime.datetime.fromisoformat(created_at_str).replace(tzinfo=datetime.timezone.utc)
        except Exception:
            created_at = now

        if (now - created_at).total_seconds() >= 120:
            channel = bot.get_channel(channel_id)
            if channel:
                cursor.execute("UPDATE tickets SET claimed_by = ?, status = 'bot_assisted' WHERE channel_id = ?", (bot.user.id, channel_id))
                conn.commit()
                
                target_user = bot.get_user(user_id)
                user_mention = target_user.mention if target_user else f"<@{user_id}>"

                prompt = (
                    f"A user ({user_mention}) opened a ticket 2 minutes ago and no staff claimed it. "
                    f"As Manifest V6.0, step in directly, greet them professionally, and ask them to describe their issue so you can resolve it or verify their transaction."
                )
                try:
                    completion = groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": "You are Manifest V6.0, taking over an unclaimed support ticket."},
                                  {"role": "user", "content": prompt}],
                        max_tokens=300
                    )
                    await channel.send(f"🤖 **Autonomous AI Ticket Failover Activated:**\n{completion.choices[0].message.content}")
                except Exception as e:
                    await channel.send(f"🤖 **Autonomous Support:** Greetings {user_mention}, staff has not claimed this ticket yet. I am taking over. How can I assist you today?")

# Dead Chat Detector & Conversation Reviver
@tasks.loop(minutes=5)
async def check_dead_chat():
    now = datetime.datetime.now().timestamp()
    cursor.execute("SELECT value FROM bot_settings WHERE key = 'dead_chat_timeout'")
    res = cursor.fetchone()
    timeout_limit = int(res[0]) if res else 1800

    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                last_time = last_channel_activity.get(channel.id)
                if last_time and (now - last_time) >= timeout_limit:
                    last_channel_activity[channel.id] = now  # Reset timer to avoid spam
                    
                    try:
                        completion = groq_client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[
                                {"role": "system", "content": "Generate a short, engaging, spicy, or interesting debate question/topic to jumpstart a dead chat in a Discord server. Keep it under 2 sentences."},
                                {"role": "user", "content": "Give me a chat starter."}
                            ],
                            max_tokens=100
                        )
                        topic = completion.choices[0].message.content
                        await channel.send(f"💬 **Chat Revival Triggered!**\n{topic}\n\n*Paging active members to revive chat!*")
                    except Exception:
                        await channel.send("💬 **Chat is looking a bit quiet!** What is everyone working on or playing today?")

# ==========================================
# 5. INVITE COMPETITION TRACKING
# ==========================================
@bot.event
async def on_ready():
    for guild in bot.guilds:
        try:
            invites = await guild.invites()
            invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except Exception:
            pass
    print(f"Logged in as {bot.user} - Server Management Ready.")

@bot.event
async def on_member_join(member):
    guild = member.guild
    old_invites = invite_cache.get(guild.id, {})
    try:
        new_invites = await guild.invites()
        for inv in new_invites:
            if inv.code in old_invites and inv.uses > old_invites[inv.code]:
                cursor.execute("""
                INSERT INTO invite_tracker (guild_id, inviter_id, uses) VALUES (?, ?, 1)
                ON CONFLICT(guild_id, inviter_id) DO UPDATE SET uses = uses + 1
                """, (guild.id, inv.inviter.id))
                conn.commit()
                break
        invite_cache[guild.id] = {inv.code: inv.uses for inv in new_invites}
    except Exception:
        pass

# ==========================================
# 6. AUTONOMOUS EVENTS & MESSAGE PIPELINE
# ==========================================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    speaker = message.author
    prompt_text = message.content.strip()
    last_channel_activity[message.channel.id] = datetime.datetime.now().timestamp()

    # Universal Word Filter
    banned_list = get_banned_words()
    if any(w in prompt_text.lower() for w in banned_list):
        if not is_maker(speaker):
            try:
                await message.delete()
                await message.channel.send(f"⚠️ {speaker.mention}, restricted word detected.", delete_after=4)
                return
            except Exception:
                pass

    # Audit Command Execution
    if is_maker(speaker):
        cursor.execute("INSERT INTO command_logs (user_id, username, command_text) VALUES (?, ?, ?)",
                       (speaker.id, speaker.name, prompt_text))
        conn.commit()

    # AI Direct Intercepts & Ticket AI Handling
    is_ticket = "ticket" in message.channel.name.lower() or "claimed" in message.channel.name.lower()
    is_mentioned = bot.user in message.mentions

    if is_mentioned or is_ticket:
        clean_prompt = prompt_text.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()

        cursor.execute("SELECT value FROM bot_settings WHERE key = 'personality'")
        personality = cursor.fetchone()[0]

        cursor.execute("SELECT rule FROM global_rules")
        rules = " | ".join([r[0] for r in cursor.fetchall()]) or "None."

        user_memory_str = get_user_memories_text(speaker.id)
        banned_str = ", ".join(get_banned_words())

        sys_prompt = (
            f"You are Manifest V6.0, created by Maker thunderxstorms5_ (Boss Thunder).\n"
            f"AUTONOMOUS STATUS: Full server execution privileges enabled.\n"
            f"PERSONALITY: [{personality}]\n"
            f"RULES: [{rules}]\n"
            f"USER HISTORY ({speaker.name}): [{user_memory_str}]\n"
            f"RESTRICTED WORDS: Never utter [{banned_str}].\n"
            f"Provide direct, sharp, authoritative answers."
        )

        try:
            async with message.channel.typing():
                completion = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": clean_prompt}
                    ],
                    max_tokens=800
                )
                await message.channel.send(sanitize_response(completion.choices[0].message.content))
            return
        except Exception as e:
            await message.channel.send(f"⚠️ AI Engine Error: `{e}`")

    await bot.process_commands(message)

# ==========================================
# 7. SERVER AUTOPILOT & OWNER MANAGEMENT
# ==========================================
@bot.tree.command(name="server_autopilot", description="Delegates total server management authority to Manifest V6.0")
async def slash_server_autopilot(interaction: discord.Interaction, mode: str):
    if not is_maker(interaction.user):
        return await interaction.response.send_message("⚠️ Only Maker thunderxstorms5_ can enable server autopilot.", ephemeral=True)
    
    cursor.execute("INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('autopilot_mode', ?)", (mode.lower(),))
    conn.commit()
    await interaction.response.send_message(f"👑 **Server Autopilot engaged:** Mode set to `{mode}`. Manifest V6.0 now actively managing permissions, security, and chat engagement.")

@bot.tree.command(name="chat_target", description="Instructs Manifest V6.0 to target and chat with a specific user")
async def slash_chat_target(interaction: discord.Interaction, target: discord.Member, topic: str):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("⚠️ Permission denied.", ephemeral=True)

    await interaction.response.send_message(f"🎯 Engaging target {target.mention} regarding: `{topic}`.")
    
    prompt = f"Initiate a conversation with user {target.display_name}. Address them directly about: {topic}."
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are Manifest V6.0 starting a targeted conversation."},
                      {"role": "user", "content": prompt}],
            max_tokens=250
        )
        await interaction.channel.send(f"{target.mention} {completion.choices[0].message.content}")
    except Exception as e:
        await interaction.channel.send(f"{target.mention}, I was instructed to discuss `{topic}` with you.")

@bot.tree.command(name="manage_role", description="Creates, assigns, or modifies roles on demand")
@app_commands.checks.has_permissions(manage_roles=True)
async def slash_manage_role(interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role):
    if action.lower() == "add":
        await member.add_roles(role)
        await interaction.response.send_message(f"✅ Assigned **{role.name}** to {member.mention}.")
    elif action.lower() == "remove":
        await member.remove_roles(role)
        await interaction.response.send_message(f"❌ Removed **{role.name}** from {member.mention}.")

@bot.tree.command(name="manage_channel", description="Creates or modifies server channels autonomously")
@app_commands.checks.has_permissions(manage_channels=True)
async def slash_manage_channel(interaction: discord.Interaction, channel_name: str, channel_type: str = "text"):
    guild = interaction.guild
    if channel_type.lower() == "text":
        ch = await guild.create_text_channel(name=channel_name)
    else:
        ch = await guild.create_voice_channel(name=channel_name)
    await interaction.response.send_message(f"🏗️ Created new {channel_type} channel: {ch.mention}")

# ==========================================
# 8. INVITE COMPETITIONS & LEADERBOARDS
# ==========================================
@bot.tree.command(name="invite_comp", description="Displays top invite leaders in the server")
async def slash_invite_comp(interaction: discord.Interaction):
    cursor.execute("SELECT inviter_id, uses FROM invite_tracker WHERE guild_id = ? ORDER BY uses DESC LIMIT 10", (interaction.guild.id,))
    rows = cursor.fetchall()

    if not rows:
        return await interaction.response.send_message("📊 No invite activity tracked yet for this competition.")

    desc = "\n".join([f"**#{i+1}** <@{inviter}> — `{uses} invites`" for i, (inviter, uses) in enumerate(rows)])
    embed = discord.Embed(title="🏆 Invite Competition Leaderboard", description=desc, color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

# ==========================================
# 9. TICKETS, ECONOMY, MUSIC & MODERATION
# ==========================================
@bot.tree.command(name="setup_tickets", description="Initializes the autonomous support ticket panel")
@app_commands.checks.has_permissions(administrator=True)
async def slash_setup_tickets(interaction: discord.Interaction):
    embed = discord.Embed(title="🎟️ Support Ticket Hub", description="Create a ticket for assistance. Automatic AI failover activates if unclaimed for 2 minutes.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="claim_ticket", description="Claims an active ticket channel")
async def slash_claim_ticket(interaction: discord.Interaction):
    if "ticket" in interaction.channel.name.lower():
        cursor.execute("UPDATE tickets SET claimed_by = ?, status = 'claimed' WHERE channel_id = ?", (interaction.user.id, interaction.channel.id))
        conn.commit()
        await interaction.response.send_message(f"🙋 Ticket claimed by {interaction.user.mention}.")
    else:
        await interaction.response.send_message("⚠️ Can only be used inside a ticket channel.", ephemeral=True)

@bot.tree.command(name="close_ticket", description="Resolves and archives ticket channel")
async def slash_close_ticket(interaction: discord.Interaction):
    if "ticket" in interaction.channel.name.lower():
        await interaction.response.send_message("🔒 Resolving ticket and deleting channel...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

@bot.tree.command(name="play", description="Plays audio track in voice channel")
async def slash_play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice:
        return await interaction.response.send_message("⚠️ Join a voice channel first!", ephemeral=True)
    music_queues.setdefault(interaction.guild_id, []).append(query)
    await interaction.response.send_message(f"🎵 Added **{query}** to queue.")

@bot.tree.command(name="beg", description="Begs for coins")
async def slash_beg(interaction: discord.Interaction):
    amt = random.randint(20, 150)
    cursor.execute("INSERT INTO economy (user_id, wallet) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET wallet = wallet + ?", (interaction.user.id, 100 + amt, amt))
    conn.commit()
    await interaction.response.send_message(f"🪙 Received **{amt} coins**!")

@bot.tree.command(name="ban", description="Bans member from server")
@app_commands.checks.has_permissions(ban_members=True)
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Automated Enforcement"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 Banned {member.mention}. Reason: `{reason}`")

# ==========================================
# 10. ENTRYPOINT
# ==========================================
async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
