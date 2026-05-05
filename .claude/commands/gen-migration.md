---
description: Generate database migration SQL for models
agent: build
---

Generate SQL migration for creating or modifying database tables.

## Migration Configuration

Ask the user for the following information:

1. **Migration Type**:
   - `create` - Create new table
   - `alter` - Modify existing table
   - `drop` - Drop table
   - `index` - Add index
2. **Target Model** (e.g., `User`, `Order`)
3. **Database Type** (sqlite, postgresql, mysql - affects SQL syntax)
4. **Fields** (for create/alter: `name:type:constraints`)
5. **Foreign Keys** (optional references to other tables)

## Generated SQL Examples

### Create Table

```sql
-- SQLite / PostgreSQL / MySQL
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SQLite
    -- id SERIAL PRIMARY KEY,              -- PostgreSQL
    -- id INT AUTO_INCREMENT PRIMARY KEY,  -- MySQL
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    age INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_status ON users(status);
```

### Alter Table

```sql
-- Add column
ALTER TABLE users ADD COLUMN phone VARCHAR(20);

-- Modify column (PostgreSQL)
ALTER TABLE users ALTER COLUMN age SET DEFAULT 18;

-- SQLite workaround for ALTER (limited support)
-- Requires table recreation
```

### Foreign Keys

```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total DECIMAL(10,2),
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Index for foreign key
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

### Join Table (Many-to-Many)

```sql
CREATE TABLE user_roles (
    user_id INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
);

CREATE INDEX idx_user_roles_user_id ON user_roles(user_id);
CREATE INDEX idx_user_roles_role_id ON user_roles(role_id);
```

## Field Type Mapping

| Python Type | SQLite | PostgreSQL | MySQL |
|-------------|--------|------------|-------|
| `int` | INTEGER | INTEGER | INT |
| `str` | TEXT/VARCHAR | VARCHAR | VARCHAR |
| `float` | REAL | DOUBLE PRECISION | DOUBLE |
| `bool` | INTEGER | BOOLEAN | BOOLEAN |
| `datetime` | TIMESTAMP | TIMESTAMP | TIMESTAMP |
| `date` | DATE | DATE | DATE |
| `Decimal` | DECIMAL | DECIMAL | DECIMAL |
| `Optional[T]` | NULL | NULL | NULL |

## Constraints

```sql
-- Primary Key (auto-increment)
id INTEGER PRIMARY KEY AUTOINCREMENT  -- SQLite
id SERIAL PRIMARY KEY                 -- PostgreSQL
id INT AUTO_INCREMENT PRIMARY KEY     -- MySQL

-- Unique
email VARCHAR(255) UNIQUE

-- Not Null
name VARCHAR(100) NOT NULL

-- Default
status VARCHAR(20) DEFAULT 'active'

-- Check (PostgreSQL/MySQL)
age INTEGER CHECK (age >= 0)

-- Foreign Key with actions
FOREIGN KEY (user_id) REFERENCES users(id) 
    ON DELETE CASCADE 
    ON UPDATE CASCADE
```

## Migration File Naming

```
migrations/
├── 001_create_users.sql
├── 002_create_orders.sql
├── 003_add_user_indexes.sql
└── 004_add_order_status.sql
```

## Best Practices

1. **Always create indexes** on foreign keys and frequently queried columns
2. **Use CASCADE carefully** - understand data deletion impact
3. **Add timestamps** (created_at, updated_at) for audit trails
4. **Use appropriate field sizes** - don't use TEXT for short strings
5. **Test migrations** on a copy of production data before deploying
