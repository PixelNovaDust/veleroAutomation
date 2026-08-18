import requests


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

        self.logger = logger

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

        try:

            response = self.session.request(
                method,
                url,
                timeout=30,
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