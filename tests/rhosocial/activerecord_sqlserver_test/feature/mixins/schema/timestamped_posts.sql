CREATE TABLE [timestamped_posts] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [title] NVARCHAR(255) NOT NULL,
    [content] NVARCHAR(MAX) NOT NULL,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL
);
