CREATE TABLE [versioned_products] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [price] DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    [version] INT NOT NULL DEFAULT 1
);
