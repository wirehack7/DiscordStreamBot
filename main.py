import os
import discord
from dotenv import load_dotenv
from discord.ext import tasks
import aiohttp
import asyncio
import logging
import aiofiles
import aiofiles.os
import giphypop


class MyClient(discord.Client):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # an attribute we can access from our task
        self.twitch_user_id = 0
        self.bearer_token = 0
        self.stream_data = []
        self.live = False
        self.dimensions = {"{width}": "500", "{height}": "281"}
        self.g = giphypop.Giphy(api_key=os.getenv('GIPHY'))
        self.expression = "cat"

    async def twitch_get_bearer(self, client_id: str, client_secret: str):
        logger.info('Getting Twitch bearer token...')
        async with aiohttp.ClientSession() as session:
            async with session.post('https://id.twitch.tv/oauth2/token?' +
                                    f'client_id={client_id}&' +
                                    f'client_secret={client_secret}' +
                                    '&grant_type=client_credentials'
                                    ) as r:
                logger.debug(f'Bearer HTTP status: {r.status}')
                if r.status == 200:
                    js = await r.json()
                    logger.debug(f'Token type: {js["token_type"]}')
                    if js['token_type'] != 'bearer':
                        await session.close()
                        raise ValueError(f'Token type is wrong: {js["token_type"]}')
                    await session.close()
                    return js['access_token']

    async def twitch_get_user_id(self, bearer, username, client_id):
        logger.info(f'Trying to get user id of {username}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/users?login={username}', headers=headers) as r:
                logger.debug(f'HTTP Status: {r.status}')
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
                    await self.twitch_get_user_id(self.bearer_token, username, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    self.twitch_user_id = js['data'][0]['id']
                    logger.debug(f'Got User id: {self.twitch_user_id}')

    async def twitch_get_stream(self, bearer, client_id):
        logger.info(f'Getting stream info of id {self.twitch_user_id}')
        headers = {'Authorization': f'Bearer {bearer}', 'Client-Id': client_id}
        async with aiohttp.ClientSession() as session:
            async with session.get(f'https://api.twitch.tv/helix/streams?user_id={self.twitch_user_id}',
                                   headers=headers) as r:
                if r.status != 200:
                    await session.close()
                    self.bearer_token = await self.twitch_get_bearer(os.getenv('CLIENT_ID'), os.getenv('CLIENT_SECRET'))
                    await self.twitch_get_stream(self.bearer_token, client_id)
                else:
                    js = await r.json()
                    await session.close()
                    logger.debug(len(js['data']))
                    self.stream_data = js['data']

    async def setup_hook(self) -> None:
        # start the task to run in the background
        self.my_background_task.start()

    async def on_ready(self):
        logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        logger.info('------.v0.4')

    @tasks.loop(seconds=60)  # task runs every 60 seconds
    async def my_background_task(self):
        await self.twitch_get_stream(self.bearer_token, os.getenv('CLIENT_ID'))
        logger.debug(self.stream_data)
        channel = self.get_channel(int(os.getenv('CHANNEL')))
        if len(self.stream_data) > 0 and self.live is not True:
            logger.info(f"Found stream with title {self.stream_data[0]['title']}")

            # Create thumbnail url
            image_url = self.stream_data[0]['thumbnail_url']
            # replace dimension placeholders in URL
            for word, dimension in self.dimensions.items():
                image_url = image_url.replace(word, dimension)
            # Try to download thumbnail
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as r:
                    if r.status == 200:
                        f = await aiofiles.open('./stream_thumb.jpg', mode='wb')
                        await f.write(await r.read())
                        await f.close()
                    await session.close()
            message = f"\U0001F534 Ich bin live!\n**{self.stream_data[0]['title']}**\nhttps://www.twitch.tv/{os.getenv('TWITCH_NAME')}"
            try:
                await channel.send(
                    message,
                    suppress_embeds=True,
                    file=discord.File(r'./stream_thumb.jpg'))
                logger.info("Sent chat message")
            except Exception as e:
                logger.error(f"Couldn't send message: {e}")

            await aiofiles.os.remove('./stream_thumb.jpg')
            self.live = True
        elif len(self.stream_data) == 0:
            logger.info(f"{os.getenv('TWITCH_NAME')} is not streaming...")
            self.live = False

    @my_background_task.before_loop
    async def before_my_task(self):
        await self.twitch_get_user_id(self.bearer_token, os.getenv('TWITCH_NAME'),
                                      os.getenv('CLIENT_ID'))
        await self.wait_until_ready()  # wait until the bot logs in

    async def on_message(self, message):
        logger.debug(f"Author var is of type {type(message.author)}")

        if message.author == client.user:
            logger.info("Don't react to own messages")
            return
        elif str(message.author) == "natit":
            self.expression = "dog"
        elif str(message.author) == "wirehack7":
            self.expression = "gundam mech"
        elif str(message.author) == "tongo91":
            self.expression = "panda"
        elif str(message.author) == "lo0twig":
            self.expression = "super mario"
        else:
            self.expression = "cat"

        channel = message.channel
        content = message.content
        user = message.author

        if isinstance(message.channel, discord.channel.DMChannel):
            logger.info(f"Received DM from {message.author}, sending {self.expression} GIF")
            #await self.g.screensaver('cat')

            try:
                await channel.send(f"Hey hey {user.display_name}\n{self.g.screensaver(self.expression).media_url}")
            except Exception as e:
                logger.error(f"Couldn't send message: {e}")


if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(filename)s:%(lineno)s - %(funcName)20s() ] [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    load_dotenv()

    TOKEN = os.getenv('DISCORD_TOKEN')
    client = MyClient(intents=discord.Intents.default())
    client.run(TOKEN)
