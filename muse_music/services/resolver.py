from __future__ import annotations

import asyncio
import logging
import re
from time import monotonic
from typing import List, Optional

import discord
from discord import app_commands
from redbot.core import commands

from ..lavalink_manager import LavalinkManager
from ..models import Track

log = logging.getLogger("red.muse_music.resolver")

URL_RE = re.compile(r"https?://")


class TimedCache:
    def __init__(self, ttl: float = 8.0, maxsize: int = 32):
        self.ttl = ttl
        self.maxsize = maxsize
        self._cache = {}

    def _prune(self) -> None:
        now = monotonic()
        self._cache = {k: v for k, v in self._cache.items() if now - v[0] < self.ttl}
        while len(self._cache) > self.maxsize:
            self._cache.pop(next(iter(self._cache)))

    def get(self, key: str) -> Optional[List[Track]]:
        self._prune()
        if key in self._cache:
            return self._cache[key][1]
        return None

    def set(self, key: str, value: List[Track]) -> None:
        self._prune()
        self._cache[key] = (monotonic(), value)


class ResolverService:
    """Resolves user queries to Lavalink tracks without enqueuing."""

    def __init__(self, lavalink: LavalinkManager):
        self.lavalink = lavalink
        self.cache = TimedCache(ttl=10.0, maxsize=64)
        self.lock = asyncio.Lock()

    async def search(self, query: str, requester: discord.Member) -> List[Track]:
        cached = self.cache.get(query)
        if cached:
            return cached
        await self.lavalink.wait_ready()
        node = self.lavalink.get_node()
        if node is None:
            raise commands.UserFeedbackCheckFailure("No Lavalink nodes are configured.")
        results = await node.get_tracks(query)
        tracks: List[Track] = []
        for data in results.get("tracks", [])[:25]:
            tracks.append(Track.from_lavalink(data, requester.id))
        self.cache.set(query, tracks)
        return tracks

    async def autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        if len(current) < 2:
            return []
        if not interaction.user or not getattr(interaction.user, "voice", None) or not interaction.user.voice.channel:
            return []
        if URL_RE.match(current):
            return [app_commands.Choice(name=current[:100], value=current)]
        prefix, query = self._parse_prefix(current)
        search_query = f"{prefix}{query}"
        try:
            results = await self.search(search_query, interaction.user)  # type: ignore[arg-type]
        except Exception:
            return []
        choices: List[app_commands.Choice[str]] = []
        for track in results[:25]:
            title = track.title
            duration = self._format_duration(track.duration)
            name = f"{title} ({duration})"
            choices.append(app_commands.Choice(name=name[:100], value=track.uri or track.title))
        return choices

    def _format_duration(self, duration_ms: int) -> str:
        seconds = duration_ms // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    def _parse_prefix(self, query: str) -> tuple[str, str]:
        lowered = query.lower()
        if lowered.startswith("yt:"):
            return "ytsearch:", query[3:].strip()
        if lowered.startswith("sc:"):
            return "scsearch:", query[3:].strip()
        return "ytsearch:", query
