-- database : app (sqlite, path from DB_PATH)
-- table(s) : example_entity
-- purpose  : the reference read for ExampleEntity — active rows, newest first.
--            Grain is one row per example_entity.id, so no dedup is needed (id is the
--            primary key). The status is bound, never interpolated.
-- engine   : this file lives under queries/sqlite/, so it is reachable only when
--            DB_BACKEND=sqlite. Never spell the engine into the filename: the directory
--            already carries it, and a name that repeats it can disagree with it.
SELECT
	id,
	name,
	status,
	created_at
FROM example_entity
WHERE status = ?
ORDER BY created_at DESC;
