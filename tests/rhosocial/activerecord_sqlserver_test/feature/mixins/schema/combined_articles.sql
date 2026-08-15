CREATE TABLE [combined_articles] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [title] NVARCHAR(255) NOT NULL,
    [content] NVARCHAR(MAX) NOT NULL,
    [status] NVARCHAR(50) NOT NULL DEFAULT 'draft',
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    [version] INT NOT NULL DEFAULT 1,
    [deleted_at] DATETIME2 NULL
);
