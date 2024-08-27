from unittest import IsolatedAsyncioTestCase
from asgiref.sync import sync_to_async
from .test import AppserviceSetup


class MatrixRoomTest(
    AppserviceSetup,
    IsolatedAsyncioTestCase
):
    """
    Test managing companies and units
    """
