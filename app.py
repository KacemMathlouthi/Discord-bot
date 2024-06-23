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

    if message.content.startswith("batrouna"):
        user_message = message.content[len("batrouna"):].strip()
        username = str(message.author)
        channel = str(message.channel)

        print(f'[{channel}] {username}: "{user_message}"')
        await send_message(message, user_message)
    await client.process_commands(message)


# JOIN VOICE CHANNEL COMMAND
@client.command(name="join")
async def join(ctx, *, channel_name: str):
    channel = discord.utils.get(ctx.guild.voice_channels, name=channel_name)
    if channel:
        try:
            if ctx.voice_client is not None:
                await ctx.voice_client.move_to(channel)
            else:
                await channel.connect()
            await ctx.send(f"Joined {channel_name} voice channel!")
        except RuntimeError as e:
            await ctx.send("Failed to connect to the voice channel. Make sure PyNaCl is installed.")
            print(e)
    else:
        await ctx.send(f"Voice channel '{channel_name}' not found.")

# LEAVE VOICE CHANNEL COMMAND
@client.command(name="leave")
async def leave(ctx):
    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
        await ctx.send("Disconnected from the voice channel.")
    else:
        await ctx.send("I am not in a voice channel.")

# PLAY MUSIC COMMAND
@client.command(name="play")
async def play(ctx, *, url: str):
    if ctx.voice_client is None:
        await ctx.send("I need to be in a voice channel to play music. Use the /join command to invite me to a voice channel.")
        return
    
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
