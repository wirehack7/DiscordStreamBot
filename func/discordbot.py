import time
import datetime
import configparser

import discord
from discord.ext import tasks

import aiohttp
import logging
import aiofiles
import aiofiles.os
import asyncio

import giphypop


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logging = logging.getLogger(__name__)

        self.config = configparser.ConfigParser()
        try:
            with open('config.ini') as fh:
                self.config.read_file(fh)
            fh.close()
        except Exception as e:
            raise FileNotFoundError(f'Cannot find config file: {e}')

        if 'DISCORD' not in self.config or 'TWITCH' not in self.config:
            raise ValueError('Section for config not found, please check your config!')

        if 'DIABLO' in self.config:
            self.diablo = {}
            self.diablo_emoji = [lambda: '', lambda: str(self.config['DIABLO']['emoji']) + " "][
                'emoji' in self.config['DIABLO']]()
            self.diablo_boss_sent = False
            self.diablo_boss_sent_now = False

        # an attribute we can access from our task
        self.twitch_user_id = 0
        self.bearer_token = 0
        self.stream_data = []
        self.live = False
        self.dimensions = {"{width}": "500", "{height}": "281"}

        if 'GIPHY' in self.config:
            self.g = giphypop.Giphy(api_key=self.config['GIPHY']['apikey'])
            self.expression = "cat"

    async def twitch_get_bearer(self, client_id: str, client_secret: str):
        self.logging.info('Getting Twitch bearer token...')
        async with aiohttp.ClientSession() as session:
            async with session.post('https://id.twitch.tv/oauth2/token?' +
                                    f'client_id={client_id}&' +
                                    f'client_secret={client_secret}' +
                                    '&grant_type=client_credentials'
                                    ) as r:
                self.logging.debug(f'Bearer HTTP status: {r.status}')
                if r.status == 200:
                    js = await r.json()
                    self.logging.debug(f'Token type: {js["token_type"]}')
                    if js['token_type'] != 'bearer':
                        await session.close()
                        raise ValueError(f'Token type is wrong: {js["token_type"]}')
                    await session.close()
                    return js['access_token']

    async def twitch_get_user_id(self, bearer, username, client_id):
        self.logging.info(f'Trying to get user id of {username}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/users?login={username}', headers=headers) as r:
                self.logging.debug(f'HTTP Status: {r.status}')
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(client_id, self.config['TWITCH']['client_secret'])
                    await self.twitch_get_user_id(self.bearer_token, username, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    self.twitch_user_id = js['data'][0]['id']
                    self.logging.debug(f'Got User id: {self.twitch_user_id}')

    async def twitch_get_stream(self, bearer, client_id):
        self.logging.info(f'Getting stream info of id {self.twitch_user_id}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/streams?user_id={self.twitch_user_id}',
                                   headers=headers) as r:
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(
                        client_id,
                        self.config['TWITCH']['client_secret']
                    )
                    await self.twitch_get_stream(self.bearer_token, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    self.logging.debug(len(js['data']))
                    self.stream_data = js['data']

    async def get_stream_thumb(self, url):
        async with aiohttp.ClientSession() as session:
            self.logging.debug(f"Trying to download {url}")
            async with session.get(url) as r:
                if r.status == 200:
                    f = await aiofiles.open('./stream_thumb.jpg', mode='wb')
                    await f.write(await r.read())
                    self.logging.debug("Wrote stream thumb")
                    await session.close()
                    return True
                else:
                    await session.close()
                    return False

    async def get_diablo_data(self):
        self.logging.info(f'Getting Diablo IV data')
        async with aiohttp.ClientSession() as session:
            headers = {
                # let's camouflage ourself
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" +
                              "(KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            }
            async with session.get('https://d4armory.io/api/events/recent', headers=headers) as r:
                if r.status != 200:
                    await session.close()
                    self.logging.error(f"Couldn't retrieve boss info, got status: {r.status}")
                    raise Exception(f"Couldn't retrieve boss info, got status: {r.status}")
                else:
                    js = await r.json()
                    await session.close()
                    return js

    async def send_d4_info(self, message):
        if message.channel.id == int(self.config['DIABLO']['channel']) \
                and (message.content == "!boss" or message.content == "!legion"):

            try:
                data = await self.get_diablo_data()
            except Exception as e:
                self.logging.error(f"Couldn't retrieve D4 data: {e}")
                return
            if message.content == "!boss":
                try:
                    await message.channel.send(
                        f"Next worldboss:\n" +
                        f"{self.diablo_emoji}**{data['boss']['expectedName']}** in {data['boss']['zone']}/{data['boss']['territory']} at " +
                        f"**{datetime.datetime.fromtimestamp(data['boss']['expected']).strftime('%H:%M:%S')}**\n\n" +
                        f"Following worldboss:\n" +
                        f"{self.diablo_emoji}**{data['boss']['nextExpectedName']}** at "
                        f"**{datetime.datetime.fromtimestamp(data['boss']['nextExpected']).strftime('%H:%M:%S')}**\n"
                    )
                except Exception as e:
                    self.logging.error(f"Couldn't send message: {e}")
            elif message.content == "!legion":
                try:
                    await message.channel.send(
                        f"{self.diablo_emoji}Next legion:\n" +
                        f"In {data['legion']['zone']}/{data['legion']['territory']} at " +
                        f"**{datetime.datetime.fromtimestamp(data['legion']['timestamp']).strftime('%H:%M:%S')}**\n"
                    )
                except Exception as e:
                    self.logging.error(f"Couldn't send message: {e}")

    async def send_gif(self, message):
        if isinstance(message.channel, discord.channel.DMChannel):
            if message.author == self.user.id:
                self.logging.debug("Don't react to own messages")
                return

            author = str(message.author)
            if 'GIFFUN' in self.config:
                if author in self.config['GIFFUN']:
                    self.expression = self.config['GIFFUN'][str(message.author)]

            self.logging.info(f"Received DM from {message.author}, sending {self.expression} GIF")

            try:
                await message.channel.send(
                    f"Hey hey {message.author.display_name}\n{self.g.screensaver(self.expression).media_url}")
                return
            except Exception as e:
                self.logging.error(f"Couldn't send message: {e}")
                return

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.background_twitch.start()
        if 'DIABLO' in self.config and (self.config['DIABLO']['alerts'].lower() == 'true'):
            self.background_d4boss.start()

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def background_twitch(self):
        await self.twitch_get_stream(self.bearer_token, self.config['TWITCH']['client_id'])
        self.logging.debug(self.stream_data)
        channel = self.get_channel(int(self.config['DISCORD']['channel']))
        if len(self.stream_data) > 0 and self.live is not True:
            self.logging.info(f"Found stream with title {self.stream_data[0]['title']}")
            self.logging.debug(self.stream_data)
            # Create thumbnail url
            image_url = self.stream_data[0]['thumbnail_url']
            # replace dimension placeholders in URL
            for word, dimension in self.dimensions.items():
                image_url = image_url.replace(word, dimension)
            # Try to download thumbnail
            thumbnail = self.get_stream_thumb(image_url)
            # wait random 2sec until I/O finishes
            await asyncio.sleep(2)
            message = str(self.config['DISCORD']['message']) + \
                      f"\n**{self.stream_data[0]['title']}**\n" + \
                      f"https://www.twitch.tv/{self.config['TWITCH']['name']}"
            self.logging.debug(message)
            try:
                if thumbnail is True:
                    await channel.send(
                        message,
                        suppress_embeds=True,
                        file=discord.File(r'./stream_thumb.jpg')
                    )
                else:
                    await channel.send(
                        message,
                        suppress_embeds=True
                    )
                self.logging.info("Sent chat message")
            except Exception as e:
                self.logging.error(f"Couldn't send message: {e}")

            # wait another 2sec to remove file
            await asyncio.sleep(2)
            await aiofiles.os.remove('./stream_thumb.jpg')
            self.live = True
        elif len(self.stream_data) == 0:
            self.logging.info(f"{self.config['TWITCH']['name']} is not streaming...")
            self.live = False

    @background_twitch.before_loop
    async def background_twitch_before(self):
        await self.twitch_get_user_id(self.bearer_token, self.config['TWITCH']['name'],
                                      self.config['TWITCH']['CLIENT_ID'])
        await self.wait_until_ready()  # wait until the bot logs in

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def background_d4boss(self):
        self.logging.info(f'Checking world boss spawn...')
        if self.diablo['boss']['expected'] == 0:
            raise ValueError('Diablo 4 Worldboss timer not set')

        message = f"**WORLDBOSS SPAWN ALERT**\n" + \
                  f"{self.diablo_emoji} **{self.diablo['boss']['expectedName']}** in *{self.diablo['boss']['zone']}/{self.diablo['boss']['territory']}* at " + \
                  f"**{datetime.datetime.fromtimestamp(self.diablo['boss']['expected']).strftime('%H:%M:%S')}**\n"

        channel = self.get_channel(int(self.config['DIABLO']['channel']))
        minutes = (int(self.diablo['boss']['expected']) - int(time.time())) / 60
        logging.debug(f'Diablo 4 current minutes diff: {str(minutes)}')
        if minutes <= int(self.config['DIABLO']['minutes']) and self.diablo_boss_sent is not True:
            self.logging.info(f'Sending D4 world boss alert, time diff (minutes): {minutes}')
            self.diablo_boss_sent = True
            try:
                await channel.send(message)
            except Exception as e:
                logging.error(f"Couldn't send message: {e}")
        elif 0 >= minutes > -2 and self.diablo_boss_sent_now is not True:
            self.logging.info(f'Sending D4 world boss alert, time diff (minutes): {minutes}')
            self.diablo_boss_sent_now = True
            try:
                await channel.send(message)
            except Exception as e:
                logging.error(f"Couldn't send message: {e}")
        elif minutes <= -10:
            self.diablo_boss_sent_now = False
            self.diablo_boss_sent = False
            self.diablo = await self.get_diablo_data()

    @background_d4boss.before_loop
    async def background_d4boss_before(self):
        self.diablo = await self.get_diablo_data()
        await self.wait_until_ready()  # wait until the bot logs in

    async def on_message(self, message):
        logging.debug(message)
        if message.author.id == self.user.id:
            self.logging.debug("Don't react to own messages")
            return

        # send funny gif
        if 'GIPHY' in self.config:
            await self.send_gif(message)

        # Diablo IV boss info
        await self.send_d4_info(message)

    async def on_ready(self):
        self.logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        self.logging.info('------.v0.4')
        game = discord.Game("Counting 1 and 0 BEEBOOP")
        await self.change_presence(status=discord.Status.online, activity=game)
        for guild in self.guilds:
            if 'DIABLO' in self.config and (int(self.config['DIABLO']['server']) == guild.id):
                self.logging.info(f"I'm in server {guild.name}!")
                if isinstance(int(self.config['DIABLO']['channel']), discord.channel.Thread):
                    try:
                        await self.get_channel(int(self.config['DIABLO']['channel'])).join()
                    except Exception as e:
                        print(f"Cannot join thread: {e}")
