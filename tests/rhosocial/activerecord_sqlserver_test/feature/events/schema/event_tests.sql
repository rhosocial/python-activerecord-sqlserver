CREATE TABLE [event_tests] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [status] NVARCHAR(50) NOT NULL DEFAULT 'draft',
    [revision] INT NOT NULL DEFAULT 1,
    [content] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL
);
