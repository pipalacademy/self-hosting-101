from .tasks import CONFIG, CheckFailed, Task, Validator, add_task, validator
from .app import app as wsgi


__all__ = [
    "App",
    "validator",
    "Validator",
    "CheckFailed"
]


class App:
    def __init__(self, tasks_file, domain=None):
        for t in Task.load_from_file(tasks_file):
            add_task(t)

        if domain is not None:
            self.set_config("domain", domain)

        self.wsgi = wsgi

    def set_config(self, key, value):
        CONFIG[key] = value
