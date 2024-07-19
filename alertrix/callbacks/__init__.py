import inspect
import logging
import re
import traceback
from dataclasses import dataclass

import nio
from matrixappservice import MatrixClient

from . import alertrix
from . import directmessage
from . import encryption
from . import onboarding


@dataclass
class RecursiveMessageHandler:
    """
    Recursively searches through a nested list of patterns and callbacks until it finds a pattern that matches the
    attributes name and calls that callback.
    """
    attribute_prefix: str  # Look only at attributes that start with this prefix
    callbacks: [list, tuple]

    async def __call__(
            self,
            client: MatrixClient,
            room: nio.MatrixRoom,
            event: nio.RoomMessage,
            prefix: str = None,
            callbacks: [list, tuple] = None,
            *args, **kwargs,
    ):
        if prefix is None:
            prefix = self.attribute_prefix
        if callbacks is None:
            callbacks = self.callbacks
        # Use this flag to only process the first valid attribute of the event
        attribute_processed = False
        for attribute in event.source['content'].keys():
            if attribute.startswith(prefix):
                next_level_prefix = attribute.removeprefix(prefix + '.').split('.')[0]
                for pattern, callback in callbacks:
                    if not re.match(pattern, next_level_prefix):
                        continue
                    attribute_processed = True
                    if callable(callback):
                        try:
                            args = (
                                client,
                                room,
                                event,
                            )
                            kwargs = {}
                            cb_response = callback(
                                *args,
                                **kwargs,
                            )
                            if inspect.isawaitable(cb_response):
                                await cb_response
                        except Exception as e:
                            logging.warning(
                                '%(error_type)s exception while running %(function)s for pattern "%(pattern)s"' % {
                                    'error_type': str(type(e)),
                                    'function': callback,
                                    'pattern': pattern,
                                },
                            )
                            logging.warning(''.join(traceback.format_exception(e)))
                    elif '__iter__' in dir(callback):
                        await self.__call__(
                            client,
                            room,
                            event,
                            prefix='.'.join([prefix, next_level_prefix]),
                            callbacks=callback,
                        )
                    else:
                        try:
                            raise TypeError(
                                'cannot use object of type \'%(type)s\' as callback' % {
                                    'type': type(callback),
                                },
                            )
                        except TypeError as e:
                            logging.warning(''.join(traceback.format_exception(e)))
            if attribute_processed:
                break
