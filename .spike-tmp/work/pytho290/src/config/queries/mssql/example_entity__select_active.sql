-- database : app (SQL Server, from DB_DSN or the composed DB_* variables)
-- table(s) : dbo.example_entity
-- purpose  : the same read as queries/sqlite/example_entity__select_active.sql, written
--            in T-SQL, and capped at the same 1000 rows. Two files, one caller:
--            load_query("example_entity__select_active.sql") picks this one only when
--            DB_BACKEND=mssql, so both must honour one contract.
-- engine   : `TOP (n)` is what SQLite cannot parse — verified, it fails with
--            `no such function: TOP`. Bracket quoting is NOT a differentiator: SQLite
--            accepts `[id]` too. Under a flat layout this text could reach a SQLite
--            connection and surface as an OperationalError thrown from inside pandas,
--            long after the cause. The per-engine directory makes that unreachable
--            rather than merely detectable.
SELECT TOP (1000)
	[id],
	[name],
	[status],
	[created_at]
FROM [dbo].[example_entity]
WHERE [status] = ?
ORDER BY [created_at] DESC;
