import web
import json
import datetime

db_uri = "sqlite:///treadmill.db"
db = web.database(db_uri)


class App:
    def __init__(self, row):
        self.id = row.id
        self.name = row.name
        self.current_task = row.current_task
        self.score = row.score
        self.created = self.parse_timestamp(row.created)
        self.last_updated = self.parse_timestamp(row.last_updated)

    def parse_timestamp(self, timestamp):
        return datetime.datetime.fromisoformat(timestamp)

    @classmethod
    def find_all(cls):
        rows = db.select("app", order="score desc")
        return [cls(row) for row in rows]

    @classmethod
    def find(cls, name):
        row = db.where("app", name=name).first()
        if row:
            return cls(row)

    def is_task_done(self, task_name):
        rows = db.where("task", app_id=self.id, name=task_name)
        return bool(rows)

    def mark_task_as_done(self, task_name):
        self.add_changelog("task-done", f"Completed task {task_name}.")
        db.insert("completed_tasks", app_id=self.id, task=task_name)

    def get_changelog(self):
        rows = db.where("changelog", app_id=self.id, order="timestamp desc")
        return [self._process_changelog(row) for row in rows]

    def _process_changelog(self, row):
        row.timestamp = self.parse_timestamp(row.timestamp)
        return row

    def add_changelog(self, type, message):
        db.insert("changelog", app_id=self.id, type=type, message=message)

    def _update(self, **kwargs):
        db.update("app", **kwargs, where="id=$id", vars={"id": self.id})

    def update_score(self):
        rows = db.where("task", app_id=self.id).list()
        score = len(rows)
        self._update(score=score)

    def update_status(self, status):
        self.add_changelog("deploy", "Deployed the app")
        self._update(current_task=status['current_task'])

        for task_name, task_status in status['tasks'].items():
            self.update_task_status(task_name, task_status)

        self.update_score()

    def has_task(self, name):
        return db.where("task", app_id=self.id, name=name).first() is not None

    def get_task_status(self, name):
        task_status = db.where("task", app_id=self.id, name=name).first()
        if task_status:
            task_status.checks = json.loads(task_status.checks)
        return task_status

    def update_task_status(self, name, task_status):
        status = task_status['status']
        checks = json.dumps(task_status['checks'])
        if self.has_task(name):
            db.update("task",
                status=status,
                checks=checks,
                where="name=$name and app_id=$app_id",
                vars={"name": name, "app_id": self.id})
        else:
            db.insert("task",
                app_id=self.id,
                name=name,
                status=status,
                checks=checks)

def main():
    import sys
    app_name = sys.argv[1]
    db.insert("app", name=app_name, score=0, current_task="homepage")
    print("Created new app", app_name)

if __name__ == "__main__":
    main()
