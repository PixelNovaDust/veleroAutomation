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

        exact_matches = [
            user
            for user in users
            if user.get("name", "") == caller
        ]

        if len(exact_matches) == 1:

            user = exact_matches[0]

            self.logger.debug(
                "Caller matched exactly: %s (%s)",
                user["name"],
                user["id"]
            )

            return user

        if not exact_matches:

            raise PagerDutyError(
                "Exact PagerDuty user not found: {}".format(
                    caller
                )
            )

        raise PagerDutyError(
            "Multiple exact PagerDuty users found: {}".format(
                caller
            )
        )