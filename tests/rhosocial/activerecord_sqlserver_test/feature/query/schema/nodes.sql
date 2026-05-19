CREATE TABLE [nodes] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [parent_id] INT NULL,
    [value] DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_parent_id] ([parent_id]),
    FOREIGN KEY ([parent_id]) REFERENCES [nodes]([id]) ON DELETE CASCADE
);
