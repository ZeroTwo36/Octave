import asyncio
import nextcord
from nextcord.ext import commands
import youtube_dl

from random import choice

players = {}

_queue = {}
    

youtube_dl.utils.bug_reports_message = lambda: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(nextcord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(nextcord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)



client = commands.AutoShardedBot(command_prefix='?octave ')
client.remove_command("help")

@client.command(description="See the Bot Help")
async def help(ctx):
    embed = nextcord.Embed(title="Help - Octave!")
    for command in client.walk_commands():
        embed.add_field(name=command.name,value=command.description+"\n"+command.signature)
    await ctx.send(embed = embed)

@client.event
async def on_ready():
  while True:
    await client.change_presence(activity=nextcord.Activity(type=nextcord.ActivityType.listening,name=f'🎧 ?octave help'))
    await asyncio.sleep(20)

@client.command(description="View the Queue")
async def queue(ctx):
    string = "```c++\n"
    if ctx.guild.id in _queue:
        for s in _queue[ctx.guild.id]:
            string += s.title+"\n"
    else:
        string += "The Queue is empty!\n"
    string += "```"
    await ctx.send(string)

@client.command(description="Let me play Music")
async def play(ctx,*, query):
    await _play(ctx,query)

async def _play(ctx,query):
    if not ctx.author.voice:
        return await ctx.reply('You aren\'t connected to a Voice Channel')
    channel = ctx.author.voice.channel
    try:
        await channel.connect()
    except Exception as e:
        print(e)
    guild = ctx.guild
    voice = guild.voice_client
    if not voice.is_playing():
        async with ctx.channel.typing():
            player = await YTDLSource.from_url(query,loop=client.loop,stream=True)
            voice.play(player, after=lambda e: print('Player Error: %s' % e) if e else None)
        players[ctx.guild.id] = player.title
        
        if ctx.guild.id in _queue:
            _queue[ctx.guild.id].append(player)
        else:
            _queue[ctx.guild.id] = [player]
        await ctx.send(f"**🎶 Now playing:** `{player.title}`")
        _queue[ctx.guild.id].pop(0)
        await asyncio.sleep(player.data.get('duration'))
        if len(_queue[ctx.guild.id]) > 0:
            for k in _queue[ctx.guild.id]:
                voice.play(k, after=lambda e: print('Player Error: %s' % e) if e else None)
                await ctx.send(f"**🎶 Now playing:** `{player.title}`")
                _queue[ctx.guild.id].pop(0)
                await asyncio.sleep(player.data.get('duration'))
        await voice.disconnect()
        await ctx.send(f"**🎧 I have left the channel because the Queue was empty**")

    else:
        async with ctx.channel.typing():
            player = await YTDLSource.from_url(query,loop=client.loop,stream=True)
        players[ctx.guild.id] = player.title
        await ctx.send(f"**🎶 Queued:** `{player.title}`")
    
        if ctx.guild.id in _queue:
            _queue[ctx.guild.id].append(player)
        else:
            _queue[ctx.guild.id] = [player]


@client.command(description="Make me stop playing Music and Leave the Channel")
async def leave(ctx):
    if not ctx.author.voice:
        return await ctx.reply('You aren\'t connected to a Voice Channel')
    channel = ctx.guild.voice_client
    await channel.disconnect()
    players[ctx.guild.id] = None


@client.command(description="Stop the Player")
async def stop(ctx):
    if not ctx.author.voice:
        return await ctx.reply('You aren\'t connected to a Voice Channel')
    voice = ctx.guild.voice_client
    await voice.stop()



@client.command(description="I will **pause** the Music")
async def pause(ctx):
    if not ctx.author.voice:
        return await ctx.reply('You aren\'t connected to a Voice Channel')
    channel = ctx.guild.voice_client
    await channel.pause()

@client.command(description="I will **resume** the Music")
async def resume(ctx):
    if not ctx.author.voice:
        return await ctx.reply('You aren\'t connected to a Voice Channel')
    channel = ctx.guild.voice_client
    await channel.resume()

import textwrap
import urllib
import aiohttp
import datetime

@client.command(description="Change the Volume",aliases=['vol'])
async def volume(ctx,vol:int=None):
    if not vol:
        return await ctx.reply(f'🔊 Current Volume is {ctx.voice_client.source.volume*100}')
    if not ctx.voice_client:
        return await ctx.reply("Not connected to a Voice Channel!")

    ctx.voice_client.source.volume = vol / 100
    await ctx.reply(f'🔊 Volume changed to {ctx.voice_client.source.volume*100}%!')

@client.command(aliases = ['l', 'lyrc', 'lyric']) # adding aliases to the command so they they can be triggered with other names
async def lyrics(ctx, *, search = None):
    """A command to find lyrics easily!"""
    if not search: # if user hasnt given an argument, throw a error and come out of the command
      if not players[ctx.guild.id]:
        embed = nextcord.Embed(
            title = "No search argument!",
            description = "You havent entered anything, so i couldnt find lyrics!"
        )
        return await ctx.reply(embed = embed)
        # ctx.reply is available only on discord.py version 1.6.0, if you have a version lower than that use ctx.send
      else:
        search = players[ctx.guild.id]
    song = urllib.parse.quote(search) # url-encode the song provided so it can be passed on to the API
    
    async with aiohttp.ClientSession() as lyricsSession:
        async with lyricsSession.get(f'https://some-random-api.ml/lyrics?title={song}') as jsondata: # define jsondata and fetch from API
            if not 300 > jsondata.status >= 200: # if an unexpected HTTP status code is recieved from the website, throw an error and come out of the command
                return await ctx.send(f'Recieved poor status code of {jsondata.status}')

            lyricsData = await jsondata.json() # load the json data into its json form

    error = lyricsData.get('error')
    if error: # checking if there is an error recieved by the API, and if there is then throwing an error message and returning out of the command
        return await ctx.send(f'Recieved unexpected error: {error}')

    songLyrics = lyricsData['lyrics'] # the lyrics
    songArtist = lyricsData['author'] # the author's name
    songTitle = lyricsData['title'] # the song's title
    songThumbnail = lyricsData['thumbnail']['genius'] # the song's picture/thumbnail

    # sometimes the song's lyrics can be above 4096 characters, and if it is then we will not be able to send it in one single message on Discord due to the character limit
    # this is why we split the song into chunks of 4096 characters and send each part individually
    for chunk in textwrap.wrap(songLyrics, 4096, replace_whitespace = False):
        embed = nextcord.Embed(
            title = songTitle,
            description = chunk,
            color = nextcord.Color.blurple(),
            timestamp = datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url = songThumbnail)
        await ctx.send(embed = embed)


client.run("TOKEN")
