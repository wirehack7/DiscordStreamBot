import time
from datetime import datetime
import configparser

import discord
from discord.ext import tasks

import aiohttp
import logging
import aiofiles
import aiofiles.os
import asyncio


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

        # an attribute we can access from our task
        self.hour = ""
        self.minute = ""
        self.bearer_token = 0
        self.streams = {}
        self.stream_data = []
        self.live = False
        self.dimensions = {"{width}": "500", "{height}": "281"}
        self.thumbnail = False
        self.list_streams = self.config['TWITCH']['streams'].split(',')
        self.twitch_user_id = ""
        self.leet = False
        for stream in self.list_streams:
            stream = stream.replace(" ", "")
            self.streams[stream] = {}
            self.streams[stream]['name'] = stream
            self.streams[stream]['id'] = 0
            self.streams[stream]['live'] = False

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

    async def twitch_get_user_ids(self, bearer, streams, client_id):
        self.logging.debug(f"Got streams: {streams}")
        for stream in streams:
            self.logging.debug(f"Stream data: {stream}")
            self.logging.info(f"Trying to get user id of {stream}")
            headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://api.twitch.tv/helix/users?login={stream}", headers=headers) as r:
                    self.logging.debug(f'HTTP Status: {r.status}')
                    if r.status != 200:
                        await session.close()
                        self.bearer_token = await self.twitch_get_bearer(client_id,
                                                                         self.config['TWITCH']['client_secret'])
                        await self.twitch_get_user_ids(self.bearer_token, streams, client_id)
                    else:
                        js = await r.json()
                        await session.close()
                        self.streams[stream]['id'] = js['data'][0]['id']
                        self.logging.debug(f"Got User id: {self.streams[stream]['id']}")

    async def twitch_get_stream(self, bearer, client_id, twitch_user_id):
        self.logging.info(f'Getting stream info of id {twitch_user_id}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/streams?user_id={twitch_user_id}',
                                   headers=headers) as r:
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(
                        client_id,
                        self.config['TWITCH']['client_secret']
                    )
                    await self.twitch_get_stream(self.bearer_token, client_id, twitch_user_id)
                else:
                    js = await r.json()
                    await session.close()
                    self.logging.debug(len(js['data']))
                    self.stream_data = js['data']

    async def get_stream_thumb(self, url, stream):
        async with aiohttp.ClientSession() as session:
            self.logging.debug(f"Trying to download {url}")
            async with session.get(url) as r:
                if r.status == 200:
                    f = await aiofiles.open(f'./{stream}_thumb.jpg', mode='wb')
                    await f.write(await r.read())
                    self.logging.debug("Wrote stream thumb")
                    await session.close()
                    self.thumbnail = True
                    return
                else:
                    await session.close()
                    self.thumbnail = False
                    return

    async def sendleet(self, channel: int):
        self.logging.info(f'Checking time for leet')
        c = datetime.now()
        self.hour = c.strftime('%H')
        self.minute = c.strftime('%M')
        if self.hour == "14":
            self.leet = False
        channel = self.get_channel(channel)
        if self.hour == "13" and self.minute == "37" and self.leet is False:
            try:
                await channel.send(
                    f"1337"
                )
                self.leet = True
            except Exception as e:
                self.logging.error(f"Couldn't send message: {e}")

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.background_twitch.start()

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def background_twitch(self):
        if self.config['DISCORD']['leet_channel'] != "":
            await self.sendleet(int(self.config['DISCORD']['leet_channel']))
        self.logging.debug(f'Streams dict: {self.streams}')
        for key, value in self.streams.items():
            self.logging.info(f"Getting stream info for: {key} and data: {value}")
            await self.twitch_get_stream(self.bearer_token, self.config['TWITCH']['client_id'], value['id'])
            self.logging.debug(self.stream_data)
            channel = self.get_channel(int(self.config['DISCORD']['channel']))
            if len(self.stream_data) > 0 and self.streams[key]['live'] is not True:
                self.logging.info(f"Found stream with title {self.stream_data[0]['title']}")
                self.logging.debug(self.stream_data)
                # Create thumbnail url
                image_url = self.stream_data[0]['thumbnail_url']
                # replace dimension placeholders in URL
                for word, dimension in self.dimensions.items():
                    image_url = image_url.replace(word, dimension)

                # Try to download thumbnail
                try:
                    await asyncio.wait_for(self.get_stream_thumb(image_url, key), timeout=5)
                except asyncio.TimeoutError as e:
                    logging.warning(f'Thumbnail download timed out: {e}')

                message = str(self.config['DISCORD']['message'].replace("{name}", key)) + \
                          f"\n**{self.stream_data[0]['title']}**\n" + \
                          f"https://www.twitch.tv/{key}"
                self.logging.debug(message)
                try:
                    if self.thumbnail is True:
                        file_name = f'./{key}_thumb.jpg'
                        await channel.send(
                            message,
                            suppress_embeds=True,
                            file=discord.File(file_name)
                        )
                    else:
                        await channel.send(
                            message,
                            suppress_embeds=True
                        )
                    self.logging.info("Sent chat message")
                except Exception as e:
                    self.logging.error(f"Couldn't send message: {e}")

                self.streams[key]['live'] = True
            elif len(self.stream_data) == 0:
                self.logging.info(f"{key} is not streaming...")
                self.streams[key]['live'] = False

    @background_twitch.before_loop
    async def background_twitch_before(self):
        self.logging.debug(f"Trying to get data for streams")
        await self.twitch_get_user_ids(self.bearer_token, self.streams,
                                       self.config['TWITCH']['CLIENT_ID'])
        await self.wait_until_ready()  # wait until the bot logs in

    async def on_message(self, message):
        logging.debug(message)
        if message.author.id == self.user.id:
            self.logging.debug("Don't react to own messages")
            return

    async def on_ready(self):
        self.logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        self.logging.info('------.v0.4')
        game = discord.Game("Counting 1 and 0 BEEBOOP")
        self.logging.info(self.streams)
        await self.change_presence(status=discord.Status.online, activity=game)
