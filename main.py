import os
import asyncio
from aiohttp import web
import discord
from discord.ext import commands

# Initialize the Discord bot client with required permissions
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")

# Create a web server endpoint to satisfy Render's health checks
async def handle(request):
    return web.Response(text="Bot is running successfully!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render automatically provides a PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

# Main asynchronous execution function
async def main():
    # Start the web server in the background
    await start_web_server()
    
    # Retrieve your Discord bot token from environment variables and start the bot
    token = os.getenv("DISCORD_TOKEN")
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())


