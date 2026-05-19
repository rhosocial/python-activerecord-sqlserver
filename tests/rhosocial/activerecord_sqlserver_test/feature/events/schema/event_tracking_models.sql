CREATE TABLE [event_tracking_models] (
    [id] INT IDENTITY(1,1) PRIMARY KEY,
    [title] NVARCHAR(255) NOT NULL,
    [content] NVARCHAR(MAX) NOT NULL,
    [view_count] INT NOT NULL DEFAULT 0,
    [last_viewed_at] DATETIME2 NULL
);
