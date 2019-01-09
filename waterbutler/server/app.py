import asyncio
import logging
import os
import signal
from functools import partial

import tornado.platform.asyncio
import tornado.web
from raven.contrib.tornado import AsyncSentryClient

from waterbutler import settings
from waterbutler.server import handlers
from waterbutler.server import settings as server_settings
from waterbutler.server.api import v1
from waterbutler.version import __version__

logger = logging.getLogger(__name__)


def sig_handler(sig, frame):
    io_loop = tornado.ioloop.IOLoop.current()

    def stop_loop():
        if len(asyncio.Task.all_tasks(io_loop)) == 0:
            logger.info('Recieved signal {}. Stopping NOW...'.format(sig))
            io_loop.stop()
        else:
            io_loop.call_later(1, stop_loop)
            logger.info('Recieved signal {}. Waiting for running tasks to finish...'.format(sig))

    io_loop.add_callback_from_signal(stop_loop)


def api_to_handlers(api):
    return [
        (os.path.join('/', api.PREFIX, pattern.lstrip('/')), handler)
        for (pattern, handler) in api.HANDLERS
    ]


def make_app(debug):
    app = tornado.web.Application(
        api_to_handlers(v1) +
        [(r'/status', handlers.StatusHandler)],
        debug=debug,
    )
    app.sentry_client = AsyncSentryClient(settings.SENTRY_DSN, release=__version__)
    return app


def serve():
    app = make_app(server_settings.DEBUG)

    ssl_options = None
    if server_settings.SSL_CERT_FILE and server_settings.SSL_KEY_FILE:
        ssl_options = {
            'certfile': server_settings.SSL_CERT_FILE,
            'keyfile': server_settings.SSL_KEY_FILE,
        }

    app.listen(
        server_settings.PORT,
        address=server_settings.ADDRESS,
        xheaders=server_settings.XHEADERS,
        max_body_size=server_settings.MAX_BODY_SIZE,
        ssl_options=ssl_options,
    )

    logger.info("Listening on {0}:{1}".format(server_settings.ADDRESS, server_settings.PORT))

    signal.signal(signal.SIGTERM, partial(sig_handler))
    tornado.ioloop.IOLoop.current().start()
    # asyncio.get_event_loop().set_debug(server_settings.DEBUG)
    # asyncio.get_event_loop().run_forever()
