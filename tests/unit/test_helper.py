import unittest
from unittest.mock import MagicMock

class BaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

    def create_mock(self, target: str) -> MagicMock:
        return MagicMock()
