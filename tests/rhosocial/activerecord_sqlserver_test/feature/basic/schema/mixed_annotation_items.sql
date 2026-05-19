CREATE TABLE [mixed_annotation_items] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [name] NVARCHAR(255) NOT NULL,
    [tags] NVARCHAR(MAX) NULL,
    [meta] NVARCHAR(MAX) NULL,
    [description] NVARCHAR(MAX) NULL,
    [status] NVARCHAR(MAX) NULL
);
