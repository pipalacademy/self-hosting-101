create table app (
    id integer primary key,
    name text unique,
    current_task text,
    score int,
    healthy int default 1,
    created text default CURRENT_TIMESTAMP,
    last_updated text default CURRENT_TIMESTAMP
);

-- the completed_tasks table maintains the list of tasks that are
-- completed for each app. When a completed task is broken due to
-- a subsequent change, it is marked as broken.
create table task (
    id integer primary key,
    app_id integer references app(id),
    name text,
    status text, -- completed, broken, pending
    checks text,
    timestamp text default CURRENT_TIMESTAMP
);


-- changelog maintains all the changes to an app
-- entries could be one of the following types
--   deployed
--   task-done
--   site-unhealthy
--   site-healthy
--   tasks-broken
create table changelog (
    id integer primary key,
    app_id integer references app(id),
    timestamp text default CURRENT_TIMESTAMP,
    type text,
    message text
);
