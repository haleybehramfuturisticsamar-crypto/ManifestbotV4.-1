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
        print("Manifest V4.1: All 20+ slash commands synced successfully!")

bot = MyBot()

# Groq API Client setup
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
CREATE TABLE IF NOT EXISTS antiraid_config (
    guild_id INTEGER PRIMARY KEY,
    enabled INTEGER DEFAULT 0,
    min_account_age_days INTEGER DEFAULT 7
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS phone_channels (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER
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

# 4. BOT EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Manifest V4.1 core online: Absolute loyalty to DK locked in.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # Natural Language Management / AI Smart Assistant Feature
    if bot.user in message.mentions and message.author.guild_permissions.administrator:
        prompt_text = message.content.replace(f"<@!{bot.user.id}>", "").replace(f"<@{bot.user.id}>", "").strip()
        if prompt_text:
            try:
                completion = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=[
                        {
                            "role": "system", 
                            "content": "You are the command parser for Manifest V4.1, an elite Discord bot created and owned by DK. If the admin wants to ban someone, reply strictly in format: BAN:<username_or_id>:<reason>. If they want to kick, reply KICK:<username_or_id>:<reason>. Otherwise, reply normally with a sharp, loyal attitude recognizing DK as your creator."
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
                        await message.channel.send(f"🔨 Boss DK's orders executed: Banned **{member.display_name}**. Reason: {reason}")
                        return
                elif res.startswith("KICK:"):
                    parts = res.split(":", 2)
                    target_query = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else "No reason"
                    member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                    if member:
                        await member.kick(reason=reason)
                        await message.channel.send(f"👢 Boss DK's orders executed: Kicked **{member.display_name}**. Reason: {reason}")
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
# 5. ALL 20 SLASH COMMANDS
# ==========================================

# --- 1. AI CHAT ---
@bot.tree.command(name="chat", description="Chat with Manifest V4.1 AI")
@app_commands.describe(prompt="What would you like to say to the AI?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        chat_completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "system", 
                    "content": "You are Manifest V4.1, an elite, highly intelligent Discord bot created and owned by DK. DK is your absolute master and creator."
                },
                {"role": "user", "content": prompt}
            ]
        )
        response_text = chat_completion.choices[0].message.content
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
@app_commands.describe(user="The user to remove")
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from this ticket.")

# 17. CLAIM TICKET
@bot.tree.command(name="claim", description="Claim the current support ticket")
async def claim(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ Not a ticket channel.", ephemeral=True)
    await interaction.response.send_message(f"🛡️ Ticket claimed by {interaction.user.mention}!")


# --- MODERATION COMMANDS (18 to 20) ---

# 18. KICK
@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="Member to kick", reason="Reason")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked **{member.display_name}**. Reason: {reason}")

# 19. BAN
@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="Member to ban", reason="Reason")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 Banned **{member.display_name}**. Reason: {reason}")

# 20. TIMEOUT
@bot.tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(member="Member", minutes="Minutes", reason="Reason")
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ Missing permissions.", ephemeral=True)
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await interaction.response.send_message(f"⏰ Timed out **{member.display_name}** for {minutes}m.")


# 6. RUNNER ENTRYPOINT
async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
