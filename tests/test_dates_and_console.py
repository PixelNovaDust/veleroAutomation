import logging
import unittest
from datetime import datetime
from unittest.mock import patch

from app.console import prompt_target_date
from app.dates import (
    dates_match,
    format_display_date,
    normalize_date
)
from app.processing import is_processed


class DatesAndConsoleTests(unittest.TestCase):

    def setUp(self):

        self.logger = logging.getLogger("test.dates")
        self.logger.handlers = []
        self.logger.addHandler(logging.NullHandler())

    def test_dates_match(self):

        self.assertTrue(
            dates_match(
                "2026-03-15 08:00:00",
                "2026-03-15"
            )
        )

    def test_normalize_date_from_display_format(self):

        self.assertEqual(
            normalize_date("15-03-2026"),
            "2026-03-15"
        )

    def test_format_display_date(self):

        self.assertEqual(
            format_display_date("2026-03-15"),
            "15-03-2026"
        )

    def test_is_processed(self):

        self.assertTrue(is_processed("Yes", "Yes"))
        self.assertFalse(is_processed("No", "Yes"))
        self.assertFalse(is_processed(None, "Yes"))

    @patch("app.console.is_interactive", return_value=True)
    @patch("builtins.input", return_value="15-03-2026")
    def test_prompt_target_date(self, _input, _interactive):

        selected = prompt_target_date()

        self.assertEqual(selected, "2026-03-15")

    @patch("app.console.is_interactive", return_value=False)
    def test_prompt_target_date_non_interactive(self, _interactive):

        selected = prompt_target_date(
            {
                "processing": {
                    "default_date": "2026-03-15"
                }
            }
        )

        self.assertEqual(selected, "2026-03-15")

    def test_normalize_date_from_datetime(self):

        self.assertEqual(
            normalize_date(datetime(2026, 3, 15, 8, 0, 0)),
            "2026-03-15"
        )


if __name__ == "__main__":
    unittest.main()
