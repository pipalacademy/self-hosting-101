import os


_app_root = os.environ.get("APP_ROOT")

db_path = f"{_app_root}/private/treadmill.db" if _app_root else "treadmill.db"
db_uri = f"sqlite:///{db_path}"

github_client_id = os.environ.get("GITHUB_CLIENT_ID", "")
github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET", "")

wsgi_config = {
    "SECRET_KEY": os.environ.get("SECRET_KEY", "development"),
    "SERVER_NAME": os.environ.get("SERVER_NAME", "localhost:5000")
}
