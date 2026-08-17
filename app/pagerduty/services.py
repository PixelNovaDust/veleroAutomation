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

        if not services:

            raise PagerDutyError(
                "PagerDuty service not found: {}".format(
                    namespace
                )
            )

        exact_matches = [
            service for service in services
            if service.get("name", "").strip().lower()
            == namespace.strip().lower()
        ]

        if len(exact_matches) == 1:

            service = exact_matches[0]

            self.logger.info(
                "PagerDuty service found: %s (%s)",
                service["name"],
                service["id"]
            )

            return service

        if len(services) == 1:

            service = services[0]

            self.logger.info(
                "PagerDuty service found: %s (%s)",
                service["name"],
                service["id"]
            )

            return service

        raise PagerDutyError(
            "Multiple PagerDuty services matched: {}".format(
                namespace
            )
        )