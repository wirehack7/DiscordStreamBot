import os
import discord
from dotenv import load_dotenv
from discord.ext import tasks
import aiohttp
import asyncio
import logging

logging.basicConfig(
    encoding='utf-8',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # an attribute we can access from our task
        self.twitch_user_id = 0
        self.bearer_token = 0
        self.stream_data = []
        self.live = False

    async def twitch_get_bearer(self, client_id: str, client_secret: str):
        logging.info('Getting Twitch bearer token...')
        async with aiohttp.ClientSession() as session:
            async with session.post('https://id.twitch.tv/oauth2/token?' +
                                    f'client_id={client_id}&' +
                                    f'client_secret={client_secret}' +
                                    '&grant_type=client_credentials'
                                    ) as r:
                logging.debug(f'Bearer HTTP status: {r.status}')
                if r.status == 200:
                    js = await r.json()
                    logging.debug(f'Token type: {js["token_type"]}')
                    if js['token_type'] != 'bearer':
                        await session.close()
                        raise ValueError(f'Token type is wrong: {js["token_type"]}')
                    await session.close()
                    return js['access_token']

    async def twitch_get_user_id(self, bearer, username, client_id):
        logging.info(f'Trying to get user id of {username}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/users?login={username}', headers=headers) as r:
                logging.debug(f'HTTP Status: {r.status}')
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
                    await self.twitch_get_user_id(self.bearer_token, username, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    self.twitch_user_id = js['data'][0]['id']
                    logging.debug(f'Got User id: {self.twitch_user_id}')

    async def twitch_get_stream(self, bearer, client_id):
        logging.info(f'Getting stream info of id {self.twitch_user_id}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/streams?user_id={self.twitch_user_id}', headers=headers) as r:
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
                    await self.twitch_get_stream(self.bearer_token, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    logging.debug(len(js['data']))
                    self.stream_data = js['data']

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.my_background_task.start()

    async def on_ready(self):
        logging.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logging.info('------.v0.4')

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def my_background_task(self):
        await self.twitch_get_stream(self.bearer_token, os.getenv('CLIENT_ID'))
        logging.debug(self.stream_data)
        channel = self.get_channel(int(os.getenv('CHANNEL')))
        if len(self.stream_data) > 0 and self.live is not True:
            message = f"\U0001F534 Ich bin live!\n**{self.stream_data[0]['title']}**\nhttps://www.twitch.tv/{os.getenv('TWITCH_NAME')}"
            await channel.send(message)
            self.live = True
        elif len(self.stream_data) == 0:
            self.live = False

    @my_background_task.before_loop
    async def before_my_task(self):
        await self.twitch_get_user_id(self.bearer_token, os.getenv('TWITCH_NAME'),
                                                     os.getenv('CLIENT_ID'))
        await self.wait_until_ready()  # wait until the bot logs in


client = MyClient(intents=discord.Intents.default())
client.run(TOKEN)
