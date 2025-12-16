from __future__ import annotations

import logging
from typing import Optional

import discord

from ..models import Track
from .resolver import ResolverService

log = logging.getLogger("red.muse_music.autoplay")


class AutoplayService:
    """Optional related-track enqueueing when queues end."""

    def __init__(self, resolver: ResolverService):
        self.resolver = resolver

    async def maybe_autoplay(self, *, last_track: Optional[Track], requester: discord.Member) -> Optional[Track]:
        if not last_track:
            return None
        query = f"ytsearch:{last_track.title}"
        try:
            results = await self.resolver.search(query, requester)
        except Exception:
            log.debug("Autoplay search failed", exc_info=True)
            return None
        return results[0] if results else None
