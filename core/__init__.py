from dataclasses import asdict
from typing import Any, Dict, Type

import markdown
import requests
import web
import yaml
from flask import Flask, abort, jsonify, render_template
from jinja2 import Markup

from .db import App as LearnerApp
from .tasks import TaskParser, TaskStatus, ValidationError, Validator


class App:
    def __init__(self, tasks_file):
        self.tasks_file = tasks_file

        self.config = {}
        self._validators = {}
        self._tasks = None  # hidden because we want to lazy-load with get_tasks()

        self.wsgi = Flask(self.config.get("name", __name__))

        self.load_config(self.tasks_file)

        # validators
        self.validator(check_not_implemented)
        self.validator(check_webpage_content)

        # routes/context for Flask app
        self.wsgi.context_processor(self._update_context)
        self.wsgi.add_url_rule("/", view_func=self._index)
        self.wsgi.add_url_rule("/<name>", view_func=self._app_page)
        self.wsgi.add_url_rule("/<name>/refresh", view_func=self._app_refresh)

    def validator(self, klass: Type[Validator]):
        """Class decorator to add a class as a Validator
        """
        self._validators[klass.__name__] = klass
        return klass

    def set_config(self, key, value):
        self.config[key] = value

    def load_config(self, path):
        with open(path) as f:
            config = yaml.safe_load(f).get("config", {})

        for key, val in config.items():
            self.set_config(key, val)

    def get_tasks(self):
        if not self._tasks:
            self.load_tasks()

        return self._tasks

    def load_tasks(self):
        """Loads a list of tasks from a file.
        """
        parser = TaskParser(self.tasks_file, self._validators)
        self._tasks = parser.load_from_file(self.tasks_file)

    def get_status(self, learner_app):
        """Get status of app by running all validators

        Return value is a dict with keys:
        {tasks: List[TaskStatus], current_task: str}
        """
        evaluator = Evaluator(learner_app, config=self.config)

        tasks = {}
        for task in self.get_tasks():
            task_status = evaluator.evaluate_task(task)
            tasks[task.name] = asdict(task_status)
            if task_status.status != TaskStatus.PASS:
                break

        return dict(tasks=tasks, current_task=task.name)

    def new_app(self, name):
        """Create a new app
        """
        base_url = self._get_base_url(name)
        current_task = self.get_tasks()[0].name
        app = LearnerApp.create(name=name, base_url=base_url,
                                current_task=current_task)
        return app

    def _get_base_url(self, app_name):
        """Get base URL for a learner app from its name
        """
        return self.config.get("base_url").format(name=app_name)

    # view functions
    def _index(self):
        apps = LearnerApp.find_all()
        return render_template("index.html", apps=apps)

    def _app_page(self, name):
        app = LearnerApp.find(name)
        if not app:
            abort(404)
        return render_template("app.html", app=app, tasks=self.get_tasks())

    def _app_refresh(self, name):
        """Refresh status of app (re-run deployment or checks)
        """
        app = LearnerApp.find(name)
        if not app:
            abort(404)
        status = self.get_status(app)
        app.update_status(status)
        return jsonify(status)

    def _update_context(self):
        return {
            "datestr": web.datestr,
            "markdown_to_html": self._markdown_to_html,
        }

    def _markdown_to_html(self, md):
        return Markup(markdown.markdown(md))


class Evaluator:
    def __init__(self, learner_app: LearnerApp, config: Dict[str, Any]):
        self.learner_app = learner_app
        self.config = config

    def evaluate_task(self, task) -> TaskStatus:
        """Evaluate a single task for a learner app
        """
        print(f"[{self.learner_app.base_url}] evaluating task {task.name}...")

        results = [c.verify(self.learner_app) for c in task.checks]
        print(results)
        if all(c.status == TaskStatus.PASS for c in results):
            status = TaskStatus.PASS
        else:
            status = TaskStatus.FAIL
        return TaskStatus(status, checks=results)


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
        base_url = app.base_url
        url = f"{base_url}{self.url}"
        if self.expected_text not in requests.get(url).text:
            message = f'Text "{self.expected_text}"\nis expected in the web page {url},\nbut it is not found.'
            raise ValidationError(message)
