from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class Track:
    """Lightweight track model mirroring Muse semantics."""

    title: str
    uri: str
    duration: int
    requester_id: int
    source: str
    thumbnail: Optional[str] = None
    lavalink_track: Optional[str] = None

    @classmethod
    def from_lavalink(cls, data: Dict[str, Any], requester_id: int) -> "Track":
        info = data.get("info", {})
        return cls(
            title=info.get("title", "Unknown Track"),
            uri=info.get("uri") or info.get("identifier", ""),
            duration=int(info.get("length", 0)),
            requester_id=requester_id,
            source=info.get("sourceName", "unknown"),
            thumbnail=cls._extract_thumbnail(info),
            lavalink_track=data.get("track"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "uri": self.uri,
            "duration": self.duration,
            "requester_id": self.requester_id,
            "source": self.source,
            "thumbnail": self.thumbnail,
            "lavalink_track": self.lavalink_track,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Track":
        return cls(
            title=payload.get("title", "Unknown Track"),
            uri=payload.get("uri", ""),
            duration=int(payload.get("duration", 0)),
            requester_id=int(payload.get("requester_id", 0)),
            source=payload.get("source", "unknown"),
            thumbnail=payload.get("thumbnail"),
            lavalink_track=payload.get("lavalink_track"),
        )

    @staticmethod
    def _extract_thumbnail(info: Dict[str, Any]) -> Optional[str]:
        if info.get("artworkUrl"):
            return info["artworkUrl"]
        identifier = info.get("identifier")
        if info.get("sourceName") == "youtube" and identifier:
            return f"https://img.youtube.com/vi/{identifier}/hqdefault.jpg"
        return None
