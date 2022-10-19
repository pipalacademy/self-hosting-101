import os


_app_root = os.environ.get("APP_ROOT")

db_path = f"{_app_root}/private/treadmill.db" if _app_root else "treadmill.db"
db_uri = f"sqlite:///{db_path}"
