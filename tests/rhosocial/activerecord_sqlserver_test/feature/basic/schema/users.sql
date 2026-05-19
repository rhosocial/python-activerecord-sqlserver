CREATE TABLE [users] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(191) NOT NULL,
    [email] NVARCHAR(191) NOT NULL,
    [age] INT NULL,
    [balance] FLOAT NOT NULL DEFAULT 0.0,
    [is_active] TINYINT NOT NULL DEFAULT 1,
    [created_at] NVARCHAR(MAX) NULL,
    [updated_at] NVARCHAR(MAX) NULL
);
