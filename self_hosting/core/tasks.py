from __future__ import annotations

import contextlib
import requests
import yaml

from dataclasses import dataclass, asdict
from typing import Dict, List, Type


TASKS: List[Task] = []
VALIDATORS: Dict[str, Type[Validator]] = {}

CONFIG = {
    'domain': "localhost"
}


class Site:
    def __init__(self, name):
        self.name = name
        if name == "localhost":
            self.domain = "localhost"
            self.base_url = "http://localhost:5050"
        else:
            self.domain = f"{name}.{CONFIG['domain']}"
            self.base_url = f"https://{self.domain}"

        self.session = requests

    @contextlib.contextmanager
    def with_session(self):
        with requests.Session() as sess:
            self.session = sess
            try:
                yield self.session
            finally:
                self.session = requests

    def get(self, path, **kwargs):
        url = self.base_url.rstrip("/") + path
        print("GET", url)
        return self.session.get(url, **kwargs)

    def post(self, path, **kwargs):
        url = self.base_url.rstrip("/") + path
        print("POST", url)
        return self.session.post(url, **kwargs)

    def get_status(self):
        """Runs the tests for each task and returns the status for each task.
        """
        tasks = {}
        for task in TASKS:
            task_status = task.verify(self)
            tasks[task.name] = asdict(task_status)
            if task_status.status != TaskStatus.PASS:
                break
        return dict(tasks=tasks, current_task=task.name)


@dataclass
class CheckStatus:
    title: str
    status: str = "pass"
    message: str = ""

    def fail(self, message):
        self.status = "fail"
        self.message = message
        return self

    def error(self, message):
        self.status = "error"
        self.message = message
        return self


class CheckFailed(Exception):
    pass


class Validator:
    def validate(self, site):
        status = CheckStatus(self.title)
        try:
            self.do_validate(site)
            return status
        except CheckFailed as e:
            return status.fail(str(e))
        except Exception as e:
            return status.error(str(e))

    def do_validate(self, site):
        raise NotImplementedError()


def validator(v: Type[Validator]):
    """Decorartor to mark a validator

    Marked class should inherit from Validator class
    """
    VALIDATORS[v.__name__] = v
    return v


@validator
class check_not_implemented(Validator):
    def __init__(self):
        self.title = "Checks are not yet implemented for this task"

    def do_validate(self, site):
        raise CheckFailed("coming soon...")


@validator
class check_webpage_content(Validator):
    def __init__(self, url, expected_text):
        self.url = url
        self.expected_text = expected_text
        self.title = f"Check webpage content: {url}"

    def do_validate(self, site):
        if self.expected_text not in site.get(self.url).text:
            message = f'Text "{self.expected_text}"\nis expected in the web page {site.base_url}{self.url},\nbut it is not found.'
            raise CheckFailed(message)


@dataclass
class TaskStatus:
    PASS = "pass"
    FAIL = "fail"

    status: str
    checks: List[CheckStatus]


class Task:
    def __init__(self, name, title, description, checks):
        self.name = name
        self.title = title
        self.description = description
        self.checks = checks

    def verify(self, site) -> TaskStatus:
        print(f"[{site.domain}] verifying task {self.name}...")

        results = [c.validate(site) for c in self.checks]
        print(results)
        if all(c.status == TaskStatus.PASS for c in results):
            status = TaskStatus.PASS
        else:
            status = TaskStatus.FAIL
        return TaskStatus(status, checks=results)

    @classmethod
    def load_from_file(cls, filename) -> List[Task]:
        """Loads a list of tasks from a file.
        """
        data = yaml.safe_load_all(open(filename))
        return [cls.from_dict(d) for d in data]

    @classmethod
    def from_dict(cls, data) -> Task:
        """Loads a Task from dict.
        """
        name = data['name']
        title = data['title']
        description = data['description']
        checks = [cls.parse_check(c) for c in data['checks']]
        return Task(name, title, description, checks)

    @staticmethod
    def parse_check(check_data):
        if isinstance(check_data, str):
            return VALIDATORS[check_data]()
        elif isinstance(check_data, dict) and len(check_data) == 1:
            name, args = list(check_data.items())[0]
            cls = VALIDATORS[name]
            return cls(**args)
        else:
            raise ValueError(f"Invalid check: {check_data}")


def add_task(t: Task):
    TASKS.append(t)


def main():
    import sys, json
    name = sys.argv[1]
    site = Site(name)
    print(json.dumps(site.get_status(), indent=2))


if __name__ == "__main__":
    main()
