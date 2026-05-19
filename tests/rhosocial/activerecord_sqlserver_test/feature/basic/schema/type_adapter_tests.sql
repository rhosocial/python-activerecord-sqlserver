CREATE TABLE [type_adapter_tests] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [optional_name] NVARCHAR(255) NULL,
    [optional_age] INT NULL,
    [last_login] NVARCHAR(MAX) NULL,
    [is_premium] BIT NULL,
    [unsupported_union] NVARCHAR(255) NULL,
    [custom_bool] NVARCHAR(3) NULL,
    [optional_custom_bool] NVARCHAR(3) NULL
);
