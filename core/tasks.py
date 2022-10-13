from __future__ import annotations

import yaml

from dataclasses import dataclass, asdict
from typing import Dict, List, Type


TASKS: List[Task] = []
VALIDATORS: Dict[str, Type[Validator]] = {}

# default config
CONFIG = {
    'domain': "localhost"
}


def get_status(learner_app):
    """Runs the tests for each task and returns the status for each task.
    """
    tasks = {}
    for task in get_tasks():
        task_status = task.verify(learner_app)
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


def validator(v: Type[Validator]):
    """Decorartor to mark a validator

    Marked class should inherit from Validator class
    """
    VALIDATORS[v.__name__] = v
    return v


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

    def verify(self, learner_app) -> TaskStatus:
        base_url = get_base_url(learner_app.name)
        print(f"[{base_url}] verifying task {self.name}...")

        results = [c.verify(learner_app) for c in self.checks]
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
        with open(filename) as f:
            data = yaml.safe_load(f)

        tasks = data["tasks"]
        return [cls.from_dict(t) for t in tasks]

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


def load_tasks():
    tasks_file = CONFIG['tasks_file']
    tasks = Task.load_from_file(tasks_file)
    for task in tasks:
        add_task(task)


def get_tasks():
    if not TASKS:
        load_tasks()

    return TASKS


def get_base_url(app_name):
    base_url_fmt = CONFIG.get("base_url", "http://{name}.{domain}")
    return base_url_fmt.format(name=app_name, domain=CONFIG['domain'])
