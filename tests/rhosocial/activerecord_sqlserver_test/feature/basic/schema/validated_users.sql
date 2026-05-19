CREATE TABLE [validated_users] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(50) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [age] INT NULL
);
