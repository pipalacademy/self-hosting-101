import functools
from dataclasses import asdict

import markdown
import web
from flask import Flask, abort, g, jsonify, redirect, render_template, request, url_for
from jinja2 import Markup

from . import config
from .auth import Github, login_user, logout_user, get_logged_in_user
from .db import User


app = Flask(__name__)
app.secret_key = config.secret_key


def get_github():
    redirect_uri = url_for("github_callback", _external=True)
    return Github(config.github_client_id, config.github_client_secret, redirect_uri)


def auth_required(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not g.user:
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


@app.template_filter()
def markdown_to_html(md):
    return Markup(markdown.markdown(md))


@app.before_request
def before_request():
    g.user = get_logged_in_user()


@app.context_processor
def update_context():
    return {
        "datestr": web.datestr,
        "title": g.treadmill.title,
        "subtitle": g.treadmill.subtitle,
        "current_user": g.user,
    }


@app.route("/")
def index():
    if get_logged_in_user():
        return redirect(url_for("dashboard"))

    return render_template("index.html")


@app.route("/leaderboard")
def leaderboard():
    sites = g.treadmill.get_all_sites()
    return render_template("leaderboard.html", sites=sites)


@app.route("/dashboard")
@auth_required
def dashboard():
    """Renders dashboard (site page).

    `tasks` given to the template is a list of dict.

    task.status can be either of "pass", "fail", "current", "locked".
    """
    site = g.treadmill.get_site(g.user.username)
    if not site:
        abort(404)

    raw_tasks = g.treadmill.get_tasks()
    tasks = []

    for raw_task in raw_tasks:
        task = asdict(raw_task)
        task_status = site.get_task_status(task["name"])
        task["status"] = task_status.status if task_status else "locked"
        task["checks"] = task_status.checks if task_status else []

        if task["name"] == site.current_task:
            task["status"] = "current"

        tasks.append(task)

    return render_template(
        "dashboard.html",
        tasks=tasks,
        progress=get_progress(tasks),
    )


@app.route("/site/<name>/refresh", methods=["POST"])
def site_refresh(name):
    """Refresh status of site (re-run deployment or checks)
    """
    site = g.treadmill.get_site(name)
    if not site:
        abort(404)
    status = g.treadmill.get_status(site)
    site.update_status(status)
    return jsonify(status)


@app.route("/auth/github")
def github_initiate():
    """Initiate github oauth flow
    """
    url = get_github().get_oauth_url()
    return redirect(url)


@app.route("/auth/github/callback")
def github_callback():
    """Callback for github oauth flow
    """
    code = request.args.get("code")
    if not code:
        abort(400)

    gh = get_github()
    token = gh.get_access_token(code)
    username = gh.get_username(token)

    user = User.find(username=username) or User.create(username=username)
    login_user(user)

    g.treadmill.get_site(user.username) or g.treadmill.new_site(user.username)

    return redirect(url_for("index"))


@app.route("/account/me")
@auth_required
def verify_auth():
    """Verify that user is logged in
    """
    return jsonify(
        username=g.user.username,
    )


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/logout")
@auth_required
def logout():
    logout_user()
    return redirect("/")


def get_progress(tasks):
    passed_tasks = sum(1 for task in tasks if task["status"] == "pass")
    return round(passed_tasks * 100 / len(tasks))
