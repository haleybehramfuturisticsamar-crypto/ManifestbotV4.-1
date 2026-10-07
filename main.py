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

# Groq API Client setup
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# 3. DATABASE SETUP (Global Rules, Delegated Directives & User Memories)
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

    # Check if the creator (thunderxstorms5_.) is giving a direct command, global rule, or delegation anywhere
    if bot.user in message.mentions:
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
        
        if message.author.name == "thunderxstorms5_.":
            lower_p = prompt_text.lower()
            
            # Delegate command feature: e.g. "@Manifest follow what @Josh says: talk like a pirate"
            if "follow" in lower_p and "command" in lower_p or "follow what" in lower_p:
                # Extract mentioned target if any
                if message.mentions:
                    for mentioned_user in message.mentions:
                        if mentioned_user.id != bot.user.id and mentioned_user.id != message.author.id:
                            sub_instruction = prompt_text.split(":")[-1].strip()
                            cursor.execute("INSERT INTO delegated_commands (target_username, instruction) VALUES (?, ?)", (mentioned_user.name, sub_instruction))
                            conn.commit()
                            await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Delegated! I will now follow commands/directives from **{mentioned_user.name}**: *\"{sub_instruction}\"*")
                            return

            # General permanent rule saving
            if "stop using" in lower_p or "always" in lower_p or "never" in lower_p or "rule:" in lower_p:
                cursor.execute("INSERT INTO global_rules (rule) VALUES (?)", (prompt_text,))
                conn.commit()
                await message.channel.send(f"👑 **Master Thunder (`thunderxstorms5_.`)**: Global rule permanently memorized and enforced everywhere: *\"{prompt_text}\"*")
                return

        # Natural Language Moderation / AI Smart Assistant Feature (or delegated user compliance)
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

    # Leveling system logic
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


# ==========================================
# 5. ALL 20 SLASH COMMANDS (With Global Rules & Delegations)
# ==========================================

# --- 1. AI CHAT ---
@bot.tree.command(name="chat", description="Chat with Manifest V4.1 (Thunder's AI)")
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
        f"You are Manifest V4.1, Thunder's advanced bot. Your creator, owner, and absolute master is thunderxstorms5_. (Thunder). "
        f"Global Active Directives: [{directives}]. "
        f"Active user-specific delegation for current user '{username}': [{delegated_rule}]. "
        f"You are talking to '{display_name}' (ID: {user_id}). If username is thunderxstorms5_., bow down to your creator. "
        f"Personal user notes/memory: {stored_notes}."
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

        lower_prompt = prompt.lower()
        if "remember that" in lower_prompt or "remember i " in lower_prompt:
            new_note = prompt.split("that")[-1].strip() if "that" in lower_prompt else prompt
            updated_notes = new_note if stored_notes == "No prior notes saved for this user." else stored_notes + "; " + new_note
            cursor.execute("INSERT OR REPLACE INTO user_memories (user_id, username, notes) VALUES (?, ?, ?)", 
                           (user_id, username, updated_notes))
            conn.commit()
            response_text += f"\n\n*(🧠 Memory updated: Saved that you {new_note})*"

        if len(response_text) > 2000:
            await interaction.followup.send(response_text[:1997] + "...")
        else:
            await interaction.followup.send(response_text)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Groq Error: `{e}`")

# --- 2. HUG ---
@bot.tree.command(name="hug", description="Give someone a warm hug!")
@app_commands.describe(member="The member you want to hug")
async def hug(interaction: discord.Interaction, member: discord.Member):
    gifs = [
        "https://media.giphy.com/media/3oEdv4hwWTzBhWvaU0/giphy.gif",
        "https://media.giphy.com/media/1xV828LzeGWZq/giphy.gif"
    ]
    embed = discord.Embed(description=f"🤗 **{interaction.user.mention}** gave a warm hug to **{member.mention}**!", color=discord.Color.pink())
    embed.set_image(url=random.choice(gifs))
    await interaction.response.send_message(embed=embed)

# --- 3. DAB ---
@bot.tree.command(name="dab", description="Show off your coolest dab!")
async def dab(interaction: discord.Interaction):
    embed = discord.Embed(description=f"😎 **{interaction.user.mention}** hits a massive dab!", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

# --- 4. COINFLIP ---
@bot.tree.command(name="coinflip", description="Flip a coin (Heads or Tails)")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads 🪙", "Tails 🪙"])
    await interaction.response.send_message(f"The coin landed on: **{result}**!")

# --- 5. 8BALL ---
@bot.tree.command(name="8ball", description="Ask the magic 8ball a question")
@app_commands.describe(question="Your question")
async def _8ball(interaction: discord.Interaction, question: str):
    responses = ["Yes, absolutely.", "Ask again later.", "No way.", "Without a doubt.", "Very doubtful.", "Outlook good."]
    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.dark_purple())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)
    await interaction.response.send_message(embed=embed)

# --- 6. ROLL DICE ---
@bot.tree.command(name="roll", description="Roll a 6-sided dice")
async def roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 You rolled a **{random.randint(1, 6)}**!")

# --- 7. SERVER INFO ---
@bot.tree.command(name="serverinfo", description="View server details")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name} Info", color=discord.Color.blue())
    embed.add_field(name="Owner", value=guild.owner, inline=True)
    embed.add_field(name="Members", value=guild.member_count, inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
    await interaction.response.send_message(embed=embed)

# --- 8. USER INFO ---
@bot.tree.command(name="userinfo", description="Get info about a user")
@app_commands.describe(member="The member to check")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    m = member or interaction.user
    embed = discord.Embed(title=f"👤 User Info: {m.display_name}", color=discord.Color.green())
    embed.set_thumbnail(url=m.display_avatar.url)
    embed.add_field(name="ID", value=m.id, inline=True)
    embed.add_field(name="Joined Server", value=m.joined_at.strftime("%b %d, %Y") if m.joined_at else "Unknown", inline=True)
    await interaction.response.send_message(embed=embed)

# --- 9. PING ---
@bot.tree.command(name="ping", description="Check bot's latency")
async def ping(interaction: discord.Interaction):
    lat = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency is `{lat}ms`.")

# --- 10. POLL ---
@bot.tree.command(name="poll", description="Create a simple yes/no poll")
@app_commands.describe(question="The poll question")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 Quick Poll", description=question, color=discord.Color.gold())
    embed.set_footer(text=f"Poll started by {interaction.user.display_name}")
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message("✅ Poll created!", ephemeral=True)


# --- TICKET SYSTEM COMMANDS (11 to 17) ---
class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Create Ticket", style=discord.ButtonStyle.green, custom_id="create_ticket_btn")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category:
            category = await guild.create_category("Tickets")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        channel_name = f"ticket-{interaction.user.name}"
        ticket_channel = await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
        
        cursor.execute("INSERT INTO tickets (channel_id, user_id, guild_id, status) VALUES (?, ?, ?, ?)", 
                       (ticket_channel.id, interaction.user.id, guild.id, 'open'))
        conn.commit()

        embed = discord.Embed(title="Support Ticket", description="Support staff will be with you shortly. Use `/close` to close this ticket.", color=discord.Color.blue())
        await ticket_channel.send(content=interaction.user.mention, embed=embed)
        await interaction.response.send_message(f"✅ Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

# 11. SETUP
@bot.tree.command(name="setup", description="Deploy the interactive support ticket panel")
async def setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
    
    embed = discord.Embed(title="Support Center", description="Click the button below to open a private support ticket.", color=discord.Color.purple())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Support ticket panel deployed successfully!", ephemeral=True)

# 12. CLOSE
@bot.tree.command(name="close", description="Close an active ticket")
async def close(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    
    cursor.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    await interaction.channel.edit(name=f"closed-{interaction.channel.name}")
    await interaction.response.send_message("🔒 Ticket closed.")

# 13. REOPEN
@bot.tree.command(name="reopen", description="Reopen a closed ticket")
async def reopen(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    
    cursor.execute("UPDATE tickets SET status = 'open' WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    await interaction.channel.edit(name=interaction.channel.name.replace("closed-", ""))
    await interaction.response.send_message("🔓 Ticket re-opened.")

# 14. DELETE TICKET
@bot.tree.command(name="delete", description="Permanently delete a ticket channel")
async def delete_ticket(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    
    cursor.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    await interaction.response.send_message("🗑️ Deleting ticket in 3 seconds...")
    await asyncio.sleep(3)
    await interaction.channel.delete()

# 15. ADD USER TO TICKET
@bot.tree.command(name="add", description="Add a user to the ticket")
@app_commands.describe(user="The user to add")
async def add_user(interaction: discord.Interaction, user: discord.Member):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to this ticket.")

# 16. REMOVE USER FROM TICKET
@bot.tree.command(name="remove", description="Remove a user from the ticket")
@app_
