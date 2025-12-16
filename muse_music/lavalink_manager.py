from __future__ import annotations

import logging
import asyncio
from typing import Any, Optional

import aiohttp

import discord
import lavalink

log = logging.getLogger("red.muse_music.lavalink")


class LavalinkVoiceClient(discord.VoiceProtocol):
    def __init__(self, client: discord.Client, channel: discord.abc.Connectable):
        super().__init__(client)
        self.client = client
        self.channel = channel
        self.lavalink: lavalink.Client = getattr(client, "muse_lavalink")

    async def on_voice_server_update(self, data: dict[str, Any]):
        await self.lavalink.voice_update_handler(data)

    async def on_voice_state_update(self, data: dict[str, Any]):
        await self.lavalink.voice_update_handler(data)

    async def connect(self, *, timeout: float | None = None, reconnect: bool | None = None) -> None:  # type: ignore[override]
        self.lavalink.voice_states[self.channel.guild.id] = None
        await self.channel.guild.change_voice_state(channel=self.channel)

    async def disconnect(self, *, force: bool | None = None) -> None:  # type: ignore[override]
        if not force and not self.channel:
            return
        await self.channel.guild.change_voice_state(channel=None)
        self.cleanup()


class LavalinkManager:
    def __init__(
        self,
        bot: discord.Client,
        *,
        host: str = "localhost",
        port: int = 2333,
        password: str = "youshallnotpass",
        region: str = "us",
    ):
        self.bot = bot
        self.host = host
        self.port = port
        self.password = password
        self.region = region
        self.client: Optional[lavalink.Client] = None
        self._event_bridge = None
        self._http: Optional[aiohttp.ClientSession] = None
        self._node_ready: asyncio.Event = asyncio.Event()

    async def start(self, event_bridge: Any) -> None:
        if self.client:
            return
        self._event_bridge = event_bridge
        self.client = lavalink.Client(self.bot.user.id)  # type: ignore[arg-type]
        self.client.add_node(self.host, self.port, self.password, self.region, "muse-node")
        self.bot.muse_lavalink = self.client
        self.bot.add_listener(self._on_socket_response, "on_socket_response")
        self.client.add_event_hook(self._dispatch_event)
        log.info("Connected Lavalink client to %s:%s", self.host, self.port)
        if not self._http or self._http.closed:
            headers = {"Authorization": self.password}
            self._http = aiohttp.ClientSession(headers=headers)

    async def stop(self) -> None:
        if not self.client:
            return
        try:
            self.bot.remove_listener(self._on_socket_response, "on_socket_response")
        except Exception:
            pass
        self.client = None
        if hasattr(self.bot, "muse_lavalink"):
            delattr(self.bot, "muse_lavalink")
        if self._http and not self._http.closed:
            await self._http.close()
            self._http = None
        self._node_ready.clear()

    async def _on_socket_response(self, payload: dict[str, Any]) -> None:
        if self.client:
            await self.client.voice_update_handler(payload)

    async def _dispatch_event(self, event: Any) -> None:
        if not self._event_bridge:
            return
        try:
            import lavalink as _lv

            if isinstance(event, _lv.events.NodeConnectedEvent):
                log.info("Lavalink node connected; session is ready")
                self._node_ready.set()
            elif isinstance(event, _lv.events.TrackStartEvent):
                await self._event_bridge.track_start(event)
            elif isinstance(event, _lv.events.TrackEndEvent):
                await self._event_bridge.track_end(event)
            elif isinstance(event, _lv.events.PlayerUpdateEvent):
                await self._event_bridge.player_update(event)
        except Exception:
            log.exception("Error dispatching Lavalink event")

    async def wait_ready(self, timeout: float = 10.0) -> None:
        if not self.client:
            raise RuntimeError("Lavalink client is not initialised.")
        try:
            await asyncio.wait_for(self._node_ready.wait(), timeout=timeout)
        except asyncio.TimeoutError as exc:
            raise RuntimeError("Lavalink node did not become ready in time.") from exc

    async def get_player(self, guild_id: int):
        if not self.client:
            raise RuntimeError("Lavalink client is not initialised.")
        await self.wait_ready()
        return self.client.player_manager.create(guild_id)

    def get_node(self):
        if not self.client:
            return None
        if not self._node_ready.is_set():
            return None
        return self.client.node_manager.get_node()

    def get_session_id(self) -> str:
        node = self.get_node()
        if not node or not getattr(node, "session_id", None):
            raise RuntimeError("Lavalink session is not ready yet.")
        return node.session_id  # type: ignore[attr-defined]

    async def update_player(self, guild_id: int, **payload: Any) -> dict[str, Any]:
        await self.wait_ready()
        session_id = self.get_session_id()
        headers = {"Authorization": self.password, "Session-Id": session_id}
        if not self._http or self._http.closed:
            self._http = aiohttp.ClientSession(headers=headers)
        else:
            self._http._default_headers.update(headers)  # type: ignore[attr-defined]
        url = f"http://{self.host}:{self.port}/v4/sessions/{session_id}/players/{guild_id}"
        async with self._http.patch(url, json=payload) as resp:
            if resp.status >= 400:
                text = await resp.text()
                raise RuntimeError(f"Lavalink REST update failed: {resp.status} {text}")
            try:
                return await resp.json()
            except Exception:
                return {}

    async def connect(self, guild_id: int, channel_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if not guild:
            raise RuntimeError("Guild not found for Lavalink connection")
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            raise RuntimeError("Target channel is not a voice channel")
        if guild.voice_client and isinstance(guild.voice_client, LavalinkVoiceClient):
            await guild.voice_client.move_to(channel)
        else:
            await channel.connect(cls=LavalinkVoiceClient)

    async def disconnect(self, guild_id: int) -> None:
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            await guild.voice_client.disconnect(force=True)
