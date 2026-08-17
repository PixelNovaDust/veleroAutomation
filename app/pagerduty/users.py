from app.pagerduty.client import PagerDutyError


class PagerDutyUsers:

    def __init__(self, client, logger):

        self.client = client
        self.logger = logger

    def find_user(self, caller):

        if not caller:
            raise PagerDutyError("Caller is empty.")

        response = self.client.request(
            "GET",
            "/users",
            params={
                "query": caller,
                "limit": 100
            }
        )

        users = response.json().get("users", [])

        if not users:

            raise PagerDutyError(
                "PagerDuty user not found: {}".format(
                    caller
                )
            )

        exact_matches = [
            user for user in users
            if user.get("name", "").strip().lower()
            == caller.strip().lower()
        ]

        if len(exact_matches) == 1:

            user = exact_matches[0]

            self.logger.info(
                "PagerDuty user found: %s (%s)",
                user["name"],
                user["id"]
            )

            return user

        if len(users) == 1:

            user = users[0]

            self.logger.info(
                "PagerDuty user found: %s (%s)",
                user["name"],
                user["id"]
            )

            return user

        raise PagerDutyError(
            "Multiple PagerDuty users matched: {}".format(
                caller
            )
        )