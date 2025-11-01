import time
from datetime import datetime
import configparser
import os
from typing import Dict, Optional, Any

import discord
from discord.ext import tasks

import aiohttp
import logging
import aiofiles
import aiofiles.os
import asyncio


class MyClient(discord.Client):
    def __init__(self, logging_enabled: bool = True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logging_enabled = logging_enabled
        self.logging = logging.getLogger(__name__) if logging_enabled else None

        self.config = configparser.ConfigParser()
        try:
            # Look for config.ini in project root, then in config/ subdirectory
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(project_root, "config.ini")
            if not os.path.exists(config_path):
                config_path = os.path.join(project_root, "config", "config.ini.dist")
            with open(config_path) as fh:
                self.config.read_file(fh)
            fh.close()
        except Exception as e:
            raise FileNotFoundError(f"Cannot find config file: {e}")

        if "DISCORD" not in self.config or "TWITCH" not in self.config:
            raise ValueError("Section for config not found, please check your config!")

        # Performance: Cache frequently accessed config values
        self.discord_config = self.config["DISCORD"]
        self.twitch_config = self.config["TWITCH"]

        # Stream monitoring attributes
        self.hour = ""
        self.minute = ""
        self.bearer_token = None
        self.bearer_token_expires = 0
        self.streams: Dict[str, Dict[str, Any]] = {}
        self.stream_data = []
        self.live = False
        self.dimensions = {"{width}": "500", "{height}": "281"}
        self.thumbnail = False
        self.list_streams = self.twitch_config["streams"].split(",")
        self.twitch_user_id = ""
        self.leet = False

        # Performance: Cache user IDs to avoid repeated API calls
        self.user_id_cache: Dict[str, str] = {}

        # Performance: Reuse HTTP session
        self.http_session: Optional[aiohttp.ClientSession] = None

        # Message logging setup (only if enabled)
        self.message_logging_enabled = (
            self.logging_enabled and self.discord_config.get("logging", "") != ""
        )

        if self.message_logging_enabled:
            self.queue = asyncio.Queue()
            self.worker_task = None
            # Ensure server_log directory exists
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            server_log_dir = os.path.join(project_root, "data", "server_log")
            os.makedirs(server_log_dir, exist_ok=True)

        # Initialize streams dictionary
        for stream in self.list_streams:
            stream = stream.strip()  # Performance: strip whitespace once
            if stream:  # Skip empty strings
                self.streams[stream] = {"name": stream, "id": 0, "live": False}

    def _log_info(self, message: str) -> None:
        """Safe logging method that only logs if logging is enabled"""
        if self.logging_enabled and self.logging:
            self.logging.info(message)

    def _log_debug(self, message: str) -> None:
        """Safe logging method that only logs if logging is enabled"""
        if self.logging_enabled and self.logging:
            self.logging.debug(message)

    def _log_warning(self, message: str) -> None:
        """Safe logging method that only logs if logging is enabled"""
        if self.logging_enabled and self.logging:
            self.logging.warning(message)

    def _log_error(self, message: str) -> None:
        """Safe logging method that only logs if logging is enabled"""
        if self.logging_enabled and self.logging:
            self.logging.error(message)

    async def setup_hook(self) -> None:
        """Initialize async components"""
        # Create persistent HTTP session for better performance
        self.http_session = aiohttp.ClientSession()

        # Only start message logging worker if enabled
        if self.message_logging_enabled:
            self.worker_task = asyncio.create_task(self.worker())

        # Get initial bearer token and user IDs
        await self._initialize_twitch_data()

        # Start the background task for Twitch monitoring
        self.background_twitch.start()

    async def close(self) -> None:
        """Clean shutdown"""
        if self.http_session:
            await self.http_session.close()

        if self.worker_task and self.message_logging_enabled:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        await super().close()

    async def _initialize_twitch_data(self) -> None:
        """Initialize Twitch bearer token and user IDs"""
        try:
            self.bearer_token = await self.twitch_get_bearer(
                self.twitch_config["client_id"], self.twitch_config["client_secret"]
            )
            await self.twitch_get_user_ids(
                self.bearer_token, self.streams, self.twitch_config["client_id"]
            )
        except Exception as e:
            self._log_error(f"Failed to initialize Twitch data: {e}")

    async def _ensure_valid_token(self) -> str:
        """Ensure we have a valid bearer token, refresh if needed"""
        current_time = time.time()

        # Refresh token if it's expired or will expire soon (with 5 min buffer)
        if not self.bearer_token or current_time >= (self.bearer_token_expires - 300):
            self._log_info("Refreshing Twitch bearer token...")
            self.bearer_token = await self.twitch_get_bearer(
                self.twitch_config["client_id"], self.twitch_config["client_secret"]
            )

        return self.bearer_token

    async def twitch_get_bearer(self, client_id: str, client_secret: str) -> str:
        """Get Twitch bearer token with improved error handling"""
        self._log_info("Getting Twitch bearer token...")

        url = (
            f"https://id.twitch.tv/oauth2/token?"
            f"client_id={client_id}&"
            f"client_secret={client_secret}&"
            f"grant_type=client_credentials"
        )

        try:
            async with self.http_session.post(url) as r:
                self._log_debug(f"Bearer HTTP status: {r.status}")

                if r.status == 200:
                    js = await r.json()

                    if js.get("token_type") != "bearer":
                        raise ValueError(f"Invalid token type: {js.get('token_type')}")

                    # Cache token expiration time
                    self.bearer_token_expires = time.time() + js.get("expires_in", 3600)

                    self._log_debug(f"Token expires in: {js.get('expires_in')} seconds")
                    return js["access_token"]
                else:
                    error_text = await r.text()
                    raise aiohttp.ClientResponseError(
                        r.request_info, r.history, status=r.status, message=error_text
                    )
        except Exception as e:
            self._log_error(f"Failed to get bearer token: {e}")
            raise

    async def twitch_get_user_ids(
        self, bearer: str, streams: Dict[str, Dict], client_id: str
    ) -> None:
        """Get Twitch user IDs with batch processing and caching"""
        self._log_debug(f"Getting user IDs for streams: {list(streams.keys())}")

        headers = {"Authorization": f"Bearer {bearer}", "Client-Id": client_id}

        # Performance: Batch process multiple usernames in one request
        uncached_streams = [
            stream for stream in streams.keys() if stream not in self.user_id_cache
        ]

        if not uncached_streams:
            # All streams are cached, update from cache
            for stream in streams:
                if stream in self.user_id_cache:
                    streams[stream]["id"] = self.user_id_cache[stream]
            return

        # Build batch request URL (Twitch API supports multiple login names)
        login_params = "&".join([f"login={stream}" for stream in uncached_streams])
        url = f"https://api.twitch.tv/helix/users?{login_params}"

        try:
            async with self.http_session.get(url, headers=headers) as r:
                self._log_debug(f"User IDs HTTP Status: {r.status}")

                if r.status == 401:  # Token expired
                    self._log_info("Token expired, refreshing...")
                    new_bearer = await self._ensure_valid_token()
                    await self.twitch_get_user_ids(new_bearer, streams, client_id)
                    return
                elif r.status != 200:
                    error_text = await r.text()
                    self._log_error(
                        f"Failed to get user IDs: {r.status} - {error_text}"
                    )
                    return

                js = await r.json()

                # Update cache and streams
                for user_data in js.get("data", []):
                    login = user_data["login"]
                    user_id = user_data["id"]

                    self.user_id_cache[login] = user_id
                    if login in streams:
                        streams[login]["id"] = user_id
                        self._log_debug(f"Got User ID for {login}: {user_id}")

        except Exception as e:
            self._log_error(f"Exception getting user IDs: {e}")

    async def twitch_get_stream(
        self, bearer: str, client_id: str, twitch_user_id: str
    ) -> None:
        """Get stream information with improved error handling"""
        self._log_info(f"Getting stream info for user ID: {twitch_user_id}")

        headers = {"Authorization": f"Bearer {bearer}", "Client-Id": client_id}
        url = f"https://api.twitch.tv/helix/streams?user_id={twitch_user_id}"

        try:
            async with self.http_session.get(url, headers=headers) as r:
                if r.status == 401:  # Token expired
                    new_bearer = await self._ensure_valid_token()
                    await self.twitch_get_stream(new_bearer, client_id, twitch_user_id)
                    return
                elif r.status != 200:
                    error_text = await r.text()
                    self._log_error(
                        f"Failed to get stream info: {r.status} - {error_text}"
                    )
                    self.stream_data = []
                    return

                js = await r.json()
                self.stream_data = js.get("data", [])
                self._log_debug(f"Stream data length: {len(self.stream_data)}")

        except Exception as e:
            self._log_error(f"Exception getting stream info: {e}")
            self.stream_data = []

    async def get_stream_thumb(self, url: str, stream: str) -> bool:
        """Download stream thumbnail with improved error handling and performance"""
        try:
            self._log_debug(f"Downloading thumbnail: {url}")

            async with self.http_session.get(url) as r:
                if r.status == 200:
                    # Save thumbnail in data/images subdirectory
                    project_root = os.path.dirname(
                        os.path.dirname(os.path.dirname(__file__))
                    )
                    images_dir = os.path.join(project_root, "data", "images")
                    # Ensure images directory exists
                    os.makedirs(images_dir, exist_ok=True)
                    file_path = os.path.join(images_dir, f"{stream}_thumb.jpg")

                    # Performance: Use async file operations
                    async with aiofiles.open(file_path, mode="wb") as f:
                        async for chunk in r.content.iter_chunked(8192):  # 8KB chunks
                            await f.write(chunk)

                    self._log_debug(f"Successfully downloaded thumbnail for {stream}")
                    return True
                else:
                    self._log_warning(f"Failed to download thumbnail: HTTP {r.status}")
                    return False

        except Exception as e:
            self._log_error(f"Exception downloading thumbnail: {e}")
            return False

    async def sendleet(self, channel_id: int) -> None:
        """Send 1337 message at the right time"""
        self._log_info("Checking time for leet message")

        c = datetime.now()
        self.hour = c.strftime("%H")
        self.minute = c.strftime("%M")

        if self.hour == "14":
            self.leet = False

        channel = self.get_channel(channel_id)
        if not channel:
            self._log_error(f"Could not find channel with ID: {channel_id}")
            return

        if self.hour == "13" and self.minute == "37" and not self.leet:
            try:
                leet_user = self.discord_config.get("leet_user", "").strip()
                message = f"1337 <@{leet_user}>" if leet_user else "1337"

                await channel.send(message)
                self.leet = True
                self._log_info("Sent leet message")

            except Exception as e:
                self._log_error(f"Failed to send leet message: {e}")

    @tasks.loop(seconds=60)
    async def background_twitch(self):
        """Main background task for Twitch monitoring"""
        try:
            # Send leet message if configured
            leet_channel = self.discord_config.get("leet_channel", "").strip()
            if leet_channel:
                await self.sendleet(int(leet_channel))

            # Process each stream
            for stream_name, stream_info in self.streams.items():
                await self._process_stream(stream_name, stream_info)

        except Exception as e:
            self._log_error(f"Error in background task: {e}")

    async def _process_stream(self, stream_name: str, stream_info: Dict) -> None:
        """Process a single stream for live status"""
        self._log_info(f"Processing stream: {stream_name}")

        try:
            # Ensure we have a valid token
            bearer = await self._ensure_valid_token()

            # Get stream information
            await self.twitch_get_stream(
                bearer, self.twitch_config["client_id"], stream_info["id"]
            )

            channel_id = self.discord_config.get("channel", "").strip()
            if not channel_id:
                self._log_warning("No Discord channel configured")
                return

            channel = self.get_channel(int(channel_id))
            if not channel:
                self._log_error(f"Could not find Discord channel: {channel_id}")
                return

            # Check if stream went live
            if len(self.stream_data) > 0 and not stream_info["live"]:
                await self._handle_stream_live(stream_name, stream_info, channel)
            elif len(self.stream_data) == 0:
                self._log_info(f"{stream_name} is not streaming...")
                stream_info["live"] = False

        except Exception as e:
            self._log_error(f"Error processing stream {stream_name}: {e}")

    async def _handle_stream_live(
        self, stream_name: str, stream_info: Dict, channel
    ) -> None:
        """Handle when a stream goes live"""
        stream_data = self.stream_data[0]
        self._log_info(f"Stream {stream_name} went live: {stream_data['title']}")

        # Create thumbnail URL
        image_url = stream_data["thumbnail_url"]
        for placeholder, dimension in self.dimensions.items():
            image_url = image_url.replace(placeholder, dimension)

        # Download thumbnail with timeout
        thumbnail_downloaded = False
        try:
            thumbnail_downloaded = await asyncio.wait_for(
                self.get_stream_thumb(image_url, stream_name), timeout=5.0
            )
        except asyncio.TimeoutError:
            self._log_warning(f"Thumbnail download timed out for {stream_name}")

        # Build message
        message_template = self.discord_config.get("message", "{name} is live!")
        message = message_template.replace("{name}", stream_name).replace(
            "{user}", stream_name
        )
        message += f"\n**{stream_data['title']}**\n"
        message += f"https://www.twitch.tv/{stream_name}"

        # Send message
        try:
            if thumbnail_downloaded:
                project_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(__file__))
                )
                images_dir = os.path.join(project_root, "data", "images")
                file_path = os.path.join(images_dir, f"{stream_name}_thumb.jpg")
                await channel.send(
                    message, suppress_embeds=True, file=discord.File(file_path)
                )
                # Clean up thumbnail file
                try:
                    await aiofiles.os.remove(file_path)
                except Exception:
                    pass  # Ignore cleanup errors
            else:
                await channel.send(message, suppress_embeds=True)

            stream_info["live"] = True
            self._log_info(f"Sent live notification for {stream_name}")

        except Exception as e:
            self._log_error(f"Failed to send live notification for {stream_name}: {e}")

    @background_twitch.before_loop
    async def background_twitch_before(self):
        """Setup before starting the background loop"""
        self._log_debug("Initializing background task...")
        await self.wait_until_ready()

    async def worker(self) -> None:
        """Message logging worker (only runs if logging enabled)"""
        if not self.message_logging_enabled:
            return

        while True:
            try:
                message, log_file = await self.queue.get()

                # Build log entry
                attachments_text = ""
                if message.attachments:
                    attachments_text = " Attachments: " + " ".join(
                        attachment.url for attachment in message.attachments
                    )

                log_entry = (
                    f"[{message.created_at}] {message.channel.name} "
                    f"{message.author.display_name}({message.author.name}): "
                    f"{message.content}{attachments_text}\n"
                )

                # Write to log file
                async with aiofiles.open(log_file, mode="a+", encoding="utf-8") as logs:
                    await logs.write(log_entry)

                self.queue.task_done()

            except Exception as e:
                self._log_error(f"Error in message logging worker: {e}")

    async def on_message(self, message: Any) -> None:
        """Handle incoming messages"""
        # Don't log own messages
        if message.author.id == self.user.id:
            self._log_debug("Ignoring own message")
            return

        # Only process message logging if enabled
        if not self.message_logging_enabled:
            return

        # Check if message is from the configured guild
        logging_guild_id = self.discord_config.get("logging", "").strip()
        if not logging_guild_id:
            return

        try:
            if message.guild and message.guild.id == int(logging_guild_id):
                project_root = os.path.dirname(
                    os.path.dirname(os.path.dirname(__file__))
                )
                log_file = os.path.join(
                    project_root,
                    "data",
                    "server_log",
                    f"{message.guild.name}_messages.txt",
                )
                await self.queue.put((message, log_file))
                self._log_debug(f"Queued message for logging: {message.id}")
        except (ValueError, TypeError) as e:
            self._log_error(f"Invalid logging guild ID configuration: {e}")

    async def on_ready(self) -> None:
        """Bot ready event"""
        self._log_info(f"Logged in as {self.user} (ID: {self.user.id})")
        self._log_info("------v0.5 (Performance Optimized)")

        # Set bot presence
        game = discord.Game("Counting 1 and 0 BEEBOOP")
        await self.change_presence(status=discord.Status.online, activity=game)

        self._log_info(f"Monitoring {len(self.streams)} streams")
        if self.logging_enabled:
            self._log_debug(f"Streams: {list(self.streams.keys())}")
