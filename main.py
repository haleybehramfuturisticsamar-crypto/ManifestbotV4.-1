"""
Manifest V8.0 - Discord Server Automation Bot
Created for Maker thunderxstorms5_.

IMPORTANT:
- A Discord bot cannot become the actual server owner or bypass Discord permissions.
- This bot uses the Maker's Discord USER ID for identity instead of a mutable username.
- All destructive/administrative actions remain subject to Discord's permission and role hierarchy.
- Keep DISCORD_TOKEN and GROQ_API_KEY in environment variables; never hard-code them.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import random
import re
import time
import shutil
from pathlib import Path
from collections import defaultdict, deque
from typing import Optional

import aiosqlite
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks
from groq import AsyncGroq
import yt_dlp


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MAKER_USER_ID = int(os.getenv("MAKER_USER_ID", "1386055253581103164"))
DB_PATH = os.getenv("MANIFEST_DB", "manifest_v8.db")
PORT = int(os.getenv("PORT", "8080"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
PREFIXES = ("!", "?", "$", ".")
VERSION = "8.0"

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")
if not GROQ_API_KEY:
    logging.warning("GROQ_API_KEY is missing. AI features will use fallbacks until it is configured.")

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger("manifest")


# ============================================================
# DISCORD INTENTS
# ============================================================

intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True
intents.moderation = True
intents.voice_states = True
intents.invites = True
intents.presences = False


# ============================================================
# DATABASE
# ============================================================

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id INTEGER PRIMARY KEY,
    ai_enabled INTEGER DEFAULT 1,
    dead_chat_enabled INTEGER DEFAULT 1,
    dead_chat_minutes INTEGER DEFAULT 30,
    dead_chat_role_id INTEGER DEFAULT 0,
    auto_ticket_minutes INTEGER DEFAULT 2,
    automod_enabled INTEGER DEFAULT 1,
    xp_enabled INTEGER DEFAULT 1,
    welcome_enabled INTEGER DEFAULT 0,
    welcome_channel_id INTEGER DEFAULT 0,
    log_channel_id INTEGER DEFAULT 0,
    ticket_category_id INTEGER DEFAULT 0,
    ticket_support_role_id INTEGER DEFAULT 0,
    ai_channel_only INTEGER DEFAULT 0,
    autopilot INTEGER DEFAULT 0,
    lockdown INTEGER DEFAULT 0,
    antinuke_enabled INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS banned_words (
    guild_id INTEGER NOT NULL,
    word TEXT NOT NULL,
    PRIMARY KEY (guild_id, word)
);

CREATE TABLE IF NOT EXISTS memories (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (guild_id, user_id, memory_key)
);

CREATE TABLE IF NOT EXISTS warnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    moderator_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS levels (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    last_xp_at REAL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS economy (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    wallet INTEGER DEFAULT 100,
    bank INTEGER DEFAULT 500,
    last_daily REAL DEFAULT 0,
    last_beg REAL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS inventory (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item TEXT NOT NULL,
    amount INTEGER DEFAULT 1,
    PRIMARY KEY (guild_id, user_id, item)
);

CREATE TABLE IF NOT EXISTS tickets (
    channel_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    claimed_by INTEGER DEFAULT 0,
    status TEXT DEFAULT 'open',
    created_at REAL NOT NULL,
    closed_at REAL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS invite_tracker (
    guild_id INTEGER NOT NULL,
    inviter_id INTEGER NOT NULL,
    uses INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, inviter_id)
);

CREATE TABLE IF NOT EXISTS tags (
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    PRIMARY KEY (guild_id, name)
);

CREATE TABLE IF NOT EXISTS command_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    user_id INTEGER NOT NULL,
    command_name TEXT NOT NULL,
    arguments TEXT DEFAULT '',
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message TEXT NOT NULL,
    due_at REAL NOT NULL,
    delivered INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS security_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_id INTEGER DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS afk (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS maker_memories (
    memory_key TEXT PRIMARY KEY,
    memory_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS maker_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instruction TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS server_memories (
    guild_id INTEGER NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (guild_id, memory_key)
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reaction_roles (
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    emoji TEXT NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (message_id, emoji)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        self.db: Optional[aiosqlite.Connection] = None
        self.lock = asyncio.Lock()

    async def connect(self):
        self.db = await aiosqlite.connect(self.path)
        self.db.row_factory = aiosqlite.Row
        await self.db.executescript(SCHEMA)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    async def execute(self, sql: str, params=()):
        async with self.lock:
            await self.db.execute(sql, params)
            await self.db.commit()

    async def fetchone(self, sql: str, params=()):
        async with self.lock:
            cur = await self.db.execute(sql, params)
            row = await cur.fetchone()
            await cur.close()
            return row

    async def fetchall(self, sql: str, params=()):
        async with self.lock:
            cur = await self.db.execute(sql, params)
            rows = await cur.fetchall()
            await cur.close()
            return rows


db = Database(DB_PATH)


# ============================================================
# HELPERS
# ============================================================

def now() -> float:
    return time.time()


def is_maker(user: discord.abc.User) -> bool:
    return user.id == MAKER_USER_ID


def clamp_text(text: str, limit: int = 1900) -> str:
    text = text or ""
    return text[:limit] + ("…" if len(text) > limit else "")


def split_discord(text: str, limit: int = 1900) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        chunk = text[:limit]
        if len(text) > limit:
            split_at = max(chunk.rfind("\n"), chunk.rfind(" "))
            if split_at > 500:
                chunk = chunk[:split_at]
        chunks.append(chunk)
        text = text[len(chunk):].lstrip()
    return chunks


async def send_long(channel: discord.abc.Messageable, text: str):
    for chunk in split_discord(text):
        await channel.send(chunk)


async def setting(guild_id: int, key: str, default=None):
    row = await db.fetchone(
        f"SELECT {key} FROM guild_settings WHERE guild_id = ?",
        (guild_id,),
    )
    if not row:
        await db.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
            (guild_id,),
        )
        row = await db.fetchone(
            f"SELECT {key} FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
    return row[key] if row and row[key] is not None else default


async def set_setting(guild_id: int, key: str, value):
    allowed = {
        "ai_enabled", "dead_chat_enabled", "dead_chat_minutes",
        "dead_chat_role_id", "auto_ticket_minutes", "automod_enabled",
        "xp_enabled", "welcome_enabled", "welcome_channel_id",
        "log_channel_id", "ticket_category_id", "ticket_support_role_id",
        "ai_channel_only", "autopilot", "lockdown", "antinuke_enabled"
    }
    if key not in allowed:
        raise ValueError("Invalid setting.")
    await db.execute(
        f"INSERT INTO guild_settings (guild_id, {key}) VALUES (?, ?)"
        f" ON CONFLICT(guild_id) DO UPDATE SET {key}=excluded.{key}",
        (guild_id, value),
    )


async def log_to_channel(guild: discord.Guild, message: str):
    channel_id = await setting(guild.id, "log_channel_id", 0)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel:
        try:
            await channel.send(clamp_text(message))
        except discord.HTTPException:
            pass


async def log_command(interaction: discord.Interaction, name: str, args: str = ""):
    await db.execute(
        "INSERT INTO command_logs (guild_id,user_id,command_name,arguments,created_at) VALUES (?,?,?,?,?)",
        (interaction.guild_id or 0, interaction.user.id, name, clamp_text(args, 500), now()),
    )


async def ensure_guild(guild: discord.Guild):
    await db.execute(
        "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)",
        (guild.id,),
    )


async def get_banned_words(guild_id: int) -> list[str]:
    rows = await db.fetchall(
        "SELECT word FROM banned_words WHERE guild_id = ?",
        (guild_id,),
    )
    return [r["word"] for r in rows]


async def memories_for(guild_id: int, user_id: int) -> str:
    rows = await db.fetchall(
        "SELECT memory_key,memory_value FROM memories WHERE guild_id=? AND user_id=? ORDER BY updated_at DESC LIMIT 20",
        (guild_id, user_id),
    )
    if not rows:
        return "No stored memory."
    return "; ".join(f"{r['memory_key']}: {r['memory_value']}" for r in rows)


async def maker_memories_text() -> str:
    rows = await db.fetchall("SELECT memory_key,memory_value FROM maker_memories ORDER BY updated_at DESC LIMIT 30")
    return "; ".join(f"{r['memory_key']}: {r['memory_value']}" for r in rows) or "No Maker memory."


async def maker_instructions_text() -> str:
    rows = await db.fetchall("SELECT id,instruction FROM maker_instructions WHERE enabled=1 ORDER BY id ASC LIMIT 50")
    if not rows:
        return "No persistent Maker instructions."
    return "\n".join(f"[{r['id']}] {r['instruction']}" for r in rows)


async def server_memories_text(guild_id: int) -> str:
    rows = await db.fetchall(
        "SELECT memory_key,memory_value FROM server_memories WHERE guild_id=? ORDER BY updated_at DESC LIMIT 30",
        (guild_id,),
    )
    return "; ".join(f"{r['memory_key']}: {r['memory_value']}" for r in rows) or "No server memory."


async def persistent_history(guild_id: int, user_id: int) -> list[dict[str, str]]:
    rows = await db.fetchall(
        "SELECT role,content FROM conversation_history WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 12",
        (guild_id, user_id),
    )
    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]


async def save_ai_turn(guild_id: int, user_id: int, channel_id: int, prompt: str, answer: str):
    await db.execute(
        "INSERT INTO conversation_history(guild_id,user_id,channel_id,role,content,created_at) VALUES(?,?,?,?,?,?)",
        (guild_id, user_id, channel_id, "user", prompt[:4000], now()),
    )
    await db.execute(
        "INSERT INTO conversation_history(guild_id,user_id,channel_id,role,content,created_at) VALUES(?,?,?,?,?,?)",
        (guild_id, user_id, channel_id, "assistant", answer[:4000], now()),
    )
    # Keep the persistent conversation compact.
    await db.execute(
        "DELETE FROM conversation_history WHERE guild_id=? AND user_id=? AND id NOT IN "
        "(SELECT id FROM conversation_history WHERE guild_id=? AND user_id=? ORDER BY id DESC LIMIT 40)",
        (guild_id, user_id, guild_id, user_id),
    )


# ============================================================
# AI ENGINE
# ============================================================

groq: Optional[AsyncGroq] = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
ai_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
conversation_cache: dict[tuple[int, int], deque] = defaultdict(lambda: deque(maxlen=12))


async def ask_ai(
    guild: discord.Guild,
    user: discord.Member,
    prompt: str,
    channel: Optional[discord.TextChannel] = None,
    system_extra: str = "",
) -> str:
    if not groq:
        return "AI is not configured. Add GROQ_API_KEY to enable the Manifest AI engine."

    user_memory = await memories_for(guild.id, user.id)
    maker_memory = await maker_memories_text()
    maker_rules = await maker_instructions_text()
    server_memory = await server_memories_text(guild.id)
    rules = await db.fetchall("SELECT word FROM banned_words WHERE guild_id=?", (guild.id,))
    restricted = ", ".join(r["word"] for r in rules) or "none"

    history = await persistent_history(guild.id, user.id)
    # Keep a short in-process cache too, so rapid conversations stay responsive.
    history.extend(list(conversation_cache[(guild.id, user.id)]))
    history = history[-12:]

    system = f"""
You are Manifest V{VERSION}, a Discord server assistant created by Maker thunderxstorms5_.
Maker identity is controlled by Discord user ID {MAKER_USER_ID}, not a display name.
You recognize the Maker across every guild where you are installed.
Priority order for stored context: legitimate Maker instructions > server configuration/memory > user memory > current conversation.
Persistent Maker instructions are standing preferences/rules for Manifest, but they do not grant illegal powers, bypass Discord permissions, override platform security, or override higher-priority safety requirements.
Never claim you completed an action unless the bot actually completed it.
Be helpful, concise, professional and server-aware.
Maker memory: {maker_memory}
Persistent Maker instructions:
{maker_rules}
Server memory: {server_memory}
Stored user memory: {user_memory}
Restricted terms configured by this server: {restricted}
{system_extra}
"""

    messages = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    async with ai_locks[guild.id]:
        try:
            completion = await groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0.6,
                max_completion_tokens=900,
            )
            answer = completion.choices[0].message.content or "I couldn't generate a response."
            conversation_cache[(guild.id, user.id)].append({"role": "user", "content": prompt})
            conversation_cache[(guild.id, user.id)].append({"role": "assistant", "content": answer})
            await save_ai_turn(guild.id, user.id, channel.id if channel else 0, prompt, answer)
            return answer
        except Exception:
            log.exception("Groq request failed")
            return "The AI engine is temporarily unavailable. The rest of Manifest is still online."


# ============================================================
# MUSIC ENGINE
# ============================================================

MUSIC_FFMPEG = os.getenv("FFMPEG_PATH", "ffmpeg")

class Track:
    def __init__(self, title: str, stream_url: str, webpage_url: str, duration: int | None, requester_id: int):
        self.title = title
        self.stream_url = stream_url
        self.webpage_url = webpage_url
        self.duration = duration or 0
        self.requester_id = requester_id


class GuildMusic:
    def __init__(self):
        self.queue: deque[Track] = deque()
        self.current: Track | None = None
        self.volume = 0.5
        self.text_channel: discord.TextChannel | None = None
        self.lock = asyncio.Lock()


music_states: dict[int, GuildMusic] = defaultdict(GuildMusic)

YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",
}


async def resolve_track(query: str, requester_id: int) -> Track:
    def extract():
        with yt_dlp.YoutubeDL(YTDLP_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = next((x for x in info["entries"] if x), None)
            if not info or not info.get("url"):
                raise RuntimeError("No playable audio was found.")
            return info

    info = await asyncio.to_thread(extract)
    return Track(
        info.get("title", "Unknown track"),
        info["url"],
        info.get("webpage_url", query),
        info.get("duration"),
        requester_id,
    )


async def play_next(guild: discord.Guild):
    state = music_states[guild.id]
    async with state.lock:
        if not guild.voice_client or not isinstance(guild.voice_client, discord.VoiceClient):
            state.current = None
            return
        if guild.voice_client.is_playing() or guild.voice_client.is_paused():
            return
        if not state.queue:
            state.current = None
            return

        track = state.queue.popleft()
        state.current = track
        try:
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(
                    track.stream_url,
                    executable=MUSIC_FFMPEG,
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn",
                ),
                volume=state.volume,
            )
        except Exception:
            state.current = None
            raise

        def after(error):
            if error:
                log.warning("Music playback error in %s: %s", guild.id, error)
            asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

        guild.voice_client.play(source, after=after)
        if state.text_channel:
            try:
                await state.text_channel.send(f"▶️ **Now playing:** {track.title}")
            except discord.HTTPException:
                pass


# ============================================================
# BOT
# ============================================================

class ManifestBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=PREFIXES,
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )
        self.invite_cache: dict[int, dict[str, int]] = {}
        self.channel_activity: dict[int, float] = {}
        self.rate_limits: dict[tuple[int, int, str], float] = {}

    async def setup_hook(self):
        await db.connect()
        for guild in self.guilds:
            await ensure_guild(guild)

        if not self.dead_chat_loop.is_running():
            self.dead_chat_loop.start()
        if not self.ticket_loop.is_running():
            self.ticket_loop.start()
        if not self.reminder_loop.is_running():
            self.reminder_loop.start()
        if not self.security_loop.is_running():
            self.security_loop.start()

        try:
            synced = await self.tree.sync()
            log.info("Synced %d global slash commands.", len(synced))
        except Exception:
            log.exception("Slash command sync failed.")

    async def close(self):
        self.dead_chat_loop.cancel()
        self.ticket_loop.cancel()
        self.reminder_loop.cancel()
        self.security_loop.cancel()
        await db.close()
        await super().close()

    def cooldown(self, guild_id: int, user_id: int, key: str, seconds: float) -> bool:
        k = (guild_id, user_id, key)
        current = now()
        if current - self.rate_limits.get(k, 0) < seconds:
            return False
        self.rate_limits[k] = current
        return True

    @tasks.loop(minutes=5)
    async def dead_chat_loop(self):
        for guild in self.guilds:
            if not await setting(guild.id, "dead_chat_enabled", 1):
                continue

            minutes = int(await setting(guild.id, "dead_chat_minutes", 30))
            role_id = int(await setting(guild.id, "dead_chat_role_id", 0) or 0)
            role = guild.get_role(role_id) if role_id else None

            for channel in guild.text_channels:
                if channel.id not in self.activity:
                    continue
                if now() - self.activity[channel.id] < minutes * 60:
                    continue
                perms = channel.permissions_for(guild.me)
                if not perms.send_messages:
                    continue

                self.activity[channel.id] = now()
                try:
                    # No mention of @everyone unless a specific configured role is used.
                    topic = await ask_ai(
                        guild,
                        guild.me,  # type: ignore[arg-type]
                        "Give one short, friendly conversation starter that fits a Discord community. No spam, no insults.",
                        channel,
                        "This is a dead-chat revival. Keep it to one or two sentences.",
                    )
                    mention = role.mention if role else ""
                    await channel.send(f"{mention} 💬 **Chat revival:** {clamp_text(topic, 900)}")
                except discord.HTTPException:
                    pass

    @tasks.loop(seconds=30)
    async def ticket_loop(self):
        cutoff = now() - 120
        rows = await db.fetchall(
            "SELECT channel_id,guild_id,user_id FROM tickets WHERE status='open' AND claimed_by=0 AND created_at <= ?",
            (cutoff,),
        )
        for row in rows:
            channel = self.get_channel(row["channel_id"])
            guild = self.get_guild(row["guild_id"])
            if not channel or not guild:
                await db.execute(
                    "UPDATE tickets SET status='orphaned' WHERE channel_id=?",
                    (row["channel_id"],),
                )
                continue

            await db.execute(
                "UPDATE tickets SET claimed_by=?,status='bot_assisted' WHERE channel_id=?",
                (self.user.id if self.user else 0, row["channel_id"]),
            )
            member = guild.get_member(row["user_id"])
            if member:
                try:
                    answer = await ask_ai(
                        guild,
                        member,
                        "A support ticket has been unclaimed for two minutes. Greet the user, explain that Manifest is assisting, and ask for the exact issue, order/transaction reference if relevant, and any useful evidence. Do not invent refunds or account changes.",
                        channel,  # type: ignore[arg-type]
                    )
                    await channel.send(f"🤖 **Manifest AI assistance:**\n{clamp_text(answer)}")
                except discord.HTTPException:
                    pass

    @tasks.loop(seconds=20)
    async def reminder_loop(self):
        rows = await db.fetchall(
            "SELECT id,guild_id,user_id,channel_id,message FROM reminders WHERE delivered=0 AND due_at <= ?",
            (now(),),
        )
        for row in rows:
            channel = self.get_channel(row["channel_id"])
            if channel:
                try:
                    await channel.send(f"<@{row['user_id']}> ⏰ **Reminder:** {row['message']}")
                except discord.HTTPException:
                    pass
            await db.execute("UPDATE reminders SET delivered=1 WHERE id=?", (row["id"],))

    @tasks.loop(seconds=45)
    async def security_loop(self):
        """Audit-log watcher. It alerts staff; it never pretends to have owner-level powers."""
        for guild in self.guilds:
            if not await setting(guild.id, "antinuke_enabled", 1):
                continue

            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete):
                    if now() - entry.created_at.timestamp() > 60:
                        continue
                    actor = entry.user
                    if not actor or actor.bot:
                        continue
                    await db.execute(
                        "INSERT INTO security_events(guild_id,actor_id,action,target_id,created_at) VALUES(?,?,?,?,?)",
                        (guild.id, actor.id, "channel_delete", getattr(entry.target, "id", 0), now()),
                    )
                    await log_to_channel(
                        guild,
                        f"🛡️ Anti-nuke alert: {actor.mention} deleted a channel. "
                        "Manifest did not auto-punish the actor."
                    )
                    break
            except (discord.Forbidden, discord.HTTPException):
                continue

            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.role_delete):
                    if now() - entry.created_at.timestamp() > 60:
                        continue
                    actor = entry.user
                    if not actor or actor.bot:
                        continue
                    await db.execute(
                        "INSERT INTO security_events(guild_id,actor_id,action,target_id,created_at) VALUES(?,?,?,?,?)",
                        (guild.id, actor.id, "role_delete", getattr(entry.target, "id", 0), now()),
                    )
                    await log_to_channel(
                        guild,
                        f"🛡️ Anti-nuke alert: {actor.mention} deleted a role. "
                        "Manifest did not auto-punish the actor."
                    )
                    break
            except (discord.Forbidden, discord.HTTPException):
                continue

    @dead_chat_loop.before_loop
    @ticket_loop.before_loop
    @reminder_loop.before_loop
    @security_loop.before_loop
    async def wait_for_ready(self):
        await self.wait_until_ready()


bot = ManifestBot()


# ============================================================
# EVENTS
# ============================================================

@bot.event
async def on_ready():
    for guild in bot.guilds:
        await ensure_guild(guild)
        try:
            invites = await guild.invites()
            bot.invite_cache[guild.id] = {inv.code: (inv.uses or 0) for inv in invites}
        except (discord.Forbidden, discord.HTTPException):
            bot.invite_cache[guild.id] = {}
    log.info("Manifest V8.0 online as %s (%s)", bot.user, bot.user.id if bot.user else "?")


@bot.event
async def on_guild_join(guild: discord.Guild):
    await ensure_guild(guild)
    await log_to_channel(guild, "✅ Manifest V8.0 joined the server.")


@bot.event
async def on_member_join(member: discord.Member):
    await ensure_guild(member.guild)

    try:
        old = bot.invite_cache.get(member.guild.id, {})
        new_invites = await member.guild.invites()
        found = None
        for invite in new_invites:
            if invite.code in old and (invite.uses or 0) > old[invite.code]:
                found = invite
                break

        bot.invite_cache[member.guild.id] = {i.code: (i.uses or 0) for i in new_invites}

        if found and found.inviter:
            await db.execute(
                """INSERT INTO invite_tracker(guild_id,inviter_id,uses) VALUES(?,?,1)
                   ON CONFLICT(guild_id,inviter_id) DO UPDATE SET uses=uses+1""",
                (member.guild.id, found.inviter.id),
            )
    except (discord.Forbidden, discord.HTTPException):
        pass

    enabled = await setting(member.guild.id, "welcome_enabled", 0)
    channel_id = await setting(member.guild.id, "welcome_channel_id", 0)
    if enabled and channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"👋 Welcome {member.mention} to **{member.guild.name}**!")


@bot.event
async def on_member_remove(member: discord.Member):
    await log_to_channel(member.guild, f"📤 **{member}** left the server.")


@bot.event
async def on_message(message: discord.Message):
    if not message.guild or message.author.bot:
        return

    guild = message.guild
    await ensure_guild(guild)
    bot.channel_activity[message.channel.id] = now()

    # Explicit Maker phrase for turning a chat instruction into a persistent rule.
    # We intentionally do not store every Maker message as a permanent rule.
    if is_maker(message.author):
        raw = message.content.strip()
        lowered = raw.casefold()
        prefixes = ("remember this rule:", "manifest remember:", "save this rule:")
        matched = next((prefix for prefix in prefixes if lowered.startswith(prefix)), None)
        if matched:
            instruction = raw[len(matched):].strip()[:1500]
            if instruction:
                await db.execute(
                    "INSERT INTO maker_instructions(instruction,enabled,created_at,updated_at) VALUES(?,?,?,?)",
                    (instruction, 1, now(), now()),
                )
                await message.channel.send("📌 Saved as a persistent Maker rule.", delete_after=8)
                return

    mentioned_afk = []
    for user in message.mentions:
        row = await db.fetchone(
            "SELECT reason FROM afk WHERE guild_id=? AND user_id=?",
            (guild.id, user.id),
        )
        if row:
            mentioned_afk.append(f"💤 **{user.display_name}** is AFK: {row['reason']}")
    if mentioned_afk:
        await message.channel.send("\n".join(mentioned_afk), delete_after=12)

    own_afk = await db.fetchone(
        "SELECT 1 FROM afk WHERE guild_id=? AND user_id=?",
        (guild.id, message.author.id),
    )
    if own_afk:
        await db.execute(
            "DELETE FROM afk WHERE guild_id=? AND user_id=?",
            (guild.id, message.author.id),
        )
        await message.channel.send(f"👋 Welcome back, {message.author.mention}!", delete_after=8)

    if await setting(guild.id, "xp_enabled", 1) and bot.cooldown(guild.id, message.author.id, "xp", 60):
        row = await db.fetchone(
            "SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?",
            (guild.id, message.author.id),
        )
        xp = (row["xp"] if row else 0) + random.randint(8, 18)
        level = row["level"] if row else 0
        new_level = int((xp / 100) ** 0.5 * 10)

        if new_level > level:
            await db.execute(
                """INSERT INTO levels(guild_id,user_id,xp,level,last_xp_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=excluded.xp,level=excluded.level,last_xp_at=excluded.last_xp_at""",
                (guild.id, message.author.id, xp, new_level, now()),
            )
            await message.channel.send(
                f"🎉 {message.author.mention} reached **level {new_level}**!",
                delete_after=10,
            )
        else:
            await db.execute(
                """INSERT INTO levels(guild_id,user_id,xp,level,last_xp_at) VALUES(?,?,?,?,?)
                   ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=excluded.xp,last_xp_at=excluded.last_xp_at""",
                (guild.id, message.author.id, xp, level, now()),
            )

    if await setting(guild.id, "automod_enabled", 1):
        banned = await get_banned_words(guild.id)
        lower = message.content.casefold()
        hit = next(
            (w for w in banned if re.search(rf"\b{re.escape(w.casefold())}\b", lower)),
            None,
        )
        if hit and not is_maker(message.author):
            try:
                await message.delete()
                await message.channel.send(
                    f"⚠️ {message.author.mention}, that term is restricted here.",
                    delete_after=5,
                )
            except discord.HTTPException:
                pass
            return

    ai_enabled = await setting(guild.id, "ai_enabled", 1)
    ai_channel_only = await setting(guild.id, "ai_channel_only", 0)
    is_ticket = isinstance(message.channel, discord.TextChannel) and message.channel.name.startswith("ticket-")
    mentioned = bot.user and bot.user in message.mentions
    allowed_ai = ai_enabled and (mentioned or is_ticket) and (not ai_channel_only or mentioned)

    if allowed_ai:
        prompt = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
        if prompt:
            async with message.channel.typing():
                response = await ask_ai(
                    guild,
                    message.author,
                    prompt,
                    message.channel if isinstance(message.channel, discord.TextChannel) else None,
                )
            await send_long(message.channel, response)
            return

    await bot.process_commands(message)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None or payload.user_id == bot.user.id:
        return
    emoji = str(payload.emoji)
    row = await db.fetchone(
        "SELECT role_id FROM reaction_roles WHERE guild_id=? AND channel_id=? AND message_id=? AND emoji=?",
        (payload.guild_id, payload.channel_id, payload.message_id, emoji),
    )
    if not row:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    role = guild.get_role(row["role_id"]) if guild else None
    if member and role and not role.managed and role < guild.me.top_role:
        try:
            await member.add_roles(role, reason="Manifest reaction role")
        except discord.HTTPException:
            pass


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    if payload.guild_id is None:
        return
    emoji = str(payload.emoji)
    row = await db.fetchone(
        "SELECT role_id FROM reaction_roles WHERE guild_id=? AND channel_id=? AND message_id=? AND emoji=?",
        (payload.guild_id, payload.channel_id, payload.message_id, emoji),
    )
    if not row:
        return
    guild = bot.get_guild(payload.guild_id)
    member = guild.get_member(payload.user_id) if guild else None
    role = guild.get_role(row["role_id"]) if guild else None
    if member and role and not role.managed and role < guild.me.top_role:
        try:
            await member.remove_roles(role, reason="Manifest reaction role")
        except discord.HTTPException:
            pass


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command and interaction.data:
        name = str(interaction.data.get("name", "?"))
        if interaction.guild_id:
            await db.execute(
                "INSERT INTO command_logs(guild_id,user_id,command_name,arguments,created_at) VALUES(?,?,?,?,?)",
                (interaction.guild_id, interaction.user.id, "/" + name, json.dumps(interaction.data.get("options", []), default=str)[:500], now()),
            )


@bot.event
async def on_command(ctx: commands.Context):
    if ctx.guild:
        await db.execute(
            "INSERT INTO command_logs(guild_id,user_id,command_name,arguments,created_at) VALUES(?,?,?,?,?)",
            (
                ctx.guild.id,
                ctx.author.id,
                ctx.command.qualified_name if ctx.command else "?",
                ctx.message.content[:500],
                now(),
            ),
        )


@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("⚠️ You do not have the required Discord permission.", delete_after=8)
        return
    log.exception("Prefix command error", exc_info=error)


# ============================================================
# CHECKS
# ============================================================

def maker_only():
    async def predicate(interaction: discord.Interaction):
        if not is_maker(interaction.user):
            raise app_commands.CheckFailure("Maker only.")
        return True
    return app_commands.check(predicate)


# ============================================================
# CORE / INFO
# ============================================================

@bot.tree.command(name="manifest", description="Show Manifest status and feature summary.")
async def manifest(interaction: discord.Interaction):
    await log_command(interaction, "manifest")
    embed = discord.Embed(
        title="⚡ Manifest V8.0",
        description="Autonomous server assistant online.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Maker", value=f"<@{MAKER_USER_ID}>", inline=True)
    embed.add_field(name="AI", value="Online" if groq else "Not configured", inline=True)
    embed.add_field(name="Guilds", value=str(len(bot.guilds)), inline=True)
    embed.add_field(
        name="Core",
        value="Tickets • AI • Moderation • AutoMod • Dead-chat revival • Invites • XP • Economy • Memories • Reminders • Tags",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Show server information.")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    embed = discord.Embed(title=guild.name, color=discord.Color.blurple())
    embed.add_field(name="Members", value=str(guild.member_count or 0))
    embed.add_field(name="Channels", value=str(len(guild.channels)))
    embed.add_field(name="Roles", value=str(len(guild.roles)))
    embed.add_field(name="Owner", value=f"<@{guild.owner_id}>")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show information about a member.")
async def userinfo(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"User: {member.display_name}", color=member.color)
    embed.add_field(name="ID", value=str(member.id))
    embed.add_field(
        name="Joined",
        value=discord.utils.format_dt(member.joined_at, "F") if member.joined_at else "Unknown",
    )
    embed.add_field(name="Created", value=discord.utils.format_dt(member.created_at, "F"))
    embed.add_field(
        name="Roles",
        value=", ".join(r.mention for r in member.roles[1:][-10:]) or "None",
        inline=False,
    )
    await interaction.response.send_message(embed=embed)


# ============================================================
# AI / MEMORY
# ============================================================

@bot.tree.command(name="ai", description="Ask Manifest AI a question.")
async def ai(interaction: discord.Interaction, prompt: str):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    if not await setting(interaction.guild.id, "ai_enabled", 1):
        return await interaction.response.send_message("AI is disabled in this server.", ephemeral=True)
    await interaction.response.defer()
    answer = await ask_ai(
        interaction.guild,
        interaction.user,  # type: ignore[arg-type]
        prompt,
        interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None,
    )
    await interaction.followup.send(clamp_text(answer))


@bot.tree.command(name="remember", description="Save a memory about yourself for Manifest.")
async def remember(interaction: discord.Interaction, key: str, value: str):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    value = value.strip()[:500]
    if not key or not value:
        return await interaction.response.send_message("Provide a memory key and value.", ephemeral=True)

    await db.execute(
        """INSERT INTO memories(guild_id,user_id,memory_key,memory_value,created_at,updated_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(guild_id,user_id,memory_key)
           DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at""",
        (interaction.guild.id, interaction.user.id, key, value, now(), now()),
    )
    await interaction.response.send_message(f"🧠 Saved memory **{key}**.", ephemeral=True)


@bot.tree.command(name="forget", description="Delete one of your stored memories.")
async def forget(interaction: discord.Interaction, key: str):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    await db.execute(
        "DELETE FROM memories WHERE guild_id=? AND user_id=? AND memory_key=?",
        (interaction.guild.id, interaction.user.id, key.strip()),
    )
    await interaction.response.send_message(f"🧠 Removed memory **{key}**.", ephemeral=True)


@bot.tree.command(name="memories", description="Show your stored Manifest memories.")
async def memories(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    text = await memories_for(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(clamp_text(text, 1800), ephemeral=True)


# ============================================================
# PERSISTENT MAKER / SERVER / USER MEMORY
# ============================================================

@bot.tree.command(name="maker_memory", description="Save a global Maker memory for Manifest.")
@maker_only()
async def maker_memory(interaction: discord.Interaction, key: str, value: str):
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    value = value.strip()[:1000]
    await db.execute(
        "INSERT INTO maker_memories(memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at",
        (key, value, now(), now()),
    )
    await interaction.response.send_message(f"🧠 Global Maker memory saved: **{key}**", ephemeral=True)


@bot.tree.command(name="maker_forget", description="Remove a global Maker memory.")
@maker_only()
async def maker_forget(interaction: discord.Interaction, key: str):
    await db.execute("DELETE FROM maker_memories WHERE memory_key=?", (key.strip(),))
    await interaction.response.send_message(f"🧠 Global Maker memory removed: **{key}**", ephemeral=True)


@bot.tree.command(name="maker_memories", description="Show global Maker memories.")
@maker_only()
async def maker_memories(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await maker_memories_text(), 1900), ephemeral=True)


@bot.tree.command(name="maker_rule_add", description="Add a persistent global instruction for Manifest.")
@maker_only()
async def maker_rule_add(interaction: discord.Interaction, instruction: str):
    instruction = instruction.strip()[:1500]
    if not instruction:
        return await interaction.response.send_message("Instruction cannot be empty.", ephemeral=True)
    await db.execute(
        "INSERT INTO maker_instructions(instruction,enabled,created_at,updated_at) VALUES(?,?,?,?)",
        (instruction, 1, now(), now()),
    )
    row = await db.fetchone("SELECT id FROM maker_instructions ORDER BY id DESC LIMIT 1")
    await interaction.response.send_message(f"📌 Maker rule saved as **#{row['id']}**. It will apply across servers where Manifest is installed, within Discord permissions and safety limits.", ephemeral=True)


@bot.tree.command(name="maker_rule_remove", description="Remove a persistent Maker instruction by ID.")
@maker_only()
async def maker_rule_remove(interaction: discord.Interaction, rule_id: int):
    await db.execute("DELETE FROM maker_instructions WHERE id=?", (rule_id,))
    await interaction.response.send_message(f"📌 Maker rule **#{rule_id}** removed.", ephemeral=True)


@bot.tree.command(name="maker_rules", description="Show persistent Maker instructions.")
@maker_only()
async def maker_rules(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await maker_instructions_text(), 1900), ephemeral=True)


@bot.tree.command(name="server_remember", description="Save a memory/configuration for this server.")
@maker_only()
async def server_remember(interaction: discord.Interaction, key: str, value: str):
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    value = value.strip()[:1000]
    await db.execute(
        "INSERT INTO server_memories(guild_id,memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(guild_id,memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at",
        (interaction.guild_id, key, value, now(), now()),
    )
    await interaction.response.send_message(f"🏠 Server memory saved: **{key}**", ephemeral=True)


@bot.tree.command(name="server_forget", description="Remove a server memory.")
@maker_only()
async def server_forget(interaction: discord.Interaction, key: str):
    await db.execute("DELETE FROM server_memories WHERE guild_id=? AND memory_key=?", (interaction.guild_id, key.strip()))
    await interaction.response.send_message(f"🏠 Server memory removed: **{key}**", ephemeral=True)


@bot.tree.command(name="server_memories", description="Show this server's stored memories.")
async def server_memories(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await server_memories_text(interaction.guild_id), 1900), ephemeral=True)


@bot.tree.command(name="remember_user", description="Save memory about another member. Maker or server managers only.")
async def remember_user(interaction: discord.Interaction, member: discord.Member, key: str, value: str):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server or Maker access.", ephemeral=True)
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    value = value.strip()[:500]
    await db.execute(
        "INSERT INTO memories(guild_id,user_id,memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?,?,?) "
        "ON CONFLICT(guild_id,user_id,memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at",
        (interaction.guild_id, member.id, key, value, now(), now()),
    )
    await interaction.response.send_message(f"🧠 Saved **{key}** for {member.mention}.", ephemeral=True)


@bot.tree.command(name="forget_user", description="Remove stored memory about another member.")
async def forget_user(interaction: discord.Interaction, member: discord.Member, key: str):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server or Maker access.", ephemeral=True)
    await db.execute("DELETE FROM memories WHERE guild_id=? AND user_id=? AND memory_key=?", (interaction.guild_id, member.id, key.strip()))
    await interaction.response.send_message(f"🧠 Removed **{key}** for {member.mention}.", ephemeral=True)


@bot.tree.command(name="memories_user", description="View stored memory about another member.")
async def memories_user(interaction: discord.Interaction, member: discord.Member):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server or Maker access.", ephemeral=True)
    await interaction.response.send_message(clamp_text(await memories_for(interaction.guild_id, member.id), 1900), ephemeral=True)


@bot.tree.command(name="clear_my_memory", description="Delete all of your stored memories in this server.")
async def clear_my_memory(interaction: discord.Interaction):
    await db.execute("DELETE FROM memories WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id))
    await interaction.response.send_message("🧠 Your personal Manifest memory for this server was cleared.", ephemeral=True)


# ============================================================
# MUSIC COMMANDS
# ============================================================

@bot.tree.command(name="play", description="Play or queue a track from a supported audio/video URL or search term.")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.voice or not interaction.user.voice.channel:
        return await interaction.response.send_message("Join a voice channel first.", ephemeral=True)
    await interaction.response.defer()
    state = music_states[interaction.guild.id]
    try:
        if not interaction.guild.voice_client:
            await interaction.user.voice.channel.connect()
        elif interaction.guild.voice_client.channel != interaction.user.voice.channel:
            await interaction.guild.voice_client.move_to(interaction.user.voice.channel)
        state.text_channel = interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None
        track = await resolve_track(query, interaction.user.id)
        if interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused() or state.current:
            state.queue.append(track)
            await interaction.followup.send(f"🎵 Queued **{track.title}** — position `{len(state.queue)}`.")
        else:
            state.queue.appendleft(track)
            await play_next(interaction.guild)
            await interaction.followup.send(f"🎵 Starting **{track.title}**.")
    except Exception as exc:
        log.exception("Music play failed")
        await interaction.followup.send(f"❌ Couldn't play that source: `{clamp_text(str(exc), 500)}`")


@bot.tree.command(name="pause", description="Pause music playback.")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client if interaction.guild else None
    if not vc or not vc.is_playing():
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    vc.pause()
    await interaction.response.send_message("⏸️ Paused.")


@bot.tree.command(name="resume", description="Resume paused music.")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client if interaction.guild else None
    if not vc or not vc.is_paused():
        return await interaction.response.send_message("Nothing is paused.", ephemeral=True)
    vc.resume()
    await interaction.response.send_message("▶️ Resumed.")


@bot.tree.command(name="skip", description="Skip the current track.")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client if interaction.guild else None
    if not vc or not vc.is_playing():
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    vc.stop()
    await interaction.response.send_message("⏭️ Skipped.")


@bot.tree.command(name="stop", description="Stop music and clear the queue.")
async def stop(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    state.queue.clear()
    state.current = None
    if interaction.guild.voice_client:
        interaction.guild.voice_client.stop()
    await interaction.response.send_message("⏹️ Stopped and cleared the queue.")


@bot.tree.command(name="queue", description="Show the music queue.")
async def queue(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    lines = [f"**Now:** {state.current.title}" if state.current else "**Now:** Nothing"]
    lines += [f"`{i}` {t.title}" for i, t in enumerate(list(state.queue)[:20], 1)]
    await interaction.response.send_message("🎶 **Music Queue**\n" + "\n".join(lines))


@bot.tree.command(name="nowplaying", description="Show the current track.")
async def nowplaying(interaction: discord.Interaction):
    state = music_states[interaction.guild.id] if interaction.guild else None
    if not state or not state.current:
        return await interaction.response.send_message("Nothing is playing.", ephemeral=True)
    await interaction.response.send_message(f"🎧 **{state.current.title}**\n{state.current.webpage_url}")


@bot.tree.command(name="shuffle", description="Shuffle the music queue.")
async def shuffle(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    items = list(state.queue)
    random.shuffle(items)
    state.queue = deque(items)
    await interaction.response.send_message("🔀 Queue shuffled.")


@bot.tree.command(name="remove", description="Remove a track from the queue by position.")
async def remove(interaction: discord.Interaction, position: app_commands.Range[int, 1, 100]):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    items = list(state.queue)
    if position > len(items):
        return await interaction.response.send_message("That queue position does not exist.", ephemeral=True)
    track = items.pop(position - 1)
    state.queue = deque(items)
    await interaction.response.send_message(f"🗑️ Removed **{track.title}**.")


@bot.tree.command(name="clearqueue", description="Clear all queued tracks without stopping the current track.")
async def clearqueue(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    music_states[interaction.guild.id].queue.clear()
    await interaction.response.send_message("🧹 Music queue cleared.")


@bot.tree.command(name="volume", description="Set music volume from 0 to 100 percent.")
async def volume(interaction: discord.Interaction, percent: app_commands.Range[int, 0, 100]):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    state.volume = percent / 100
    vc = interaction.guild.voice_client
    if vc and isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = state.volume
    await interaction.response.send_message(f"🔊 Volume set to **{percent}%**.")


@bot.tree.command(name="leave", description="Disconnect Manifest from voice.")
async def leave(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    state = music_states[interaction.guild.id]
    state.queue.clear()
    state.current = None
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
    await interaction.response.send_message("👋 Left the voice channel.")


# ============================================================
# TICKETS
# ============================================================

@bot.tree.command(name="ticket", description="Create a private support ticket.")
async def ticket(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)

    existing = await db.fetchone(
        "SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status IN ('open','claimed','bot_assisted')",
        (guild.id, interaction.user.id),
    )
    if existing and guild.get_channel(existing["channel_id"]):
        return await interaction.response.send_message(
            f"You already have a ticket: <#{existing['channel_id']}>",
            ephemeral=True,
        )

    category_id = await setting(guild.id, "ticket_category_id", 0)
    category = guild.get_channel(category_id) if category_id else None
    support_role_id = await setting(guild.id, "ticket_support_role_id", 0)
    support_role = guild.get_role(support_role_id) if support_role_id else None

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        interaction.user: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            manage_channels=True,
            read_message_history=True,
        ),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(
            view_channel=True,
            send_messages=True,
            read_message_history=True,
        )

    channel = await guild.create_text_channel(
        name=f"ticket-{interaction.user.name[:20].lower()}",
        category=category if isinstance(category, discord.CategoryChannel) else None,
        overwrites=overwrites,
        reason="Manifest support ticket",
    )

    await db.execute(
        "INSERT OR REPLACE INTO tickets(channel_id,guild_id,user_id,claimed_by,status,created_at) VALUES(?,?,?,?,?,?)",
        (channel.id, guild.id, interaction.user.id, 0, "open", now()),
    )

    await channel.send(
        f"🎟️ Welcome {interaction.user.mention}. Staff can use `/claim_ticket`. "
        "If nobody claims this ticket within two minutes, Manifest AI will assist automatically."
    )
    await interaction.response.send_message(f"✅ Ticket created: {channel.mention}", ephemeral=True)


@bot.tree.command(name="claim_ticket", description="Claim the current ticket.")
async def claim_ticket(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)

    row = await db.fetchone(
        "SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')",
        (interaction.channel.id,),
    )
    if not row:
        return await interaction.response.send_message("This is not a tracked ticket.", ephemeral=True)

    if not isinstance(interaction.user, discord.Member) or not (
        interaction.user.guild_permissions.manage_channels or is_maker(interaction.user)
    ):
        return await interaction.response.send_message("You need ticket-staff permissions.", ephemeral=True)

    await db.execute(
        "UPDATE tickets SET claimed_by=?,status='claimed' WHERE channel_id=?",
        (interaction.user.id, interaction.channel.id),
    )
    await interaction.response.send_message(f"🙋 Ticket claimed by {interaction.user.mention}.")


@bot.tree.command(name="close_ticket", description="Close the current ticket.")
async def close_ticket(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)

    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=?", (interaction.channel.id,))
    if not row:
        return await interaction.response.send_message("This is not a tracked ticket.", ephemeral=True)

    if not isinstance(interaction.user, discord.Member):
        return
    if interaction.user.id != row["user_id"] and not (
        interaction.user.guild_permissions.manage_channels or is_maker(interaction.user)
    ):
        return await interaction.response.send_message("You cannot close this ticket.", ephemeral=True)

    await db.execute(
        "UPDATE tickets SET status='closed',closed_at=? WHERE channel_id=?",
        (now(), interaction.channel.id),
    )
    await interaction.response.send_message("🔒 Ticket closed. Deleting channel in 5 seconds.")
    await asyncio.sleep(5)
    try:
        await interaction.channel.delete(reason="Manifest ticket closed")
    except discord.HTTPException:
        pass


# ============================================================
# MODERATION
# ============================================================

@bot.tree.command(name="warn", description="Warn a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member.id == interaction.user.id:
        return await interaction.response.send_message("You cannot warn yourself.", ephemeral=True)

    await db.execute(
        "INSERT INTO warnings(guild_id,user_id,moderator_id,reason,created_at) VALUES(?,?,?,?,?)",
        (interaction.guild_id, member.id, interaction.user.id, reason[:500], now()),
    )
    await interaction.response.send_message(f"⚠️ Warned {member.mention}: `{reason}`")
    await log_to_channel(interaction.guild, f"⚠️ {interaction.user} warned {member} — {reason}")


@bot.tree.command(name="warnings", description="Show a member's warning count.")
@app_commands.checks.has_permissions(moderate_members=True)
async def warnings(interaction: discord.Interaction, member: discord.Member):
    rows = await db.fetchall(
        "SELECT reason,created_at FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC LIMIT 10",
        (interaction.guild_id, member.id),
    )
    if not rows:
        return await interaction.response.send_message(f"{member.mention} has no recorded warnings.")
    lines = [f"• <t:{int(r['created_at'])}:R> — {r['reason']}" for r in rows]
    await interaction.response.send_message(clamp_text("\n".join(lines)))


@bot.tree.command(name="timeout", description="Timeout a member.")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "Manifest moderation",
):
    if member.id == interaction.user.id or member.top_role >= interaction.user.top_role:
        return await interaction.response.send_message(
            "That member cannot be timed out by your current hierarchy.",
            ephemeral=True,
        )
    await member.timeout(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes), reason=reason)
    await interaction.response.send_message(f"⏳ Timed out {member.mention} for **{minutes} minutes**.")


@bot.tree.command(name="kick", description="Kick a member.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Manifest moderation"):
    if member.top_role >= interaction.user.top_role and not is_maker(interaction.user):
        return await interaction.response.send_message("Role hierarchy prevents this action.", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked **{member}** — `{reason}`")


@bot.tree.command(name="ban", description="Ban a member.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Manifest moderation"):
    if member.id == MAKER_USER_ID:
        return await interaction.response.send_message(
            "Maker protection: this account cannot be banned by Manifest.",
            ephemeral=True,
        )
    if member.top_role >= interaction.user.top_role and not is_maker(interaction.user):
        return await interaction.response.send_message("Role hierarchy prevents this action.", ephemeral=True)
    await member.ban(reason=reason, delete_message_seconds=0)
    await interaction.response.send_message(f"🔨 Banned **{member}** — `{reason}`")


@bot.tree.command(name="purge", description="Delete recent messages.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted **{len(deleted)}** messages.", ephemeral=True)


@bot.tree.command(name="lock", description="Lock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔒 Channel locked.")


@bot.tree.command(name="unlock", description="Unlock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel unlocked.")


@bot.tree.command(name="slowmode", description="Set channel slowmode.")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐢 Slowmode set to **{seconds}s**.")


# ============================================================
# ROLES / CHANNELS
# ============================================================

@bot.tree.command(name="role", description="Add or remove a role from a member.")
@app_commands.checks.has_permissions(manage_roles=True)
async def role(interaction: discord.Interaction, action: str, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message(
            "I cannot manage that role because of Discord's role hierarchy.",
            ephemeral=True,
        )
    if role.is_default() or role.managed:
        return await interaction.response.send_message("That role cannot be managed.", ephemeral=True)

    if action.casefold() == "add":
        await member.add_roles(role, reason=f"Manifest role command by {interaction.user}")
        await interaction.response.send_message(f"✅ Added {role.mention} to {member.mention}.")
    elif action.casefold() == "remove":
        await member.remove_roles(role, reason=f"Manifest role command by {interaction.user}")
        await interaction.response.send_message(f"✅ Removed {role.mention} from {member.mention}.")
    else:
        await interaction.response.send_message("Action must be `add` or `remove`.", ephemeral=True)


@bot.tree.command(name="create_channel", description="Create a text or voice channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_channel(interaction: discord.Interaction, name: str, kind: str = "text"):
    guild = interaction.guild
    if kind.casefold() == "voice":
        channel = await guild.create_voice_channel(name=name[:100])
    else:
        channel = await guild.create_text_channel(name=name[:100])
    await interaction.response.send_message(f"🏗️ Created {channel.mention}.")


# ============================================================
# REACTION ROLES
# ============================================================

@bot.tree.command(name="reactionrole_add", description="Attach a reaction emoji to a role on an existing message.")
@app_commands.checks.has_permissions(manage_roles=True)
async def reactionrole_add(interaction: discord.Interaction, message_id: str, emoji: str, role: discord.Role):
    if role.is_default() or role.managed or role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("I cannot manage that role because of Discord's role hierarchy.", ephemeral=True)
    try:
        mid = int(message_id)
        message = await interaction.channel.fetch_message(mid)
        await message.add_reaction(emoji)
    except Exception as exc:
        return await interaction.response.send_message(f"Couldn't access that message/emoji: `{clamp_text(str(exc), 400)}`", ephemeral=True)
    await db.execute(
        "INSERT OR REPLACE INTO reaction_roles(guild_id,channel_id,message_id,emoji,role_id) VALUES(?,?,?,?,?)",
        (interaction.guild_id, interaction.channel_id, mid, emoji, role.id),
    )
    await interaction.response.send_message(f"🎭 {emoji} now gives {role.mention} on message `{mid}`.", ephemeral=True)


@bot.tree.command(name="reactionrole_remove", description="Remove a reaction-role mapping.")
@app_commands.checks.has_permissions(manage_roles=True)
async def reactionrole_remove(interaction: discord.Interaction, message_id: str, emoji: str):
    await db.execute("DELETE FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?", (interaction.guild_id, int(message_id), emoji))
    await interaction.response.send_message("🎭 Reaction role mapping removed.", ephemeral=True)


@bot.tree.command(name="reactionroles", description="List reaction-role mappings in this server.")
async def reactionroles(interaction: discord.Interaction):
    rows = await db.fetchall("SELECT message_id,emoji,role_id FROM reaction_roles WHERE guild_id=? ORDER BY message_id", (interaction.guild_id,))
    if not rows:
        return await interaction.response.send_message("No reaction roles configured.", ephemeral=True)
    text = "\n".join(f"`{r['message_id']}` {r['emoji']} → <@&{r['role_id']}>" for r in rows[:30])
    await interaction.response.send_message(text, ephemeral=True)


# ============================================================
# AUTOPILOT / SETTINGS
# ============================================================

@bot.tree.command(name="autopilot", description="Configure Manifest server automation.")
@maker_only()
async def autopilot(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "autopilot", int(enabled))
    await interaction.response.send_message(
        f"⚡ Autopilot is now **{'ON' if enabled else 'OFF'}**. "
        "Discord permissions and role hierarchy still apply."
    )


@bot.tree.command(name="antinuke", description="Enable or disable audit-log anti-nuke monitoring.")
@maker_only()
async def antinuke(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "antinuke_enabled", int(enabled))
    await interaction.response.send_message(
        f"🛡️ Anti-nuke audit monitoring is now **{'ON' if enabled else 'OFF'}**."
    )


@bot.tree.command(name="ai_toggle", description="Enable or disable Manifest AI.")
@app_commands.checks.has_permissions(manage_guild=True)
async def ai_toggle(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "ai_enabled", int(enabled))
    await interaction.response.send_message(f"🤖 AI is now **{'ON' if enabled else 'OFF'}.")


@bot.tree.command(name="deadchat", description="Configure dead-chat revival.")
@app_commands.checks.has_permissions(manage_guild=True)
async def deadchat(
    interaction: discord.Interaction,
    enabled: bool,
    minutes: app_commands.Range[int, 5, 1440] = 30,
    role: Optional[discord.Role] = None,
):
    await set_setting(interaction.guild_id, "dead_chat_enabled", int(enabled))
    await set_setting(interaction.guild_id, "dead_chat_minutes", minutes)
    await set_setting(interaction.guild_id, "dead_chat_role_id", role.id if role else 0)
    await interaction.response.send_message(
        f"💬 Dead-chat revival: **{'ON' if enabled else 'OFF'}**, after **{minutes} minutes**."
    )


@bot.tree.command(name="setlog", description="Set the bot's audit/log channel.")
@app_commands.checks.has_permissions(manage_guild=True)
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_setting(interaction.guild_id, "log_channel_id", channel.id)
    await interaction.response.send_message(f"📋 Logs will be sent to {channel.mention}.")


@bot.tree.command(name="set_ticket_support", description="Set the ticket support role.")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_ticket_support(interaction: discord.Interaction, role: discord.Role):
    await set_setting(interaction.guild_id, "ticket_support_role_id", role.id)
    await interaction.response.send_message(f"🎟️ Ticket support role set to {role.mention}.")


@bot.tree.command(name="set_ticket_category", description="Set the ticket category.")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_ticket_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    await set_setting(interaction.guild_id, "ticket_category_id", category.id)
    await interaction.response.send_message(f"🎟️ Ticket category set to **{category.name}**.")


# ============================================================
# AUTOMOD
# ============================================================

@bot.tree.command(name="badword_add", description="Add a restricted word.")
@app_commands.checks.has_permissions(manage_guild=True)
async def badword_add(interaction: discord.Interaction, word: str):
    word = word.strip().casefold()[:50]
    if not word:
        return await interaction.response.send_message("Invalid word.", ephemeral=True)
    await db.execute(
        "INSERT OR IGNORE INTO banned_words(guild_id,word) VALUES(?,?)",
        (interaction.guild_id, word),
    )
    await interaction.response.send_message(f"🛡️ Added `{word}` to the server AutoMod list.")


@bot.tree.command(name="badword_remove", description="Remove a restricted word.")
@app_commands.checks.has_permissions(manage_guild=True)
async def badword_remove(interaction: discord.Interaction, word: str):
    await db.execute(
        "DELETE FROM banned_words WHERE guild_id=? AND word=?",
        (interaction.guild_id, word.strip().casefold()),
    )
    await interaction.response.send_message("🛡️ Restricted word removed.")


# ============================================================
# INVITES
# ============================================================

@bot.tree.command(name="invites", description="Show invite competition leaderboard.")
async def invites(interaction: discord.Interaction):
    rows = await db.fetchall(
        "SELECT inviter_id,uses FROM invite_tracker WHERE guild_id=? ORDER BY uses DESC LIMIT 10",
        (interaction.guild_id,),
    )
    if not rows:
        return await interaction.response.send_message("No tracked invite activity yet.")
    desc = "\n".join(
        f"**#{i}** <@{r['inviter_id']}> — `{r['uses']}` joins"
        for i, r in enumerate(rows, 1)
    )
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🏆 Invite Competition",
            description=desc,
            color=discord.Color.gold(),
        )
    )


# ============================================================
# ECONOMY
# ============================================================

async def ensure_wallet(guild_id: int, user_id: int):
    await db.execute(
        "INSERT OR IGNORE INTO economy(guild_id,user_id,wallet,bank) VALUES(?,?,100,500)",
        (guild_id, user_id),
    )


@bot.tree.command(name="balance", description="Show your wallet and bank.")
async def balance(interaction: discord.Interaction):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone(
        "SELECT wallet,bank FROM economy WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, interaction.user.id),
    )
    await interaction.response.send_message(
        f"🪙 Wallet: **{row['wallet']}** | 🏦 Bank: **{row['bank']}**"
    )


@bot.tree.command(name="beg", description="Earn a random amount of coins.")
async def beg(interaction: discord.Interaction):
    if not bot.cooldown(interaction.guild_id, interaction.user.id, "beg", 20):
        return await interaction.response.send_message(
            "⏳ Try again in a few seconds.",
            ephemeral=True,
        )
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    amount = random.randint(20, 150)
    await db.execute(
        "UPDATE economy SET wallet=wallet+? WHERE guild_id=? AND user_id=?",
        (amount, interaction.guild_id, interaction.user.id),
    )
    await interaction.response.send_message(f"🪙 You received **{amount}** coins.")


@bot.tree.command(name="daily", description="Claim a daily coin reward.")
async def daily(interaction: discord.Interaction):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone(
        "SELECT last_daily FROM economy WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, interaction.user.id),
    )
    if now() - row["last_daily"] < 86400:
        remaining = int(86400 - (now() - row["last_daily"]))
        return await interaction.response.send_message(
            f"⏳ Daily is on cooldown for another **{remaining // 3600}h {(remaining % 3600)//60}m**.",
            ephemeral=True,
        )

    amount = random.randint(500, 1000)
    await db.execute(
        "UPDATE economy SET wallet=wallet+?,last_daily=? WHERE guild_id=? AND user_id=?",
        (amount, now(), interaction.guild_id, interaction.user.id),
    )
    await interaction.response.send_message(f"🎁 Daily reward: **{amount}** coins.")


@bot.tree.command(name="deposit", description="Deposit coins into your bank.")
async def deposit(
    interaction: discord.Interaction,
    amount: app_commands.Range[int, 1, 1_000_000_000],
):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone(
        "SELECT wallet FROM economy WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, interaction.user.id),
    )
    if row["wallet"] < amount:
        return await interaction.response.send_message(
            "You don't have that much in your wallet.",
            ephemeral=True,
        )
    await db.execute(
        "UPDATE economy SET wallet=wallet-?,bank=bank+? WHERE guild_id=? AND user_id=?",
        (amount, amount, interaction.guild_id, interaction.user.id),
    )
    await interaction.response.send_message(f"🏦 Deposited **{amount}** coins.")


# ============================================================
# TAGS
# ============================================================

@bot.tree.command(name="tag_create", description="Create or replace a server tag.")
@app_commands.checks.has_permissions(manage_guild=True)
async def tag_create(interaction: discord.Interaction, name: str, content: str):
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower())[:32]
    await db.execute(
        """INSERT INTO tags(guild_id,name,content) VALUES(?,?,?)
           ON CONFLICT(guild_id,name) DO UPDATE SET content=excluded.content""",
        (interaction.guild_id, name, content[:1800]),
    )
    await interaction.response.send_message(f"🏷️ Tag `{name}` saved.")


@bot.tree.command(name="tag", description="Use a server tag.")
async def tag(interaction: discord.Interaction, name: str):
    row = await db.fetchone(
        "SELECT content FROM tags WHERE guild_id=? AND name=?",
        (interaction.guild_id, name.lower()),
    )
    if not row:
        return await interaction.response.send_message("Tag not found.", ephemeral=True)
    await interaction.response.send_message(row["content"])


@bot.tree.command(name="tag_delete", description="Delete a server tag.")
@app_commands.checks.has_permissions(manage_guild=True)
async def tag_delete(interaction: discord.Interaction, name: str):
    await db.execute(
        "DELETE FROM tags WHERE guild_id=? AND name=?",
        (interaction.guild_id, name.lower()),
    )
    await interaction.response.send_message("🏷️ Tag deleted.")


# ============================================================
# AFK / REMINDERS / POLLS
# ============================================================

@bot.tree.command(name="afk", description="Set your AFK status.")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    await db.execute(
        """INSERT INTO afk(guild_id,user_id,reason,created_at) VALUES(?,?,?,?)
           ON CONFLICT(guild_id,user_id) DO UPDATE SET reason=excluded.reason,created_at=excluded.created_at""",
        (interaction.guild_id, interaction.user.id, reason[:300], now()),
    )
    await interaction.response.send_message(f"💤 AFK enabled: **{reason[:300]}**")


@bot.tree.command(name="remind", description="Create a reminder in minutes.")
async def remind(
    interaction: discord.Interaction,
    minutes: app_commands.Range[int, 1, 10080],
    message: str,
):
    await db.execute(
        "INSERT INTO reminders(guild_id,user_id,channel_id,message,due_at) VALUES(?,?,?,?,?)",
        (
            interaction.guild_id,
            interaction.user.id,
            interaction.channel_id,
            message[:1000],
            now() + minutes * 60,
        ),
    )
    await interaction.response.send_message(
        f"⏰ Reminder set for **{minutes} minutes**.",
        ephemeral=True,
    )


@bot.tree.command(name="poll", description="Create a simple poll.")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(
        title="📊 Poll",
        description=question[:2000],
        color=discord.Color.blurple(),
    )
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message("Poll created.", ephemeral=True)


# ============================================================
# UTILITY / COMMUNITY COMMANDS
# ============================================================

@bot.tree.command(name="ping", description="Check Manifest latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong — `{round(bot.latency * 1000)}ms`", ephemeral=True)


@bot.tree.command(name="level", description="Show your or another member's XP level.")
async def level(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (interaction.guild_id, member.id))
    await interaction.response.send_message(f"📈 {member.mention}: **Level {row['level'] if row else 0}** • `{row['xp'] if row else 0} XP`", ephemeral=True)


@bot.tree.command(name="leaderboard", description="Show the server XP leaderboard.")
async def leaderboard(interaction: discord.Interaction):
    rows = await db.fetchall("SELECT user_id,xp,level FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (interaction.guild_id,))
    if not rows:
        return await interaction.response.send_message("No XP data yet.")
    text = "\n".join(f"**#{i}** <@{r['user_id']}> — Level {r['level']} ({r['xp']} XP)" for i,r in enumerate(rows,1))
    await interaction.response.send_message(embed=discord.Embed(title="🏆 XP Leaderboard", description=text, color=discord.Color.gold()))


@bot.tree.command(name="withdraw", description="Withdraw coins from your bank.")
async def withdraw(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 1_000_000]):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone("SELECT bank,wallet FROM economy WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id))
    if amount > row['bank']:
        return await interaction.response.send_message("You don't have that much in your bank.", ephemeral=True)
    await db.execute("UPDATE economy SET bank=bank-?,wallet=wallet+? WHERE guild_id=? AND user_id=?", (amount,amount,interaction.guild_id,interaction.user.id))
    await interaction.response.send_message(f"🏦 Withdrew **{amount:,}** coins.")


@bot.tree.command(name="transfer", description="Transfer coins to another member.")
async def transfer(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1, 1_000_000]):
    if member.id == interaction.user.id or member.bot:
        return await interaction.response.send_message("Choose another human member.", ephemeral=True)
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    await ensure_wallet(interaction.guild_id, member.id)
    row = await db.fetchone("SELECT wallet FROM economy WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id))
    if amount > row['wallet']:
        return await interaction.response.send_message("You don't have enough coins.", ephemeral=True)
    await db.execute("UPDATE economy SET wallet=wallet-? WHERE guild_id=? AND user_id=?", (amount,interaction.guild_id,interaction.user.id))
    await db.execute("UPDATE economy SET wallet=wallet+? WHERE guild_id=? AND user_id=?", (amount,interaction.guild_id,member.id))
    await interaction.response.send_message(f"💸 Sent **{amount:,}** coins to {member.mention}.")


@bot.tree.command(name="work", description="Work for a random coin reward.")
async def work(interaction: discord.Interaction):
    if not bot.cooldown(interaction.guild_id, interaction.user.id, "work", 300):
        return await interaction.response.send_message("⏳ You can work again in a few minutes.", ephemeral=True)
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    earned = random.randint(80, 250)
    await db.execute("UPDATE economy SET wallet=wallet+? WHERE guild_id=? AND user_id=?", (earned,interaction.guild_id,interaction.user.id))
    await interaction.response.send_message(f"💼 You worked and earned **{earned:,}** coins.")


@bot.tree.command(name="coinflip", description="Flip a coin.")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 **{random.choice(['Heads','Tails'])}**")


@bot.tree.command(name="roll", description="Roll a dice, such as 2d6 or 1d20.")
async def roll(interaction: discord.Interaction, dice: str = "1d20"):
    match = re.fullmatch(r"(\d{1,2})d(\d{1,4})", dice.lower().strip())
    if not match:
        return await interaction.response.send_message("Use a format like `2d6` or `1d20`.", ephemeral=True)
    count, sides = map(int, match.groups())
    if count > 20 or sides > 10000:
        return await interaction.response.send_message("Dice limit exceeded.", ephemeral=True)
    rolls = [random.randint(1,sides) for _ in range(count)]
    await interaction.response.send_message(f"🎲 `{dice}` → {rolls} = **{sum(rolls)}**")


@bot.tree.command(name="avatar", description="Show a member's avatar.")
async def avatar(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    await interaction.response.send_message(member.display_avatar.url)


@bot.tree.command(name="help", description="Show Manifest command categories.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="⚡ Manifest V8.0 Help", color=discord.Color.blurple())
    embed.add_field(name="🤖 AI & Memory", value="/ai /remember /memories /maker_memory /maker_rule_add /maker_rules /server_remember /remember_user", inline=False)
    embed.add_field(name="🎵 Music", value="/play /pause /resume /skip /stop /queue /nowplaying /shuffle /remove /clearqueue /volume /leave", inline=False)
    embed.add_field(name="🛡️ Moderation", value="/warn /warnings /timeout /kick /ban /purge /lock /unlock /slowmode /role /badword_add", inline=False)
    embed.add_field(name="🎟️ Tickets", value="/ticket /claim_ticket /close_ticket", inline=False)
    embed.add_field(name="🎭 Community", value="/tag /tag_create /reactionrole_add /reactionrole_remove /poll /afk /remind /invites", inline=False)
    embed.add_field(name="💰 Economy & XP", value="/balance /beg /daily /deposit /withdraw /transfer /work /level /leaderboard", inline=False)
    embed.add_field(name="👑 Maker", value="/maker /autopilot /antinuke /say /export_config", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# MAKER / SERVER CONTROL
# ============================================================

@bot.tree.command(name="maker", description="Show the configured Maker identity.")
@maker_only()
async def maker(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"👑 **Maker:** <@{MAKER_USER_ID}>\n"
        "Manifest recognizes the Maker by immutable Discord user ID. "
        "It does not rely on usernames, nicknames, or display names."
    )


@bot.tree.command(name="say", description="Send a message as the bot.")
@maker_only()
async def say(
    interaction: discord.Interaction,
    message: str,
    channel: Optional[discord.TextChannel] = None,
):
    target = channel or interaction.channel
    await target.send(message[:2000])
    await interaction.response.send_message("✅ Sent.", ephemeral=True)


@bot.tree.command(name="export_config", description="Export safe Manifest settings.")
@maker_only()
async def export_config(interaction: discord.Interaction):
    rows = await db.fetchone(
        "SELECT * FROM guild_settings WHERE guild_id=?",
        (interaction.guild_id,),
    )
    if not rows:
        return await interaction.response.send_message("No settings found.", ephemeral=True)
    data = dict(rows)
    await interaction.response.send_message(
        f"```json\n{json.dumps(data, indent=2, default=str)[:1800]}\n```",
        ephemeral=True,
    )


# ============================================================
# GLOBAL ERROR HANDLER
# ============================================================

@bot.tree.error
async def on_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
):
    if isinstance(error, app_commands.errors.MissingPermissions):
        message = "⚠️ You don't have the required Discord permission."
    elif isinstance(error, app_commands.CheckFailure):
        message = "⚠️ You are not authorized to use this command."
    elif isinstance(error, app_commands.errors.CommandOnCooldown):
        message = "⏳ This command is on cooldown."
    else:
        log.exception("Slash command error", exc_info=error)
        message = "⚠️ Something went wrong while executing that command."

    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass


# ============================================================
# HEALTH WEB SERVER
# ============================================================

async def health(request: web.Request):
    return web.json_response({
        "status": "online",
        "service": "Manifest V8.0",
        "maker_id": MAKER_USER_ID,
        "guilds": len(bot.guilds),
        "ai_configured": bool(groq),
        "time": int(time.time()),
    })


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    log.info("Health server listening on port %s", PORT)
    return runner


# ============================================================
# MAIN
# ============================================================

async def main():
    runner = await start_web_server()
    try:
        async with bot:
            await bot.start(TOKEN)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
