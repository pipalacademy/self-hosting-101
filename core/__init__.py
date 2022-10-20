from dataclasses import asdict
from typing import Any, Dict, Type

import markdown
import requests
import web
import yaml
from flask import Flask, abort, jsonify, redirect, request, render_template, session, url_for
from jinja2 import Markup

from . import config as core_config
from .auth import Github, login_user, get_logged_in_user, logout_user
from .db import Site, User
from .tasks import TaskParser, TaskStatus, ValidationError, Validator


class App:
    def __init__(self, tasks_file):
        self.tasks_file = tasks_file

        props = self.load_properties(self.tasks_file)
        self.title = props["title"]
        self.subtitle = props.get("subtitle", "")
        self.name = props.get("name", __name__)

        self.config = self.load_config(self.tasks_file)
        self._validators = {}
        self._tasks = None  # hidden because we want to lazy-load with get_tasks()

        self.wsgi = Flask(self.name)
        self.wsgi.config.update(core_config.wsgi_defaults)
        self.wsgi.config.from_prefixed_env()

        # validators
        self.validator(check_not_implemented)
        self.validator(check_webpage_content)

        # routes/context for Flask app

        self.wsgi.context_processor(self._update_context)

        self.wsgi.add_url_rule("/", view_func=self._index)
        self.wsgi.add_url_rule("/<name>", view_func=self._site_page)
        self.wsgi.add_url_rule("/<name>/refresh", view_func=self._site_refresh)

        self.wsgi.add_url_rule("/auth/github/initiate", view_func=self._github_initiate)
        self.wsgi.add_url_rule("/auth/github/callback", view_func=self._github_callback)
        self.wsgi.add_url_rule("/auth/me", view_func=self._verify_auth)
        self.wsgi.add_url_rule("/auth/logout", view_func=self._logout)

        with self.wsgi.app_context():
            self.github = Github(
                client_id=core_config.github_client_id,
                client_secret=core_config.github_client_secret,
                redirect_uri=url_for("_github_callback", _external=True)
            )

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

        return config

    def load_properties(self, path):
        with open(path) as f:
            props = yaml.safe_load(f)

        # discard keys tasks and config if they exist
        props.pop("tasks", None)
        props.pop("config", None)

        return props

    def get_tasks(self):
        if self._tasks is None:
            self._tasks = self.load_tasks()

        return self._tasks

    def load_tasks(self):
        """Loads a list of tasks from a file.
        """
        parser = TaskParser(self.tasks_file, self._validators)
        return parser.load_from_file(self.tasks_file)

    def get_status(self, site):
        """Get status of site by running all validators

        Return value is a dict with keys:
        {tasks: List[TaskStatus], current_task: str}
        """
        evaluator = Evaluator(site, config=self.config)

        tasks = {}
        for task in self.get_tasks():
            task_status = evaluator.evaluate_task(task)
            tasks[task.name] = asdict(task_status)
            if task_status.status != TaskStatus.PASS:
                break

        return dict(tasks=tasks, current_task=task.name)

    def _get_base_url(self, site_name):
        """Get base URL for a site from its name
        """
        return self.config["base_url"].format(name=site_name)

    def _patch_site(self, site):
        """Any post-processing for a site, after it is fetched from DB
        """
        site.base_url = self._get_base_url(site.name)
        return site

    def new_site(self, name):
        """Create a new site
        """
        current_task = self.get_tasks()[0]
        site = Site.create(name, current_task=current_task.name)
        return self._patch_site(site)

    def get_all_sites(self):
        sites = Site.find_all()
        return [self._patch_site(site) for site in sites]

    def get_site(self, *args, **kwargs):
        site = Site.find(*args, **kwargs)
        return site and self._patch_site(site)

    # view functions
    def _index(self):
        sites = self.get_all_sites()
        return render_template("index.html", apps=sites)

    def _site_page(self, name):
        site = self.get_site(name)
        if not site:
            abort(404)
        return render_template("app.html", app=site, tasks=self.get_tasks())

    def _site_refresh(self, name):
        """Refresh status of site (re-run deployment or checks)
        """
        site = self.get_site(name)
        if not site:
            abort(404)
        status = self.get_status(site)
        site.update_status(status)
        return jsonify(status)

    def _github_initiate(self):
        """Initiate github oauth flow
        """
        url = self.github.get_oauth_url()
        return redirect(url)

    def _github_callback(self):
        """Callback for github oauth flow
        """
        code = request.args.get("code")
        if not code:
            abort(400)

        token = self.github.get_access_token(code)
        username = self.github.get_username(token)

        user = User.find(username=username) or User.create(username=username)
        self._update_ip_address(user)
        login_user(user)
        return redirect("/")

    def _verify_auth(self):
        """Verify that user is logged in
        """
        user = get_logged_in_user()
        if not user:
            abort(401)
        return jsonify(
            username=user.username,
            ip_address=user.ip_address,
        )

    def _logout(self):
        logout_user()
        return redirect("/")

    def _update_ip_address(self, user):
        if "ip_address" in session:
            ip_addr = session.pop("ip_address")
            user.update_ip_address(ip_addr)

    def _update_context(self):
        return {
            "datestr": web.datestr,
            "markdown_to_html": self._markdown_to_html,
            "title": self.title,
            "subtitle": self.subtitle,
            "user": get_logged_in_user(),
        }

    def _markdown_to_html(self, md):
        return Markup(markdown.markdown(md))


class Evaluator:
    def __init__(self, site: Site, config: Dict[str, Any]):
        self.site = site
        self.config = config

    def evaluate_task(self, task) -> TaskStatus:
        """Evaluate a single task for a site
        """
        print(f"[{self.site.base_url}] evaluating task {task.name}...")

        results = [c.verify(self.site) for c in task.checks]
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

    def validate(self, site):
        raise ValidationError("coming soon...")


class check_webpage_content(Validator):
    def __init__(self, url, expected_text):
        self.url = url
        self.expected_text = expected_text

    def __str__(self):
        return f"Check webpage content: {self.url}"

    def validate(self, site):
        base_url = site.base_url
        url = f"{base_url}{self.url}"
        if self.expected_text not in requests.get(url).text:
            message = f'Text "{self.expected_text}"\nis expected in the web page {url},\nbut it is not found.'
            raise ValidationError(message)
