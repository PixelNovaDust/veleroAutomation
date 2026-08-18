from app.pagerduty.client import PagerDutyError
from app.pagerduty.users import PagerDutyUsers
from app.pagerduty.services import PagerDutyServices


class PagerDutyIncidents:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

        self.users = PagerDutyUsers(
            client,
            logger
        )

        self.services = PagerDutyServices(
            client,
            logger
        )

    def create_incident(
        self,
        caller,
        namespace,
        description
    ):

        if not self.client.enabled:

            self.logger.info(
                "PagerDuty is disabled."
            )

            return {
                "success": True,
                "incident_id": None
            }

        if not self.client.api_token:

            raise PagerDutyError(
                "PagerDuty API token is not configured."
            )

        user = self.users.find_user(caller)

        service = self.services.find_service(namespace)

        incident = {
            "type": "incident",

            "title": "Velero backup issue for {}".format(
                namespace
            ),

            "service": {
                "id": service["id"],
                "type": "service_reference"
            },

            "urgency": self.client.urgency,

            "status": "triggered",

            "assignments": [
                {
                    "assignee": {
                        "id": user["id"],
                        "type": "user_reference"
                    }
                }
            ],

            "body": {
                "type": "incident_body",
                "details": description or
                "Velero backup issue for {}".format(
                    namespace
                )
            }
        }

        if self.client.priority_id:

            incident["priority"] = {
                "id": self.client.priority_id,
                "type": "priority_reference"
            }

        response = self.client.request(
            "POST",
            "/incidents",
            json={
                "incident": incident
            }
        )

        incident_data = response.json().get(
            "incident"
        )

        if not incident_data:

            raise PagerDutyError(
                "PagerDuty did not return incident details."
            )

        incident_id = incident_data.get("id")

        return {
            "success": True,
            "incident_id": incident_id,
            "incident_number": incident_data.get(
                "incident_number"
            )
        }