from app.pagerduty.client import PagerDutyError


class PagerDutyServices:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

        # One lookup per distinct namespace in a run.
        self.cache = {}

    def find_service(self, namespace):

        if not namespace:
            raise PagerDutyError(
                "Namespace is empty."
            )

        cache_key = namespace.strip().lower()

        if cache_key in self.cache:

            cached = self.cache[cache_key]

            if isinstance(cached, str):
                raise PagerDutyError(cached)

            return cached

        try:
            service = self._lookup(namespace)

        except PagerDutyError as error:

            self.cache[cache_key] = str(error)

            raise

        self.cache[cache_key] = service

        return service

    def _lookup(self, namespace):

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
