from discord.ext import commands
from random import randint


class dice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='dice')
    async def dice(self, ctx):
        nb = randint(0,5)
        nb_list=[':one:',':two:',':three:' ,':four:', ':five:', ':six:']
        await ctx.send(nb_list[nb])

async def setup(bot):
    await bot.add_cog(dice(bot))