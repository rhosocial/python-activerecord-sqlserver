CREATE TABLE [type_tests] (
    [id] NVARCHAR(36) NOT NULL PRIMARY KEY,
    [string_field] NVARCHAR(255) NOT NULL DEFAULT 'test string',
    [int_field] INT NOT NULL DEFAULT 42,
    [float_field] FLOAT NOT NULL DEFAULT 3.14,
    [decimal_field] FLOAT NOT NULL DEFAULT 10.99,
    [bool_field] TINYINT NOT NULL DEFAULT 1,
    [datetime_field] NVARCHAR(MAX) NOT NULL,
    [json_field] NVARCHAR(MAX) NULL,
    [nullable_field] NVARCHAR(255) NULL
);
