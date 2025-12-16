# Muse Music Cog (Lavalink)

Hybrid slash/prefix music controls that mirror the Muse UX while delegating all audio work to Red's built-in Lavalink client.

## Getting started

1. **Install the cog**
   * Place the `muse_music` folder in a repo you load into Red or drop it into your local cogs path.
   * Load it with `[p]load muse_music`.

2. **Point Red at your Lavalink node**
   * Use Red's Audio/Lavalink setup commands (e.g., `[p]audioset node add mynode http://<host>:2333 youshallnotpass us` followed by `[p]audioset node switch mynode`).
   * Ensure the port/password match your Lavalink server (for example, port `2333` and password `youshallnotpass`).

3. **Use the commands**
   * Commands are namespaced under `/muse` so they can coexist with Red's built-in Audio cog (no need to unload it). Examples:
     * `/muse play`, `/muse pause`, `/muse resume`, `/muse skip`, `/muse stop`, `/muse queue`, `/muse nowplaying`, `/muse loop`, `/muse remove`, `/muse move`, `/muse clear`, `/muse volume`, `/muse autoplay`, `/muse maxqueue` — all require you to be in a voice channel.
   * `/muse play` includes autocomplete for YouTube/SoundCloud searches; it never alters playback until you submit the command.

4. **Autoplay & limits**
   * Toggle related-track autoplay with `/muse autoplay true|false`.
   * Restrict queue size per guild with `/muse maxqueue <size>`.

All playback, decoding, and streaming stay inside Lavalink; the cog only orchestrates commands, queues, and embeds.
