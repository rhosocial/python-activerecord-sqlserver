CREATE TABLE [tasks] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [title] NVARCHAR(255) NOT NULL,
    [is_completed] TINYINT NOT NULL DEFAULT 0,
    [deleted_at] NVARCHAR(MAX) NULL
);
