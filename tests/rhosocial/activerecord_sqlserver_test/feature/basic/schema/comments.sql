CREATE TABLE [comments] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [post_ref] INT NOT NULL,
    [author] INT NOT NULL,
    [text] NVARCHAR(MAX) NOT NULL,
    [created_at] DATETIME2 NOT NULL,
    [updated_at] DATETIME2 NULL,
    [approved] TINYINT DEFAULT 0,
    INDEX [idx_post_ref] ([post_ref]),
    INDEX [idx_author] ([author]),
    FOREIGN KEY ([post_ref]) REFERENCES [posts]([id]) ON DELETE CASCADE,
    FOREIGN KEY ([author]) REFERENCES [users]([id]) ON DELETE NO ACTION
);
