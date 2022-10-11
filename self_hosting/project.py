from core import App, CheckFailed, Validator, validator


@validator
class check_http_status(Validator):
    def __init__(self, url, expected_status):
        self.url = url
        self.expected_status = expected_status

        self.title = f"Check HTTP status: {self.url} [{self.expected_status}]"

    def do_validate(self, site):
        # NOTE: maybe this can just be a function that should return a bool
        # value? that would be simpler than raising an exception, but would
        # also not have custom error statements
        r = site.get(self.url)
        if str(r.status_code) != str(self.expected_status):
            raise CheckFailed(
                f"For URL {self.url}, actual status code {r.status_code} "
                f"does not match expected status code {self.expected_status}"
            )


app = App("tasks.yml")


if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else None
    if domain is not None:
        app.set_config("domain", domain)

    app.wsgi.run()
