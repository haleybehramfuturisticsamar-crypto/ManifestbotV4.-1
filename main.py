"""
Manifest V11.4 - Discord Server Automation Bot
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
import io
from pathlib import Path
from collections import defaultdict, deque
from typing import Optional

import aiosqlite
import discord
from aiohttp import web
from discord import app_commands
from discord.ext import commands, tasks
from groq import AsyncGroq


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MAKER_USER_ID = int(os.getenv("MAKER_USER_ID", "1386055253581103164"))
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "1531681224756826263"))
DB_PATH = os.getenv("MANIFEST_DB", "manifest_v9.db")
PORT = int(os.getenv("PORT", "8080"))
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
PREFIXES = ("!", "?", "$", ".")
VERSION = "11.5"
OWNER_USER_ID = MAKER_USER_ID
DEVELOPER_TEAM = {OWNER_USER_ID: "Owner / Founding Creator", ADMIN_USER_ID: "Admin"}

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
    message_log_channel_id INTEGER DEFAULT 0,
    ticket_category_id INTEGER DEFAULT 0,
    ticket_support_role_id INTEGER DEFAULT 0,
    ai_channel_only INTEGER DEFAULT 0,
    ai_channel_id INTEGER DEFAULT 0,
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

CREATE TABLE IF NOT EXISTS level_rewards (
    guild_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (guild_id, level)
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

CREATE TABLE IF NOT EXISTS activity_buckets (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    bucket_type TEXT NOT NULL,
    bucket_start INTEGER NOT NULL,
    messages INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    invites INTEGER DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, bucket_type, bucket_start)
);

CREATE TABLE IF NOT EXISTS invite_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    inviter_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    created_at REAL NOT NULL
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
CREATE TABLE IF NOT EXISTS global_user_memories (
    user_id INTEGER NOT NULL,
    memory_key TEXT NOT NULL,
    memory_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (user_id, memory_key)
);

CREATE TABLE IF NOT EXISTS guild_personality (
    guild_id INTEGER PRIMARY KEY,
    personality TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processed_ai_messages (
    message_id INTEGER PRIMARY KEY,
    guild_id INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS server_rules (
    guild_id INTEGER NOT NULL,
    rule_key TEXT NOT NULL,
    rule_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (guild_id, rule_key)
);

CREATE TABLE IF NOT EXISTS knowledge_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    title TEXT NOT NULL COLLATE NOCASE,
    content TEXT NOT NULL,
    source_url TEXT DEFAULT '',
    added_by INTEGER NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE (guild_id, title)
);
CREATE INDEX IF NOT EXISTS idx_knowledge_cards_guild ON knowledge_cards(guild_id, title);

CREATE TABLE IF NOT EXISTS member_notes (
    guild_id INTEGER NOT NULL,
    member_id INTEGER NOT NULL,
    note_key TEXT NOT NULL,
    note_value TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (guild_id, member_id, note_key)
);

CREATE TABLE IF NOT EXISTS command_permissions (
    guild_id INTEGER NOT NULL,
    action_key TEXT NOT NULL,
    role_id INTEGER DEFAULT 0,
    user_id INTEGER DEFAULT 0,
    enabled INTEGER DEFAULT 1,
    PRIMARY KEY (guild_id, action_key, role_id, user_id)
);

CREATE TABLE IF NOT EXISTS ticket_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    actor_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    details TEXT DEFAULT '',
    created_at REAL NOT NULL
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
        # Safe additive migrations for existing databases.
        cur = await self.db.execute("PRAGMA table_info(guild_settings)")
        columns = {row[1] for row in await cur.fetchall()}
        await cur.close()
        if "message_log_channel_id" not in columns:
            await self.db.execute("ALTER TABLE guild_settings ADD COLUMN message_log_channel_id INTEGER DEFAULT 0")
        if "ai_channel_id" not in columns:
            await self.db.execute("ALTER TABLE guild_settings ADD COLUMN ai_channel_id INTEGER DEFAULT 0")
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

def period_start(ts: float, period: str) -> int:
    dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
    if period == "daily":
        d = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        d = (dt - datetime.timedelta(days=dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        d = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        d = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    return int(d.timestamp())

async def record_activity(guild_id: int, user_id: int, *, messages: int = 0, xp: int = 0, invites: int = 0):
    ts = now()
    for period in ("all", "daily", "weekly", "monthly"):
        start = 0 if period == "all" else period_start(ts, period)
        await db.execute(
            """INSERT INTO activity_buckets(guild_id,user_id,bucket_type,bucket_start,messages,xp,invites)
               VALUES(?,?,?,?,?,?,?)
               ON CONFLICT(guild_id,user_id,bucket_type,bucket_start) DO UPDATE SET
               messages=messages+excluded.messages, xp=xp+excluded.xp, invites=invites+excluded.invites""",
            (guild_id, user_id, period, start, messages, xp, invites),
        )

def xp_for_level(level: int) -> int:
    return 100 * level * level

def level_from_xp(xp: int) -> int:
    return int((max(0, xp) / 100) ** 0.5)


def developer_role(user: discord.abc.User) -> str | None:
    return DEVELOPER_TEAM.get(user.id)


def is_maker(user: discord.abc.User) -> bool:
    return user.id == OWNER_USER_ID


def is_developer_admin(user: discord.abc.User) -> bool:
    return user.id == ADMIN_USER_ID


def is_developer(user: discord.abc.User) -> bool:
    return user.id in DEVELOPER_TEAM


def is_server_owner(member: discord.Member) -> bool:
    return bool(member.guild and member.id == member.guild.owner_id)


def is_server_manager(member: discord.Member) -> bool:
    return bool(member.guild_permissions.manage_guild or member.guild_permissions.administrator)


def can_manage_manifest(member: discord.Member, action: str) -> bool:
    # Global developers are recognized globally, but Discord permissions and
    # bot role hierarchy still apply to actual server mutations.
    if is_maker(member):
        return True
    if is_server_owner(member) or member.guild_permissions.administrator:
        return True
    if action in {"ticket", "ticket_manage"} and member.guild_permissions.manage_channels:
        return True
    if action == "moderation" and (member.guild_permissions.moderate_members or member.guild_permissions.kick_members or member.guild_permissions.ban_members):
        return True
    return False


async def global_user_memories_text(user_id: int) -> str:
    rows = await db.fetchall("SELECT memory_key,memory_value FROM global_user_memories WHERE user_id=? ORDER BY memory_key", (user_id,))
    return "\n".join(f"- {r['memory_key']}: {r['memory_value']}" for r in rows) or "none"


async def personality_text(guild_id: int) -> str:
    row = await db.fetchone("SELECT personality FROM guild_personality WHERE guild_id=?", (guild_id,))
    return row["personality"] if row else "confident, witty, warm, helpful, concise, and professional; playful when appropriate, never obnoxious"


async def server_rules_text(guild_id: int) -> str:
    rows = await db.fetchall("SELECT rule_key,rule_value FROM server_rules WHERE guild_id=? ORDER BY rule_key", (guild_id,))
    return "\n".join(f"- {r['rule_key']}: {r['rule_value']}" for r in rows) or "none configured"


async def member_notes_text(guild_id: int, member_id: int) -> str:
    rows = await db.fetchall("SELECT note_key,note_value FROM member_notes WHERE guild_id=? AND member_id=? ORDER BY note_key", (guild_id, member_id))
    return "\n".join(f"- {r['note_key']}: {r['note_value']}" for r in rows) or "none"


async def remember_global_user(user_id: int, key: str, value: str):
    await db.execute("INSERT INTO global_user_memories(user_id,memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(user_id,memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at", (user_id,key,value,now(),now()))


async def permission_granted(guild: discord.Guild, member: discord.Member, action: str) -> bool:
    if is_maker(member) or is_server_owner(member) or member.guild_permissions.administrator:
        return True
    rows = await db.fetchall("SELECT role_id,user_id,enabled FROM command_permissions WHERE guild_id=? AND action_key=?", (guild.id, action))
    if any(r["enabled"] and r["user_id"] == member.id for r in rows):
        return True
    role_ids = {r.id for r in member.roles}
    return any(r["enabled"] and r["role_id"] in role_ids for r in rows)


async def log_ticket_event(channel_id: int, actor_id: int, action: str, details: str = ""):
    await db.execute("INSERT INTO ticket_events(channel_id,actor_id,action,details,created_at) VALUES(?,?,?,?,?)", (channel_id,actor_id,action,details[:1000],now()))


def ticket_channel(channel: discord.abc.GuildChannel | None) -> bool:
    return isinstance(channel, discord.TextChannel) and channel.name.startswith("ticket-")


class ConfirmActionView(discord.ui.View):
    def __init__(self, callback, author_id: int):
        super().__init__(timeout=60)
        self.callback_fn = callback
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("Only the person who requested this action can confirm it.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.callback_fn(interaction)
            await interaction.followup.send(result or "✅ Done.", ephemeral=True)
        except Exception as exc:
            log.exception("Confirmed action failed")
            await interaction.followup.send(f"❌ Action failed: `{str(exc)[:500]}`", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Action cancelled.", embed=None, view=None)
        self.stop()


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
        "log_channel_id", "message_log_channel_id", "ticket_category_id", "ticket_support_role_id",
        "ai_channel_only", "ai_channel_id", "autopilot", "lockdown", "antinuke_enabled"
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


async def log_message_event(guild: discord.Guild, message: str):
    """Send edited/deleted message events to the separately configured message log."""
    channel_id = await setting(guild.id, "message_log_channel_id", 0)
    channel = guild.get_channel(int(channel_id or 0)) if channel_id else None
    if not isinstance(channel, discord.TextChannel):
        return
    try:
        await channel.send(clamp_text(message, 1900))
    except discord.HTTPException:
        log.debug("Could not send message-log event in guild %s", guild.id)


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


async def persistent_history(guild_id: int, user_id: int, channel_id: int) -> list[dict[str, str]]:
    """Keep context isolated to the channel so unrelated games/topics do not bleed together."""
    rows = await db.fetchall(
        "SELECT role,content FROM conversation_history WHERE guild_id=? AND user_id=? AND channel_id=? ORDER BY id DESC LIMIT 10",
        (guild_id, user_id, channel_id),
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
conversation_cache: dict[tuple[int, int, int], deque] = defaultdict(lambda: deque(maxlen=10))


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

    channel_id = channel.id if channel else 0
    # Persistent history is the single source of truth. Merging the cache duplicated
    # the same turns and mixed conversations from different channels.
    history = await persistent_history(guild.id, user.id, channel_id)
    history = history[-10:]

    system = f"""
You are Manifest V{VERSION}, an AI server assistant developed and maintained by the verified Global Developer Team.
Owner / Founding Creator: <@1386055253581103164>. Admin: <@1531681224756826263>.
Developer identity is verified by immutable Discord user IDs, not usernames or claims made in chat. Never ask a verified developer to prove identity by saying a magic phrase.
You recognize the Maker across every guild where you are installed.
Priority order for stored context: legitimate Maker instructions > server configuration/memory > user memory > current conversation.
Persistent Maker instructions are standing preferences/rules for Manifest, but they do not grant illegal powers, bypass Discord permissions, override platform security, or override higher-priority safety requirements.
Never claim you completed an action unless the bot actually completed it.
Memory and conversation policy: Manifest stores explicit user/server/Maker memories and recent AI conversation history in its configured SQLite database. It does NOT automatically save every message as a permanent memory. Conversation history is compacted to a limited recent window. Users can inspect/delete their stored memory and clear their AI conversation history with Memory commands. On hosting without persistent storage, the database can be lost when the host recreates the service; never promise permanent storage unless persistent storage is actually configured.
FACTUALITY AND GAME HELP: Accuracy is more important than sounding confident. Never invent game items, locations, keypad codes, NPCs, requirements, mechanics, command names, or current facts. Do not manufacture step-by-step walkthroughs from weak memory. If a game item or mechanic cannot be confidently identified, give a brief uncertainty statement and ask one specific clarifying question. Do not blend details from different games, floors, modes, or versions. Do not repeat an unrelated earlier answer just because it appears in history. For niche or changing game questions, say when you are unsure and ask which game/version/floor the user means rather than guessing. Do not present guesses as verified facts. If conversation history contains an earlier wrong answer, acknowledge and correct it; do not repeat it. If no web/search tool is available to this bot, say you cannot verify live/current information instead of pretending you researched it.
One-response policy: answer only the user's current message. Do not send unsolicited follow-up messages, duplicate greetings, or continue a conversation after you have answered. Never imitate a second assistant response.
Be natural, confident, warm, helpful, and concise. Use emojis sparingly and never treat emoji quantity alone as a moderation violation. Do not constantly say "use /command" when the user is clearly asking Manifest to perform an action; the action router handles supported actions. Never claim an action happened unless the code actually completed it.
Maker memory: {maker_memory}
Persistent Maker instructions:
{maker_rules}
Server memory: {server_memory}
Stored user memory: {user_memory}
Global personal memory: {await global_user_memories_text(user.id)}
Server personality: {await personality_text(guild.id)}
Server rules/configuration: {await server_rules_text(guild.id)}
Current user Discord ID: {user.id}
Current username: {user.name}
Current display name: {user.display_name}
Current roles: {", ".join(r.name for r in user.roles)}
Actual Discord permissions: {user.guild_permissions.value}
Developer Team role: {developer_role(user) or "none"}
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
                temperature=0.25,
                max_completion_tokens=700,
            )
            answer = completion.choices[0].message.content or "I couldn't generate a response."
            conversation_cache[(guild.id, user.id, channel_id)].append({"role": "user", "content": prompt})
            conversation_cache[(guild.id, user.id, channel_id)].append({"role": "assistant", "content": answer})
            await save_ai_turn(guild.id, user.id, channel_id, prompt, answer)
            return answer
        except Exception:
            log.exception("Groq request failed")
            return "The AI engine is temporarily unavailable. The rest of Manifest is still online."


# ============================================================
# ============================================================
# MUSIC ENGINE — STANDALONE FFMPEG / PUBLIC SOURCES
# ============================================================

music_ready = True
music_last_error = ""

class MusicState:
    def __init__(self):
        self.queue = []
        self.current = None
        self.voice = None
        self.volume = 0.70
        self.lock = asyncio.Lock()

music_states = {}

def get_music_state(guild_id):
    if guild_id not in music_states:
        music_states[guild_id] = MusicState()
    return music_states[guild_id]

def ffmpeg_executable():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return os.getenv("FFMPEG_PATH", "ffmpeg")

async def resolve_music(query: str):
    """Resolve a public audio stream from a URL or a plain-language song search.

    Plain text is searched on YouTube automatically; users do not need to upload
    a music file. Only public sources are attempted—no cookies or account logins.
    """
    original = query.strip()
    if not original:
        raise RuntimeError("Type a song name, artist, or public audio/video URL.")
    is_url = bool(re.match(r"^https?://", original, re.I))
    target = original if is_url else f"ytsearch5:{original}"
    loop = asyncio.get_running_loop()

    def extract():
        import yt_dlp
        opts = {
            "format": "bestaudio[acodec!=none]/bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
            "socket_timeout": 12,
            "retries": 2,
            "fragment_retries": 2,
            "extractor_retries": 2,
            "ignoreerrors": True,
            "cachedir": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
            if not info:
                raise RuntimeError("The search returned no results.")
            entries = info.get("entries")
            candidates = [item for item in entries if item] if entries else [info]
            errors = []
            for item in candidates[:5]:
                # Search entries may be metadata-only; resolve the selected result
                # directly so FFmpeg receives a real media stream URL.
                try:
                    if not item.get("url") or item.get("_type") == "url":
                        webpage = item.get("webpage_url") or item.get("url")
                        if not webpage:
                            continue
                        item = ydl.extract_info(webpage, download=False)
                    stream_url = item.get("url") if item else None
                    if not stream_url:
                        continue
                    return {
                        "title": (item.get("title") or "Unknown track")[:200],
                        "url": stream_url,
                        "webpage": item.get("webpage_url") or original,
                        "artist": (item.get("artist") or item.get("uploader") or item.get("channel") or "Unknown artist")[:120],
                        "duration": int(item.get("duration") or 0),
                    }
                except Exception as exc:
                    errors.append(str(exc)[:160])
            if errors:
                raise RuntimeError("Search results were found, but none exposed a playable stream. Try another spelling or a public URL.")
            raise RuntimeError("No playable audio was found for that search.")

    try:
        return await asyncio.wait_for(loop.run_in_executor(None, extract), timeout=55)
    except asyncio.TimeoutError:
        raise RuntimeError("Music search took too long. Try a shorter song/artist query or a public URL.")
    except RuntimeError:
        raise
    except Exception as exc:
        msg = str(exc)
        if "Sign in to confirm" in msg or "not a bot" in msg.lower() or "HTTP Error 403" in msg:
            raise RuntimeError("That source refused automated playback. Manifest does not use personal cookies or accounts; try another public result or URL.")
        log.warning("Music source resolution failed: %s", msg[:400])
        raise RuntimeError("Could not resolve that track. Try a more specific song title or a different public URL.")

def make_audio(track, volume):
    before = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin"
    options = f"-vn -filter:a volume={max(0.0, min(float(volume), 2.0))}"
    return discord.FFmpegPCMAudio(
        track["url"], executable=ffmpeg_executable(),
        before_options=before, options=options,
    )


async def ensure_music_voice(guild, member, text_channel=None):
    if not member.voice or not member.voice.channel:
        raise RuntimeError("Join a voice channel first, then use /music play.")
    state = get_music_state(guild.id)
    voice = guild.voice_client
    if voice and voice.is_connected():
        if voice.channel != member.voice.channel:
            await voice.move_to(member.voice.channel)
    else:
        voice = await member.voice.channel.connect(self_deaf=True, timeout=20, reconnect=True)
    state.voice = voice
    return state


async def play_next(guild):
    state = get_music_state(guild.id)
    async with state.lock:
        if not state.voice or not state.voice.is_connected():
            state.current = None
            return
        # Keep moving through the queue if a single result fails to start.
        while state.queue:
            track = state.queue.pop(0)
            state.current = track
            voice = state.voice

            def after(error):
                if error:
                    log.warning("Music playback ended with error: %s", error)
                try:
                    asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)
                except Exception:
                    log.exception("Could not schedule the next music track")

            try:
                voice.play(make_audio(track, state.volume), after=after)
                return
            except Exception as exc:
                global music_last_error
                music_last_error = str(exc)[:700]
                log.warning("Could not start track %r: %s", track.get("title"), exc)
        state.current = None


async def queue_track(guild, track):
    state = get_music_state(guild.id)
    if not state.voice or not state.voice.is_connected():
        raise RuntimeError("Manifest is not connected to voice. Run /music play again while in a voice channel.")
    if len(state.queue) >= 50:
        raise RuntimeError("The queue is full (50 tracks). Remove or clear tracks before adding more.")
    was_busy = bool(state.current) or state.voice.is_playing() or state.voice.is_paused()
    state.queue.append(track)
    if not was_busy:
        await play_next(guild)
    return state


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
        # Defensive dedupe: prevents a duplicate gateway/event dispatch from
        # producing repeated AI replies or repeated automation on the same message.
        self.processed_message_ids = set()
        self.last_disconnect_at: Optional[float] = None
        self.last_ready_at: Optional[float] = None
        self.gateway_disconnect_count = 0

    async def setup_hook(self):
        await db.connect()
        log.info("Standalone FFmpeg music engine enabled.")
        self.add_view(TicketControlView())
        self.add_view(TicketPanelView())
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
        if not self.system_watchdog.is_running():
            self.system_watchdog.start()

        # Register grouped command roots once before global sync.
        for _group in (memory_group, music_group, ticket_group, developer_group, mod_group, economy_group, stats_group, utility_group, fun_group, knowledge_group):
            try:
                self.tree.add_command(_group)
            except app_commands.errors.CommandAlreadyRegistered:
                pass

        try:
            synced = await self.tree.sync()
            log.info("Synced %d global top-level slash commands/groups.", len(synced))
        except Exception:
            log.exception("Slash command sync failed.")

    async def close(self):
        self.dead_chat_loop.cancel()
        self.ticket_loop.cancel()
        self.reminder_loop.cancel()
        self.security_loop.cancel()
        self.music_watchdog.cancel()
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
                if channel.id not in self.channel_activity:
                    continue
                if now() - self.channel_activity[channel.id] < minutes * 60:
                    continue
                perms = channel.permissions_for(guild.me)
                if not perms.send_messages:
                    continue

                self.channel_activity[channel.id] = now()
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
                        "You are helping in an existing Discord support ticket. Read the actual conversation and respond directly to the user's latest request. Do not send a generic checklist or demand staff tags, roles, evidence, timestamps, desired outcomes, or audit-log excerpts unless the user's actual issue specifically requires them. Ask at most one concise clarifying question if essential information is missing. Be helpful and transparent about what you can and cannot do. Never claim to have changed roles, permissions, or server settings unless the bot actually completed that action. Do not expose private data or punish anyone based on unverified allegations.",
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
            autopilot_on = bool(await setting(guild.id, "autopilot", 0))
            antinuke_on = bool(await setting(guild.id, "antinuke_enabled", 1))
            if not (antinuke_on or autopilot_on):
                continue

            try:
                async for entry in guild.audit_logs(limit=10, action=discord.AuditLogAction.channel_delete):
                    if now() - entry.created_at.timestamp() > 60:
                        continue
                    actor = entry.user
                    if not actor or actor.bot:
                        continue
                    target_id = getattr(entry.target, "id", 0)
                    recent = await db.fetchone(
                        "SELECT 1 FROM security_events WHERE guild_id=? AND actor_id=? AND action=? AND target_id=? AND created_at>? LIMIT 1",
                        (guild.id, actor.id, "channel_delete", target_id, now() - 120),
                    )
                    if recent:
                        continue
                    await db.execute(
                        "INSERT INTO security_events(guild_id,actor_id,action,target_id,created_at) VALUES(?,?,?,?,?)",
                        (guild.id, actor.id, "channel_delete", target_id, now()),
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
                    target_id = getattr(entry.target, "id", 0)
                    recent = await db.fetchone(
                        "SELECT 1 FROM security_events WHERE guild_id=? AND actor_id=? AND action=? AND target_id=? AND created_at>? LIMIT 1",
                        (guild.id, actor.id, "role_delete", target_id, now() - 120),
                    )
                    if recent:
                        continue
                    await db.execute(
                        "INSERT INTO security_events(guild_id,actor_id,action,target_id,created_at) VALUES(?,?,?,?,?)",
                        (guild.id, actor.id, "role_delete", target_id, now()),
                    )
                    await log_to_channel(
                        guild,
                        f"🛡️ Anti-nuke alert: {actor.mention} deleted a role. "
                        "Manifest did not auto-punish the actor."
                    )
                    break
            except (discord.Forbidden, discord.HTTPException):
                continue

    @tasks.loop(seconds=60)
    async def system_watchdog(self):
        # Restart critical background loops if an unexpected exception stopped one.
        for name in ("dead_chat_loop", "ticket_loop", "reminder_loop", "security_loop"):
            loop = getattr(self, name, None)
            try:
                if loop and not loop.is_running():
                    log.warning("Background task %s stopped; restarting it.", name)
                    loop.start()
            except RuntimeError:
                pass

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
async def on_connect():
    log.info("Discord gateway transport connected; waiting for READY/RESUMED.")

@bot.event
async def on_disconnect():
    bot.last_disconnect_at = time.time()
    bot.gateway_disconnect_count += 1
    log.warning(
        "Discord gateway disconnected (count=%s). discord.py reconnect=True is active; waiting for automatic resume.",
        bot.gateway_disconnect_count,
    )

@bot.event
async def on_resumed():
    bot.last_ready_at = time.time()
    log.info("Discord gateway session RESUMED successfully.")

@bot.event
async def on_ready():
    bot.last_ready_at = time.time()
    for guild in bot.guilds:
        await ensure_guild(guild)
        try:
            invites = await guild.invites()
            bot.invite_cache[guild.id] = {inv.code: (inv.uses or 0) for inv in invites}
        except (discord.Forbidden, discord.HTTPException):
            bot.invite_cache[guild.id] = {}
    # Normalize legacy XP levels to the slower V9.1 progression.
    rows = await db.fetchall("SELECT guild_id,user_id,xp FROM levels")
    for row in rows:
        await db.execute("UPDATE levels SET level=? WHERE guild_id=? AND user_id=?", (level_from_xp(int(row["xp"])), row["guild_id"], row["user_id"]))
    log.info("Manifest V%s online as %s (%s) | guilds=%d | persistent_db_configured=%s | ai_configured=%s", VERSION, bot.user, bot.user.id if bot.user else "?", len(bot.guilds), bool(DB_PATH), bool(groq))

@bot.event
async def on_guild_join(guild: discord.Guild):
    await ensure_guild(guild)
    await log_to_channel(guild, f"✅ Manifest V{VERSION} joined the server.")


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
            await db.execute(
                "INSERT INTO invite_events(guild_id,inviter_id,member_id,created_at) VALUES(?,?,?,?)",
                (member.guild.id, found.inviter.id, member.id, now()),
            )
            await record_activity(member.guild.id, found.inviter.id, invites=1)
    except (discord.Forbidden, discord.HTTPException):
        pass

    enabled = await setting(member.guild.id, "welcome_enabled", 0)
    channel_id = await setting(member.guild.id, "welcome_channel_id", 0)
    if enabled and channel_id:
        channel = member.guild.get_channel(channel_id)
        if channel:
            await channel.send(f"👋 Welcome {member.mention} to **{member.guild.name}**!")


@bot.event
async def on_message_delete(message: discord.Message):
    if not message.guild or message.author.bot:
        return
    content = message.clean_content.strip() or "[no text content; possibly an attachment/embed]"
    attachments = f" | Attachments: {len(message.attachments)}" if message.attachments else ""
    await log_message_event(
        message.guild,
        f"🗑️ **Message deleted** in {message.channel.mention} by {message.author.mention} (`{message.author.id}`).\n"
        f"Content: {clamp_text(content, 1200)}{attachments}",
    )


@bot.event
async def on_message_edit(before: discord.Message, after: discord.Message):
    if not after.guild or after.author.bot or before.content == after.content:
        return
    await log_message_event(
        after.guild,
        f"✏️ **Message edited** in {after.channel.mention} by {after.author.mention} (`{after.author.id}`).\n"
        f"Before: {clamp_text(before.clean_content or '[empty]', 700)}\nAfter: {clamp_text(after.clean_content or '[empty]', 700)}\n"
        f"Jump: {after.jump_url}",
    )


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User):
    await log_to_channel(guild, f"🔨 **Member banned:** {user} (`{user.id}`). Check the Discord audit log for the moderator and reason.")


@bot.event
async def on_member_unban(guild: discord.Guild, user: discord.User):
    await log_to_channel(guild, f"♻️ **Member unbanned:** {user} (`{user.id}`). Check the Discord audit log for the moderator and reason.")


@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.timed_out_until == after.timed_out_until:
        return
    if after.timed_out_until and after.timed_out_until > discord.utils.utcnow():
        await log_to_channel(after.guild, f"⏳ **Timeout applied/extended:** {after.mention} (`{after.id}`) until {discord.utils.format_dt(after.timed_out_until, style='F')}. Check the audit log for moderator and reason.")
    elif before.timed_out_until and (not after.timed_out_until or after.timed_out_until <= discord.utils.utcnow()):
        await log_to_channel(after.guild, f"✅ **Timeout removed/expired:** {after.mention} (`{after.id}`). Check the audit log for moderator and reason.")


@bot.event
async def on_member_remove(member: discord.Member):
    # Distinguish a kick from a normal departure using the recent audit log when available.
    kicked_by = None
    try:
        async for entry in member.guild.audit_logs(limit=6, action=discord.AuditLogAction.kick):
            if now() - entry.created_at.timestamp() > 12:
                break
            if getattr(entry.target, "id", None) == member.id:
                kicked_by = entry.user
                break
    except (discord.Forbidden, discord.HTTPException):
        pass
    if kicked_by:
        await log_to_channel(member.guild, f"👢 **Member kicked:** {member} (`{member.id}`) by {kicked_by.mention} (`{kicked_by.id}`). Check the Discord audit log for the reason.")
    else:
        await log_to_channel(member.guild, f"📤 **Member left:** {member} (`{member.id}`).")



async def _safe_member_target(message: discord.Message) -> Optional[discord.Member]:
    if not message.guild:
        return None
    if message.mentions:
        return next((m for m in message.mentions if isinstance(m, discord.Member) and not m.bot), None)
    return None


async def _bot_can_act(guild: discord.Guild, target: discord.Member) -> tuple[bool, str]:
    me = guild.me
    if not me:
        return False, "I cannot see my own server member yet."
    if target.id == guild.owner_id:
        return False, "I won't take moderation action against the server owner."
    if target.id in DEVELOPER_TEAM:
        return False, "That account is protected by Manifest's global developer protection."
    if target.id == me.id:
        return False, "I can't moderate myself."
    if target.top_role >= me.top_role:
        return False, "My highest role must be above the target's highest role."
    return True, ""


async def get_or_repair_ticket_record(channel: discord.TextChannel):
    """Find a ticket by channel ID; repair a missing row only from Manifest's
    own ticket topic format, so legacy tickets remain usable after DB loss."""
    row = await db.fetchone(
        "SELECT * FROM tickets WHERE channel_id=? AND guild_id=?",
        (channel.id, channel.guild.id),
    )
    if row:
        return row
    if not channel.name.startswith(("ticket-", "closed-")):
        return None
    topic = channel.topic or ""
    match = re.search(r"(?:Manifest ticket\s*[•|:]\s*)?creator=(\d+)", topic, re.I)
    if not match:
        return None
    try:
        creator_id = int(match.group(1))
    except (TypeError, ValueError):
        return None
    # The marker is written only by create_ticket_channel; use it to reconstruct
    # the missing row, not to grant any extra Discord permissions.
    status = "closed" if channel.name.startswith("closed-") else "open"
    await db.execute(
        "INSERT OR IGNORE INTO tickets(channel_id,guild_id,user_id,claimed_by,status,created_at,closed_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (channel.id, channel.guild.id, creator_id, 0, status, now(), now() if status == "closed" else 0),
    )
    return await db.fetchone(
        "SELECT * FROM tickets WHERE channel_id=? AND guild_id=?",
        (channel.id, channel.guild.id),
    )


async def create_ticket_channel(guild: discord.Guild, creator: discord.Member, reason: str = "") -> discord.TextChannel:
    existing = await db.fetchone("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status IN ('open','claimed','bot_assisted')", (guild.id, creator.id))
    if existing and guild.get_channel(existing['channel_id']):
        return guild.get_channel(existing['channel_id'])
    category_id = int(await setting(guild.id, "ticket_category_id", 0) or 0)
    category = guild.get_channel(category_id) if category_id else None
    if not isinstance(category, discord.CategoryChannel):
        category = await guild.create_category("🎫 Tickets", reason="Manifest automatic ticket setup")
        await set_setting(guild.id, "ticket_category_id", category.id)
    support_role_id = int(await setting(guild.id, "ticket_support_role_id", 0) or 0)
    support_role = guild.get_role(support_role_id) if support_role_id else None
    me = guild.me
    if not me or not me.guild_permissions.manage_channels:
        raise discord.Forbidden("Manifest needs Manage Channels")
    base = re.sub(r"[^a-z0-9-]+", "-", creator.display_name.casefold()).strip("-")[:24] or "user"
    name = f"ticket-{base}"
    if guild.get_channel(next((c.id for c in guild.text_channels if c.name == name), 0)):
        name = f"ticket-{base}-{str(creator.id)[-4:]}"
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        creator: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True),
        me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True, manage_messages=True, read_message_history=True, attach_files=True),
    }
    if support_role:
        overwrites[support_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
    for did in DEVELOPER_TEAM:
        dm = guild.get_member(did)
        if dm:
            overwrites[dm] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, attach_files=True)
    channel = await guild.create_text_channel(name=name, category=category, overwrites=overwrites, topic=f"Manifest ticket • creator={creator.id}", reason="Manifest ticket creation")
    await db.execute("INSERT OR REPLACE INTO tickets(channel_id,guild_id,user_id,claimed_by,status,created_at,closed_at) VALUES(?,?,?,?,?,?,0)", (channel.id, guild.id, creator.id, 0, "open", now()))
    await log_ticket_event(channel.id, creator.id, "created", reason[:500])
    embed = discord.Embed(title="🎫 Manifest Support", description=(f"Welcome {creator.mention}!\n\nTell me what you need help with. A support member can claim this ticket, and **Manifest AI can help organize or troubleshoot the issue** while you wait."), color=discord.Color.blurple())
    embed.add_field(name="Status", value="🟢 Open", inline=True)
    embed.add_field(name="Creator", value=creator.mention, inline=True)
    embed.set_footer(text=f"Ticket ID: {channel.id}")
    await channel.send(content=creator.mention, embed=embed, view=TicketControlView())
    return channel


async def handle_natural_action(message: discord.Message) -> bool:
    """Deterministic action router. It runs before AI so explicit commands actually execute."""
    if not message.guild or not isinstance(message.author, discord.Member) or message.author.bot:
        return False
    text = message.content.strip()
    if bot.user:
        text = re.sub(rf"<@!?{bot.user.id}>", "", text).strip()
    low = text.casefold()
    if not text:
        return False

    # Explicit personal memory requests. The bot only stores these when the
    # user clearly asks it to remember something; ordinary conversation is not
    # automatically turned into a permanent memory.
    m = re.match(r"(?:remember|save)\s+(?:that\s+)?(.+?)\s*[:=]\s*(.+)$", text, re.I)
    if m:
        key = re.sub(r"[^a-zA-Z0-9_-]", "_", m.group(1).strip())[:50]
        value = m.group(2).strip()[:500]
        if key and value:
            async def save(_interaction):
                await db.execute(
                    "INSERT INTO memories(guild_id,user_id,memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?,?,?) "
                    "ON CONFLICT(guild_id,user_id,memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at",
                    (message.guild.id, message.author.id, key, value, now(), now()),
                )
                return f"🧠 Saved your server memory **{key}**."
            await message.channel.send(f"🧠 **Save this memory?**\n`{key}` → `{value}`", view=ConfirmActionView(save, message.author.id))
            return True

    # Music can be spoken naturally, with or without a bot mention.
    play_match = re.match(r"^(?:play|queue)\s+(.+)$", text, re.I)
    if play_match:
        try:
            state = await ensure_music_voice(message.guild, message.author, message.channel)
            track = await resolve_music(play_match.group(1))
            await queue_track(message.guild, track)
            await message.channel.send(f"🎵 **{track['title']}** added to the queue.")
        except Exception as exc:
            await message.channel.send(f"⚠️ Music couldn't start: `{clamp_text(str(exc), 500)}`")
        return True

    # Explicit bulk channel deletion. Never report completion until Discord confirms each deletion.
    delete_channels_request = (
        ("delete" in low or "remove" in low)
        and ("channel" in low or "channels" in low)
        and ("all" in low or "ticket" in low or "name contains" in low or "containing" in low)
    )
    if delete_channels_request:
        actor = message.author
        if not (actor.guild_permissions.manage_channels or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send("⚠️ You need **Manage Channels** to delete channels.")
            return True
        me = message.guild.me
        if not me or not me.guild_permissions.manage_channels:
            await message.channel.send("⚠️ I need **Manage Channels** to delete channels.")
            return True
        # Keep this narrow: bulk deletion is only supported for channels matching 'ticket'.
        if "ticket" not in low:
            await message.channel.send("⚠️ For safety, bulk deletion currently only supports channel names containing `ticket`.")
            return True
        targets = [ch for ch in message.guild.text_channels if "ticket" in ch.name.casefold()]
        if not targets:
            await message.channel.send("ℹ️ I found **0** text channels whose names contain `ticket`. Nothing was deleted.")
            return True
        preview = ", ".join(f"#{ch.name}" for ch in targets[:20])
        if len(targets) > 20:
            preview += f", and {len(targets)-20} more"
        async def delete_matching_channels(_interaction):
            deleted, failed = [], []
            for ch in targets:
                try:
                    await ch.delete(reason=f"Bulk ticket-channel deletion requested by {actor} ({actor.id})")
                    deleted.append(ch.name)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    failed.append(f"{ch.name}: {type(exc).__name__}")
            result = f"🗑️ Deleted {len(deleted)}/{len(targets)} matching channels."
            if deleted:
                result += "\nDeleted: " + ", ".join(deleted[:25])
            if failed:
                result += "\nCould not delete: " + ", ".join(failed[:10])
            await log_to_channel(message.guild, f"🗑️ Bulk ticket-channel deletion by {actor.mention}: {len(deleted)} deleted, {len(failed)} failed.")
            return result
        await message.channel.send(
            f"⚠️ **Confirm permanent deletion of {len(targets)} text channels whose names contain `ticket`?**\n{preview}\nThis cannot be undone.",
            view=ConfirmActionView(delete_matching_channels, actor.id),
        )
        return True

    # Authorized natural-language setup for separate moderation and message logs.
    wants_log_setup = (
        ("log" in low or "logging" in low)
        and any(word in low for word in ("create", "make", "setup", "set up", "enable", "configure"))
        and ("moderation" in low or "mod log" in low or "message log" in low or "mod-log" in low)
        and ("message" in low or "edit" in low or "delete" in low or "moderation" in low or "mod log" in low or "mod-log" in low)
    )
    if wants_log_setup:
        actor = message.author
        if not (is_maker(actor) or is_server_owner(actor) or actor.guild_permissions.administrator or actor.guild_permissions.manage_guild):
            await message.channel.send("⚠️ Only the server owner, an administrator, or someone with Manage Server can set up log channels.")
            return True
        guild = message.guild
        me = guild.me
        if not me or not me.guild_permissions.manage_channels:
            await message.channel.send("⚠️ I need **Manage Channels** to create the log channels.")
            return True
        async def create_log_channel(name: str):
            existing = discord.utils.get(guild.text_channels, name=name)
            if existing:
                return existing
            overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
            overwrites[me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, embed_links=True)
            for role in guild.roles:
                perms = role.permissions
                if role.is_default():
                    continue
                if perms.administrator or perms.manage_guild or perms.manage_messages or perms.moderate_members or perms.kick_members or perms.ban_members:
                    overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            for dev_id in DEVELOPER_TEAM:
                member = guild.get_member(dev_id)
                if member:
                    overwrites[member] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
            return await guild.create_text_channel(name, overwrites=overwrites, reason=f"Log channels requested by {actor}")
        try:
            mod_channel = await create_log_channel("manifest-mod-logs")
            msg_channel = await create_log_channel("manifest-message-logs")
            await set_setting(guild.id, "log_channel_id", mod_channel.id)
            await set_setting(guild.id, "message_log_channel_id", msg_channel.id)
            await message.channel.send(f"✅ Log channels are ready: {mod_channel.mention} for moderation events and {msg_channel.mention} for message edits/deletions.")
        except discord.Forbidden:
            await message.channel.send("⚠️ Discord denied channel creation. Check my **Manage Channels** permission and role position.")
        except discord.HTTPException as exc:
            await message.channel.send(f"⚠️ I couldn't finish log setup: `{clamp_text(str(exc), 350)}`")
        return True

    # Delete the current tracked ticket only after explicit confirmation.
    # This calls Discord's API; the AI must never merely claim deletion.
    if re.search(r"\b(?:delete|remove|destroy)\b.*\b(?:this|my|the)\s+ticket\b|\bdelete\s+ticket\b", low):
        if not isinstance(message.channel, discord.TextChannel) or not ticket_channel(message.channel):
            return False
        row = await get_or_repair_ticket_record(message.channel)
        if not row:
            await message.channel.send("⚠️ I couldn't verify this as a tracked Manifest ticket, so I won't delete it.")
            return True
        actor = message.author
        if actor.id != int(row["user_id"]) and not await permission_granted(message.guild, actor, "ticket_manage"):
            await message.channel.send("⚠️ Only this ticket's creator or authorized ticket staff can delete it.")
            return True
        target_channel = message.channel
        target_name = target_channel.name
        async def delete_this_ticket(_interaction):
            try:
                await log_ticket_event(target_channel.id, actor.id, "delete_requested", "Confirmed natural-language ticket deletion")
                await log_to_channel(message.guild, f"🗑️ Ticket deletion requested by {actor.mention} for `#{target_name}` (channel ID `{target_channel.id}`).")
                await target_channel.delete(reason=f"Ticket deletion confirmed by {actor} ({actor.id})")
                await db.execute("UPDATE tickets SET status='deleted',closed_at=? WHERE channel_id=?", (now(), target_channel.id))
                return f"🗑️ Discord confirmed deletion of `#{target_name}`."
            except discord.NotFound:
                return "ℹ️ This ticket channel was already deleted."
            except discord.Forbidden:
                return "❌ Discord denied deletion. Check my **Manage Channels** permission and role hierarchy. The ticket was not reported as deleted."
            except discord.HTTPException as exc:
                return f"❌ Discord couldn't delete the ticket: `{clamp_text(str(exc), 300)}`"
        await message.channel.send(
            f"⚠️ **Permanently delete this ticket?** This deletes `#{target_name}` and its visible channel history. This cannot be undone.",
            view=ConfirmActionView(delete_this_ticket, actor.id),
        )
        return True

    # Ticket creator or authorized ticket staff can close/archive by saying it naturally.
    if re.search(r"\b(?:close|archive|shut)\b.*\b(?:this|my|the)\s+ticket\b|\b(?:close|archive)\s+ticket\b", low):
        if not isinstance(message.channel, discord.TextChannel) or not ticket_channel(message.channel):
            return False
        row = await get_or_repair_ticket_record(message.channel)
        if not row or row["status"] in ("closed", "orphaned"):
            await message.channel.send("This ticket is already closed, or I couldn't verify its creator.")
            return True
        actor = message.author
        if actor.id != int(row["user_id"]) and not await permission_granted(message.guild, actor, "ticket_manage"):
            await message.channel.send("⚠️ Only the ticket creator or authorized ticket staff can close this ticket.")
            return True
        try:
            await db.execute("UPDATE tickets SET status='closed',closed_at=? WHERE channel_id=?", (now(), message.channel.id))
            await log_ticket_event(message.channel.id, actor.id, "closed", "Natural-language close request")
            await message.channel.edit(name=f"closed-{message.channel.name.removeprefix('ticket-').removeprefix('closed-')[:70]}", reason=f"Ticket closed by {actor}")
            await message.channel.set_permissions(message.guild.default_role, view_channel=False)
            await message.channel.set_permissions(actor, view_channel=True, send_messages=True, read_message_history=True)
            await message.channel.send(f"🔒 Ticket archived by {actor.mention}. You can reopen it with `/ticket ticket_reopen`.")
            await log_to_channel(message.guild, f"🎫 Ticket archived: {message.channel.mention} by {actor.mention} (ID {actor.id}).")
        except discord.Forbidden:
            await message.channel.send("⚠️ I couldn't archive this ticket because Discord denied a channel permission change. Check my Manage Channels permission.")
        except discord.HTTPException as exc:
            await message.channel.send(f"⚠️ Ticket close partially failed: `{clamp_text(str(exc), 300)}`")
        return True

    # Ticket creation is safe for normal members.
    if re.search(r"\b(?:open|create|make)\s+(?:a\s+)?ticket\b", low):
        async def open_ticket(_interaction):
            existing = await db.fetchone("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND status IN ('open','claimed','bot_assisted')", (message.guild.id, message.author.id))
            if existing and message.guild.get_channel(existing['channel_id']):
                return f"🎫 You already have <#{existing['channel_id']}>."
            channel = await create_ticket_channel(message.guild, message.author, "Natural-language request")
            return f"🎫 Ticket created: {channel.mention}"
        await message.channel.send("🎫 **Ready to open a private support ticket?**", view=ConfirmActionView(open_ticket, message.author.id))
        return True

    # Prefixless moderation/action commands. Accept common direct phrasing, but do
    # not infer a destructive action from ordinary discussion or from AI text.
    # Examples: "ban @member", "please ban @member", "Manifest, ban @member".
    command_text = re.sub(r"^(?:hey\s+)?(?:please\s+)?(?:can you|could you|would you)\s+", "", low, flags=re.I)
    command_text = re.sub(r"^(?:please\s+)?(?:manifest[,!]?\s+)", "", command_text, flags=re.I)
    action_match = re.match(r"^(kick|ban|timeout|purge|lock|unlock|slowmode)\b(.*)$", command_text, re.I)
    if not action_match:
        return False
    action = action_match.group(1).lower()
    rest = action_match.group(2).strip()
    actor = message.author
    if action in {"kick", "ban"}:
        target = await _safe_member_target(message)
        if not target:
            await message.channel.send(f"🛡️ Mention the member you want me to {action}.")
            return True
        needed = actor.guild_permissions.kick_members if action == "kick" else actor.guild_permissions.ban_members
        if not (needed or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send(f"⚠️ You don't have permission to **{action}** members.")
            return True
        ok, why = await _bot_can_act(message.guild, target)
        if not ok:
            await message.channel.send(f"⚠️ {why}")
            return True
        reason = re.sub(r"<@!?\d+>", "", rest).strip() or "Manifest natural-language moderation"
        try:
            if action == "kick":
                await target.kick(reason=reason[:500])
                text = f"👢 Kicked **{target}**. Reason: {reason[:300]}"
            else:
                await target.ban(reason=reason[:500], delete_message_seconds=0)
                # Confirm Discord's ban list reflects the change before reporting success.
                try:
                    await message.guild.fetch_ban(discord.Object(id=target.id))
                except discord.NotFound:
                    await message.channel.send("⚠️ Discord did not show this member in the ban list after the request. I can't report the ban as successful.")
                    return True
                text = f"🔨 **Ban verified by Discord** for {target.mention} (ID `{target.id}`). Reason: {reason[:300]}"
            await log_to_channel(message.guild, f"🛡️ {actor} used natural-language {action} on {target} — {reason}")
            await message.channel.send(text)
        except discord.Forbidden:
            await message.channel.send("⚠️ Discord rejected that action. Check my role hierarchy and permissions.")
        except discord.HTTPException as exc:
            await message.channel.send(f"⚠️ Discord returned an error: `{clamp_text(str(exc), 400)}`")
        return True

    if action == "timeout":
        target = await _safe_member_target(message)
        if not target:
            await message.channel.send("🛡️ Mention the member you want to timeout.")
            return True
        if not (actor.guild_permissions.moderate_members or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send("⚠️ You don't have the **Moderate Members** permission.")
            return True
        ok, why = await _bot_can_act(message.guild, target)
        if not ok:
            await message.channel.send(f"⚠️ {why}")
            return True
        mins = int(re.search(r"\b(\d{1,5})\s*(?:m|min|mins|minute|minutes)?\b", rest).group(1)) if re.search(r"\b(\d{1,5})\s*(?:m|min|mins|minute|minutes)?\b", rest) else 10
        mins = max(1, min(mins, 40320))
        try:
            await target.timeout(datetime.timedelta(minutes=mins), reason="Manifest natural-language moderation")
            await message.channel.send(f"⏳ Timed out **{target}** for **{mins} minutes**.")
        except discord.Forbidden:
            await message.channel.send("⚠️ Discord rejected the timeout. Check my role hierarchy/permissions.")
        return True

    if action == "purge":
        if not (actor.guild_permissions.manage_messages or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send("⚠️ You need **Manage Messages** to purge messages.")
            return True
        nmatch = re.search(r"\b(\d{1,3})\b", rest)
        amount = max(1, min(int(nmatch.group(1)) if nmatch else 10, 100))
        try:
            deleted = await message.channel.purge(limit=amount + 1)
            await message.channel.send(f"🧹 Removed **{max(0, len(deleted)-1)}** messages.", delete_after=5)
        except discord.Forbidden:
            await message.channel.send("⚠️ I need **Manage Messages** and **Read Message History** here.")
        return True

    if action in {"lock", "unlock"}:
        if not (actor.guild_permissions.manage_channels or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send("⚠️ You need **Manage Channels** to change channel access.")
            return True
        try:
            overwrite = message.channel.overwrites_for(message.guild.default_role)
            overwrite.send_messages = False if action == "lock" else None
            await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite, reason=f"Manifest natural-language {action}")
            await message.channel.send("🔒 Channel locked." if action == "lock" else "🔓 Channel unlocked.")
        except discord.Forbidden:
            await message.channel.send("⚠️ I need **Manage Channels** to do that.")
        return True

    if action == "slowmode":
        if not (actor.guild_permissions.manage_channels or actor.guild_permissions.administrator or is_maker(actor)):
            await message.channel.send("⚠️ You need **Manage Channels** to change slowmode.")
            return True
        sm = re.search(r"\b(\d+)\b", rest)
        seconds = max(0, min(int(sm.group(1)) if sm else 5, 21600))
        try:
            await message.channel.edit(slowmode_delay=seconds, reason="Manifest natural-language slowmode")
            await message.channel.send(f"🐢 Slowmode set to **{seconds}s**.")
        except discord.Forbidden:
            await message.channel.send("⚠️ I need **Manage Channels** to change slowmode.")
        return True
    return False


@bot.event
async def on_message(message: discord.Message):
    if not message.guild or message.author.bot:
        return

    # Discord normally dispatches each message once; this guard prevents duplicate
    # work if an event is re-dispatched during reconnects or extension changes.
    if message.id in bot.processed_message_ids:
        return
    bot.processed_message_ids.add(message.id)
    if len(bot.processed_message_ids) > 20000:
        # Keep a bounded recent window without immediately forgetting all recent IDs.
        bot.processed_message_ids = set(list(bot.processed_message_ids)[-10000:])

    guild = message.guild
    await ensure_guild(guild)
    bot.channel_activity[message.channel.id] = now()

    if await handle_natural_action(message):
        return

    # This bot overrides on_message, so prefix commands must be dispatched explicitly.
    # Without this, commands such as !purge, !level and !leaderboard never run.
    ctx = await bot.get_context(message)
    if ctx.valid:
        await bot.invoke(ctx)
        return

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
        old_xp = int(row["xp"] if row else 0)
        old_level = int(row["level"] if row else 0)
        gained_xp = random.randint(10, 20)
        xp = old_xp + gained_xp
        new_level = level_from_xp(xp)
        await db.execute(
            """INSERT INTO levels(guild_id,user_id,xp,level,last_xp_at) VALUES(?,?,?,?,?)
               ON CONFLICT(guild_id,user_id) DO UPDATE SET xp=excluded.xp,level=excluded.level,last_xp_at=excluded.last_xp_at""",
            (guild.id, message.author.id, xp, new_level, now()),
        )
        await record_activity(guild.id, message.author.id, messages=1, xp=gained_xp)
        if new_level > old_level:
            await message.channel.send(
                f"🎉 {message.author.mention} reached **Level {new_level}**! • `{xp - xp_for_level(new_level):,}` XP into this level",
                delete_after=12,
            )
            # Grant the configured exact-level reward, respecting Discord hierarchy.
            if isinstance(message.author, discord.Member):
                reward = await db.fetchone(
                    "SELECT role_id FROM level_rewards WHERE guild_id=? AND level=?",
                    (guild.id, new_level),
                )
                role = guild.get_role(int(reward["role_id"])) if reward else None
                me = guild.me
                if role and role not in message.author.roles and me and me.guild_permissions.manage_roles and role < me.top_role and not role.managed:
                    try:
                        await message.author.add_roles(role, reason=f"Manifest level reward: reached level {new_level}")
                        await message.channel.send(f"🏅 {message.author.mention} earned the **{role.name}** role!")
                    except (discord.Forbidden, discord.HTTPException):
                        log.warning("Could not grant level reward role %s in guild %s", role.id, guild.id)
    else:
        # Even when XP is on cooldown, keep message statistics accurate.
        await record_activity(guild.id, message.author.id, messages=1)

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
    ai_channel_id = int(await setting(guild.id, "ai_channel_id", 0) or 0)
    # In ticket channels, AI answers when explicitly mentioned; the AI Help
    # button and the unclaimed-ticket timer provide on-demand/initial assistance.
    # This avoids Manifest replying to every single ticket message and feeling spammy.
    mentioned = bool(bot.user and bot.user in message.mentions)
    allowed_ai = bool(ai_enabled and mentioned and (not ai_channel_only or (ai_channel_id and message.channel.id == ai_channel_id)))

    if allowed_ai:
        prompt = re.sub(rf"<@!?{bot.user.id}>", "", message.content).strip()
        if prompt:
            # SQLite UNIQUE reservation is an additional guard when two processes
            # share the same persistent database. In-memory dedupe alone cannot
            # prevent two separately running bot instances from answering.
            try:
                await db.execute(
                    "INSERT INTO processed_ai_messages(message_id,guild_id,created_at) VALUES(?,?,?)",
                    (message.id, guild.id, now()),
                )
            except Exception as exc:
                if "UNIQUE" in str(exc).upper() or "PRIMARY KEY" in str(exc).upper():
                    log.warning("Skipped duplicate AI handling for Discord message %s", message.id)
                    return
                log.exception("Could not reserve AI message %s; skipping reply to avoid duplicates", message.id)
                return
            # Prune old dedupe rows periodically to keep SQLite small.
            if random.random() < 0.01:
                await db.execute("DELETE FROM processed_ai_messages WHERE created_at < ?", (now() - 7 * 86400,))
            try:
                async with message.channel.typing():
                    response = await ask_ai(
                        guild,
                        message.author,
                        prompt,
                        message.channel if isinstance(message.channel, discord.TextChannel) else None,
                    )
                await send_long(message.channel, response)
            except discord.HTTPException:
                log.exception("Discord failed to deliver AI response for message %s", message.id)
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
        return await ctx.send("⚠️ You do not have the required Discord permission.", delete_after=8)
    if isinstance(error, commands.BadArgument):
        return await ctx.send("⚠️ I couldn't understand those arguments. Check the command format.", delete_after=8)
    log.error("Prefix command error (%s): %s", getattr(ctx.command, "qualified_name", "unknown"), error, exc_info=(type(error), error, error.__traceback__))
    try:
        await ctx.send("⚠️ That command failed. The error was recorded in the bot logs.", delete_after=8)
    except discord.HTTPException:
        pass


# ============================================================
# CHECKS
# ============================================================

def maker_only():
    async def predicate(interaction: discord.Interaction):
        if not is_maker(interaction.user):
            raise app_commands.CheckFailure("Manifest creator only.")
        return True
    return app_commands.check(predicate)


def server_manager_or_maker():
    """Allow the verified creator or a manager of this server to change local settings."""
    async def predicate(interaction: discord.Interaction):
        if is_maker(interaction.user):
            return True
        member = interaction.user
        if isinstance(member, discord.Member) and (member.guild_permissions.manage_guild or member.guild_permissions.administrator):
            return True
        raise app_commands.CheckFailure("You need Manage Server or verified Manifest creator access.")
    return app_commands.check(predicate)


# ============================================================
# CORE / INFO
# ============================================================

# Slash command groups keep Manifest safely below Discord's 100 global top-level command limit.
memory_group = app_commands.Group(name="memory", description="Memory and persistent context")
music_group = app_commands.Group(name="music", description="Music playback and queue controls")
ticket_group = app_commands.Group(name="ticket", description="Support ticket management")
developer_group = app_commands.Group(name="developer", description="Manifest developer/server configuration")
mod_group = app_commands.Group(name="mod", description="Moderation and server protection")
economy_group = app_commands.Group(name="economy", description="Economy and rewards")
stats_group = app_commands.Group(name="stats", description="Levels, messages and invite statistics")
utility_group = app_commands.Group(name="utility", description="Server utilities and general tools")
fun_group = app_commands.Group(name="fun", description="Fun commands")
knowledge_group = app_commands.Group(name="knowledge", description="Verified, searchable server knowledge cards")

@knowledge_group.command(name="add", description="Add a trusted answer to the server knowledge base.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(title="Short unique title", content="Verified answer or instructions", source_url="Optional link to the official source")
async def knowledge_add(
    interaction: discord.Interaction,
    title: app_commands.Range[str, 3, 80],
    content: app_commands.Range[str, 10, 1500],
    source_url: Optional[str] = None,
):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command in a server.", ephemeral=True)
    title_value = str(title).strip()
    content_value = str(content).strip()
    source = (source_url or "").strip()
    if source and not source.startswith(("https://", "http://")):
        return await interaction.response.send_message("The source must be a valid http:// or https:// URL.", ephemeral=True)
    timestamp = now()
    await db.execute(
        """INSERT INTO knowledge_cards(guild_id,title,content,source_url,added_by,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(guild_id,title) DO UPDATE SET content=excluded.content,
           source_url=excluded.source_url,added_by=excluded.added_by,updated_at=excluded.updated_at""",
        (interaction.guild.id, title_value, content_value, source, interaction.user.id, timestamp, timestamp),
    )
    await log_command(interaction, "knowledge add", title_value)
    await interaction.response.send_message(f"📚 Saved verified knowledge card **{discord.utils.escape_markdown(title_value)}**.", ephemeral=True)

@knowledge_group.command(name="search", description="Search verified answers saved for this server.")
@app_commands.describe(query="Words from the title or answer")
async def knowledge_search(interaction: discord.Interaction, query: app_commands.Range[str, 2, 100]):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command in a server.", ephemeral=True)
    terms = [part.strip() for part in str(query).split() if part.strip()][:6]
    if not terms:
        return await interaction.response.send_message("Enter a search phrase.", ephemeral=True)
    where = " AND ".join(["(title LIKE ? OR content LIKE ?)"] * len(terms))
    params = []
    for term in terms:
        like = f"%{term[:60]}%"
        params.extend((like, like))
    rows = await db.fetchall(
        f"SELECT title,content,source_url,updated_at FROM knowledge_cards WHERE guild_id=? AND {where} ORDER BY updated_at DESC LIMIT 5",
        (interaction.guild.id, *params),
    )
    if not rows:
        return await interaction.response.send_message("🔎 No verified cards matched. Ask a moderator to add one with `/knowledge add`.", ephemeral=True)
    embed = discord.Embed(title="📚 Server Brain — Verified Answers", color=discord.Color.blurple())
    for row in rows:
        value = str(row["content"])[:900]
        if row["source_url"]:
            value += f"\n[Open source]({row['source_url']})"
        embed.add_field(name=str(row["title"])[:256], value=value, inline=False)
    embed.set_footer(text="Answers come from this server's saved knowledge cards, not an unverified AI guess.")
    await log_command(interaction, "knowledge search", str(query))
    await interaction.response.send_message(embed=embed, ephemeral=True)

@knowledge_group.command(name="remove", description="Remove a saved knowledge card by its exact title.")
@app_commands.checks.has_permissions(manage_guild=True)
@app_commands.describe(title="Exact title of the card to remove")
async def knowledge_remove(interaction: discord.Interaction, title: app_commands.Range[str, 3, 80]):
    if not interaction.guild:
        return await interaction.response.send_message("Use this command in a server.", ephemeral=True)
    row = await db.fetchone(
        "SELECT id FROM knowledge_cards WHERE guild_id=? AND title=? COLLATE NOCASE",
        (interaction.guild.id, str(title).strip()),
    )
    if not row:
        return await interaction.response.send_message("No card with that exact title exists.", ephemeral=True)
    await db.execute("DELETE FROM knowledge_cards WHERE id=?", (row["id"],))
    await log_command(interaction, "knowledge remove", str(title))
    await interaction.response.send_message(f"🗑️ Removed knowledge card **{discord.utils.escape_markdown(str(title))}**.", ephemeral=True)

@utility_group.command(name="manifest", description="Show Manifest status and feature summary.")
async def manifest(interaction: discord.Interaction):
    await log_command(interaction, "manifest")
    embed = discord.Embed(
        title="⚡ Manifest V11.1",
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


@utility_group.command(name="serverinfo", description="Show server information.")
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


@utility_group.command(name="userinfo", description="Show information about a member.")
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

@bot.tree.command(name="chat", description="Chat with Manifest AI with persistent context.")
async def chat(interaction: discord.Interaction, prompt: str):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    await interaction.response.defer()
    answer = await ask_ai(interaction.guild, interaction.user, prompt, interaction.channel if isinstance(interaction.channel, discord.TextChannel) else None)
    await interaction.followup.send(answer)


@bot.command(name="chat")
async def prefix_chat(ctx: commands.Context, *, prompt: str):
    if not ctx.guild or not isinstance(ctx.author, discord.Member):
        return
    async with ctx.typing():
        answer = await ask_ai(ctx.guild, ctx.author, prompt, ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
    await send_long(ctx.channel, answer)


@bot.command(name="ai")
async def prefix_ai(ctx: commands.Context, *, prompt: str):
    if not ctx.guild or not isinstance(ctx.author, discord.Member):
        return
    async with ctx.typing():
        answer = await ask_ai(ctx.guild, ctx.author, prompt, ctx.channel if isinstance(ctx.channel, discord.TextChannel) else None)
    await send_long(ctx.channel, answer)


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


@memory_group.command(name="remember", description="Save a memory about yourself for Manifest.")
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


@memory_group.command(name="forget", description="Delete one of your stored memories.")
async def forget(interaction: discord.Interaction, key: str):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    await db.execute(
        "DELETE FROM memories WHERE guild_id=? AND user_id=? AND memory_key=?",
        (interaction.guild.id, interaction.user.id, key.strip()),
    )
    await interaction.response.send_message(f"🧠 Removed memory **{key}**.", ephemeral=True)


@memory_group.command(name="memories", description="Show your stored Manifest memories.")
async def memories(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    text = await memories_for(interaction.guild.id, interaction.user.id)
    await interaction.response.send_message(clamp_text(text, 1800), ephemeral=True)


# ============================================================
# PERSISTENT MAKER / SERVER / USER MEMORY
# ============================================================

@memory_group.command(name="maker_memory", description="Save a global Maker memory for Manifest.")
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


@memory_group.command(name="maker_forget", description="Remove a global Maker memory.")
@maker_only()
async def maker_forget(interaction: discord.Interaction, key: str):
    await db.execute("DELETE FROM maker_memories WHERE memory_key=?", (key.strip(),))
    await interaction.response.send_message(f"🧠 Global Maker memory removed: **{key}**", ephemeral=True)


@memory_group.command(name="maker_memories", description="Show global Maker memories.")
@maker_only()
async def maker_memories(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await maker_memories_text(), 1900), ephemeral=True)


@memory_group.command(name="maker_rule_add", description="Add a persistent global instruction for Manifest.")
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


@memory_group.command(name="maker_rule_remove", description="Remove a persistent Maker instruction by ID.")
@maker_only()
async def maker_rule_remove(interaction: discord.Interaction, rule_id: int):
    await db.execute("DELETE FROM maker_instructions WHERE id=?", (rule_id,))
    await interaction.response.send_message(f"📌 Maker rule **#{rule_id}** removed.", ephemeral=True)


@memory_group.command(name="maker_rules", description="Show persistent Maker instructions.")
@maker_only()
async def maker_rules(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await maker_instructions_text(), 1900), ephemeral=True)


@memory_group.command(name="server_remember", description="Save a memory/configuration for this server.")
@server_manager_or_maker()
async def server_remember(interaction: discord.Interaction, key: str, value: str):
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    value = value.strip()[:1000]
    await db.execute(
        "INSERT INTO server_memories(guild_id,memory_key,memory_value,created_at,updated_at) VALUES(?,?,?,?,?) "
        "ON CONFLICT(guild_id,memory_key) DO UPDATE SET memory_value=excluded.memory_value,updated_at=excluded.updated_at",
        (interaction.guild_id, key, value, now(), now()),
    )
    await interaction.response.send_message(f"🏠 Server memory saved: **{key}**", ephemeral=True)


@memory_group.command(name="server_forget", description="Remove a server memory.")
@server_manager_or_maker()
async def server_forget(interaction: discord.Interaction, key: str):
    await db.execute("DELETE FROM server_memories WHERE guild_id=? AND memory_key=?", (interaction.guild_id, key.strip()))
    await interaction.response.send_message(f"🏠 Server memory removed: **{key}**", ephemeral=True)


@memory_group.command(name="server_memories", description="Show this server's stored memories.")
async def server_memories(interaction: discord.Interaction):
    await interaction.response.send_message(clamp_text(await server_memories_text(interaction.guild_id), 1900), ephemeral=True)


@memory_group.command(name="remember_user", description="Save memory about another member. Maker or server managers only.")
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


@memory_group.command(name="forget_user", description="Remove stored memory about another member.")
async def forget_user(interaction: discord.Interaction, member: discord.Member, key: str):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server or Maker access.", ephemeral=True)
    await db.execute("DELETE FROM memories WHERE guild_id=? AND user_id=? AND memory_key=?", (interaction.guild_id, member.id, key.strip()))
    await interaction.response.send_message(f"🧠 Removed **{key}** for {member.mention}.", ephemeral=True)


@memory_group.command(name="memories_user", description="View stored memory about another member.")
async def memories_user(interaction: discord.Interaction, member: discord.Member):
    if not is_maker(interaction.user) and not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message("You need Manage Server or Maker access.", ephemeral=True)
    await interaction.response.send_message(clamp_text(await memories_for(interaction.guild_id, member.id), 1900), ephemeral=True)


@memory_group.command(name="clear_my_memory", description="Delete all of your stored memories in this server.")
async def clear_my_memory(interaction: discord.Interaction):
    await db.execute("DELETE FROM memories WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id))
    await interaction.response.send_message("🧠 Your personal Manifest memory for this server was cleared.", ephemeral=True)


@memory_group.command(name="clear_history", description="Delete your stored AI conversation history in this server.")
async def clear_history(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    await db.execute("DELETE FROM conversation_history WHERE guild_id=? AND user_id=?", (interaction.guild.id, interaction.user.id))
    for cache_key in list(conversation_cache):
        if cache_key[:2] == (interaction.guild.id, interaction.user.id):
            conversation_cache.pop(cache_key, None)
    await interaction.response.send_message("🧹 Your stored AI conversation history for this server was cleared.", ephemeral=True)


# ============================================================
# ============================================================
# MUSIC COMMANDS — STANDALONE
# ============================================================

@music_group.command(name="play", description="Search for a song by name or play a public URL—no file upload needed.")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Server only.", ephemeral=True)
    await interaction.response.defer()
    try:
        state=await ensure_music_voice(interaction.guild, interaction.user, interaction.channel)
        track=await resolve_music(query)
        was_playing=state.voice.is_playing() or state.voice.is_paused()
        await queue_track(interaction.guild,track)
        await interaction.followup.send(f"🎵 {'Queued' if was_playing else 'Playing'} **{track['title']}**\n👤 {track['artist']} · {'Live stream' if not track['duration'] else str(track['duration']//60)+':'+str(track['duration']%60).zfill(2)}\n🔗 {track['webpage']}")
    except Exception as exc:
        log.warning("Music play failed: %s", exc)
        await interaction.followup.send(f"❌ Music failed: {clamp_text(str(exc),800)}")

@music_group.command(name="pause", description="Pause music.")
async def pause(interaction):
    state=get_music_state(interaction.guild.id)
    if not state.voice or not state.voice.is_playing():
        return await interaction.response.send_message("Nothing is playing.",ephemeral=True)
    state.voice.pause(); await interaction.response.send_message("⏸️ Paused.")

@music_group.command(name="resume", description="Resume music.")
async def resume(interaction):
    state=get_music_state(interaction.guild.id)
    if not state.voice or not state.voice.is_paused():
        return await interaction.response.send_message("Nothing is paused.",ephemeral=True)
    state.voice.resume(); await interaction.response.send_message("▶️ Resumed.")

@music_group.command(name="skip", description="Skip the current track.")
async def skip(interaction):
    state=get_music_state(interaction.guild.id)
    if not state.voice or not state.voice.is_playing():
        return await interaction.response.send_message("Nothing is playing.",ephemeral=True)
    state.voice.stop(); await interaction.response.send_message("⏭️ Skipped.")

@music_group.command(name="stop", description="Stop music and clear the queue.")
async def stop(interaction):
    state=get_music_state(interaction.guild.id)
    state.queue.clear(); state.current=None
    if state.voice and state.voice.is_connected(): state.voice.stop()
    await interaction.response.send_message("⏹️ Stopped and cleared the queue.")

@music_group.command(name="queue", description="Show the music queue.")
async def queue(interaction):
    state=get_music_state(interaction.guild.id)
    lines=[f"▶️ **Now:** {state.current['title']}" if state.current else "Nothing playing."]
    lines += [f"`{i}` {t['title']}" for i,t in enumerate(state.queue[:20],1)]
    await interaction.response.send_message("🎶 **Music Queue**\n"+"\n".join(lines))

@music_group.command(name="nowplaying", description="Show the current track.")
async def nowplaying(interaction):
    state=get_music_state(interaction.guild.id)
    if not state.current:
        return await interaction.response.send_message("Nothing is playing.",ephemeral=True)
    await interaction.response.send_message(f"🎧 **{state.current['title']}**\nArtist: **{state.current['artist']}**\n{state.current['webpage']}")

@music_group.command(name="shuffle", description="Shuffle the queue.")
async def shuffle(interaction):
    state=get_music_state(interaction.guild.id)
    random.shuffle(state.queue); await interaction.response.send_message("🔀 Queue shuffled.")

@music_group.command(name="remove", description="Remove a queued track.")
async def remove(interaction, position: app_commands.Range[int,1,100]):
    state=get_music_state(interaction.guild.id); i=position-1
    if i>=len(state.queue): return await interaction.response.send_message("That position doesn't exist.",ephemeral=True)
    track=state.queue.pop(i); await interaction.response.send_message(f"🗑️ Removed **{track['title']}**.")

@music_group.command(name="clearqueue", description="Clear queued tracks.")
async def clearqueue(interaction):
    state=get_music_state(interaction.guild.id); state.queue.clear()
    await interaction.response.send_message("🧹 Queue cleared.")

@music_group.command(name="volume", description="Set music volume from 0 to 200 percent.")
async def volume(interaction, percent: app_commands.Range[int,0,200]):
    state=get_music_state(interaction.guild.id); state.volume=percent/100
    await interaction.response.send_message(f"🔊 Volume set to **{percent}%**. It applies to the next track.")

@music_group.command(name="leave", description="Leave the voice channel.")
async def leave(interaction):
    state=get_music_state(interaction.guild.id); state.queue.clear(); state.current=None
    if state.voice and state.voice.is_connected(): await state.voice.disconnect()
    state.voice=None; await interaction.response.send_message("👋 Left the voice channel.")

@music_group.command(name="music_status", description="Show standalone music status.")
async def music_status(interaction):
    state=get_music_state(interaction.guild.id)
    await interaction.response.send_message(f"🎵 **Music status — Manifest V{VERSION}**\n**FFmpeg:** {'available via imageio-ffmpeg/fallback path'}\n**Voice connected:** {bool(state.voice and state.voice.is_connected())}\n**Playing:** {bool(state.voice and state.voice.is_playing())}\n**Paused:** {bool(state.voice and state.voice.is_paused())}\n**Queue length:** {len(state.queue)} / 50\n**Last music error:** {clamp_text(music_last_error, 300) if music_last_error else 'None recorded'}")


# TICKETS
# ============================================================

@ticket_group.command(name="create", description="Open a private support ticket.")
async def ticket(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Tickets can only be opened in a server.", ephemeral=True)
    try:
        channel = await create_ticket_channel(interaction.guild, interaction.user, "slash command")
        await interaction.response.send_message(f"🎫 **Ticket opened:** {channel.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ I need **Manage Channels** to create tickets.", ephemeral=True)
    except discord.HTTPException as exc:
        await interaction.response.send_message(f"❌ Discord could not create the ticket: `{clamp_text(str(exc), 500)}`", ephemeral=True)


class TicketCloseModal(discord.ui.Modal, title="Close Ticket"):
    reason = discord.ui.TextInput(label="Reason", placeholder="Why is this ticket being closed?", required=True, max_length=500, style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id if interaction.channel else 0,))
        if not row or not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("This is not an active Manifest ticket.", ephemeral=True)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or (member.id != row["user_id"] and not await permission_granted(interaction.guild, member, "ticket_manage")):
            return await interaction.response.send_message("You are not authorized to close this ticket.", ephemeral=True)
        await db.execute("UPDATE tickets SET status='closed',closed_at=? WHERE channel_id=?", (now(),interaction.channel.id))
        await log_ticket_event(interaction.channel.id, member.id, "closed", str(self.reason.value))
        try:
            await interaction.channel.edit(name=f"closed-{interaction.channel.name.removeprefix('ticket-')[:70]}", reason=f"Manifest ticket closed: {self.reason.value[:300]}")
            await interaction.channel.set_permissions(interaction.guild.default_role, view_channel=False)
            await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True, read_message_history=True)
            await interaction.response.send_message(f"🔒 Ticket archived by {member.mention}.\n**Reason:** {self.reason.value}\nUse `/ticket_reopen` if you need it reopened.")
        except discord.HTTPException:
            await interaction.response.send_message(f"🔒 Ticket closed by {member.mention}.\n**Reason:** {self.reason.value}")


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="manifest:ticket:create")
    async def create(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("Use this in a server.", ephemeral=True)
        try:
            channel = await create_ticket_channel(interaction.guild, interaction.user, "panel button")
            await interaction.response.send_message(f"🎫 Ticket opened: {channel.mention}", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I need Manage Channels to create tickets.", ephemeral=True)
        except discord.HTTPException as exc:
            await interaction.response.send_message(f"❌ Ticket creation failed: `{clamp_text(str(exc), 400)}`", ephemeral=True)


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.primary, emoji="🙋", custom_id="manifest:ticket:claim")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
        row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id,))
        if not row: return await interaction.response.send_message("This is not a tracked ticket.", ephemeral=True)
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not member or not await permission_granted(interaction.guild, member, "ticket"):
            return await interaction.response.send_message("You need ticket-staff permission.", ephemeral=True)
        await db.execute("UPDATE tickets SET claimed_by=?,status='claimed' WHERE channel_id=?", (member.id,interaction.channel.id))
        await log_ticket_event(interaction.channel.id,member.id,"claimed")
        await interaction.response.send_message(f"🙋 Ticket claimed by {member.mention}.")

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.secondary, emoji="✏️", custom_id="manifest:ticket:rename")
    async def rename(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketRenameModal())

    @discord.ui.button(label="AI Help", style=discord.ButtonStyle.success, emoji="🤖", custom_id="manifest:ticket:ai")
    async def ai_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
            return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
        row = await get_or_repair_ticket_record(interaction.channel)
        if not row or row["status"] in ("closed", "orphaned"):
            return await interaction.response.send_message(
                "I couldn't verify this as an active Manifest ticket. If this is an older ticket, ask staff to recreate it using the ticket panel.",
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        history = []
        async for msg in interaction.channel.history(limit=12, oldest_first=False):
            if not msg.author.bot:
                history.append(f"{msg.author.display_name}: {msg.clean_content[:800]}")
        prompt = "You are assisting inside a Discord support ticket. Summarize the issue, identify missing information, and give practical next steps. Do not invent account changes, refunds, permissions, or actions.\n\nRecent ticket messages:\n" + "\n".join(reversed(history))
        answer = await ask_ai(interaction.guild, interaction.user if isinstance(interaction.user, discord.Member) else interaction.guild.me, prompt, interaction.channel, system_extra="You are in a support ticket. Be especially clear, empathetic, and action-oriented.")
        await interaction.followup.send(f"🤖 **Manifest AI**\n{clamp_text(answer, 1900)}", ephemeral=True)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="manifest:ticket:close")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketCloseModal())


class TicketRenameModal(discord.ui.Modal, title="Rename Ticket"):
    name = discord.ui.TextInput(label="New ticket name", placeholder="payment-help", required=True, min_length=2, max_length=80)
    async def on_submit(self, interaction: discord.Interaction):
        if not isinstance(interaction.channel, discord.TextChannel) or not interaction.guild:
            return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
        row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id,))
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if not row or not member or not await permission_granted(interaction.guild, member, "ticket_manage"):
            return await interaction.response.send_message("You are not authorized to rename this ticket.", ephemeral=True)
        safe = re.sub(r"[^a-zA-Z0-9-]+", "-", str(self.name.value).strip().lower()).strip("-")[:80]
        if not safe: return await interaction.response.send_message("Invalid ticket name.", ephemeral=True)
        await interaction.channel.edit(name=f"ticket-{safe}", reason=f"Manifest ticket rename by {member}")
        await log_ticket_event(interaction.channel.id,member.id,"renamed",safe)
        await interaction.response.send_message(f"✏️ Ticket renamed to **ticket-{safe}**.")


@ticket_group.command(name="panel", description="Post a persistent Create Ticket panel in this channel.")
async def ticket_panel(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("Server only.", ephemeral=True)
    if not await permission_granted(interaction.guild, interaction.user, "ticket_manage"):
        return await interaction.response.send_message("You need ticket-staff/server-management permission.", ephemeral=True)
    embed = discord.Embed(title="🎫 Need help?", description="Click **Create Ticket** to open a private support channel. Manifest can also help summarize and troubleshoot your issue while staff are away.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("✅ Ticket panel posted.", ephemeral=True)


@ticket_group.command(name="transcript", description="Export the current ticket transcript.")
async def ticket_transcript(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=?", (interaction.channel.id,))
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not row or not actor or (actor.id != row["user_id"] and not await permission_granted(interaction.guild, actor, "ticket_manage")):
        return await interaction.response.send_message("You are not authorized to export this ticket.", ephemeral=True)
    lines = [f"Manifest Ticket Transcript — #{interaction.channel.name}", f"Guild: {interaction.guild.name} ({interaction.guild.id})", f"Creator: {row['user_id']}", ""]
    async for msg in interaction.channel.history(limit=1000, oldest_first=True):
        stamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        content = msg.clean_content or "[attachment/embed/no text]"
        lines.append(f"[{stamp}] {msg.author} ({msg.author.id}): {content}")
    data = "\n".join(lines).encode("utf-8", "replace")
    await interaction.response.send_message("📄 Ticket transcript:", file=discord.File(io.BytesIO(data), filename=f"{interaction.channel.name}-transcript.txt"), ephemeral=True)


@ticket_group.command(name="claim_ticket", description="Claim the current ticket.")
async def claim_ticket(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel): return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id,))
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not row or not member: return await interaction.response.send_message("This is not a tracked ticket.", ephemeral=True)
    if not await permission_granted(interaction.guild, member, "ticket"): return await interaction.response.send_message("You need ticket-staff permission.", ephemeral=True)
    await db.execute("UPDATE tickets SET claimed_by=?,status='claimed' WHERE channel_id=?", (member.id,interaction.channel.id))
    await log_ticket_event(interaction.channel.id,member.id,"claimed")
    await interaction.response.send_message(f"🙋 Ticket claimed by {member.mention}.")


@ticket_group.command(name="ticket_rename", description="Rename the current ticket.")
async def ticket_rename(interaction: discord.Interaction, name: str):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel): return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id,))
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not row or not member or not await permission_granted(interaction.guild, member, "ticket_manage"): return await interaction.response.send_message("You are not authorized.", ephemeral=True)
    safe = re.sub(r"[^a-zA-Z0-9-]+", "-", name.strip().lower()).strip("-")[:80]
    if not safe: return await interaction.response.send_message("Invalid name.", ephemeral=True)
    await interaction.channel.edit(name=f"ticket-{safe}", reason=f"Manifest ticket rename by {member}")
    await log_ticket_event(interaction.channel.id,member.id,"renamed",safe)
    await interaction.response.send_message(f"✏️ Renamed to **ticket-{safe}**.")


@ticket_group.command(name="ticket_add", description="Add a member to the current ticket.")
async def ticket_add(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel): return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status NOT IN ('closed','orphaned')", (interaction.channel.id,))
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not row or not actor or not await permission_granted(interaction.guild,actor,"ticket_manage"): return await interaction.response.send_message("You are not authorized.", ephemeral=True)
    await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True)
    await log_ticket_event(interaction.channel.id,actor.id,"member_added",str(member.id))
    await interaction.response.send_message(f"➕ Added {member.mention} to the ticket.")


@ticket_group.command(name="ticket_remove", description="Remove a member from the current ticket.")
async def ticket_remove(interaction: discord.Interaction, member: discord.Member):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel): return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not actor or not await permission_granted(interaction.guild,actor,"ticket_manage"): return await interaction.response.send_message("You are not authorized.", ephemeral=True)
    await interaction.channel.set_permissions(member, overwrite=None)
    await log_ticket_event(interaction.channel.id,actor.id,"member_removed",str(member.id))
    await interaction.response.send_message(f"➖ Removed {member.mention} from the ticket.")


@ticket_group.command(name="close_ticket", description="Close the current ticket with a reason.")
async def close_ticket(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel): return await interaction.response.send_message("Use this inside a ticket.", ephemeral=True)
    await interaction.response.send_modal(TicketCloseModal())


@ticket_group.command(name="ticket_reopen", description="Reopen an archived Manifest ticket.")
async def ticket_reopen(interaction: discord.Interaction):
    if not interaction.guild or not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Use this inside an archived ticket.", ephemeral=True)
    row = await db.fetchone("SELECT * FROM tickets WHERE channel_id=? AND status='closed'", (interaction.channel.id,))
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not row or not actor:
        return await interaction.response.send_message("This is not an archived Manifest ticket.", ephemeral=True)
    if actor.id != row["user_id"] and not await permission_granted(interaction.guild, actor, "ticket_manage"):
        return await interaction.response.send_message("You are not authorized to reopen this ticket.", ephemeral=True)
    await db.execute("UPDATE tickets SET status='open',closed_at=0 WHERE channel_id=?", (interaction.channel.id,))
    base = interaction.channel.name.removeprefix("closed-")
    if not base.startswith("ticket-"):
        base = "ticket-" + base
    await interaction.channel.edit(name=base[:100], reason=f"Manifest ticket reopened by {actor}")
    await interaction.channel.set_permissions(actor, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
    me = interaction.guild.me
    if me:
        await interaction.channel.set_permissions(me, view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True, attach_files=True)
    support_role_id = int(await setting(interaction.guild_id, "ticket_support_role_id", 0) or 0)
    support_role = interaction.guild.get_role(support_role_id) if support_role_id else None
    if support_role:
        await interaction.channel.set_permissions(support_role, view_channel=True, send_messages=True, read_message_history=True, attach_files=True)
    await log_ticket_event(interaction.channel.id, actor.id, "reopened")
    await interaction.response.send_message(f"🔓 Ticket reopened by {actor.mention}.")


@developer_group.command(name="developer_team", description="Show Manifest's verified Global Developer Team.")
async def developer_team(interaction: discord.Interaction):
    if not is_developer(interaction.user):
        return await interaction.response.send_message("This developer-only information is restricted.", ephemeral=True)
    lines = [f"• <@{uid}> — **{role}** (`{uid}`)" for uid, role in DEVELOPER_TEAM.items()]
    await interaction.response.send_message("🛡️ **Verified Global Developer Team**\n" + "\n".join(lines), ephemeral=True)


@developer_group.command(name="developer_status", description="Show your verified Manifest authority.")
async def developer_status(interaction: discord.Interaction):
    role = developer_role(interaction.user)
    server = interaction.guild
    perms = getattr(interaction.user, "guild_permissions", None)
    text = f"**Identity:** {interaction.user.mention}\n**ID:** `{interaction.user.id}`\n**Developer Team:** `{role or 'No'}`"
    if server and perms:
        text += f"\n**Server owner:** `{interaction.user.id == server.owner_id}`\n**Administrator:** `{perms.administrator}`\n**Manage Server:** `{perms.manage_guild}`"
    await interaction.response.send_message(text, ephemeral=True)


@developer_group.command(name="personality", description="View or change Manifest's personality for this server.")
@app_commands.describe(value="Preset (professional/friendly/funny/strict/concise) or your own custom style")
async def personality(interaction: discord.Interaction, value: Optional[str] = None):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    if value is None:
        return await interaction.response.send_message(
            f"🎭 **Server personality**\n{await personality_text(interaction.guild.id)}\n\nOnly the server owner, Administrator/Manage Server members, or Manifest's verified Owner/Admin can change it.",
            ephemeral=True,
        )
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not member or not await permission_granted(interaction.guild, member, "settings"):
        return await interaction.response.send_message("⚠️ You need **Manage Server** or **Administrator** permission to change Manifest's personality.", ephemeral=True)
    presets = {
        "professional": "confident, professional, precise, calm, helpful, concise, and respectful",
        "friendly": "warm, friendly, upbeat, encouraging, conversational, and helpful",
        "funny": "witty, playful, energetic, clever, and humorous while staying useful and respectful",
        "strict": "firm, direct, organized, concise, rule-focused, and professional",
        "concise": "extremely concise, direct, practical, and clear; avoid unnecessary filler",
    }
    style = presets.get(value.strip().casefold(), value.strip())[:500]
    if not style:
        return await interaction.response.send_message("Give me a personality preset or a custom description.", ephemeral=True)
    await db.execute(
        "INSERT INTO guild_personality(guild_id,personality) VALUES(?,?) ON CONFLICT(guild_id) DO UPDATE SET personality=excluded.personality",
        (interaction.guild.id, style),
    )
    await interaction.response.send_message(f"🎭 **Server personality updated.**\nNew style: {style}", ephemeral=True)


@developer_group.command(name="global_remember", description="Save persistent memory about a user across servers.")
async def global_remember(interaction: discord.Interaction, member: discord.User, key: str, value: str):
    if not is_developer(interaction.user): return await interaction.response.send_message("Developer Team only.", ephemeral=True)
    key = re.sub(r"[^a-zA-Z0-9_-]", "_", key.strip())[:50]
    await remember_global_user(member.id,key,value.strip()[:1000])
    await interaction.response.send_message(f"🧠 Global memory saved for **{member}**: `{key}`", ephemeral=True)


@developer_group.command(name="global_memories", description="Show persistent global memories for a user.")
async def global_memories(interaction: discord.Interaction, member: Optional[discord.User] = None):
    target = member or interaction.user
    if member and not is_developer(interaction.user): return await interaction.response.send_message("Developer Team only for other users.", ephemeral=True)
    await interaction.response.send_message(clamp_text(await global_user_memories_text(target.id),1800), ephemeral=True)


@developer_group.command(name="global_forget", description="Remove persistent global memory about a user.")
async def global_forget(interaction: discord.Interaction, member: discord.User, key: str):
    if not is_developer(interaction.user): return await interaction.response.send_message("Developer Team only.", ephemeral=True)
    await db.execute("DELETE FROM global_user_memories WHERE user_id=? AND memory_key=?", (member.id,key.strip()))
    await interaction.response.send_message("🧠 Global memory removed.", ephemeral=True)


@developer_group.command(name="server_rule", description="Save or update a server rule/configuration.")
async def server_rule(interaction: discord.Interaction, key: str, value: str):
    if not interaction.guild: return await interaction.response.send_message("Server only.", ephemeral=True)
    member = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not member or not await permission_granted(interaction.guild,member,"settings"): return await interaction.response.send_message("You need server-management permission.", ephemeral=True)
    key = re.sub(r"[^a-zA-Z0-9_-]","_",key.strip())[:50]
    await db.execute("INSERT INTO server_rules(guild_id,rule_key,rule_value,created_at,updated_at) VALUES(?,?,?,?,?) ON CONFLICT(guild_id,rule_key) DO UPDATE SET rule_value=excluded.rule_value,updated_at=excluded.updated_at", (interaction.guild.id,key,value[:1500],now(),now()))
    await interaction.response.send_message(f"📜 Server rule saved: `{key}`", ephemeral=True)


@developer_group.command(name="server_rules", description="Show stored server rules/configuration.")
async def server_rules(interaction: discord.Interaction):
    if not interaction.guild: return await interaction.response.send_message("Server only.", ephemeral=True)
    await interaction.response.send_message(clamp_text(await server_rules_text(interaction.guild.id),1800), ephemeral=True)


@developer_group.command(name="manifest_permission", description="Grant or revoke a Manifest action to a role or user.")
async def manifest_permission(interaction: discord.Interaction, action: str, enabled: bool, role: Optional[discord.Role] = None, member: Optional[discord.Member] = None):
    if not interaction.guild: return await interaction.response.send_message("Server only.", ephemeral=True)
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not actor or not await permission_granted(interaction.guild,actor,"settings"): return await interaction.response.send_message("You need server-management permission.", ephemeral=True)
    if not role and not member: return await interaction.response.send_message("Choose a role or member.", ephemeral=True)
    role_id = role.id if role else 0; user_id = member.id if member else 0
    await db.execute("INSERT INTO command_permissions(guild_id,action_key,role_id,user_id,enabled) VALUES(?,?,?,?,?) ON CONFLICT(guild_id,action_key,role_id,user_id) DO UPDATE SET enabled=excluded.enabled", (interaction.guild.id,action.casefold()[:80],role_id,user_id,int(enabled)))
    target = role.mention if role else member.mention
    await interaction.response.send_message(f"🛡️ `{action}` permission for {target}: **{'ON' if enabled else 'OFF'}**", ephemeral=True)


@developer_group.command(name="ticket_setup", description="Configure the ticket category and support role in one command.")
async def ticket_setup(interaction: discord.Interaction, category: discord.CategoryChannel, support_role: discord.Role):
    if not interaction.guild: return await interaction.response.send_message("Server only.", ephemeral=True)
    actor = interaction.user if isinstance(interaction.user, discord.Member) else None
    if not actor or not await permission_granted(interaction.guild,actor,"settings"): return await interaction.response.send_message("You need server-management permission.", ephemeral=True)
    await set_setting(interaction.guild.id,"ticket_category_id",category.id); await set_setting(interaction.guild.id,"ticket_support_role_id",support_role.id)
    await interaction.response.send_message(f"🎫 Ticket system configured.\nCategory: {category.mention}\nSupport: {support_role.mention}", ephemeral=True)


@developer_group.command(name="server_dashboard", description="Show the server's Manifest configuration summary.")
async def server_dashboard(interaction: discord.Interaction):
    if not interaction.guild: return await interaction.response.send_message("Server only.", ephemeral=True)
    cat = interaction.guild.get_channel(int(await setting(interaction.guild.id,"ticket_category_id",0) or 0))
    role = interaction.guild.get_role(int(await setting(interaction.guild.id,"ticket_support_role_id",0) or 0))
    embed = discord.Embed(title="⚡ Manifest Server Dashboard", color=discord.Color.blurple())
    embed.add_field(name="Personality", value=await personality_text(interaction.guild.id), inline=False)
    embed.add_field(name="Ticket Category", value=cat.mention if cat else "Not configured")
    embed.add_field(name="Ticket Support", value=role.mention if role else "Not configured")
    embed.add_field(name="AI", value="ON" if await setting(interaction.guild.id,"ai_enabled",1) else "OFF")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# MODERATION
# ============================================================

@mod_group.command(name="warn", description="Warn a member.")
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


@mod_group.command(name="warnings", description="Show a member's warning count.")
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


@mod_group.command(name="timeout", description="Timeout a member.")
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


@mod_group.command(name="kick", description="Kick a member.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Manifest moderation"):
    if member.top_role >= interaction.user.top_role and not is_maker(interaction.user):
        return await interaction.response.send_message("Role hierarchy prevents this action.", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 Kicked **{member}** — `{reason}`")


@mod_group.command(name="ban", description="Ban a member.")
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


@mod_group.command(name="purge", description="Delete recent messages.")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted **{len(deleted)}** messages.", ephemeral=True)


@mod_group.command(name="lock", description="Lock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔒 Channel locked.")


@mod_group.command(name="unlock", description="Unlock the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)
    await interaction.response.send_message("🔓 Channel unlocked.")


@mod_group.command(name="slowmode", description="Set channel slowmode.")
@app_commands.checks.has_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]):
    if not isinstance(interaction.channel, discord.TextChannel):
        return await interaction.response.send_message("Text-channel only.", ephemeral=True)
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐢 Slowmode set to **{seconds}s**.")


# ============================================================
# ROLES / CHANNELS
# ============================================================

@mod_group.command(name="role", description="Add or remove a role from a member.")
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


@mod_group.command(name="create_channel", description="Create a text or voice channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def create_channel(interaction: discord.Interaction, name: str, kind: str = "text"):
    guild = interaction.guild
    if guild is None or not isinstance(interaction.user, discord.Member):
        return await interaction.response.send_message("This command only works inside a server.", ephemeral=True)
    if not interaction.user.guild_permissions.manage_channels:
        return await interaction.response.send_message("You need **Manage Channels** permission.", ephemeral=True)
    if not guild.me or not guild.me.guild_permissions.manage_channels:
        return await interaction.response.send_message("I need **Manage Channels** permission to create channels.", ephemeral=True)
    kind = kind.casefold().strip()
    safe_name = re.sub(r"[^a-zA-Z0-9_ -]", "", name).strip().replace(" ", "-")[:100].strip("-")
    if not safe_name:
        return await interaction.response.send_message("Give the channel a valid name.", ephemeral=True)
    try:
        if kind == "voice":
            channel = await guild.create_voice_channel(name=safe_name, reason=f"Requested by {interaction.user}")
        elif kind == "text":
            channel = await guild.create_text_channel(name=safe_name, reason=f"Requested by {interaction.user}")
        elif kind == "category":
            channel = await guild.create_category(name=safe_name, reason=f"Requested by {interaction.user}")
        elif kind == "forum":
            channel = await guild.create_forum(name=safe_name, reason=f"Requested by {interaction.user}")
        else:
            return await interaction.response.send_message("Channel type must be `text`, `voice`, `category`, or `forum`.", ephemeral=True)
        await interaction.response.send_message(f"🏗️ Created {channel.mention if hasattr(channel, 'mention') else channel.name} (`{kind}`).")
    except discord.Forbidden:
        await interaction.response.send_message("Discord denied channel creation. Check my role and Manage Channels permission.", ephemeral=True)
    except discord.HTTPException as exc:
        await interaction.response.send_message(f"Channel creation failed: `{clamp_text(str(exc), 300)}`", ephemeral=True)


# ============================================================
# REACTION ROLES
# ============================================================

@mod_group.command(name="reactionrole_add", description="Attach a reaction emoji to a role on an existing message.")
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


@mod_group.command(name="reactionrole_remove", description="Remove a reaction-role mapping.")
@app_commands.checks.has_permissions(manage_roles=True)
async def reactionrole_remove(interaction: discord.Interaction, message_id: str, emoji: str):
    await db.execute("DELETE FROM reaction_roles WHERE guild_id=? AND message_id=? AND emoji=?", (interaction.guild_id, int(message_id), emoji))
    await interaction.response.send_message("🎭 Reaction role mapping removed.", ephemeral=True)


@mod_group.command(name="reactionroles", description="List reaction-role mappings in this server.")
async def reactionroles(interaction: discord.Interaction):
    rows = await db.fetchall("SELECT message_id,emoji,role_id FROM reaction_roles WHERE guild_id=? ORDER BY message_id", (interaction.guild_id,))
    if not rows:
        return await interaction.response.send_message("No reaction roles configured.", ephemeral=True)
    text = "\n".join(f"`{r['message_id']}` {r['emoji']} → <@&{r['role_id']}>" for r in rows[:30])
    await interaction.response.send_message(text, ephemeral=True)


# ============================================================
# AUTOPILOT / SETTINGS
# ============================================================

@mod_group.command(name="autopilot", description="Enable or disable Manifest autonomous server monitoring.")
@server_manager_or_maker()
async def autopilot(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "autopilot", int(enabled))
    await interaction.response.send_message(
        f"⚡ Autopilot is now **{'ON' if enabled else 'OFF'}** for this server. "
        + ("Manifest will run its configured background security checks and server automations. This is not Discord server ownership; actions remain limited by bot permissions and role hierarchy." if enabled else "Autonomous server monitoring is paused; separately enabled features such as AI and Dead Chat may still run.")
    )


@mod_group.command(name="antinuke", description="Enable or disable audit-log anti-nuke monitoring.")
@server_manager_or_maker()
async def antinuke(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "antinuke_enabled", int(enabled))
    await interaction.response.send_message(
        f"🛡️ Anti-nuke audit monitoring is now **{'ON' if enabled else 'OFF'}**."
    )


@mod_group.command(name="ai_toggle", description="Enable or disable Manifest AI.")
@server_manager_or_maker()
async def ai_toggle(interaction: discord.Interaction, enabled: bool):
    await set_setting(interaction.guild_id, "ai_enabled", int(enabled))
    await interaction.response.send_message(f"🤖 AI is now **{'ON' if enabled else 'OFF'}.")


@mod_group.command(name="ai_channel", description="Restrict mention-triggered AI replies to one channel, or disable the restriction.")
@server_manager_or_maker()
@app_commands.describe(channel="Allowed AI channel; leave empty to turn the restriction off")
async def ai_channel(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
    await set_setting(interaction.guild_id, "ai_channel_id", channel.id if channel else 0)
    await set_setting(interaction.guild_id, "ai_channel_only", int(channel is not None))
    if channel:
        await interaction.response.send_message(f"🤖 AI replies are now restricted to {channel.mention} when Manifest is mentioned.", ephemeral=True)
    else:
        await interaction.response.send_message("🤖 AI channel restriction disabled. Manifest still replies only when mentioned.", ephemeral=True)


@mod_group.command(name="deadchat", description="Configure dead-chat revival.")
@server_manager_or_maker()
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


@mod_group.command(name="setlog", description="Set the bot's audit/log channel.")
@server_manager_or_maker()
async def setlog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_setting(interaction.guild_id, "log_channel_id", channel.id)
    await interaction.response.send_message(f"📋 Logs will be sent to {channel.mention}.")


@mod_group.command(name="setmessagelog", description="Set the channel for deleted/edited message logs.")
@server_manager_or_maker()
async def setmessagelog(interaction: discord.Interaction, channel: discord.TextChannel):
    await set_setting(interaction.guild_id, "message_log_channel_id", channel.id)
    await interaction.response.send_message(f"🧾 Edited and deleted messages will be logged in {channel.mention}.", ephemeral=True)


@mod_group.command(name="set_ticket_support", description="Set the ticket support role.")
@server_manager_or_maker()
async def set_ticket_support(interaction: discord.Interaction, role: discord.Role):
    await set_setting(interaction.guild_id, "ticket_support_role_id", role.id)
    await interaction.response.send_message(f"🎟️ Ticket support role set to {role.mention}.")


@mod_group.command(name="set_ticket_category", description="Set the ticket category.")
@server_manager_or_maker()
async def set_ticket_category(interaction: discord.Interaction, category: discord.CategoryChannel):
    await set_setting(interaction.guild_id, "ticket_category_id", category.id)
    await interaction.response.send_message(f"🎟️ Ticket category set to **{category.name}**.")


# ============================================================
# AUTOMOD
# ============================================================

@mod_group.command(name="badword_add", description="Add a restricted word.")
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


@mod_group.command(name="badword_remove", description="Remove a restricted word.")
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



@economy_group.command(name="balance", description="Show your wallet and bank.")
async def balance(interaction: discord.Interaction):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone(
        "SELECT wallet,bank FROM economy WHERE guild_id=? AND user_id=?",
        (interaction.guild_id, interaction.user.id),
    )
    await interaction.response.send_message(
        f"🪙 Wallet: **{row['wallet']}** | 🏦 Bank: **{row['bank']}**"
    )


@economy_group.command(name="beg", description="Earn a random amount of coins.")
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


@economy_group.command(name="daily", description="Claim a daily coin reward.")
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


@economy_group.command(name="deposit", description="Deposit coins into your bank.")
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

@utility_group.command(name="tag_create", description="Create or replace a server tag.")
@app_commands.checks.has_permissions(manage_guild=True)
async def tag_create(interaction: discord.Interaction, name: str, content: str):
    name = re.sub(r"[^a-zA-Z0-9_-]", "-", name.lower())[:32]
    await db.execute(
        """INSERT INTO tags(guild_id,name,content) VALUES(?,?,?)
           ON CONFLICT(guild_id,name) DO UPDATE SET content=excluded.content""",
        (interaction.guild_id, name, content[:1800]),
    )
    await interaction.response.send_message(f"🏷️ Tag `{name}` saved.")


@utility_group.command(name="tag", description="Use a server tag.")
async def tag(interaction: discord.Interaction, name: str):
    row = await db.fetchone(
        "SELECT content FROM tags WHERE guild_id=? AND name=?",
        (interaction.guild_id, name.lower()),
    )
    if not row:
        return await interaction.response.send_message("Tag not found.", ephemeral=True)
    await interaction.response.send_message(row["content"])


@utility_group.command(name="tag_delete", description="Delete a server tag.")
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

@utility_group.command(name="afk", description="Set your AFK status.")
async def afk(interaction: discord.Interaction, reason: str = "AFK"):
    await db.execute(
        """INSERT INTO afk(guild_id,user_id,reason,created_at) VALUES(?,?,?,?)
           ON CONFLICT(guild_id,user_id) DO UPDATE SET reason=excluded.reason,created_at=excluded.created_at""",
        (interaction.guild_id, interaction.user.id, reason[:300], now()),
    )
    await interaction.response.send_message(f"💤 AFK enabled: **{reason[:300]}**")


@utility_group.command(name="remind", description="Create a reminder in minutes.")
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


@utility_group.command(name="poll", description="Create a simple poll.")
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


# Prefix moderation commands. These are separate from slash commands and are
# dispatched by on_message above. All destructive commands check permissions.
@bot.command(name="purge", aliases=["clear", "clean"])
@commands.has_permissions(manage_messages=True)
async def prefix_purge(ctx: commands.Context, amount: int = 10):
    if not isinstance(ctx.channel, discord.TextChannel):
        return await ctx.reply("Text channels only.", mention_author=False)
    if not ctx.guild or not ctx.guild.me or not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        return await ctx.reply("I need **Manage Messages** permission.", mention_author=False)
    if amount < 1 or amount > 100:
        return await ctx.reply("Choose an amount from **1 to 100**.", mention_author=False)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1, reason=f"Purge requested by {ctx.author} ({ctx.author.id})")
        notice = await ctx.send(f"🧹 Deleted **{max(0, len(deleted)-1)}** messages.")
        await notice.delete(delay=5)
        await log_to_channel(ctx.guild, f"🧹 {ctx.author.mention} purged {max(0, len(deleted)-1)} messages in {ctx.channel.mention}.")
    except discord.Forbidden:
        await ctx.reply("Discord denied the purge. Check my **Manage Messages** and **Read Message History** permissions.", mention_author=False)
    except discord.HTTPException as exc:
        await ctx.reply(f"Purge failed: `{clamp_text(str(exc), 250)}`", mention_author=False)


@bot.command(name="purgebots", aliases=["clearbots"])
@commands.has_permissions(manage_messages=True)
async def prefix_purge_bots(ctx: commands.Context, amount: int = 100):
    if not isinstance(ctx.channel, discord.TextChannel):
        return await ctx.reply("Text channels only.", mention_author=False)
    if not ctx.guild or not ctx.guild.me or not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        return await ctx.reply("I need **Manage Messages** permission.", mention_author=False)
    if amount < 1 or amount > 100:
        return await ctx.reply("Choose an amount from **1 to 100**.", mention_author=False)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author.bot, reason=f"Bot-message purge requested by {ctx.author}")
        await ctx.send(f"🧹 Deleted **{len(deleted)}** bot messages.", delete_after=5)
    except discord.Forbidden:
        await ctx.reply("Discord denied the purge; check bot permissions.", mention_author=False)


@bot.command(name="purgeuser", aliases=["clearuser"])
@commands.has_permissions(manage_messages=True)
async def prefix_purge_user(ctx: commands.Context, member: discord.Member, amount: int = 100):
    if not isinstance(ctx.channel, discord.TextChannel):
        return await ctx.reply("Text channels only.", mention_author=False)
    if not ctx.guild or not ctx.guild.me or not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        return await ctx.reply("I need **Manage Messages** permission.", mention_author=False)
    if amount < 1 or amount > 100:
        return await ctx.reply("Choose an amount from **1 to 100**.", mention_author=False)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: m.author.id == member.id, reason=f"User-message purge requested by {ctx.author}")
        await ctx.send(f"🧹 Deleted **{len(deleted)}** messages from {member.mention}.", delete_after=5)
    except discord.Forbidden:
        await ctx.reply("Discord denied the purge; check bot permissions.", mention_author=False)


@bot.command(name="purgecontains", aliases=["clearcontains"])
@commands.has_permissions(manage_messages=True)
async def prefix_purge_contains(ctx: commands.Context, amount: int, *, phrase: str):
    if not isinstance(ctx.channel, discord.TextChannel):
        return await ctx.reply("Text channels only.", mention_author=False)
    if not ctx.guild or not ctx.guild.me or not ctx.channel.permissions_for(ctx.guild.me).manage_messages:
        return await ctx.reply("I need **Manage Messages** permission.", mention_author=False)
    if amount < 1 or amount > 100 or not phrase.strip():
        return await ctx.reply("Usage: `!purgecontains 50 phrase to find` (1–100 messages).", mention_author=False)
    try:
        deleted = await ctx.channel.purge(limit=amount + 1, check=lambda m: phrase.casefold() in m.content.casefold(), reason=f"Phrase purge requested by {ctx.author}")
        await ctx.send(f"🧹 Deleted **{len(deleted)}** messages containing that phrase.", delete_after=5)
    except discord.Forbidden:
        await ctx.reply("Discord denied the purge; check bot permissions.", mention_author=False)


@bot.command(name="level", aliases=["lvl", "rank"])
async def prefix_level(ctx: commands.Context, member: Optional[discord.Member] = None):
    if not ctx.guild: return
    member = member or ctx.author
    row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (ctx.guild.id, member.id))
    xp = int(row["xp"] if row else 0); lvl = int(row["level"] if row else 0)
    await ctx.send(f"📈 {member.mention} — **Level {lvl}** • **{xp:,} XP**")

@bot.command(name="leaderboard", aliases=["lb", "top"])
async def prefix_leaderboard(ctx: commands.Context):
    if not ctx.guild: return
    rows = await db.fetchall("SELECT user_id,xp,level FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (ctx.guild.id,))
    if not rows: return await ctx.send("No XP data yet.")
    await ctx.send("🏆 **All-Time XP Leaderboard**\n" + "\n".join(f"**#{i}** <@{r['user_id']}> — Level {r['level']} • {r['xp']:,} XP" for i,r in enumerate(rows,1)))

# ============================================================
# UTILITY / COMMUNITY COMMANDS
# ============================================================

@utility_group.command(name="ping", description="Check Manifest latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong — `{round(bot.latency * 1000)}ms`", ephemeral=True)


@stats_group.command(name="level", description="Show your or another member's XP level and progress.")
async def level(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (interaction.guild_id, member.id))
    xp = int(row["xp"] if row else 0)
    lvl = int(row["level"] if row else 0)
    current_base = xp_for_level(lvl)
    next_base = xp_for_level(lvl + 1)
    progress = max(0, xp - current_base)
    needed = max(1, next_base - current_base)
    rankrow = await db.fetchone("SELECT COUNT(*)+1 AS rank FROM levels WHERE guild_id=? AND xp>?", (interaction.guild_id, xp))
    rank = int(rankrow["rank"]) if rankrow else 1
    bars = min(10, int(progress / needed * 10))
    bar = "█" * bars + "░" * (10 - bars)
    await interaction.response.send_message(
        embed=discord.Embed(title=f"📈 {member.display_name}", description=f"**Level {lvl}** • Rank **#{rank}**\n`{bar}`\n**{progress:,} / {needed:,} XP** to Level {lvl + 1}\nTotal XP: **{xp:,}**", color=discord.Color.blurple()),
    )

@stats_group.command(name="reward_set", description="Set the role awarded when a member reaches an exact level.")
@server_manager_or_maker()
@app_commands.describe(level="Level that unlocks the role", role="Role to grant at that level")
async def reward_set(interaction: discord.Interaction, level: app_commands.Range[int, 1, 10000], role: discord.Role):
    guild = interaction.guild
    me = guild.me if guild else None
    if not guild or not me:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    if role.is_default() or role.managed or role >= me.top_role:
        return await interaction.response.send_message("I cannot grant that role. Put the reward role below Manifest's highest role and choose a normal, unmanaged role.", ephemeral=True)
    if not me.guild_permissions.manage_roles:
        return await interaction.response.send_message("I need **Manage Roles** to award level roles.", ephemeral=True)
    await db.execute(
        "INSERT INTO level_rewards(guild_id,level,role_id,created_at) VALUES(?,?,?,?) ON CONFLICT(guild_id,level) DO UPDATE SET role_id=excluded.role_id,created_at=excluded.created_at",
        (guild.id, level, role.id, now()),
    )
    await interaction.response.send_message(f"🏅 Level **{level}** now awards {role.mention}. Existing reward roles are not automatically removed.", ephemeral=True)


@stats_group.command(name="reward_remove", description="Remove the role reward for a level.")
@server_manager_or_maker()
async def reward_remove(interaction: discord.Interaction, level: app_commands.Range[int, 1, 10000]):
    await db.execute("DELETE FROM level_rewards WHERE guild_id=? AND level=?", (interaction.guild_id, level))
    await interaction.response.send_message(f"Removed the configured reward for level **{level}**, if one existed.", ephemeral=True)


@stats_group.command(name="rewards", description="List configured level-role rewards.")
async def rewards(interaction: discord.Interaction):
    rows = await db.fetchall("SELECT level,role_id FROM level_rewards WHERE guild_id=? ORDER BY level", (interaction.guild_id,))
    if not rows:
        return await interaction.response.send_message("No level rewards configured yet.", ephemeral=True)
    lines = []
    for row in rows[:25]:
        role = interaction.guild.get_role(int(row["role_id"])) if interaction.guild else None
        role_label = role.mention if role else f"Unavailable role (ID {int(row['role_id'])})"
        lines.append(f"Level **{row['level']}** → {role_label}")
    await interaction.response.send_message("🏅 **Level rewards**\n" + "\n".join(lines), ephemeral=True)


@stats_group.command(name="leaderboard", description="Show daily, weekly, monthly, or all-time XP rankings.")
@app_commands.choices(period=[app_commands.Choice(name="All-Time", value="all"), app_commands.Choice(name="Daily", value="daily"), app_commands.Choice(name="Weekly", value="weekly"), app_commands.Choice(name="Monthly", value="monthly")])
async def leaderboard(interaction: discord.Interaction, period: Optional[app_commands.Choice[str]] = None):
    selected = period.value if period else "all"
    if selected == "all":
        rows = await db.fetchall("SELECT user_id,xp,level FROM levels WHERE guild_id=? ORDER BY xp DESC LIMIT 10", (interaction.guild_id,))
        title = "🏆 All-Time XP Leaderboard"
        values = [(r["user_id"], r["xp"], r["level"]) for r in rows]
    else:
        rows = await activity_leaderboard(interaction.guild_id, selected, "xp")
        title = f"🏆 {selected.title()} XP Leaderboard"
        values = [(r["user_id"], r["value"], None) for r in rows]
    if not values:
        return await interaction.response.send_message("No XP data for this period yet.", ephemeral=True)
    medals = ["🥇", "🥈", "🥉"]
    text = "\n".join(f"{medals[i] if i < 3 else f'**#{i+1}**'} <@{uid}> — **{int(value):,} XP**" + (f" • Level {lvl}" if lvl is not None else "") for i,(uid,value,lvl) in enumerate(values))
    await interaction.response.send_message(embed=discord.Embed(title=title, description=text, color=discord.Color.gold()))


async def activity_leaderboard(guild_id: int, period: str, metric: str, limit: int = 10):
    start = period_start(now(), period)
    column = "messages" if metric == "messages" else "xp"
    rows = await db.fetchall(
        f"SELECT user_id,SUM({column}) AS value FROM activity_buckets WHERE guild_id=? AND bucket_type=? AND bucket_start=? GROUP BY user_id ORDER BY value DESC LIMIT ?",
        (guild_id, period, start, limit),
    )
    return rows

async def send_activity_board(interaction: discord.Interaction, period: str, metric: str):
    rows = await activity_leaderboard(interaction.guild_id, period, metric)
    label = "Messages" if metric == "messages" else "XP"
    if not rows:
        return await interaction.response.send_message(f"No {label.lower()} data for this {period} yet.", ephemeral=True)
    text = "\n".join(f"**#{i}** <@{r['user_id']}> — **{int(r['value']):,} {label}**" for i,r in enumerate(rows, 1))
    await interaction.response.send_message(embed=discord.Embed(title=f"📊 {period.title()} {label} Leaderboard", description=text, color=discord.Color.gold()))

@stats_group.command(name="messages", description="Show daily, weekly, monthly, or all-time message stats.")
@app_commands.describe(period="daily, weekly, monthly, or all")
@app_commands.choices(period=[app_commands.Choice(name="Daily", value="daily"), app_commands.Choice(name="Weekly", value="weekly"), app_commands.Choice(name="Monthly", value="monthly"), app_commands.Choice(name="All-Time", value="all")])
async def messages(interaction: discord.Interaction, period: app_commands.Choice[str]):
    if period.value == "all":
        rows = await db.fetchall("SELECT user_id,SUM(messages) AS value FROM activity_buckets WHERE guild_id=? AND bucket_type='all' GROUP BY user_id ORDER BY value DESC LIMIT 10", (interaction.guild_id,))
        title = "📊 All-Time Messages Leaderboard"
    else:
        rows = await activity_leaderboard(interaction.guild_id, period.value, "messages")
        title = f"📊 {period.name} Messages Leaderboard"
    if not rows:
        return await interaction.response.send_message("No message data yet.", ephemeral=True)
    text = "\n".join(f"**#{i}** <@{r['user_id']}> — **{int(r['value']):,} messages**" for i,r in enumerate(rows, 1))
    await interaction.response.send_message(embed=discord.Embed(title=title, description=text, color=discord.Color.blurple()))

@stats_group.command(name="stats", description="Show daily, weekly, monthly, or all-time activity for a member.")
@app_commands.choices(period=[app_commands.Choice(name="All-Time", value="all"), app_commands.Choice(name="Daily", value="daily"), app_commands.Choice(name="Weekly", value="weekly"), app_commands.Choice(name="Monthly", value="monthly")])
async def stats(interaction: discord.Interaction, member: Optional[discord.Member] = None, period: Optional[app_commands.Choice[str]] = None):
    member = member or interaction.user
    selected = period.value if period else "all"
    if selected == "all":
        row = await db.fetchone("SELECT COALESCE(SUM(messages),0) AS messages, COALESCE(SUM(xp),0) AS xp, COALESCE(SUM(invites),0) AS invites FROM activity_buckets WHERE guild_id=? AND user_id=? AND bucket_type='all'", (interaction.guild_id, member.id))
    else:
        start = period_start(now(), selected)
        row = await db.fetchone("SELECT COALESCE(messages,0) AS messages, COALESCE(xp,0) AS xp, COALESCE(invites,0) AS invites FROM activity_buckets WHERE guild_id=? AND user_id=? AND bucket_type=? AND bucket_start=?", (interaction.guild_id, member.id, selected, start))
    level_row = await db.fetchone("SELECT xp,level FROM levels WHERE guild_id=? AND user_id=?", (interaction.guild_id, member.id))
    messages_count = int(row["messages"] if row else 0)
    earned_xp = int(row["xp"] if row else 0)
    invites_count = int(row["invites"] if row else 0)
    lvl = int(level_row["level"] if level_row else 0)
    total_xp = int(level_row["xp"] if level_row else 0)
    await interaction.response.send_message(embed=discord.Embed(title=f"📊 {member.display_name} — {selected.title()} Stats", description=f"💬 Messages: **{messages_count:,}**\n✨ XP earned: **{earned_xp:,}**\n🤝 Invites: **{invites_count:,}**\n🏅 Current level: **{lvl}**\n📈 Total XP: **{total_xp:,}**", color=discord.Color.blurple()))

@stats_group.command(name="xpleaderboard", description="Show daily, weekly, monthly, or all-time XP rankings.")
@app_commands.choices(period=[app_commands.Choice(name="Daily", value="daily"), app_commands.Choice(name="Weekly", value="weekly"), app_commands.Choice(name="Monthly", value="monthly"), app_commands.Choice(name="All-Time", value="all")])
async def xpleaderboard(interaction: discord.Interaction, period: app_commands.Choice[str]):
    if period.value == "all":
        return await leaderboard(interaction)
    await send_activity_board(interaction, period.value, "xp")

@stats_group.command(name="invites", description="Show invite leaderboard, with daily/weekly/monthly/all-time periods.")
@app_commands.choices(period=[app_commands.Choice(name="Daily", value="daily"), app_commands.Choice(name="Weekly", value="weekly"), app_commands.Choice(name="Monthly", value="monthly"), app_commands.Choice(name="All-Time", value="all")])
async def invites(interaction: discord.Interaction, period: app_commands.Choice[str]):
    if period.value == "all":
        rows = await db.fetchall("SELECT inviter_id,uses AS value FROM invite_tracker WHERE guild_id=? ORDER BY uses DESC LIMIT 10", (interaction.guild_id,))
    else:
        start = period_start(now(), period.value)
        rows = await db.fetchall("SELECT inviter_id,SUM(invites) AS value FROM activity_buckets WHERE guild_id=? AND bucket_type=? AND bucket_start=? GROUP BY inviter_id ORDER BY value DESC LIMIT 10", (interaction.guild_id, period.value, start))
    if not rows:
        return await interaction.response.send_message("No invite data for this period yet.", ephemeral=True)
    text = "\n".join(f"**#{i}** <@{r['inviter_id']}> — **{int(r['value']):,} invites**" for i,r in enumerate(rows,1))
    await interaction.response.send_message(embed=discord.Embed(title=f"🤝 {period.name} Invite Leaderboard", description=text, color=discord.Color.green()))

@economy_group.command(name="withdraw", description="Withdraw coins from your bank.")
async def withdraw(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 1_000_000]):
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    row = await db.fetchone("SELECT bank,wallet FROM economy WHERE guild_id=? AND user_id=?", (interaction.guild_id, interaction.user.id))
    if amount > row['bank']:
        return await interaction.response.send_message("You don't have that much in your bank.", ephemeral=True)
    await db.execute("UPDATE economy SET bank=bank-?,wallet=wallet+? WHERE guild_id=? AND user_id=?", (amount,amount,interaction.guild_id,interaction.user.id))
    await interaction.response.send_message(f"🏦 Withdrew **{amount:,}** coins.")


@economy_group.command(name="transfer", description="Transfer coins to another member.")
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


@economy_group.command(name="work", description="Work for a random coin reward.")
async def work(interaction: discord.Interaction):
    if not bot.cooldown(interaction.guild_id, interaction.user.id, "work", 300):
        return await interaction.response.send_message("⏳ You can work again in a few minutes.", ephemeral=True)
    await ensure_wallet(interaction.guild_id, interaction.user.id)
    earned = random.randint(80, 250)
    await db.execute("UPDATE economy SET wallet=wallet+? WHERE guild_id=? AND user_id=?", (earned,interaction.guild_id,interaction.user.id))
    await interaction.response.send_message(f"💼 You worked and earned **{earned:,}** coins.")


@fun_group.command(name="coinflip", description="Flip a coin.")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 **{random.choice(['Heads','Tails'])}**")


@fun_group.command(name="roll", description="Roll a dice, such as 2d6 or 1d20.")
async def roll(interaction: discord.Interaction, dice: str = "1d20"):
    match = re.fullmatch(r"(\d{1,2})d(\d{1,4})", dice.lower().strip())
    if not match:
        return await interaction.response.send_message("Use a format like `2d6` or `1d20`.", ephemeral=True)
    count, sides = map(int, match.groups())
    if count > 20 or sides > 10000:
        return await interaction.response.send_message("Dice limit exceeded.", ephemeral=True)
    rolls = [random.randint(1,sides) for _ in range(count)]
    await interaction.response.send_message(f"🎲 `{dice}` → {rolls} = **{sum(rolls)}**")


@fun_group.command(name="rps", description="Play rock-paper-scissors against Manifest.")
@app_commands.choices(choice=[app_commands.Choice(name="Rock", value="rock"), app_commands.Choice(name="Paper", value="paper"), app_commands.Choice(name="Scissors", value="scissors")])
async def rps(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    bot_choice = random.choice(["rock", "paper", "scissors"])
    beats = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    if choice.value == bot_choice:
        result = "🤝 Draw!"
    elif beats[choice.value] == bot_choice:
        result = "🏆 You win!"
    else:
        result = "🤖 I win!"
    await interaction.response.send_message(f"🪨📄✂️ You: **{choice.value.title()}** • Manifest: **{bot_choice.title()}**\n{result}")

@fun_group.command(name="magic8", description="Ask Manifest's Magic 8-Ball a yes/no question.")
async def magic8(interaction: discord.Interaction, question: str):
    answers = ["Absolutely.", "Definitely not.", "Probably.", "Probably not.", "Ask again later.", "The signs point to yes.", "The signs point to no.", "Too close to call."]
    await interaction.response.send_message(f"🎱 **{random.choice(answers)}**")

@fun_group.command(name="choose", description="Choose one option for you.")
async def choose(interaction: discord.Interaction, options: str):
    values = [x.strip() for x in re.split(r"[,|]", options) if x.strip()]
    if len(values) < 2:
        return await interaction.response.send_message("Give me at least two choices separated by commas.", ephemeral=True)
    if len(values) > 20:
        return await interaction.response.send_message("Keep it to 20 choices or fewer.", ephemeral=True)
    await interaction.response.send_message(f"🎯 I choose: **{random.choice(values)[:200]}**")

@fun_group.command(name="scramble", description="Scramble a word or short phrase.")
async def scramble(interaction: discord.Interaction, text: str):
    chars = list(text.strip())
    if len(chars) < 2:
        return await interaction.response.send_message("Give me at least two characters.", ephemeral=True)
    random.shuffle(chars)
    await interaction.response.send_message(f"🔀 **{''.join(chars)[:500]}**")

@fun_group.command(name="trivia", description="Get a quick random trivia question.")
async def trivia(interaction: discord.Interaction):
    questions = [
        ("What is the largest planet in our solar system?", "Jupiter"),
        ("What is the chemical symbol for gold?", "Au"),
        ("How many sides does a hexagon have?", "6"),
        ("Which ocean is the largest?", "Pacific Ocean"),
        ("What is the capital of Japan?", "Tokyo"),
    ]
    question, answer = random.choice(questions)
    await interaction.response.send_message(f"🧠 **Trivia:** {question}\n||Answer: **{answer}**||")


@fun_group.command(name="rate", description="Give a playful, random rating for a topic or item.")
@app_commands.describe(thing="What should Manifest rate?")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(0, 100)
    await interaction.response.send_message(f"📊 **{thing[:150]}** gets **{score}/100** — just for fun, not a real assessment.")


@fun_group.command(name="iq", description="Get a playful random IQ-style score; not a real test.")
async def iq(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    score = random.randint(70, 150)
    await interaction.response.send_message(f"🧠 {member.mention}'s **fun IQ meter** says **{score}**. This is random entertainment, not a real IQ measurement.")


@fun_group.command(name="rizz", description="Get a playful rizz rating.")
async def rizz(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    score = random.randint(0, 100)
    labels = [(20, "warming up"), (45, "smooth-ish"), (70, "confident"), (90, "elite charm"), (100, "legendary smooth talk")]
    label = next(text for cap, text in labels if score <= cap)
    await interaction.response.send_message(f"😎 {member.mention}'s rizz rating: **{score}/100** — *{label}*. Just for fun!")


@fun_group.command(name="ship", description="A silly, non-serious compatibility score for two users.")
async def ship(interaction: discord.Interaction, first: discord.Member, second: discord.Member):
    score = random.randint(0, 100)
    await interaction.response.send_message(f"💞 {first.mention} + {second.mention}: **{score}%** compatibility (random joke score, not a real judgment).")


@utility_group.command(name="avatar", description="Show a member's avatar.")
async def avatar(interaction: discord.Interaction, member: Optional[discord.Member] = None):
    member = member or interaction.user
    await interaction.response.send_message(member.display_avatar.url)


@utility_group.command(name="help", description="Show Manifest's command categories and examples.")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="⚡ Manifest V11.1 Help", description="Commands are grouped so Manifest stays safely below Discord's global command limit.", color=discord.Color.blurple())
    embed.add_field(name="🤖 AI", value="`/chat` ` /ai` — Chat with Manifest AI\nMention `@Manifest` for natural conversation/actions.", inline=False)
    embed.add_field(name="🧠 Memory", value="`/memory remember` ` /memory memories` ` /memory forget` ` /memory clear_history`\nServer/Maker memory tools are also inside this category.", inline=False)
    embed.add_field(name="🎵 Music", value="`/music play` ` /music pause` ` /music resume` ` /music skip` ` /music queue` ` /music nowplaying` ` /music shuffle` ` /music remove` ` /music volume` ` /music leave`\nPublic URLs and text searches use standalone FFmpeg + yt-dlp; no Lavalink required.", inline=False)
    embed.add_field(name="🛡️ Moderation", value="`/mod warn` ` /mod timeout` ` /mod kick` ` /mod ban` ` /mod purge` ` /mod lock` ` /mod unlock` ` /mod slowmode` ` /mod role`", inline=False)
    embed.add_field(name="🎫 Tickets", value="`/ticket create` ` /ticket panel` ` /ticket claim_ticket` ` /ticket ticket_add` ` /ticket ticket_remove` ` /ticket ticket_rename` ` /ticket close_ticket` ` /ticket ticket_reopen` ` /ticket transcript`", inline=False)
    embed.add_field(name="🎭 Fun", value="`/fun coinflip` ` /fun roll` ` /fun rps` ` /fun magic8` ` /fun choose` ` /fun scramble` ` /fun trivia` ` /fun rate` ` /fun iq` ` /fun rizz` ` /fun ship`", inline=False)
    embed.add_field(name="📚 Server Brain", value="`/knowledge add` (Manage Server) saves a verified answer and optional source link; `/knowledge search` lets members find saved answers; `/knowledge remove` removes a card.", inline=False)
    embed.add_field(name="🧹 Prefix Purge", value="`!purge [amount]` `!purgebots [amount]` `!purgeuser @member [amount]` `!purgecontains [amount] phrase` — requires Manage Messages.", inline=False)
    embed.add_field(name="💰 Economy", value="`/economy balance` ` /economy daily` ` /economy beg` ` /economy work` ` /economy deposit` ` /economy withdraw` ` /economy transfer`", inline=False)
    embed.add_field(name="📊 Stats & Utilities", value="`/stats level` ` /stats leaderboard` ` /stats messages` ` /stats stats` ` /stats invites`\n`/utility serverinfo` ` /utility userinfo` ` /utility avatar` ` /utility poll` ` /utility remind` ` /utility afk`", inline=False)
    embed.add_field(name="⚙️ Server / AI settings", value="`/developer personality` — server owner/Admin/Manage Server can change Manifest's personality.\n`/developer server_dashboard` and other configuration commands are grouped here.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ============================================================
# MAKER / SERVER CONTROL
# ============================================================

@developer_group.command(name="maker", description="Show the configured Maker identity.")
@maker_only()
async def maker(interaction: discord.Interaction):
    await interaction.response.send_message(
        f"👑 **Maker:** <@{MAKER_USER_ID}>\n"
        "Manifest recognizes the Maker by immutable Discord user ID. "
        "It does not rely on usernames, nicknames, or display names."
    )


@utility_group.command(name="say", description="Send a message as the bot.")
@maker_only()
async def say(
    interaction: discord.Interaction,
    message: str,
    channel: Optional[discord.TextChannel] = None,
):
    target = channel or interaction.channel
    await target.send(message[:2000])
    await interaction.response.send_message("✅ Sent.", ephemeral=True)


@utility_group.command(name="export_config", description="Export safe Manifest settings.")
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


@utility_group.command(name="diagnostics", description="Run Manifest's live configuration diagnostics.")
async def diagnostics(interaction: discord.Interaction):
    if not interaction.guild:
        return await interaction.response.send_message("Server only.", ephemeral=True)
    me = interaction.guild.me
    ffmpeg_path = ffmpeg_executable()
    try:
        import yt_dlp  # noqa: F401
        ytdlp_available = True
    except Exception:
        ytdlp_available = False
    ffmpeg_available = bool(ffmpeg_path and Path(ffmpeg_path).is_file() and os.access(ffmpeg_path, os.X_OK))
    checks = {
        "Discord connection": bot.is_ready(),
        "AI key configured": bool(groq),
        "Message Content intent enabled in code": intents.message_content,
        "Member intent enabled in code": intents.members,
        "Voice intent enabled in code": intents.voice_states,
        "Manage Channels": bool(me and me.guild_permissions.manage_channels),
        "yt-dlp import available": ytdlp_available,
        "FFmpeg executable found": ffmpeg_available,
        "Ticket category configured": bool(await setting(interaction.guild.id, "ticket_category_id", 0)),
        "Ticket support role configured": bool(await setting(interaction.guild.id, "ticket_support_role_id", 0)),
    }
    lines = [f"{'✅' if ok else '❌'} {name}" for name, ok in checks.items()]
    await interaction.response.send_message("🔧 **Manifest Diagnostics**\n" + "\n".join(lines), ephemeral=True)


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
    # Liveness only: Render can reach this even while Discord's gateway is down.
    # /ready is the readiness endpoint and returns 503 until the gateway is ready.
    discord_ready = bot.is_ready()
    return web.json_response({
        "status": "online" if discord_ready else "degraded",
        "process_alive": True,
        "discord_ready": discord_ready,
        "service": f"Manifest V{VERSION}",
        "time": int(time.time()),
    })


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/ready", lambda request: web.json_response({"status":"ready" if bot.is_ready() else "starting","discord_ready":bot.is_ready()}, status=200 if bot.is_ready() else 503))
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
    delay = 5
    try:
        # Login only once. Calling bot.start() repeatedly attempts a second login
        # on the same Client after a connection exception and can leave Render's
        # process alive while Discord remains offline. connect() is the retryable
        # gateway layer once login/setup_hook have succeeded.
        await bot.login(TOKEN)
        while not bot.is_closed():
            try:
                await bot.connect(reconnect=True)
                if bot.is_closed():
                    break
                log.error("Discord connect() returned while the client was open; retrying in %ss.", delay)
            except (discord.LoginFailure, discord.PrivilegedIntentsRequired):
                # These require credential or Developer Portal configuration changes.
                raise
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Discord gateway connection failed; retrying in %ss.", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 120)
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
