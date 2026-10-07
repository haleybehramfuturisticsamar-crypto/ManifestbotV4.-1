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
        print("All slash commands synced successfully!")

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
conn.commit()

xp_cooldowns = {}

# 4. BOT EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Bot is online with Groq AI and fully slash-command enabled!")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    # Leveling system logic (passive tracking on chat messages)
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

# 5. ALL SLASH COMMANDS COLLECTION
@bot.tree.command(name="chat", description="Chat with Groq AI using Llama 3.3")
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

@bot.tree.command(name="rank", description="Check your or another user's rank and XP")
@app_commands.describe(member="The member to check (optional)")
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

@bot.tree.command(name="leaderboard", description="View the server XP level leaderboard")
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

@bot.tree.command(name="ping", description="Check the bot's live response latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! Latency: **{round(bot.latency * 1000)}ms**")

@bot.tree.command(name="coinflip", description="Flip a coin (Heads or Tails)")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

@bot.tree.command(name="roll", description="Roll a random die between 1 and 6")
async def roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 You rolled a **{random.randint(1, 6)}**!")

@bot.tree.command(name="serverinfo", description="Display detailed information about this server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📌 Server Info - {guild.name}", color=discord.Color.blue())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=guild.owner, inline=True)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Created On", value=guild.created_at.strftime("%b %d, %Y"), inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="antiraid", description="Toggle or configure anti-raid protection")
@app_commands.describe(status="Enable or disable anti-raid", min_days="Minimum account age in days to allow joining")
@app_commands.choices(status=[
    app_commands.Choice(name="Enable", value=1),
    app_commands.Choice(name="Disable", value=0)
])
async def antiraid(interaction: discord.Interaction, status: int, min_days: int = 7):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message("❌ You need **Administrator** permissions to use this command.", ephemeral=True)
    
    cursor.execute("""
    INSERT INTO antiraid_config (guild_id, enabled, min_account_age_days) 
    VALUES (?, ?, ?)
    ON CONFLICT(guild_id) DO UPDATE SET enabled = ?, min_account_age_days = ?
    """, (interaction.guild.id, status, min_days, status, min_days))
    conn.commit()

    state_text = "Enabled ✅" if status == 1 else "Disabled ❌"
    await interaction.response.send_message(f"🛡️ Anti-raid protection is now **{state_text}** with a minimum account age threshold of **{min_days} days**.")

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
