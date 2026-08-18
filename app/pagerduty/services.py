from app.pagerduty.client import PagerDutyError


class PagerDutyServices:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

    def find_service(self, namespace):

        if not namespace:
            raise PagerDutyError(
                "Namespace is empty."
            )

        response = self.client.request(
            "GET",
            "/services",
            params={
                "query": namespace,
                "limit": 100
            }
        )

        services = response.json().get(
            "services",
            []
        )

        exact_matches = [
            service
            for service in services
            if service.get("name", "").strip().lower()
            == namespace.strip().lower()
        ]

        if len(exact_matches) == 1:
            return exact_matches[0]

        if not exact_matches:
            raise PagerDutyError(
                "Service not found: {}".format(
                    namespace
                )
            )

        raise PagerDutyError(
            "Multiple exact services found: {}".format(
                namespace
            )
        )