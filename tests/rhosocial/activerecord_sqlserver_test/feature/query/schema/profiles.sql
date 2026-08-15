-- tests/rhosocial/activerecord_sqlserver_test/feature/query/schema/profiles.sql
CREATE TABLE `profiles` (
    `id` INT IDENTITY(1,1) PRIMARY KEY,
    `user_id` INT NOT NULL,
    `bio` TEXT,
    `avatar_url` VARCHAR(512),
    `created_at` DATETIME(6),
    `updated_at` DATETIME(6),
    FOREIGN KEY (`user_id`) REFERENCES `users`(`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
