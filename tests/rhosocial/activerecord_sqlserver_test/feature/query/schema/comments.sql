CREATE TABLE [comments] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [user_id] INT NOT NULL,
    [post_id] INT NOT NULL,
    [content] NVARCHAR(MAX) NULL,
    [is_hidden] BIT DEFAULT 0,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_user_id] ([user_id]),
    INDEX [idx_post_id] ([post_id]),
    FOREIGN KEY ([user_id]) REFERENCES [users]([id]) ON DELETE NO ACTION,
    FOREIGN KEY ([post_id]) REFERENCES [posts]([id]) ON DELETE NO ACTION
);
