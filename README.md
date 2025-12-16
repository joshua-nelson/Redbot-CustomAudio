# Muse Music Cog (Lavalink)

Hybrid slash/prefix music controls that mirror the Muse UX while delegating all audio work to a dedicated Lavalink node.

## Getting started

1. **Install the cog**
   * Place the `muse_music` folder in a repo you load into Red or drop it into your local cogs path.
   * Load it with `[p]load muse_music`.

2. **Lavalink connection**
   * This cog connects directly to a Lavalink node at `localhost:2333` with the password `youshallnotpass`—no Audio cog required.
   * Make sure your Lavalink server is running with those credentials; adjust `LavalinkManager` in `muse_music/cog.py` if you host elsewhere.

3. **Use the commands**
   * Commands are namespaced under `/muse` so they can coexist with Red's built-in Audio cog (no need to unload it). Examples:
     * `/muse play`, `/muse pause`, `/muse resume`, `/muse skip`, `/muse stop`, `/muse queue`, `/muse nowplaying`, `/muse loop`, `/muse remove`, `/muse move`, `/muse clear`, `/muse volume`, `/muse autoplay`, `/muse maxqueue` — all require you to be in a voice channel.
   * `/muse play` includes autocomplete for YouTube/SoundCloud searches; it never alters playback until you submit the command.

4. **Autoplay & limits**
   * Toggle related-track autoplay with `/muse autoplay true|false`.
   * Restrict queue size per guild with `/muse maxqueue <size>`.

All playback, decoding, and streaming stay inside Lavalink; the cog only orchestrates commands, queues, and embeds.
