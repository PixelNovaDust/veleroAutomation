import time

import requests

from app.logger import file_only
from app.paths import has_unresolved_variable


RETRYABLE_STATUS_CODES = (429, 500, 502, 503, 504)


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
        self.base_url = pd_config.get(
            "base_url",
            "https://api.pagerduty.com"
        ).rstrip("/")

        self.api_token = pd_config.get("api_token")
        self.urgency = pd_config.get("urgency", "low")
        self.priority_id = pd_config.get("priority_id")

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
        # HTTP 401 much later in the run.
        if has_unresolved_variable(self.api_token):

            raise PagerDutyError(
                "PagerDuty API token is not set. The environment "
                "variable in pagerduty.api_token ({}) is empty "
                "on this machine.".format(
                    self.api_token
                )
            )

        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": "Token token={}".format(
                self.api_token
            ),
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json"
        })

    def validate_connection(self):

        if not self.enabled:

            self.logger.warning(
                "PagerDuty is disabled in the configuration, "
                "no incident will be raised."
            )

            return True

        if not self.api_token:
            raise PagerDutyError(
                "PagerDuty API token is not configured."
            )

        try:

            response = self.request(
                "GET",
                "/users/me"
            )

            user = response.json().get("user")

            if not user:
                raise PagerDutyError(
                    "PagerDuty API responded successfully, "
                    "but user information was not returned."
                )

            self.logger.debug(
                "Pagerduty API is accessible"
            )

            self.logger.debug(
                "PagerDuty token belongs to %s <%s>",
                user.get("name"),
                user.get("email"),
                extra=file_only()
            )

            return True

        except PagerDutyError:
            raise

        except Exception as error:

            self.logger.exception(
                "PagerDuty API validation failed."
            )

            raise PagerDutyError(
                "PagerDuty API validation failed: {}".format(
                    error
                )
            )


    def request(self, method, endpoint, **kwargs):

        url = self.base_url + endpoint

        attempts = max(1, self.max_retries)

        for attempt in range(1, attempts + 1):

            last_attempt = attempt == attempts

            try:

                response = self.session.request(
                    method,
                    url,
                    timeout=self.timeout_seconds,
                    **kwargs
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

            if not self._should_retry(method, response):
                break

            self._pause(response, attempt, attempts)

        if not response.ok:

            try:
                body = response.json()
                message = body.get(
                    "error",
                    response.text
                )
            except ValueError:
                message = response.text

            raise PagerDutyError(
                "PagerDuty API returned HTTP {}: {}".format(
                    response.status_code,
                    message
                )
            )

        return response

    def _should_retry(self, method, response):
        """
        Rate limiting is always safe to retry. A server error is
        only retried for reads, because a repeated POST could
        raise the same incident twice.
        """

        if response.status_code == 429:
            return True

        if str(method).upper() != "GET":
            return False

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