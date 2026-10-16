SELECT TOP (1000)
	[id],
	[name],
	[status],
	[created_at]
FROM [dbo].[example_entity]
WHERE [status] = ?
ORDER BY [created_at] DESC;
