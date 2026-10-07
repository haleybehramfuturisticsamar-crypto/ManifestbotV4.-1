print("DEBUG: Chat command triggered successfully!")
import os
import random
import datetime
import asyncio
import sqlite3
import discord
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

bot = commands.Bot(command_prefix="!", intents=intents)

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

# 4. GLOBAL ERROR HANDLER
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have the required permissions to run this command.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"⚠️ Missing argument! Usage: `{ctx.prefix}{ctx.command.name} {ctx.command.signature}`")
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Could not find that member. Please mention a valid user.")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ I don't have enough permissions in this server to do that.")
    else:
        print(f"Command Error in {ctx.command}: {error}")

# 5. BOT EVENTS
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Bot is online with Groq!")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = message.author.id
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    
    if user_id not in xp_cooldowns or now - xp_cooldowns[user_id] > 60:
        xp_cooldowns[user_id] = now
        
        cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()

        if result is None:
            cursor.execute("INSERT INTO levels (user_id, xp, level) VALUES (?, ?, ?)", (user_id, 15, 0))
            current_xp, current_lvl = 15, 0
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

# 6. AI COMMANDS (GROQ ONLY)
@bot.command(name="chat")
async def chat(ctx, *, prompt: str = None):
    if not prompt:
        return await ctx.send("⚠️ Please provide a prompt! Example: `!chat hello`")

    async with ctx.typing():
        try:
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful Discord assistant bot.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama-3.3-70b-versatile",
            )
            
            response_text = chat_completion.choices[0].message.content
            
            if len(response_text) > 2000:
                return await ctx.send(response_text[:1997] + "...")
            else:
                return await ctx.send(response_text)
                
        except Exception as e:
            print(f"Groq API Error: {e}")
            await ctx.send("⚠️ Groq servers encountered an error. Please try again in a moment.")

# 7. LEVELING COMMANDS
@bot.command(name="rank", aliases=["level", "xp"])
async def rank(ctx, member: discord.Member = None):
    target = member or ctx.author
    cursor.execute("SELECT xp, level FROM levels WHERE user_id = ?", (target.id,))
    result = cursor.fetchone()

    if not result:
        return await ctx.send(f"📊 **{target.display_name}** has no XP recorded yet.")

    xp, level = result
    next_level_xp = (level + 1) * 100

    embed = discord.Embed(title=f"📊 Rank Card - {target.display_name}", color=discord.Color.gold())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Level", value=str(level), inline=True)
    embed.add_field(name="XP Progress", value=f"{xp} / {next_level_xp}", inline=True)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", aliases=["lb"])
async def leaderboard(ctx):
    cursor.execute("SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 5")
    rows = cursor.fetchall()

    if not rows:
        return await ctx.send("No levels logged yet!")

    embed = discord.Embed(title="🏆 Server Level Leaderboard", color=discord.Color.purple())
    for index, (uid, level, xp) in enumerate(rows, start=1):
        user = bot.get_user(uid)
        username = user.name if user else f"User ID {uid}"
        embed.add_field(name=f"#{index} {username}", value=f"Level {level} | {xp} XP", inline=False)

    await ctx.send(embed=embed)

# 8. ANTI-RAID COMMANDS
@bot.command(name="antiraid")
@commands.has_permissions(administrator=True)
async def antiraid(ctx, option: str = None, min_days: int = 7):
    if option is None or option.lower() not in ["on", "off"]:
        return await ctx.send("Usage: `!antiraid on <days>` or `!antiraid off`")

    is_enabled = 1 if option.lower() == "on" else 0
    cursor.execute(
        "INSERT INTO antiraid_config (guild_id, enabled, min_account_age_days) VALUES (?, ?, ?) "
        "ON CONFLICT(guild_id) DO UPDATE SET enabled=?, min_account_age_days=?",
        (ctx.guild.id, is_enabled, min_days, is_enabled, min_days)
    )
    conn.commit()

    status_str = f"ENABLED ({min_days} days threshold)" if is_enabled else "DISABLED"
    await ctx.send(f"🛡️ Anti-Raid protection is now **{status_str}**.")

@bot.command(name="lockdown")
@commands.has_permissions(administrator=True)
async def lockdown(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔒 Channel is now in **Lockdown**.")

@bot.command(name="unlock")
@commands.has_permissions(administrator=True)
async def unlock(ctx):
    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.send("🔓 Channel lockdown **Lifted**.")

# 9. MODERATION COMMANDS
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await ctx.send(f"✅ Kicked **{member.mention}** | Reason: {reason}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await ctx.send(f"✅ Banned **{member.mention}** | Reason: {reason}")

@bot.command(name="purge", aliases=["clear"])
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int = 5):
    if amount > 100:
        return await ctx.send("Maximum limit is 100 messages.")
    deleted = await ctx.channel.purge(limit=amount + 1)
    msg = await ctx.send(f"🧹 Cleared **{len(deleted) - 1}** messages.")
    await asyncio.sleep(3)
    await msg.delete()

@bot.command(name="timeout", aliases=["mute"])
@commands.has_permissions(moderate_members=True)
async def timeout(ctx, member: discord.Member, minutes: int = 10, *, reason: str = "No reason provided"):
    duration = datetime.timedelta(minutes=minutes)
    await member.timeout(duration, reason=reason)
    await ctx.send(f"🔇 Timed out **{member.mention}** for {minutes}m | Reason: {reason}")

@bot.command(name="untimeout", aliases=["unmute"])
@commands.has_permissions(moderate_members=True)
async def untimeout(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔊 Timeout removed for **{member.mention}**.")

# 10. FUN COMMANDS
@bot.command(name="8ball")
async def eight_ball(ctx, *, question: str):
    responses = ["It is certain.", "Without a doubt.", "Cannot predict now.", "Don't count on it.", "My sources say no."]
    await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")

@bot.command(name="roll")
async def roll(ctx, dice: str = "1d6"):
    try:
        rolls, limit = map(int, dice.lower().split('d'))
        if rolls > 10 or limit > 100:
            return await ctx.send("Max limit: 10 dice, 100 sides.")
        results = [random.randint(1, limit) for _ in range(rolls)]
        await ctx.send(f"🎲 **Rolls:** {', '.join(map(str, results))} (Total: {sum(results)})")
    except Exception:
        await ctx.send("Use format `NdN` (e.g., `!roll 2d6`).")

@bot.command(name="flip")
async def flip(ctx):
    await ctx.send(f"🪙 **{random.choice(['Heads', 'Tails'])}**")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"🏓 Pong! Latency: **{round(bot.latency * 1000)}ms**")

# 11. MAIN ENTRYPOINT
async def main():
    await start_web_server()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        await bot.start(token)
    else:
        print("Error: DISCORD_TOKEN environment variable missing.")

if __name__ == "__main__":
    asyncio.run(main())
