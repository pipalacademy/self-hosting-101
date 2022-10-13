import requests

from core import App, ValidationError, Validator, get_base_url


app = App("tasks.yml")


@app.validator
class check_http_status(Validator):
    def __init__(self, url, expected_status):
        self.url = url
        self.expected_status = expected_status

    def __str__(self):
        return f"Check HTTP status: {self.url} [{self.expected_status}]"

    def validate(self, app):
        url = get_base_url(app.name) + self.url
        r = requests.get(url)
        if str(r.status_code) != str(self.expected_status):
            raise ValidationError(
                f"For URL {self.url}, actual status code {r.status_code} "
                f"does not match expected status code {self.expected_status}"
            )


if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else None
    if domain is not None:
        app.set_config("domain", domain)

    app.wsgi.run()
