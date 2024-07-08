from discord import Intents, Client, VoiceChannel, ButtonStyle, Interaction, Embed
from discord.ext import commands, tasks
import discord
from discord.ui import Button, View
import yt_dlp
from yt_dlp import YoutubeDL
import asyncio
import requests
from random import shuffle

urls = [
    'https://www.youtube.com/watch?v=8y4FtO0J4rU',
    'https://www.youtube.com/watch?v=Yky0ZHBhZxM',
    'https://www.youtube.com/watch?v=Zu_M3VgzUpk',
    'https://www.youtube.com/watch?v=lkeGcH2xZ8Y',
    'https://www.youtube.com/watch?v=4KB7b27_34Q',
    'https://www.youtube.com/watch?v=OnGLU0UpnBc',
    'https://www.youtube.com/watch?v=i2NJd2a5P0M',
    'https://www.youtube.com/watch?v=hyCtOHXcfW0',
    'https://www.youtube.com/watch?v=YJ_a0v4eJU8',
    'https://www.youtube.com/watch?v=VIVzi7rUDBA',
    'https://www.youtube.com/watch?v=Na9jREuExmU',
    'https://www.youtube.com/watch?v=JEWWmx8jKCk',
]

music_queue = []
ffmpeg_opts = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

class MusicControlView(discord.ui.View):
    def __init__(self, ctx, cog):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.cog = cog

    @discord.ui.button(emoji="⏯", style=discord.ButtonStyle.grey, custom_id="pauseplay_button")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message(":pause_button: **Paused**", ephemeral=True)
        elif interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message(":play_pause: **Resumed**", ephemeral=True)
        else:
            await interaction.response.send_message("Not playing anything at the moment!", ephemeral=True)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.grey, custom_id="skip_button")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(":fast_forward: **Skipped**", ephemeral=True)
        await self.cog.skip(self.ctx)

    @discord.ui.button(emoji="<:reacttrash:878915749375246336>", style=discord.ButtonStyle.secondary, custom_id="leave_button")
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.guild.voice_client is not None:
            if interaction.user.voice is None or interaction.user.voice.channel != interaction.guild.voice_client.channel:
                await interaction.response.send_message("Not in the same channel!", ephemeral=True)
            else:
                await interaction.guild.voice_client.disconnect()
                await interaction.response.send_message("⛔️ **Disconnected**", ephemeral=True)
        else:
            await interaction.response.send_message("Not in a voice channel!", ephemeral=True)

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.music_queue = []

    @commands.command(name='join')
    async def join(self, ctx):
        if not ctx.message.author.voice:
            await ctx.send("{} is not connected to a voice channel!".format(ctx.message.author.name))
        else:
            channel = ctx.message.author.voice.channel
            if ctx.voice_client is not None:
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect()

    @commands.command(name='leave')
    async def leave(self, ctx):
        if ctx.voice_client is not None:
            if ctx.message.author.voice.channel != ctx.voice_client.channel:
                await ctx.send(f"Not in the same channel {ctx.message.author.name}!")
            else:
                await ctx.voice_client.disconnect()
        else:
            await ctx.send("Not in a voice channel.")

    @commands.command(name='pause')
    async def pause(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_playing():
            voice_client.pause()
        else:
            await ctx.send("The bot is not playing anything at the moment.")

    @commands.command(name='resume')
    async def resume(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_paused():
            voice_client.resume()
        else:
            await ctx.send("Not playing anything before this. Use /play command!")

    @commands.command(name='stop')
    async def stop(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        else:
            await ctx.send("The bot is not playing anything at the moment.")

    @commands.command(name="play")
    async def play(self, ctx, url: str):
        await self.join(ctx)
        if url.startswith("https://www.youtube.com/"):
            self.add_to_queue(url)
            if not ctx.voice_client.is_playing():
                await self.play_next(ctx)
            else:
                info = music_queue[-1]
                embed = discord.Embed(
                    title="Added to Queue",
                    description=f"**Title:** {info['title']}\n**Duration:** {info['duration']}\n**Position in Queue:** {len(music_queue)}",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
        else:
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'default_search': 'ytsearch1',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                first_result = info['entries'][0]
                url = first_result['webpage_url']
                await self.play(ctx, url=url)

    async def play_next(self, ctx):
        if music_queue:
            song = music_queue.pop(0)
            ctx.voice_client.play(song['source'], after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(ctx), self.bot.loop))
            embed = discord.Embed(
                title="Now Playing",
                description=f"**Title:** {song['title']}\n**Duration:** {song['duration']}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, view=MusicControlView(ctx, self))
        else:
            embed = discord.Embed(title="Queue is empty, add more songs!", color=discord.Color.red())
            await ctx.send(embed=embed)

    @commands.command(name='skip')
    async def skip(self, ctx):
        voice_client = ctx.message.guild.voice_client
        if voice_client.is_playing():
            voice_client.stop()
        await self.play_next(ctx)

    @commands.command(name="queue")
    async def queue(self, ctx):
        if music_queue:
            embed = discord.Embed(
                title="🎶 Current Music Queue 🎶",
                color=discord.Color.blue()
            )
            for idx, song in enumerate(music_queue, start=1):
                embed.add_field(
                    name=f"{idx}. {song['title']}",
                    value=f"**Duration:** {song['duration']}",
                    inline=False
                )
            embed.set_footer(text=f"Total songs in queue: {len(music_queue)}")
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(
                title="🎶 Current Music Queue 🎶",
                description="The queue is currently empty.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name="clear")
    async def clear(self, ctx):
        global music_queue
        music_queue = []
        await ctx.send("Music queue cleared!")

    @commands.command(name="search")
    async def search(self, ctx, *, query: str):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'default_search': 'ytsearch5',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            results = info['entries']
            if not results:
                embed = discord.Embed(
                    title="🔍 YouTube Search Results",
                    description=f"No results found for '{query}'.",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return
            embed = discord.Embed(
                title=f"🔍 Top 5 YouTube Results for '{query}'",
                color=discord.Color.green()
            )
            for idx, entry in enumerate(results[:5], start=1):
                title = entry['title']
                duration = entry.get('duration')
                duration_formatted = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
                url = entry['webpage_url']
                embed.add_field(
                    name=f"{idx}. {title}",
                    value=f"**Duration:** {duration_formatted}\n[Watch]({url})",
                    inline=False
                )
            await ctx.send(embed=embed)

    def add_to_queue(self, url: str):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = str(info['duration'] // 60) + ":" + str(info['duration'] % 60)
            source = discord.FFmpegPCMAudio(info['url'], **ffmpeg_opts)
            music_queue.append({'title': info['title'], 'duration': duration, 'source': source})

    @commands.command(name="jalel")
    async def jalel(self, ctx):
        shuffle(urls)
        await self.play(ctx, urls[0])
        for url in range(1, 3):
            self.add_to_queue(urls[url])

async def setup(bot):
    await bot.add_cog(MusicCog(bot))