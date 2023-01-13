pip install -r $APP_ROOT/app/requirements.txt
sqlite3 $APP_ROOT/private/treadmill.db < $APP_ROOT/app/core/schema.sql
