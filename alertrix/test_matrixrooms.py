from unittest import IsolatedAsyncioTestCase
from .test import AppserviceSetup


class MatrixRoomTest(
    AppserviceSetup,
    IsolatedAsyncioTestCase
):
    """
    Test managing companies and units
    """
