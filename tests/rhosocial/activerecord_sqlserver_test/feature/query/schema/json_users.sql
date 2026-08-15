CREATE TABLE [json_users] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(255) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [age] INT NULL,
    [created_at] DATETIME2 NULL,
    [updated_at] DATETIME2 NULL,
    [settings] NVARCHAR(MAX) NULL,
    [tags] NVARCHAR(MAX) NULL,
    [profile] NVARCHAR(MAX) NULL,
    [roles] NVARCHAR(MAX) NULL,
    [scores] NVARCHAR(MAX) NULL,
    [subscription] NVARCHAR(MAX) NULL,
    [preferences] NVARCHAR(MAX) NULL
);
