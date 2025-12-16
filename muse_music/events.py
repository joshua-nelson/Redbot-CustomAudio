from __future__ import annotations

import logging
from typing import Any

import discord
from redbot.core import commands

from .player import PlayerController, LoopMode

log = logging.getLogger("red.muse_music.events")


class LavalinkEvents:
    """Event bridge between Lavalink and guild players."""

    def __init__(self, controller: PlayerController):
        self.controller = controller

    async def track_start(self, event: Any) -> None:
        log.info("Track started in guild %s", event.guild_id)

    async def track_end(self, event: Any) -> None:
        try:
            guild = event.player.guild_id if hasattr(event, "player") else event.guild_id
        except Exception:
            guild = getattr(event, "guild_id", None)
        if guild is None:
            return
        try:
            player = await self.controller.get_player(discord.Object(id=guild))
            next_track = await player.on_track_end(getattr(event, "reason", ""))
            if not next_track:
                await player.stop()
                return
            # attempt to resume playback in the same channel
            voice_channel_id = getattr(event.player, "channel_id", None)
            if voice_channel_id:
                voice_channel = discord.Object(id=voice_channel_id)
                try:
                    await player.start_playback(voice_channel, next_track)  # type: ignore[arg-type]
                except commands.UserFeedbackCheckFailure:
                    log.warning("Failed to start next track in guild %s", guild)
        except Exception:
            log.exception("Error handling track end for guild %s", guild)

    async def player_update(self, event: Any) -> None:
        # Placeholder for progress tracking in the future
        return

    async def connect(self) -> None:
        try:
            from redbot.cogs.audio import lavalink
        except ImportError:
            log.warning("Lavalink is not available; event handlers not attached.")
            return
        lavalink.add_event_hooks(
            self.track_start,
            self.track_end,
            self.player_update,
        )
        log.info("Muse music Lavalink listeners registered.")

    async def disconnect(self) -> None:
        try:
            from redbot.cogs.audio import lavalink
        except ImportError:
            return
        lavalink.remove_event_hooks(
            self.track_start,
            self.track_end,
            self.player_update,
        )
