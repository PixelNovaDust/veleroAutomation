import logging
import unittest
from unittest.mock import MagicMock

from app.processor import VeleroProcessor


def _headers():

    return {
        "Namespace": 1,
        "Date": 2,
        "Processed": 3,
        "Incident Date": 4,
        "Incident Comment": 5
    }


def _sheet_row(
    namespace="prod-ns",
    backup_date="2026-03-15 08:00:00",
    processed=None,
    incident_date=None,
    incident_comment=None
):

    values = {
        1: namespace,
        2: backup_date,
        3: processed,
        4: incident_date,
        5: incident_comment
    }

    def cell(row, column):

        item = MagicMock()
        item.value = values.get(column)
        return item

    return cell


class ProcessorTests(unittest.TestCase):

    def setUp(self):

        self.logger = logging.getLogger("test.processor")
        self.logger.handlers = []
        self.logger.addHandler(logging.NullHandler())

        self.config = {
            "processing": {
                "processed_value": "Yes",
                "failed_value": "No"
            }
        }

    def _build_processor(self, pagerduty_client):

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = _sheet_row()
        excel_manager.load.return_value = sheet

        return VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty_client,
            logger=self.logger,
            ledger=None
        )

    def test_processes_unprocessed_row_for_selected_date(self):

        pagerduty = MagicMock()
        pagerduty.create_incident.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "prod-ns-velero-backup-issue"
        }

        processor = self._build_processor(pagerduty)
        result = processor.process("2026-03-15")

        pagerduty.create_incident.assert_called_once_with(
            namespace="prod-ns",
            event_date="2026-03-15 08:00:00"
        )
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["failed"], 0)

    def test_success_writes_response_to_comment(self):

        pagerduty = MagicMock()
        pagerduty.create_incident.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "prod-ns-velero-backup-issue",
            "response": {
                "status": "success",
                "message": "Event processed",
                "dedup_key": "prod-ns-velero-backup-issue"
            }
        }

        written = {}

        def cell(row, column):

            item = MagicMock()

            def set_value(value):
                written[column] = value

            item.configure_mock(
                value=written.get(column)
            )
            type(item).value = property(
                lambda self: written.get(column),
                lambda self, value: written.__setitem__(
                    column,
                    value
                )
            )

            return item

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = cell
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        processor.process("2026-03-15")

        comment = written.get(_headers()["Incident Comment"])

        self.assertEqual(comment, "Event processed")

    def test_skips_rows_on_other_dates(self):

        pagerduty = MagicMock()

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = _sheet_row(
            backup_date="2026-03-10 08:00:00"
        )
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        result = processor.process("2026-03-15")

        pagerduty.create_incident.assert_not_called()
        self.assertEqual(result["processed"], 0)

    def test_skips_already_processed_rows(self):

        pagerduty = MagicMock()

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = _sheet_row(processed="Yes")
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        result = processor.process("2026-03-15")

        pagerduty.create_incident.assert_not_called()
        self.assertEqual(result["skipped"], 1)

    def test_pagerduty_rejection_marks_row_failed(self):

        pagerduty = MagicMock()
        pagerduty.create_incident.return_value = {
            "status": "invalid event",
            "message": "Event object is invalid",
            "dedup_key": None
        }

        processor = self._build_processor(pagerduty)
        result = processor.process("2026-03-15")

        self.assertEqual(result["failed"], 1)
        self.assertEqual(
            pagerduty.create_incident.call_count,
            4
        )
        processor.excel_manager.save.assert_called()

    def test_failed_row_retries_after_all_rows(self):

        pagerduty = MagicMock()
        pagerduty.create_incident.side_effect = [
            {
                "status": "success",
                "message": "Event processed",
                "dedup_key": "prod-a-velero-backup-issue"
            },
            {
                "status": "invalid event",
                "message": "Event object is invalid",
                "dedup_key": None
            },
            {
                "status": "success",
                "message": "Event processed",
                "dedup_key": "prod-b-velero-backup-issue"
            }
        ]

        written = {}

        def cell(row, column):

            item = MagicMock()
            type(item).value = property(
                lambda self: written.get((row, column)),
                lambda self, value: written.__setitem__(
                    (row, column),
                    value
                )
            )
            return item

        def sheet_row(row, column):

            rows = {
                2: {
                    1: "prod-a",
                    2: "2026-03-15 08:00:00",
                    3: None,
                },
                3: {
                    1: "prod-b",
                    2: "2026-03-15 09:00:00",
                    3: None,
                }
            }

            item = MagicMock()
            type(item).value = property(
                lambda self: rows.get(row, {}).get(column),
                lambda self, value: rows[row].__setitem__(
                    column,
                    value
                )
            )
            return item

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 3
        sheet.cell = sheet_row
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config={
                "processing": {
                    "processed_value": "Yes",
                    "failed_value": "No",
                    "failed_retry_attempts": 1,
                    "failed_retry_delay_seconds": 0
                }
            },
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        result = processor.process("2026-03-15")

        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(pagerduty.create_incident.call_count, 3)

    def test_mark_unprocessed_failed_writes_comment(self):

        pagerduty = MagicMock()

        written = {}

        def cell(row, column):

            item = MagicMock()
            type(item).value = property(
                lambda self: written.get((row, column)),
                lambda self, value: written.__setitem__(
                    (row, column),
                    value
                )
            )
            return item

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = cell
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        updated = processor.mark_unprocessed_failed(
            "2026-03-15",
            "PagerDuty routing key is not configured."
        )

        self.assertEqual(updated, 1)
        self.assertEqual(
            written.get((2, _headers()["Incident Comment"])),
            "PagerDuty routing key is not configured."
        )
        self.assertEqual(
            written.get((2, _headers()["Processed"])),
            "No"
        )

    def test_empty_namespace_still_triggers_pagerduty(self):

        pagerduty = MagicMock()
        pagerduty.create_incident.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "-velero-backup-issue"
        }

        excel_manager = MagicMock()
        excel_manager.validate_columns.return_value = _headers()

        sheet = MagicMock()
        sheet.max_row = 2
        sheet.cell = _sheet_row(namespace="")
        excel_manager.load.return_value = sheet

        processor = VeleroProcessor(
            excel_manager=excel_manager,
            config=self.config,
            pagerduty_client=pagerduty,
            logger=self.logger,
            ledger=None
        )

        result = processor.process("2026-03-15")

        pagerduty.create_incident.assert_called_once()
        self.assertEqual(result["processed"], 1)


if __name__ == "__main__":
    unittest.main()
