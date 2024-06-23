import os
from dotenv import load_dotenv
from discord import Intents, Client, Message, VoiceChannel
from discord.ext import commands
import discord
from groq import Groq
import yt_dlp
from yt_dlp import YoutubeDL

# LOAD OUR TOKEN FROM SOMEWHERE SAFE
load_dotenv()
dstoken = os.getenv("discord_token")
groqtoken = os.getenv("groq_token")

# BOT SETUP
intents = Intents.default()
intents.message_content = True 
client = commands.Bot(command_prefix="/", intents=intents)

# GROQ SETUP
groq_client = Groq(
    api_key=groqtoken,
)

# RESPONSE FUNCTIONALITY
def get_response(user_input: str) -> str:
    chat_completion = groq_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": "Start each conversation by saying 'asba lomar' then proceed to answer the prompt."
            },
            {
                "role": "user",
                "content": user_input
            }
        ],

        model="llama3-8b-8192",

        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        stop=None,
        stream=False,
    )
    return chat_completion.choices[0].message.content

# MESSAGE FUNCTIONALITY
async def send_message(message: Message, user_message: str) -> None:
    if not user_message:
        print('(Message was empty because intents were not enabled probably)')
        return

    try:
        response: str = get_response(user_message)
        await message.channel.send(response)
    except Exception as e:
        print(e)

# HANDLING THE STARTUP FOR OUR BOT
@client.event
async def on_ready() -> None:
    print(f'{client.user} is now running!')

# HANDLING INCOMING MESSAGES
@client.event
async def on_message(message: Message) -> None:
    if message.author == client.user:
        return
    if message.content.startswith("gpt"):
        user_message = message.content[len("gpt"):].strip()
        username = str(message.author)
        channel = str(message.channel)

        print(f'[{channel}] {username}: "{user_message}"')
        await send_message(message, user_message)
    await client.process_commands(message)


## JOIN VOICE CHANNEL COMMAND
@client.command(name="join")
async def join(ctx):
    if not ctx.message.author.voice:
        await ctx.send("{} is not connected to a voice channel!".format(ctx.message.author.name))
        return
    else:
        channel = ctx.message.author.voice.channel
        if ctx.voice_client is not None:
            if ctx.message.author.voice.channel == ctx.voice_client.channel :
                await ctx.send("I'm already in {} !".format(ctx.message.author.name))
            else:
                await ctx.voice_client.move_to(channel)
                await ctx.send(f"Joined {channel.name} voice channel!") 
        else:
            await channel.connect()
            await ctx.send(f"Joined {channel.name} voice channel!")    

# LEAVE VOICE CHANNEL COMMAND
@client.command(name="leave")
async def leave(ctx):     
    if ctx.voice_client is not None:
        if ctx.message.author.voice.channel != ctx.voice_client.channel :
            await ctx.send("We are not in the same channel {} !".format(ctx.message.author.name))
            return
        else:
            await ctx.voice_client.disconnect()
            await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not in a voice channel.")

# RESUME MUSIC COMMAND
@client.command(name='resume', help='Resumes the song')
async def resume(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_paused():
        voice_client.resume()
    else:
        await ctx.send("The bot was not playing anything before this. Use /play command!")

# PAUSE MUSIC COMMAND
@client.command(name='pause', help='This command pauses the song')
async def pause(ctx):
    voice_client = ctx.message.guild.voice_client
    if voice_client.is_playing():
        voice_client.pause()
    else:
        await ctx.send("The bot is not playing anything at the moment.")

# PLAY MUSIC COMMAND
@client.command(name="play")
async def play(ctx, *, url: str):
    if ctx.voice_client is None:
        if not ctx.message.author.voice:
            await ctx.send("{} is not connected to a voice channel!".format(ctx.message.author.name))
            return
        else:
            channel = ctx.message.author.voice.channel
            if ctx.voice_client is not None:
                if ctx.message.author.voice.channel == ctx.voice_client.channel :
                    await ctx.send("I'm already in {} !".format(ctx.message.author.name))
                else:
                    await ctx.voice_client.move_to(channel)
                    await ctx.send(f"Joined {channel.name} voice channel!") 
            else:
                await channel.connect()
                await ctx.send(f"Joined {channel.name} voice channel!")  
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        url2 = info['url']

    ffmpeg_opts = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    source = discord.FFmpegPCMAudio(url2, **ffmpeg_opts)
    ctx.voice_client.play(source)
    await ctx.send(f"Now playing: {info['title']}")

# MAIN ENTRY POINT
def main() -> None:
    client.run(dstoken)

if __name__ == '__main__':
    main()
