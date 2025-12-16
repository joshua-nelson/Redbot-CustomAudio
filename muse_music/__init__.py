from .cog import MuseMusic

__all__ = ["MuseMusic"]


async def setup(bot):
    await bot.add_cog(MuseMusic(bot))
