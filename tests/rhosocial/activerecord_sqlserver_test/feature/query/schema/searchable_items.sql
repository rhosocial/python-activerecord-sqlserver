CREATE TABLE [searchable_items] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NULL,
    [tags] NVARCHAR(MAX) NULL,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL
);
