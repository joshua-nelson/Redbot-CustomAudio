from __future__ import annotations

import asyncio
from enum import Enum
from typing import Deque, Dict, List, Optional
from collections import deque

import discord
from discord.abc import Snowflake
from redbot.core import Config, commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import humanize_timedelta

from .lavalink_manager import LavalinkManager
from .models import Track


class LoopMode(str, Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"


class GuildPlayer:
    """Stateful queue and playback controller for a single guild."""

    def __init__(self, bot: Red, guild_id: int, config: Config, lavalink: LavalinkManager):
        self.bot = bot
        self.guild_id = guild_id
        self.config = config
        self.lavalink = lavalink
        self.queue: Deque[Track] = deque()
        self.current: Optional[Track] = None
        self.loop_mode: LoopMode = LoopMode.OFF
        self.default_volume: int = 100
        self.autoplay_enabled: bool = False
        self.max_queue_length: int = 200
        self.lock = asyncio.Lock()

    async def load(self) -> None:
        settings = await self.config.guild_from_id(self.guild_id).all()
        self.loop_mode = LoopMode(settings.get("loop_mode", LoopMode.OFF.value))
        self.default_volume = int(settings.get("default_volume", 100))
        self.autoplay_enabled = bool(settings.get("autoplay", False))
        self.max_queue_length = int(settings.get("max_queue_length", 200))
        for payload in settings.get("queue", []):
            self.queue.append(Track.from_dict(payload))

    async def persist(self) -> None:
        await self.config.guild_from_id(self.guild_id).queue.set([t.to_dict() for t in self.queue])
        await self.config.guild_from_id(self.guild_id).loop_mode.set(self.loop_mode.value)

    async def enqueue(self, track: Track) -> None:
        if len(self.queue) >= self.max_queue_length:
            raise commands.UserFeedbackCheckFailure("Queue is full for this server.")
        self.queue.append(track)
        await self.persist()

    def peek(self) -> Optional[Track]:
        if self.queue:
            return self.queue[0]
        return None

    def pop_next(self) -> Optional[Track]:
        if self.queue:
            return self.queue.popleft()
        return None

    async def remove(self, index: int) -> Track:
        if index < 1 or index > len(self.queue):
            raise commands.UserFeedbackCheckFailure("Index is out of range for the queue.")
        # convert to list for safe removal
        queue_list: List[Track] = list(self.queue)
        track = queue_list.pop(index - 1)
        self.queue = deque(queue_list)
        await self.persist()
        return track

    async def move(self, start: int, end: int) -> None:
        if start < 1 or start > len(self.queue) or end < 1 or end > len(self.queue):
            raise commands.UserFeedbackCheckFailure("Positions must be within the queue range.")
        queue_list: List[Track] = list(self.queue)
        track = queue_list.pop(start - 1)
        queue_list.insert(end - 1, track)
        self.queue = deque(queue_list)
        await self.persist()

    async def clear(self) -> None:
        self.queue.clear()
        await self.persist()

    async def set_loop(self, mode: LoopMode) -> None:
        self.loop_mode = mode
        await self.persist()

    async def on_track_end(self, reason: str) -> tuple[Optional[Track], Optional[Track]]:
        finished = self.current
        self.current = None
        await self.config.guild_from_id(self.guild_id).current.clear()

        if finished is None:
            return None, None

        next_track: Optional[Track] = None
        if self.loop_mode == LoopMode.TRACK:
            next_track = finished
        elif self.loop_mode == LoopMode.QUEUE:
            self.queue.append(finished)
            next_track = self.pop_next()
        else:
            next_track = self.pop_next()

        await self.persist()
        return finished, next_track

    async def start_playback(self, voice_channel: discord.abc.Snowflake | int, track: Track) -> None:
        """Start playback for the provided track through Lavalink."""
        player = await self._get_lavalink_player(voice_channel=voice_channel)
        self.current = track
        await player.set_volume(self.default_volume)
        await player.play(track.lavalink_track, start_time=0)
        await self.config.guild_from_id(self.guild_id).current.set(track.to_dict())

    async def maybe_start_next(self, voice_channel: discord.abc.Snowflake | int) -> Optional[Track]:
        if self.current:
            return self.current
        next_track = self.pop_next()
        if next_track:
            await self.persist()
            await self.start_playback(voice_channel, next_track)
            return next_track
        return None

    async def stop(self) -> None:
        player = await self._get_lavalink_player()
        if player:
            await player.stop()
        self.current = None
        await self.config.guild_from_id(self.guild_id).current.clear()

    async def set_pause(self, paused: bool) -> None:
        player = await self._get_lavalink_player()
        if player:
            await player.set_pause(paused)

    async def set_volume(self, level: int) -> None:
        player = await self._get_lavalink_player()
        if not player:
            raise commands.UserFeedbackCheckFailure("Nothing is playing right now.")
        await player.set_volume(level)
        self.default_volume = level
        await self.config.guild_from_id(self.guild_id).default_volume.set(level)

    async def _get_lavalink_player(self, voice_channel: Optional[discord.abc.Snowflake | int] = None):
        if voice_channel is not None:
            channel_id = voice_channel if isinstance(voice_channel, int) else voice_channel.id
            try:
                await self.lavalink.connect(self.guild_id, channel_id)
            except Exception:
                raise commands.UserFeedbackCheckFailure("Unable to connect to the voice channel or Lavalink.")
        try:
            return await self.lavalink.get_player(self.guild_id)
        except Exception:
            raise commands.UserFeedbackCheckFailure("Lavalink is not available on this bot.")

    def progress_bar(self, position_ms: int) -> str:
        if not self.current:
            return "[—————]"
        length = max(self.current.duration, 1)
        proportion = min(max(position_ms / length, 0), 1)
        filled = int(proportion * 10)
        return "[" + "▮" * filled + "—" * (10 - filled) + "]"  # simple textual bar

    def format_track(self, track: Track) -> str:
        duration = humanize_timedelta(seconds=track.duration / 1000)
        return f"{track.title} • {duration}"


class PlayerController:
    """Manages GuildPlayer instances for the cog."""

    def __init__(self, bot: Red, config: Config, lavalink: LavalinkManager):
        self.bot = bot
        self.config = config
        self.players: Dict[int, GuildPlayer] = {}
        self.lavalink = lavalink

    async def get_player(self, guild: Snowflake) -> GuildPlayer:
        if guild.id not in self.players:
            player = GuildPlayer(self.bot, guild.id, self.config, self.lavalink)
            await player.load()
            self.players[guild.id] = player
        return self.players[guild.id]

    async def teardown(self) -> None:
        self.players.clear()

