import logging
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.dates import normalize_date
from app.pagerduty.client import (
    EVENTS_URL,
    PagerDutyClient,
    PagerDutyError
)
from app.pagerduty.incidents import (
    PagerDutyIncidents,
    build_dedup_key
)


def _config(**overrides):

    pagerduty = {
        "enabled": True,
        "events_url": EVENTS_URL,
        "routing_key": "test-routing-key",
        "runbook": "https://runbook.example/velero",
        "alert_name_slug": "velero-backup-issue",
        "severity": "critical",
        "timeout_seconds": 30,
        "max_retries": 1,
        "retry_delay_seconds": 0
    }

    pagerduty.update(overrides)

    return {"pagerduty": pagerduty}


class PagerDutyEventsTests(unittest.TestCase):

    def setUp(self):

        self.logger = logging.getLogger("test.pagerduty")
        self.logger.handlers = []
        self.logger.addHandler(logging.NullHandler())

    def test_normalize_date_from_datetime(self):

        value = datetime(2026, 3, 15, 10, 30, 0)

        self.assertEqual(
            normalize_date(value),
            "2026-03-15"
        )

    def test_build_dedup_key(self):

        self.assertEqual(
            build_dedup_key(
                "my-namespace",
                "velero-backup-issue"
            ),
            "my-namespace-velero-backup-issue"
        )

    @patch("app.pagerduty.client.requests.Session")
    def test_enqueue_uses_events_url_and_post(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "ns-velero-backup-issue"
        }
        session.request.return_value = response

        client = PagerDutyClient(
            _config(),
            self.logger
        )

        client.enqueue({"event_action": "trigger"})

        session.request.assert_called_once_with(
            "POST",
            EVENTS_URL,
            json={"event_action": "trigger"},
            timeout=30
        )

    @patch("app.pagerduty.client.requests.Session")
    def test_payload_uses_namespace_as_event_host(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "prod-ns-velero-backup-issue"
        }
        session.request.return_value = response

        client = PagerDutyClient(
            _config(),
            self.logger
        )

        incidents = PagerDutyIncidents(client, self.logger)

        result = incidents.create_incident(
            namespace="prod-ns",
            event_date="2026-03-15 08:00:00"
        )

        payload = session.request.call_args[1]["json"]

        self.assertEqual(
            payload["routing_key"],
            "test-routing-key"
        )
        self.assertEqual(payload["event_action"], "trigger")
        self.assertEqual(
            payload["dedup_key"],
            "prod-ns-velero-backup-issue"
        )
        self.assertEqual(
            payload["payload"]["custom_details"]["namespace"],
            "prod-ns"
        )
        self.assertEqual(
            payload["payload"]["custom_details"]["event_date"],
            "2026-03-15"
        )
        self.assertEqual(
            payload["payload"]["custom_details"]["event_host"],
            "prod-ns"
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["dedup_key"],
            "prod-ns-velero-backup-issue"
        )

    @patch("app.pagerduty.client.requests.Session")
    def test_severity_comes_from_config(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "success",
            "dedup_key": "prod-ns-velero-backup-issue"
        }
        session.request.return_value = response

        client = PagerDutyClient(
            _config(severity="warning"),
            self.logger
        )

        incidents = PagerDutyIncidents(client, self.logger)

        incidents.create_incident(
            namespace="prod-ns",
            event_date="2026-03-15"
        )

        payload = session.request.call_args[1]["json"]

        self.assertEqual(
            payload["payload"]["severity"],
            "warning"
        )

    @patch("app.pagerduty.client.requests.Session")
    def test_non_success_response_returns_failure(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "invalid event",
            "message": "Event object is invalid"
        }
        session.request.return_value = response

        client = PagerDutyClient(
            _config(),
            self.logger
        )

        incidents = PagerDutyIncidents(client, self.logger)

        result = incidents.create_incident(
            namespace="prod-ns",
            event_date="2026-03-15"
        )

        self.assertEqual(result["status"], "invalid event")
        self.assertIsNone(result["dedup_key"])

    @patch("app.pagerduty.client.requests.Session")
    def test_retry_uses_same_dedup_key(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "success",
            "message": "Event processed",
            "dedup_key": "prod-ns-velero-backup-issue"
        }
        session.request.return_value = response

        client = PagerDutyClient(
            _config(),
            self.logger
        )

        incidents = PagerDutyIncidents(client, self.logger)

        for _ in range(4):
            incidents.create_incident(
                namespace="prod-ns",
                event_date="2026-03-15"
            )

        dedup_keys = [
            call[1]["json"]["dedup_key"]
            for call in session.request.call_args_list
        ]

        self.assertEqual(len(dedup_keys), 4)
        self.assertEqual(
            dedup_keys,
            [
                "prod-ns-velero-backup-issue",
                "prod-ns-velero-backup-issue",
                "prod-ns-velero-backup-issue",
                "prod-ns-velero-backup-issue"
            ]
        )

    @patch("app.pagerduty.client.requests.Session")
    def test_routing_key_not_logged(self, session_cls):

        session = MagicMock()
        session_cls.return_value = session

        response = MagicMock()
        response.ok = True
        response.json.return_value = {
            "status": "success",
            "dedup_key": "prod-ns-velero-backup-issue"
        }
        session.request.return_value = response

        records = []

        class CaptureHandler(logging.Handler):

            def emit(self, record):
                records.append(record.getMessage())

        logger = logging.getLogger("test.pagerduty.capture")
        logger.handlers = []
        logger.addHandler(CaptureHandler())
        logger.setLevel(logging.DEBUG)

        client = PagerDutyClient(
            _config(),
            logger
        )

        incidents = PagerDutyIncidents(client, logger)

        incidents.create_incident(
            namespace="prod-ns",
            event_date="2026-03-15"
        )

        combined = "\n".join(records)

        self.assertNotIn("test-routing-key", combined)


if __name__ == "__main__":
    unittest.main()
