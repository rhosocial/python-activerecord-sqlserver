CREATE TABLE [pydantic_validated_models] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [code] NVARCHAR(32),
    [quantity] INT,
    [step_count] INT,
    [price] DECIMAL(10, 2),
    [start_at] DATETIME2,
    [end_at] DATETIME2,
    [status] NVARCHAR(32),
    [normalized_name] NVARCHAR(50),
    [created_token] NVARCHAR(255)
);
