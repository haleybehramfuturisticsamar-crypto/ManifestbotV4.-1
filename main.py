import os
import discord
from discord.ext import commands
from google import genai

# 1. Enable Intents so the bot can read message text
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 2. Initialize Bot with prefix '!'
bot = commands.Bot(command_prefix="!", intents=intents)

# 3. Initialize Gemini Client using your GEMINI_API_KEY environment variable
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Bot is ready and listening for commands!")

# --- GEMINI CHAT COMMAND ---
@bot.command(name="chat")
async def chat(ctx, *, prompt: str):
    """Generates a response from Gemini API"""
    async with ctx.typing():
        try:
            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            # Discord messages have a 2000 character limit
            if len(response.text) > 2000:
                await ctx.send(response.text[:1997] + "...")
            else:
                await ctx.send(response.text)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

# --- MODERATION COMMANDS ---
@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Kicks a member from the server"""
    try:
        await member.kick(reason=reason)
        await ctx.send(f"Kicked {member.mention} for: {reason}")
    except Exception as e:
        await ctx.send(f"Failed to kick user: {e}")

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason: str = "No reason provided"):
    """Bans a member from the server"""
    try:
        await member.ban(reason=reason)
        await ctx.send(f"Banned {member.mention} for: {reason}")
    except Exception as e:
        await ctx.send(f"Failed to ban user: {e}")

# Run the bot using the DISCORD_TOKEN environment variable
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("Error: DISCORD_TOKEN environment variable not found.")



