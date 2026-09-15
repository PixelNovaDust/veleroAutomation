import time

import requests

from app.paths import has_unresolved_variable


RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)

EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


def _number(value, default, cast=int):
    """
    Read a numeric setting while still honouring a configured
    zero, which a plain `or` fallback would discard.
    """

    if value is None or value == "":
        return default

    try:
        return cast(value)

    except (TypeError, ValueError):
        return default


class PagerDutyError(Exception):
    pass


class PagerDutyClient:

    def __init__(self, config, logger):

        pd_config = config["pagerduty"]

        self.enabled = pd_config.get("enabled", False)
        self.events_url = pd_config.get(
            "events_url",
            EVENTS_URL
        ).rstrip("/")

        self.routing_key = pd_config.get("routing_key")
        self.runbook = pd_config.get("runbook", "")
        self.alert_name_slug = pd_config.get(
            "alert_name_slug",
            "velero-backup-issue"
        )
        self.severity = pd_config.get("severity", "critical")

        self.timeout_seconds = _number(
            pd_config.get("timeout_seconds"),
            30
        )

        self.max_retries = _number(
            pd_config.get("max_retries"),
            3
        )

        self.retry_delay_seconds = _number(
            pd_config.get("retry_delay_seconds"),
            2,
            float
        )

        self.logger = logger

        # An unset environment variable leaves the placeholder
        # behind, which would otherwise surface as a puzzling
        # HTTP error much later in the run.
        if has_unresolved_variable(self.routing_key):

            raise PagerDutyError(
                "PagerDuty routing key is not set. The environment "
                "variable in pagerduty.routing_key ({}) is empty "
                "on this machine.".format(
                    self.routing_key
                )
            )

        self.session = requests.Session()

        self.session.headers.update({
            "Content-Type": "application/json"
        })

    def validate_connection(self):

        if not self.enabled:

            self.logger.warning(
                "PagerDuty is disabled in the configuration, "
                "no incident will be raised."
            )

            return True

        if not self.routing_key:
            raise PagerDutyError(
                "PagerDuty routing key is not configured."
            )

        self.logger.debug(
            "PagerDuty Events API configuration validated"
        )

        return True

    def enqueue(self, payload):

        attempts = max(1, self.max_retries)

        for attempt in range(1, attempts + 1):

            last_attempt = attempt == attempts

            try:

                response = self.session.request(
                    "POST",
                    self.events_url,
                    json=payload,
                    timeout=self.timeout_seconds
                )

            except requests.RequestException as error:

                self.logger.exception(
                    "PagerDuty connection failed"
                )

                raise PagerDutyError(
                    "PagerDuty connection failed: {}".format(
                        error
                    )
                )

            if last_attempt:
                break

            if not self._should_retry(response):
                break

            self._pause(response, attempt, attempts)

        if not response.ok:

            try:
                body = response.json()
                message = body.get(
                    "message",
                    body.get("error", response.text)
                )
            except ValueError:
                message = response.text

            raise PagerDutyError(
                "PagerDuty Events API returned HTTP {}: {}".format(
                    response.status_code,
                    message
                )
            )

        try:
            return response.json()

        except ValueError as error:

            raise PagerDutyError(
                "PagerDuty Events API returned an invalid "
                "response: {}".format(error)
            )

    def _should_retry(self, response):
        """
        Rate limiting is always safe to retry. A server error is
        only retried for POST when PagerDuty asks us to wait.
        """

        if response.status_code == 429:
            return True

        return response.status_code in RETRYABLE_STATUS_CODES

    def _pause(self, response, attempt, attempts):

        delay_seconds = self.retry_delay_seconds * attempt

        retry_after = response.headers.get("Retry-After")

        if retry_after:

            try:
                delay_seconds = float(retry_after)

            except ValueError:
                pass

        self.logger.warning(
            "PagerDuty returned HTTP %s, retrying in %ss "
            "(attempt %d of %d)",
            response.status_code,
            int(delay_seconds),
            attempt,
            attempts
        )

        time.sleep(max(0, delay_seconds))
