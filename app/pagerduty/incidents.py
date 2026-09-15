from app.dates import normalize_date
from app.pagerduty.client import PagerDutyError


def build_dedup_key(namespace, alert_name_slug):
    return "{}-{}".format(
        namespace,
        alert_name_slug
    )


class PagerDutyIncidents:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

    def create_incident(
        self,
        namespace,
        event_date,
        description=None
    ):

        if not self.client.enabled:

            self.logger.info(
                "PagerDuty is disabled."
            )

            return {
                "status": "failed",
                "message": "PagerDuty is disabled.",
                "dedup_key": None
            }

        if not self.client.routing_key:

            raise PagerDutyError(
                "PagerDuty routing key is not configured."
            )

        namespace = str(namespace or "").strip()
        formatted_event_date = normalize_date(event_date) or ""
        alert_name_slug = self.client.alert_name_slug

        dedup_key = build_dedup_key(
            namespace,
            alert_name_slug
        )

        payload = {
            "routing_key": self.client.routing_key,
            "event_action": "trigger",
            "dedup_key": dedup_key,
            "payload": {
                "summary": "Velero issue for {}".format(
                    namespace
                ),
                "source": namespace,
                "severity": self.client.severity,
                "custom_details": {
                    "namespace": namespace,
                    "event_date": formatted_event_date,
                    "event_host": namespace,
                    "runbook": self.client.runbook
                }
            }
        }

        self.logger.debug(
            "Submitting PagerDuty event for %s "
            "(dedup_key=%s, event_date=%s)",
            namespace,
            dedup_key,
            formatted_event_date
        )

        response_data = self.client.enqueue(payload)

        status = response_data.get("status")
        message = response_data.get("message", "")

        if status != "success":

            return {
                "status": status or "failed",
                "message": message or str(response_data),
                "dedup_key": None,
                "response": response_data
            }

        response_dedup_key = response_data.get("dedup_key")

        if not response_dedup_key:
            response_dedup_key = dedup_key

        return {
            "status": "success",
            "message": message,
            "dedup_key": response_dedup_key,
            "response": response_data
        }
