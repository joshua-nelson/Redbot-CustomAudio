from __future__ import annotations

import discord
from redbot.core.utils.chat_formatting import humanize_timedelta

from .models import Track
from .player import GuildPlayer


def now_playing_embed(player: GuildPlayer, position: int = 0) -> discord.Embed:
    track = player.current
    embed = discord.Embed(title="Now Playing")
    if not track:
        embed.description = "Nothing is playing right now."
        return embed

    duration = humanize_timedelta(seconds=track.duration / 1000)
    progress = player.progress_bar(position)
    embed.description = f"**{track.title}**\n{progress} `{duration}`"
    embed.add_field(name="Source", value=track.source, inline=True)
    embed.add_field(name="Requester", value=f"<@{track.requester_id}>", inline=True)
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)
    return embed


def queue_page_embed(player: GuildPlayer, page: int = 0, per_page: int = 10) -> discord.Embed:
    entries = list(player.queue)
    start = page * per_page
    end = start + per_page
    embed = discord.Embed(title="Queue")
    if player.current:
        embed.add_field(
            name="Now Playing",
            value=f"**{player.current.title}** ({humanize_timedelta(seconds=player.current.duration / 1000)})",
            inline=False,
        )
    if not entries:
        embed.description = "Queue is empty."
        return embed

    lines = []
    for idx, track in enumerate(entries[start:end], start=start + 1):
        duration = humanize_timedelta(seconds=track.duration / 1000)
        lines.append(f"`{idx}.` **{track.title}** • {duration} • <@{track.requester_id}>")
    embed.description = "\n".join(lines)
    total_pages = max(1, (len(entries) - 1) // per_page + 1)
    embed.set_footer(text=f"Page {page + 1}/{total_pages} • {len(entries)} tracks queued")
    return embed
