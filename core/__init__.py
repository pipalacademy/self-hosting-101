import requests
import yaml

from .tasks import CONFIG, ValidationError, Validator, validator, get_base_url
from .app import app as wsgi


class App:
    def __init__(self, tasks_file):
        self.tasks_file = tasks_file
        self.wsgi = wsgi

        self.set_config("tasks_file", self.tasks_file)
        self.load_config(self.tasks_file)

        # add validators
        self.validator(check_not_implemented)
        self.validator(check_webpage_content)

    def set_config(self, key, value):
        CONFIG[key] = value

    def load_config(self, path):
        with open(path) as f:
            config = yaml.safe_load(f).get("config", {})

        for key, val in config.items():
            self.set_config(key, val)

    def validator(self, *args, **kwargs):
        return validator(*args, **kwargs)

    def verify(self, app):
        return app.verify()


class check_not_implemented(Validator):
    def __init__(self):
        pass

    def __str__(self):
        return "Checks are not yet implemented for this task"

    def validate(self, app):
        raise ValidationError("coming soon...")


class check_webpage_content(Validator):
    def __init__(self, url, expected_text):
        self.url = url
        self.expected_text = expected_text

    def __str__(self):
        return f"Check webpage content: {self.url}"

    def validate(self, app):
        base_url = get_base_url(app.name)
        url = f"{base_url}{self.url}"
        if self.expected_text not in requests.get(url).text:
            message = f'Text "{self.expected_text}"\nis expected in the web page {url},\nbut it is not found.'
            raise ValidationError(message)
