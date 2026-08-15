CREATE TABLE [posts] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [user_id] INT NOT NULL,
    [title] NVARCHAR(255) NOT NULL,
    [content] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(50) NOT NULL DEFAULT 'published',
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_user_id] ([user_id]),
    INDEX [idx_status] ([status]),
    FOREIGN KEY ([user_id]) REFERENCES [users]([id]) ON DELETE CASCADE
);
