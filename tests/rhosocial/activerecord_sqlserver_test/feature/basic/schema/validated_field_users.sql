CREATE TABLE [validated_field_users] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [username] NVARCHAR(255) NOT NULL,
    [email] NVARCHAR(255) NOT NULL,
    [age] INT NULL,
    [balance] DECIMAL(10,2) NULL,
    [credit_score] INT NOT NULL,
    [status] NVARCHAR(50) NOT NULL DEFAULT 'active',
    [is_active] TINYINT NOT NULL DEFAULT 1
);
