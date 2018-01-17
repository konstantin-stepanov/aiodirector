from abc import ABCMeta, abstractmethod
import io
from typing import List, Tuple, Callable, TypeVar
import asyncio
import traceback
from urllib.parse import urlparse
from aiohttp import web, web_request, ClientSession
from aiohttp import ClientResponse  # noqa
from aiohttp.payload import BytesPayload
from aiohttp import client_exceptions, TCPConnector
from .app import Component
import logging
import aiozipkin as az
import aiozipkin.aiohttp_helpers as azah
import aiozipkin.span as azs # noqa
import aiozipkin.constants as azc


access_logger = logging.getLogger('aiohttp.access')
SPAN_KEY = 'zipkin_span'

SpanContext = TypeVar('SpanContext', web_request.Request, azs.SpanAbc)


class Handler(object):
    __metaclass__ = ABCMeta

    def __init__(self, app):
        """
        :type app: api_subscribe.core.app.BaseApplication
        """
        self.app = app

    @staticmethod
    def get_req_span(request: web_request.Request) -> azs.SpanAbc:
        if SPAN_KEY not in request:
            raise UserWarning('Tracer is not initialized')
        return request[SPAN_KEY]

    def start_span(self, context: SpanContext) -> azs.SpanAbc:
        if isinstance(context, web_request.Request):
            parent = self.get_req_span(context)
        elif isinstance(context, azs.SpanAbc):
            parent = context
        else:
            raise UserWarning('context must be instance of '
                              'aiohttp.web_request.Request or '
                              'aiozipkin.span.SpanAbc')
        span = parent.tracer.new_child(parent.context)
        span.kind(az.CLIENT)
        return span

    @abstractmethod
    def routes(self) -> List[Tuple[str, str, Callable]]:
        raise NotImplementedError()

    @abstractmethod
    def error_handler(self, request: web_request.Request,
                      error: Exception) -> web.Response:
        raise NotImplementedError()


class ResponseCodec:

    async def decode(self, context_span, response):
        """
        :type context_span: azs.Span
        :type response: ClientResponse
        """
        raise NotImplementedError()


class Server(Component):

    def __init__(self, host, port, handler,
                 access_log_format=None, access_log=access_logger,
                 shutdown_timeout=60.0):
        if not isinstance(handler, Handler):
            raise UserWarning()
        super(Server, self).__init__()
        self.host = host
        self.port = port
        self.handler = handler
        self.error_handler = handler.error_handler
        self.routes = handler.routes()
        self.access_log_format = access_log_format
        self.access_log = access_log
        self.shutdown_timeout = shutdown_timeout
        self.web_app = None
        self.web_app_handler = None
        self.servers = None
        self.server_creations = None
        self.uris = None

    async def wrap_middleware(self, app, handler):
        async def middleware_handler(request: web.Request):
            if self.app._tracer:
                context = az.make_context(request.headers)
                if context is None:
                    sampled = azah.parse_sampled(request.headers)
                    debug = azah.parse_debug(request.headers)
                    span = self.app._tracer.new_trace(sampled=sampled,
                                                      debug=debug)
                else:
                    span = self.app._tracer.join_span(context)
                request[SPAN_KEY] = span

                if span.is_noop:
                    resp, trace_str = await self._error_handle(span, request,
                                                               handler)
                    return resp

                with span:
                    span_name = '{0} {1}'.format(request.method.upper(),
                                                 request.path)
                    span.name(span_name)
                    span.kind(azah.SERVER)
                    span.tag(azah.HTTP_PATH, request.path)
                    span.tag(azah.HTTP_METHOD, request.method.upper())
                    _annotate_bytes(span, await request.read())
                    resp, trace_str = await self._error_handle(span, request,
                                                               handler)
                    span.tag(azah.HTTP_STATUS_CODE, resp.status)
                    _annotate_bytes(span, resp.body)
                    if trace_str is not None:
                        span.annotate(trace_str)
                    return resp
            else:
                resp, trace_str = await self._error_handle(None, request,
                                                           handler)
                return resp

        return middleware_handler

    async def _error_handle(self, span, request, handler):
        try:
            return await handler(request), None
        except Exception as herr:
            if span is not None:
                span.tag('error', 'true')
                span.tag('error.message', str(herr))
            try:
                return (await self.error_handler(request, herr),
                        traceback.format_exc())
            except Exception as eerr:
                self.app.log_err(eerr)
                return (web.Response(status=500, text=''),
                        traceback.format_exc())

    async def prepare(self):
        self.app.log_info("Preparing to start http server")
        self.web_app = web.Application(loop=self.loop,
                                       middlewares=[
                                           self.wrap_middleware, ])
        for method, uri, handler in self.routes:
            self.web_app.router.add_route(method, uri, handler)
        await self.web_app.startup()

        make_handler_kwargs = dict()
        if self.access_log_format is not None:
            make_handler_kwargs['access_log_format'] = self.access_log_format
        self.web_app_handler = self.web_app.make_handler(
            loop=self.loop,
            access_log=self.access_log,
            **make_handler_kwargs)
        self.server_creations, self.uris = web._make_server_creators(
            self.web_app_handler,
            loop=self.loop, ssl_context=None,
            host=self.host, port=self.port, path=None, sock=None, backlog=128)

    async def start(self):
        self.app.log_info("Starting http server")
        self.servers = await asyncio.gather(*self.server_creations,
                                            loop=self.loop)
        self.app.log_info('HTTP server ready to handle connections on %s'
                          '' % (', '.join(self.uris), ))

    async def stop(self):
        self.app.log_info("Stopping http server")
        server_closures = []
        for srv in self.servers:
            srv.close()
            server_closures.append(srv.wait_closed())
        await asyncio.gather(*server_closures, loop=self.loop)
        await self.web_app.shutdown()
        await self.web_app_handler.shutdown(self.shutdown_timeout)
        await self.web_app.cleanup()


class Client(Component):
    # TODO make pool of clients

    async def prepare(self):
        pass

    async def start(self):
        pass

    async def stop(self):
        pass

    async def post(self, context_span, span_params, response_codec, url,
                   data=None, headers=None,
                   read_timeout=None, conn_timeout=None, ssl_ctx=None):
        """
        :type context_span: azs.Span
        :type span_params: dict
        :type response_codec: AbstractResponseCodec
        :type url: str
        :type data: bytes
        :type headers: dict
        :type read_timeout: float
        :type conn_timeout: float
        :type ssl_ctx: ssl.SSLContext
        :rtype: Awaitable[ClientResponse]
        """
        conn = TCPConnector(ssl_context=ssl_ctx)
        # TODO проверить доступные хосты для передачи трассировочных заголовков
        headers = headers or {}
        headers.update(context_span.context.make_headers())
        with context_span.tracer.new_child(context_span.context) as span:
            async with ClientSession(loop=self.loop,
                                     headers=headers,
                                     read_timeout=read_timeout,
                                     conn_timeout=conn_timeout,
                                     connector=conn) as session:
                if 'name' in span_params:
                    span.name(span_params['name'])
                if 'endpoint_name' in span_params:
                    span.remote_endpoint(span_params['endpoint_name'])
                if 'tags' in span_params:
                    for tag_name, tag_val in span_params['tags'].items():
                        span.tag(tag_name, tag_val)

                span.kind(az.CLIENT)
                span.tag(azah.HTTP_METHOD, "POST")
                parsed = urlparse(url)
                span.tag(azc.HTTP_HOST, parsed.netloc)
                span.tag(azc.HTTP_PATH, parsed.path)
                span.tag(azc.HTTP_REQUEST_SIZE, str(len(data)))
                span.tag(azc.HTTP_URL, url)
                _annotate_bytes(span, data)
                try:
                    async with session.post(url, data=data) as resp:
                        response_body = await resp.read()
                        _annotate_bytes(span, response_body)
                        span.tag(azc.HTTP_STATUS_CODE, resp.status)
                        span.tag(azc.HTTP_RESPONSE_SIZE,
                                 str(len(response_body)))
                        dec = await response_codec.decode(span, resp)
                        return dec
                except client_exceptions.ClientError as e:
                    span.tag("error.message", str(e))
                    raise


def _annotate_bytes(span, data):
    if isinstance(data, BytesPayload):
        pl = io.BytesIO()
        data.write(pl)
        data = pl.getvalue()
    try:
        data_str = data.decode("UTF8")
    except Exception:
        data_str = str(data)
    span.annotate(data_str or 'null')