CREATE TABLE [order_items] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [order_id] INT NOT NULL,
    [product_name] NVARCHAR(255) NOT NULL,
    [quantity] INT NOT NULL DEFAULT 1,
    [unit_price] DECIMAL(10,2) NOT NULL,
    [subtotal] DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    INDEX [idx_order_id] ([order_id]),
    FOREIGN KEY ([order_id]) REFERENCES [orders]([id]) ON DELETE CASCADE
);
