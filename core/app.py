import web
import markdown
from flask import Flask, render_template, abort, jsonify
from jinja2 import Markup

from .db import App
from .tasks import get_tasks, get_status


app = Flask(__name__)


def markdown_to_html(md):
    return Markup(markdown.markdown(md))


@app.context_processor
def app_context():
    return {
        "datestr": web.datestr,
        "markdown_to_html": markdown_to_html,
    }


@app.route("/")
def home():
    apps = App.find_all()
    return render_template("index.html", apps=apps)


@app.route("/<name>")
def app_page(name):
    app = App.find(name)
    if not app:
        abort(404)
    return render_template("app.html", app=app, tasks=get_tasks())


@app.route("/<name>/deploy", methods=["POST"])
def app_deploy(name):
    app = App.find(name)
    if not app:
        abort(404)
    status = get_status(app)
    app.update_status(status)
    return jsonify(status)


if __name__ == "__main__":
    app.run()
