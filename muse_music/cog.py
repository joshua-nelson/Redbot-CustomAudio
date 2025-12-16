from __future__ import annotations

import logging
from typing import Optional

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

from .embeds import now_playing_embed, queue_page_embed
from .events import LavalinkEvents
from .models import Track
from .player import LoopMode, PlayerController
from .services.autoplay import AutoplayService
from .services.resolver import ResolverService

log = logging.getLogger("red.muse_music")


class MuseMusic(commands.Cog):
    """Muse-inspired music controller built on Lavalink."""

    default_guild = {
        "queue": [],
        "loop_mode": LoopMode.OFF.value,
        "default_volume": 100,
        "autoplay": False,
        "max_queue_length": 200,
        "dj_role": None,
        "current": {},
    }

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xA11CE, force_registration=True)
        self.config.register_guild(**self.default_guild)
        self.resolver = ResolverService()
        self.player_controller = PlayerController(bot, self.config)
        self.autoplay = AutoplayService(self.resolver)
        self.events = LavalinkEvents(self.player_controller, self.autoplay, bot)

    async def cog_load(self) -> None:
        await self.events.connect()

    async def cog_unload(self) -> None:
        await self.events.disconnect()
        await self.player_controller.teardown()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # enforce voice channel presence for slash invocations
        if not interaction.user or not getattr(interaction.user, "voice", None):
            await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
            return False
        return True

    async def _ensure_voice(self, ctx: commands.Context) -> Optional[discord.VoiceChannel]:
        channel = getattr(ctx.author.voice, "channel", None)
        if not channel:
            await ctx.send("You need to be in a voice channel to use music commands.")
            return None
        return channel

    async def _resolve_track(self, ctx: commands.Context, query: str) -> Track:
        prefix, adjusted = self.resolver._parse_prefix(query)
        search_query = query if query.startswith("http") else f"{prefix}{adjusted}"
        tracks = await self.resolver.search(search_query, ctx.author)
        if not tracks:
            raise commands.UserFeedbackCheckFailure("No results were found for that query.")
        return tracks[0]

    @commands.hybrid_group(name="muse", invoke_without_command=True)
    async def muse(self, ctx: commands.Context) -> None:
        """Muse-style music controls that run on Lavalink."""
        if ctx.interaction:
            await ctx.send("Use one of the subcommands, e.g. `/muse play <song>`.")
        else:
            await ctx.send_help()

    @muse.command(name="play", description="Play a track or playlist using Lavalink.")
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Queue a new track from a query or URL."""
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        async with ctx.typing():
            try:
                track = await self._resolve_track(ctx, query)
                player = await self.player_controller.get_player(ctx.guild)
                await player.enqueue(track)
            except commands.UserFeedbackCheckFailure as exc:
                await ctx.send(str(exc))
                return
            await ctx.send(f"Enqueued **{track.title}**.")
            if not player.current:
                try:
                    await player.maybe_start_next(channel)
                except commands.UserFeedbackCheckFailure as exc:
                    await ctx.send(str(exc))

    @muse.command(name="pause")
    async def pause(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.set_pause(True)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Paused playback.")

    @muse.command(name="resume")
    async def resume(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.set_pause(False)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Resumed playback.")

    @muse.command(name="skip")
    async def skip(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.stop()
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Skipped the current track.")

    @muse.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.stop()
            await player.clear()
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Stopped playback and cleared the queue.")

    @muse.command(name="queue")
    async def queue(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        embed = queue_page_embed(player, page=0)
        await ctx.send(embed=embed)

    @muse.command(name="nowplaying")
    async def nowplaying(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        embed = now_playing_embed(player, position=0)
        await ctx.send(embed=embed)

    @muse.command(name="loop")
    async def loop(self, ctx: commands.Context, mode: Optional[str] = None) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        if mode:
            try:
                target_mode = LoopMode(mode.lower())
            except ValueError:
                await ctx.send("Loop mode must be one of: off, track, queue.")
                return
        else:
            target_mode = LoopMode.OFF
        try:
            await player.set_loop(target_mode)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Loop mode set to **{target_mode.value}**.")

    @muse.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            track = await player.remove(index)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Removed **{track.title}** from the queue.")

    @muse.command(name="move")
    async def move(self, ctx: commands.Context, start: int, end: int) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.move(start, end)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Moved track from position {start} to {end}.")

    @muse.command(name="clear")
    async def clear(self, ctx: commands.Context) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.clear()
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send("Cleared the queue.")

    @muse.command(name="volume")
    async def volume(self, ctx: commands.Context, level: int) -> None:
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        if level < 0 or level > 150:
            await ctx.send("Volume must be between 0 and 150.")
            return
        player = await self.player_controller.get_player(ctx.guild)
        try:
            await player.set_volume(level)
        except commands.UserFeedbackCheckFailure as exc:
            await ctx.send(str(exc))
            return
        await ctx.send(f"Volume set to {level}.")

    @muse.command(name="autoplay")
    async def autoplay(self, ctx: commands.Context, enabled: bool) -> None:
        """Toggle autoplay for when the queue ends."""
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        player = await self.player_controller.get_player(ctx.guild)
        player.autoplay_enabled = enabled
        await self.config.guild(ctx.guild).autoplay.set(enabled)
        await ctx.send(f"Autoplay {'enabled' if enabled else 'disabled'}.")

    @muse.command(name="maxqueue")
    @commands.admin_or_permissions(manage_guild=True)
    async def maxqueue(self, ctx: commands.Context, size: int) -> None:
        """Set the maximum queue length for this server."""
        channel = await self._ensure_voice(ctx)
        if not channel:
            return
        if size < 1 or size > 1000:
            await ctx.send("Queue size must be between 1 and 1000.")
            return
        player = await self.player_controller.get_player(ctx.guild)
        player.max_queue_length = size
        await self.config.guild(ctx.guild).max_queue_length.set(size)
        await ctx.send(f"Max queue size set to {size}.")

    @play.autocomplete("query")
    async def _play_autocomplete(self, interaction: discord.Interaction, current: str):
        return await self.resolver.autocomplete(interaction, current)


async def setup(bot: Red) -> None:
    await bot.add_cog(MuseMusic(bot))
