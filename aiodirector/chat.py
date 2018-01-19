from functools import partial
import asyncio
from abc import ABCMeta, abstractmethod
from typing import Dict, Callable
from .app import Component
from .error import PrepareError
from aiotg import Bot


class Handler(object):
    __metaclass__ = ABCMeta

    def __init__(self, app):
        self.app = app
        self.bot: Bot = None
        self._active = 0
        self._stopping = False
        self._stop_fut = asyncio.Future(loop=self.app.loop)

    async def stop(self):
        self._stopping = True
        if self._active > 0:
            self.app.log_info("Waiting for telegram handler to stop")
            await asyncio.wait([self._stop_fut], loop=self.app.loop)

    def _graceful_fn(self, func):
        async def wrap(func, chat, match):
            self._active += 1
            try:
                await func(chat, match)
            finally:
                self._active -= 1
                if self._stopping and self._active == 0:
                    self._stop_fut.set_result(1)

        return partial(wrap, func)

    @abstractmethod
    async def init(self):
        raise NotImplementedError()

    def add_command(self, regexp, fn):
        """
        Manually register regexp based command
        """
        self.bot.add_command(regexp, self._graceful_fn(fn))

    def set_default(self, fn):
        """
        Set callback for default command that is called on unrecognized
        commands for 1-to-1 chats
        If default_in_groups option is True, callback is called in groups too
        """
        self.bot.default(self._graceful_fn(fn))

    def add_inline(self, regexp, fn):
        """
        Manually register regexp based callback
        """
        self.bot.add_inline(regexp, self._graceful_fn(fn))

    def add_callback(self, regexp, fn):
        """
        Manually register regexp based callback
        """
        self.bot.add_inline(regexp, self._graceful_fn(fn))


class Telegram(Component):

    def __init__(self, api_token: str, handler: Handler,
                 connect_max_attempts: int,
                 connect_retry_delay: float) -> None:
        super(Telegram, self).__init__()
        self.tg_id: int = None
        self.tg_first_name: str = None
        self.tg_username: str = None
        self.api_token: str = api_token
        self.bot: Bot = None
        self.handler = handler
        self._connect_max_attempts = connect_max_attempts
        self._connect_retry_delay = connect_retry_delay
        self._run_fut:  asyncio.Future = None

    async def prepare(self) -> None:
        self.app.log_info("Connecting to telegram")
        self.bot = Bot(self.api_token, api_timeout=5)
        self.handler.bot = self.bot
        await self.handler.init()
        attempt = 0
        while True:
            try:
                me = await self.bot.get_me()
                break
            except Exception as e:
                self.app.log_err(e)
                await asyncio.sleep(self._connect_retry_delay)
                if attempt > self._connect_max_attempts:
                    raise PrepareError("Could not connect to telegram")
                attempt += 1

        self.tg_id = me.get('id')
        self.tg_first_name = me.get('first_name')
        self.tg_username = me.get('username')
        self.app.log_info('Connecting to telegram as "%s"' % self.tg_username)

    async def start(self):
        self._run_fut = asyncio.ensure_future(self.bot.loop(), loop=self.loop)

    async def stop(self):
        self.app.log_info("Stopping telegram bot")
        self.bot.stop()
        self._run_fut.cancel()
        await self.handler.stop()
