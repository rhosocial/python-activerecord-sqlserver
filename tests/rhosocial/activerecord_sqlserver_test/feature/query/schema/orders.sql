CREATE TABLE [orders] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [user_id] INT NOT NULL,
    [order_number] NVARCHAR(255) NOT NULL,
    [total_amount] DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    [status] NVARCHAR(50) NOT NULL DEFAULT 'pending',
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_user_id] ([user_id]),
    FOREIGN KEY ([user_id]) REFERENCES [users]([id]) ON DELETE CASCADE
);
