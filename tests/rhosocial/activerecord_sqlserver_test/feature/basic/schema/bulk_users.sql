CREATE TABLE [bulk_users] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [age] INT DEFAULT 0,
    [email] NVARCHAR(255) DEFAULT ''
);
