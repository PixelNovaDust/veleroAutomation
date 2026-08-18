from app.pagerduty.client import PagerDutyError


class PagerDutyUsers:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

    def find_user(self, caller):

        if not caller:
            raise PagerDutyError(
                "Caller is empty."
            )

        caller = caller.strip()

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