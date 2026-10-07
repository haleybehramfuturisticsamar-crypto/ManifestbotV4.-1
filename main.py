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
        print("All complete bot slash commands synced successfully!")

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
    print("Full feature set active: Moderation, AI, Utility, Leveling, Phone, Tickets, and Fun/Actions!")

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
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "You are an assistant bot parser. Detect if the user wants to ban someone, kick someone, or talk. If they want to ban a user, reply strictly in format: BAN:<username_or_id>:<reason>. If they want to kick, reply KICK:<username_or_id>:<reason>. Otherwise, just reply normally."},
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
                        await message.channel.send(f"🔨 Smart AI Action: Successfully banned **{member.display_name}**. Reason: {reason}")
                        return
                elif res.startswith("KICK:"):
                    parts = res.split(":", 2)
                    target_query = parts[1].strip()
                    reason = parts[2].strip() if len(parts) > 2 else "No reason"
                    member = discord.utils.get(message.guild.members, name=target_query) or message.guild.get_member(int(target_query) if target_query.isdigit() else 0)
                    if member:
                        await member.kick(reason=reason)
                        await message.channel.send(f"👢 Smart AI Action: Successfully kicked **{member.display_name}**. Reason: {reason}")
                        return
                else:
                    await message.channel.send(res)
            except Exception as e:
                pass

    # Phone / Global Chat System Hook
    cursor.execute("SELECT channel_id FROM phone_channels WHERE channel_id = ?", (message.channel.id,))
    if cursor.fetchone():
        cursor.execute("SELECT channel_id, guild_id FROM phone_channels")
        all_phones = cursor.fetchall()
        for ch_id, g_id in all_phones:
            if g_id != message.guild.id:
                target_channel = bot.get_channel(ch_id)
                if target_channel:
                    try:
                        embed = discord.Embed(description=message.content, color=discord.Color.green())
                        embed.set_author(name=f"{message.author.name} (from {message.guild.name})", icon_url=message.author.display_avatar.url)
                        await target_channel.send(embed=embed)
                    except Exception:
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

@bot.event
async def on_member_join(member):
    cursor.execute("SELECT enabled, min_account_age_days FROM antiraid_config WHERE guild_id = ?", (member.guild.id,))
    config = cursor.fetchone()
    if config and config[0] == 1:
        min_days = config[1]
        account_age = (datetime.datetime.now(datetime.timezone.utc) - member.created_at).days
        if account_age < min_days:
            try:
                await member.send(f"⚠️ You were removed from **{member.guild.name}**. Account age under {min_days} days.")
            except discord.Forbidden:
                pass
            await member.kick(reason=f"Anti-Raid: Account age ({account_age}d) under threshold ({min_days}d).")


# ==========================================
# 5. ALL SLASH COMMANDS
# ==========================================

# --- AI COMMAND ---
@bot.tree.command(name="chat", description="Chat with Groq AI")
@app_commands.describe(prompt="What would you like to say to the AI?")
async def chat(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer()
    try:
        chat_completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = chat_completion.choices[0].message.content
        if len(response_text) > 2000:
            await interaction.followup.send(response_text[:1997] + "...")
        else:
            await interaction.followup.send(response_text)
    except Exception as e:
        await interaction.followup.send(f"⚠️ Groq Error: `{e}`")


# --- FUN & INTERACTION COMMANDS ---
@bot.tree.command(name="hug", description="Give someone a warm hug!")
@app_commands.describe(member="The member you want to hug")
async def hug(interaction: discord.Interaction, member: discord.Member):
    gifs = [
        "https://media.giphy.com/media/3oEdv4hwWTzBhWvaU0/giphy.gif",
        "https://media.giphy.com/media/1xV828LzeGWZq/giphy.gif",
        "https://media.giphy.com/media/wIePCLsUO4RWw/giphy.gif"
    ]
    embed = discord.Embed(description=f"🤗 **{interaction.user.mention}** gave a warm hug to **{member.mention}**!", color=discord.Color.pink())
    embed.set_image(url=random.choice(gifs))
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="dab", description="Show off your coolest dab!")
async def dab(interaction: discord.Interaction):
    gifs = [
        "https://media.giphy.com/media/l0HlJDaeqNUDhhaMg/giphy.gif",
        "https://media.giphy.com/media/3o7btPCcdNniyf0ArS/giphy.gif"
    ]
    embed = discord.Embed(description=f"😎 **{interaction.user.mention}** hits a massive dab!", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)


# --- TICKET SYSTEM COMMANDS ---
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

@bot.tree.command(name="setup", description="Launches a configuration panel to create interactive support panels")
async def setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
    
    embed = discord.Embed(title="Support Center", description="Click the button below to open a private support ticket with our team.", color=discord.Color.purple())
    await interaction.channel.send(embed=embed, view=TicketView())
    await interaction.response.send_message("✅ Support ticket panel deployed successfully!", ephemeral=True)

@bot.tree.command(name="close", description="Closes an active support ticket channel and archives it")
async def close(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    res = cursor.fetchone()
    if not res:
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    cursor.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.edit(name=f"closed-{interaction.channel.name}")
    await interaction.response.send_message("🔒 Ticket closed and archived.")

@bot.tree.command(name="reopen", description="Un-archives a closed ticket channel")
async def reopen(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    res = cursor.fetchone()
    if not res:
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    cursor.execute("UPDATE tickets SET status = 'open' WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    
    await interaction.channel.edit(name=interaction.channel.name.replace("closed-", ""))
    await interaction.response.send_message("🔓 Ticket re-opened.")

@bot.tree.command(name="delete", description="Permanently deletes a ticket channel from the server")
async def delete_ticket(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    res = cursor.fetchone()
    if not res:
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    cursor.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    conn.commit()
    
    await interaction.response.send_message("🗑️ Deleting ticket channel in 3 seconds...")
    await asyncio.sleep(3)
    await interaction.channel.delete()

@bot.tree.command(name="add", description="Gives a specific user access to view the private ticket")
@app_commands.describe(user="The user to add to the ticket")
async def add_user(interaction: discord.Interaction, user: discord.Member):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True)
    await interaction.response.send_message(f"✅ Added {user.mention} to this ticket.")

@bot.tree.command(name="remove", description="Revokes a user's access to the private ticket")
@app_commands.describe(user="The user to remove from the ticket")
async def remove_user(interaction: discord.Interaction, user: discord.Member):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from this ticket.")

@bot.tree.command(name="claim", description="Assigns the ticket to the staff member who used the command")
async def claim(interaction: discord.Interaction):
    cursor.execute("SELECT status FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        return await interaction.response.send_message("❌ This is not a recognized ticket channel.", ephemeral=True)
    
    await interaction.response.send_message(f"🛡️ Ticket claimed by {interaction.user.mention}!")


# --- MODERATION COMMANDS ---
@bot.tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for kicking")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.kick_members:
        return await interaction.response.send_message("❌ You lack permission to kick members.", ephemeral=True)
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Successfully kicked **{member.display_name}**. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to kick user: `{e}`", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="The member to ban", reason="Reason for banning")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.ban_members:
        return await interaction.response.send_message("❌ You lack permission to ban members.", ephemeral=True)
    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Successfully banned **{member.display_name}**. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to ban user: `{e}`", ephemeral=True)

@bot.tree.command(name="timeout", description="Timeout a member for a specified number of minutes")
@app_commands.describe(member="The member to timeout", minutes="Duration in minutes", reason="Reason")
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    if not interaction.user.guild_permissions.moderate_members:
        return await interaction.response.send_message("❌ You lack permission to timeout members.", ephemeral=True)
    try:
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 Timed out **{member.display_name}** for {minutes} minutes. Reason: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed to timeout user: `{e}`", ephemeral=True)

@bot.tree.command(name="purge", description="Clear a specified number of messages from a channel")
@app_commands.describe(amount="Number of messages to delete (1-100)")
async def purge(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        return await interaction.response.send_message("❌ You lack permission to manage messages.", ephemeral=True)
    if amount < 1 or amount > 100:
        return await interaction.response.send_message("❌ Please choose a number between 1 and 100.", ephemeral=True)
    
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Successfully cleared {len(deleted)} messages.", ephemeral=True)


# --- PHONE / GLOBAL CHAT SYSTEM ---
@bot.tree.command(name="phone_setup", description="Set the current channel as the cross-server global phone line")
async def phone_setup(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
    
    cursor.execute("""
    INSERT INTO phone_channels (guild_id, channel_id) VALUES (?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET channel_id = ?
    """, (interaction.guild.id, interaction.channel.id, interaction.channel.id))
    conn.commit()
    
    await interaction.response.send_message("📞 **Phone line connected!** Any message sent in this channel will now broadcast to other connected servers.")


# --- LEVELING & ECONOMY COMMANDS ---
@bot.tree.command(name="rank", description="Check your or another user's rank card")
@app_commands.describe(member="The member to check")
async def rank(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (target.id,))
    result = cursor.fetchone()
    if not result:
        return await interaction.response.send_message(f"📊 **{target.display_name}** has no XP recorded yet.", ephemeral=True)
    xp, level = result
    next_level_xp = (level + 1) * 100
    embed = discord.Embed(title=f"📊 Rank Card - {target.display_name}", color=discord.Color.gold())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP Progress", value=f"{xp} / {next_level_xp}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="View server XP leaderboard")
async def leaderboard(interaction: discord.Interaction):
    cursor.execute("SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 5")
    rows = cursor.fetchall()
    if not rows:
        return await interaction.response.send_message("No levels logged yet!", ephemeral=True)
    embed = discord.Embed(title="🏆 Server Level Leaderboard", color=discord.Color.purple())
    for index, (uid, level, xp) in enumerate(rows, start=1):
        user = bot.get_user(uid)
        username = user.name if user else f"User ID {uid}"
        embed.add_field(name=f"#{index} {username}", value=f"Level {level} | {xp} XP", inline=False)
    await interaction.response.send_message(embed=embed)


# --- UTILITY & FUN COMMANDS ---
@bot.tree.command(name="ping", description="Check bot latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

@bot.tree.command(name="roll", description="Roll a die (1-6)")
async def roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 You rolled a **{random.randint(1, 6)}**!")

@bot.tree.command(name="serverinfo", description="View server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📌 Server Info - {guild.name}", color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=str(guild.owner), inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="antiraid", description="Configure anti-raid protection")
@app_commands.describe(status="Enable or disable", min_days="Minimum account age in days")
@app_commands.choices(status=[app_commands.Choice(name="Enable", value=1), app_commands.Choice(name="Disable", value=0)])
async def antiraid(interaction: discord.Interaction, status: int, min_days: int = 7):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ Administrator permission required.", ephemeral=True)
    cursor.execute("""
    INSERT INTO antiraid_config (guild_id, enabled, min_account_age_days) VALUES (?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET enabled = ?, min_account_age_days = ?
    """, (interaction.guild.id, status, min_days, status, min_days))
    conn.commit()
    state = "Enabled ✅" if status == 1 else "Disabled ❌"
    await interaction.response.send_message(f"🛡️ Anti-raid protection is now **{state}** (Min age: {min_days} days).")


# 6. MAIN ENTRYPOINT
async def main():
    await start_web_server()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        await bot.start(token)
    else:
        print("Error: DISCORD_TOKEN environment variable missing.")

if __name__ == "__main__":
    asyncio.run(main())
