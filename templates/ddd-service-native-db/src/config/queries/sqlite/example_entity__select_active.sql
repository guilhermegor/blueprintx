SELECT
	id,
	name,
	status,
	created_at
FROM example_entity
WHERE status = ?
ORDER BY created_at DESC
LIMIT 1000;
