import logging
import traceback
import nio
from asgiref.sync import sync_to_async
from matrixappservice import MatrixClient
from matrixappservice.models import Event
from alertrix.events import v1


callbacks = (
)
