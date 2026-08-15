CREATE TABLE [posts] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [author] INT NOT NULL,
    [title] NVARCHAR(255) NOT NULL,
    [content] NVARCHAR(MAX) NULL,
    [published_at] DATETIME2 NULL,
    [published] TINYINT DEFAULT 0,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_author] ([author]),
    FOREIGN KEY ([author]) REFERENCES [users]([id]) ON DELETE CASCADE
);
