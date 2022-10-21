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


def markdown_to_html(md):
    return Markup(markdown.markdown(md))


@app.context_processor
def update_context():
    return {
        "datestr": web.datestr,
        "markdown_to_html": markdown_to_html,
        "title": g.treadmill.title,
        "subtitle": g.treadmill.subtitle,
        "user": get_logged_in_user(),
    }


@app.route("/")
def index():
    sites = g.treadmill.get_all_sites()
    return render_template("index.html", apps=sites)


@app.route("/site")
def site_page():
    user = get_logged_in_user()
    if user is None:
        abort(401)

    site = g.treadmill.get_site(user.username)
    if not site:
        abort(404)
    return render_template("app.html", app=site, tasks=g.treadmill.get_tasks())


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

    return redirect("/site")


@app.route("/account/me")
def verify_auth():
    """Verify that user is logged in
    """
    user = get_logged_in_user()
    if not user:
        abort(401)
    return jsonify(
        username=user.username,
    )


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")
