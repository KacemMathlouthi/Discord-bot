from discord.ext import commands
from discord import Embed


class help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='help')
    async def help_command(self, ctx):
        embed = Embed(title="Music Bot Help", description="List of commands", color=0x00ff00)
        commands_list = [
            ("/join", "Join the voice channel"),
            ("/leave", "Leave the voice channel"),
            ("/play <url/name>", "Play a song from YouTube"),
            ("/pause", "Pause the current song"),
            ("/resume", "Resume the paused song"),
            ("/skip", "Skip to the next song in the queue"),
            ("/loop", "Play the current song in loop until /loop again"),
            ("/queue", "Display the current music queue"),
            ("/clear", "Clear the current music queue"),
            ("/setalarm (hh:mm) (name)", "Set an alarm for you"),
            ("/dice", "Get a number from 1 to 6"),
            ("/rps", "Rock-Paper-Scissors Game Co-op"),
            ("/xo", "Tic-Tac-Toe Game Co-op"),
        ]
        for name, desc in commands_list:
            embed.add_field(name=name, value=desc, inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(help(bot))