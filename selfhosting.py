import requests

from core import App, ValidationError, Validator


app = App("tasks.yml")


@app.validator
class check_http_status(Validator):
    def __init__(self, url, expected_status):
        self.url = url
        self.expected_status = expected_status

    def __str__(self):
        return f"Check HTTP status: {self.url} [{self.expected_status}]"

    def validate(self, learner_app):
        url = learner_app.base_url + self.url
        r = requests.get(url)
        if str(r.status_code) != str(self.expected_status):
            raise ValidationError(
                f"For URL {self.url}, actual status code {r.status_code} "
                f"does not match expected status code {self.expected_status}"
            )


@app.validator
class check_package_exists(Validator):
    def __init__(self, package):
        self.package = package

    def __str__(self):
        return f"Check package exists: {self.package}"

    def validate(self, app):
        r = requests.get(f"{app.base_url}/packages/{self.package}")
        print("status: ", r.status_code)
        print(r.json())
        if r.status_code != 200:
            raise ValidationError(f"Package {self.package} does not exist")


@app.validator
class check_file_exists(Validator):
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return f"Check file exists: {self.path}"

    def validate(self, app):
        r = requests.get(f"{app.base_url}/{self.path}")
        if r.status_code != 200:
            raise ValidationError(f"File {self.path} does not exist")


@app.validator
class check_user_exists(Validator):
    def __init__(self, user):
        self.user = user

    def __str__(self):
        return f"Check user exists: {self.user}"

    def validate(self, app):
        r = requests.get(f"{app.base_url}/users")
        r.raise_for_status()

        users = r.json()["data"]["users"]
        if self.user not in users:
            raise ValidationError(f"User {self.user} does not exist")


if __name__ == "__main__":
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        app.wsgi.run(debug=True)

    elif cmd == "new":
        app_name = sys.argv[2]
        learner_app = app.new_app(app_name)
        print(f"App created: {learner_app.base_url}")

    elif cmd == "check":
        app_name = sys.argv[2]
        from core import LearnerApp
        learner_app = LearnerApp.find(app_name)
        if not learner_app:
            print(f"App not found: {app_name}")
            sys.exit(1)
        status = app.get_status(learner_app)
        print(status)
        learner_app.update_status(status)

    else:
        print("invalid command: ", cmd)
        sys.exit(1)
