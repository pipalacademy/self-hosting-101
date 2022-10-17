from __future__ import annotations

import yaml

from dataclasses import dataclass
from typing import List


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


class ValidationError(Exception):
    pass


class Validator:
    def verify(self, app):
        status = CheckStatus(str(self))
        try:
            self.validate(app)
            return status
        except ValidationError as e:
            return status.fail(str(e))
        except Exception as e:
            return status.error(str(e))

    def validate(self, app):
        raise NotImplementedError()


@dataclass
class TaskStatus:
    PASS = "pass"
    FAIL = "fail"

    status: str
    checks: List[CheckStatus]


@dataclass
class Task:
    name: str
    title: str
    description: str
    checks: List[Validator]


class TaskParser:
    def __init__(self, tasks_file, validators):
        self.tasks_file = tasks_file
        self.validators = validators

    def load_from_file(self, filename) -> List[Task]:
        """Loads a list of tasks from a file.
        """
        with open(filename) as f:
            data = yaml.safe_load(f)

        tasks = data['tasks']
        return [self.from_dict(t) for t in tasks]

    def from_dict(self, data) -> Task:
        """Loads a Task from dict.
        """
        name = data['name']
        title = data['title']
        description = data['description']
        checks = [self.parse_check(c) for c in data['checks']]
        return Task(name, title, description, checks)

    def parse_check(self, check_data):
        if isinstance(check_data, str):
            return self.validators[check_data]()
        elif isinstance(check_data, dict) and len(check_data) == 1:
            name, args = list(check_data.items())[0]
            cls = self.validators[name]
            return cls(**args)
        else:
            raise ValueError(f"Invalid check: {check_data}")
