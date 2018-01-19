import logging
import asyncio
from aiohttp import web, web_request
from typing import List, Tuple, Callable
from aiodirector.app import Application
from aiodirector import http, db, chat


class HttpHandler(http.Handler):
    def __init__(self, app: Application) -> None:
        self.app: Application = None
        super(HttpHandler, self).__init__(app)

    def routes(self) -> List[Tuple[str, str, Callable]]:
        return [
            ('GET', '/', self.home_handler),
        ]

    async def error_handler(self, request: web_request.Request,
                            error: Exception) -> web.Response:
        self.app.log_err(error)
        if isinstance(error, web.HTTPException):
            return error
        return web.Response(body='Internal Error', status=500)

    async def home_handler(self, request: web_request.Request) -> web.Response:
        with self.start_span(request) as span:
            span.name('test:sleep')
            with self.start_span(span) as span2:
                span2.name('test2:sleep')
                await asyncio.sleep(.1, loop=self.app.loop)

        await self.app.db.query_one(self.get_req_span(request),
                                    'test_query', 'SELECT $1::int as a',
                                    123)

        return web.Response(text='Hello world!')


class TelegramHandler(chat.Handler):

    async def init(self):
        cmds = {
            '/start': self.start,
            '/echo (.*)': self.echo,
        }
        for regexp, fn in cmds.items():
            self.add_command(regexp, fn)
        self.default(self._default)

    async def _default(self, chat, message):
        await asyncio.sleep(10)
        await chat.send_text('what?')

    async def start(self, chat, match):
        await chat.send_text('hello')

    async def echo(self, chat, match):
        await chat.reply(match.group(1))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    loop = asyncio.get_event_loop()
    app = Application(
        loop=loop
    )
    app.add(
        'http_server',
        http.Server(
            '127.0.0.1',
            8080,
            HttpHandler(app)
        )
    )
    app.add(
        'db',
        db.PgDb(
            'postgres://user:passwd@localhost:15432/db',
            pool_min_size=2,
            pool_max_size=19,
            pool_max_queries=50000,
            pool_max_inactive_connection_lifetime=300.,
            connect_max_attempts=10,
            connect_retry_delay=1),
        stop_after=['http_server']

    )
    app.add(
        'tg',
        chat.Telegram(
            api_token='143877684:AAFIIvo6NfgjhLzd0KjmKo04F3GaOz2TCdY',
            handler=TelegramHandler(app),
            connect_max_attempts=10,
            connect_retry_delay=1,
        )
    )

    app.setup_logging(
        tracer_driver='zipkin',
        tracer_addr='http://localhost:9411/',
        tracer_name='test-svc',
        tracer_sample_rate=1.0,
        tracer_send_inteval=3,
        metrics_driver='statsd',
        metrics_addr='localhost:8125',
        metrics_name='test_svc_'
    )

    app.run()
