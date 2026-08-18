from app.pagerduty.client import PagerDutyError


class PagerDutyUsers:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

        # One lookup per distinct caller in a run. A workbook
        # routinely repeats the same caller across rows.
        self.cache = {}

    def find_user(self, caller):

        if not caller:
            raise PagerDutyError(
                "Caller is empty."
            )

        caller = caller.strip()

        cache_key = caller.lower()

        if cache_key in self.cache:

            cached = self.cache[cache_key]

            if isinstance(cached, str):
                raise PagerDutyError(cached)

            return cached

        try:
            user = self._lookup(caller)

        except PagerDutyError as error:

            self.cache[cache_key] = str(error)

            raise

        self.cache[cache_key] = user

        return user

    def _lookup(self, caller):

        response = self.client.request(
            "GET",
            "/users",
            params={
                "query": caller,
                "limit": 100
            }
        )

        users = response.json().get(
            "users",
            []
        )

        # Exact caller-name match.
        exact_matches = [
            user
            for user in users
            if user.get("name", "") == caller
        ]

        if len(exact_matches) == 1:
            return exact_matches[0]

        if not exact_matches:
            raise PagerDutyError(
                "User not found: {}".format(
                    caller
                )
            )

        raise PagerDutyError(
            "Multiple exact users found: {}".format(
                caller
            )
        )
