from discord.ext import commands
from datetime import datetime, timedelta
import asyncio


class setalarm(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setalarm')
    async def set_alarm(ctx, time: str, name):

        try:

            alarm_time = datetime.strptime(time, "%H:%M").time()

            now = datetime.now().time()
            
            now_seconds = now.hour * 3600 + now.minute * 60 + now.second
            alarm_seconds = alarm_time.hour * 3600 + alarm_time.minute * 60
            
            if alarm_seconds <= now_seconds:
                alarm_seconds += 86400
            
            wait_time = alarm_seconds - now_seconds
            
            wait_time = timedelta(seconds=wait_time)
            
            await ctx.send(f'Alarm set for {time}.')
            
            await asyncio.sleep(wait_time.total_seconds())
            
            await ctx.send(f'{ctx.author.mention} Alarm! {name}.')
            
        except ValueError:
            await ctx.send("Invalid time format. Please use hh:mm format.")

async def setup(bot):
    await bot.add_cog(setalarm(bot))