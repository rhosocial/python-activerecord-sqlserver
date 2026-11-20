-- tests/rhosocial/activerecord_sqlserver_test/feature/backend/adapters/native/schema/native_types.sql
--
-- One table per family (testing plan §4.1): a failing family must localise to
-- its own table, never to a row that mixes several families. The tables belong
-- to the directory's own database, which feature/backend/conftest.py creates.
-- Every primary key is a caller-supplied INT, so a test can address the row it
-- wrote without relying on IDENTITY.

-- MONEY / SMALLMONEY: fixed-point money types with 4 decimal places.
CREATE TABLE native_money (
    id INT NOT NULL PRIMARY KEY,
    amount MONEY NULL,
    small SMALLMONEY NULL
);

-- DATETIMEOFFSET: a datetime that carries a UTC offset.
CREATE TABLE native_datetimeoffset (
    id INT NOT NULL PRIMARY KEY,
    dto DATETIMEOFFSET(7) NULL
);

-- UNIQUEIDENTIFIER: SQL Server's native 16-byte GUID type.
CREATE TABLE native_uniqueidentifier (
    id INT NOT NULL PRIMARY KEY,
    uid UNIQUEIDENTIFIER NULL
);

-- XML: a native XML column, stored in SQL Server's own XML form.
CREATE TABLE native_xml (
    id INT NOT NULL PRIMARY KEY,
    doc XML NULL
);

-- HIERARCHYID: a CLR type holding a materialised path.
CREATE TABLE native_hierarchyid (
    id INT NOT NULL PRIMARY KEY,
    hid HIERARCHYID NULL
);

-- BIT: SQL Server's native boolean (never a bit string).
CREATE TABLE native_bit (
    id INT NOT NULL PRIMARY KEY,
    flag BIT NULL
);

-- ROWVERSION: an 8-byte server-maintained concurrency token (not a time).
CREATE TABLE native_rowversion (
    id INT NOT NULL PRIMARY KEY,
    rv ROWVERSION,
    note NVARCHAR(50) NULL
);

-- TIMESTAMP: the synonym of ROWVERSION; only one such column per table.
CREATE TABLE native_timestamp (
    id INT NOT NULL PRIMARY KEY,
    rv TIMESTAMP,
    note NVARCHAR(50) NULL
);

-- JSON: SQL Server has no JSON type, the payload is text in NVARCHAR(MAX).
CREATE TABLE native_json (
    id INT NOT NULL PRIMARY KEY,
    payload NVARCHAR(MAX) NULL
);

-- GEOMETRY / GEOGRAPHY: the planar and the earth-based spatial types.
CREATE TABLE native_spatial (
    id INT NOT NULL PRIMARY KEY,
    geom GEOMETRY NULL,
    geog GEOGRAPHY NULL
);

-- WKT in an ordinary text column: the portable carrier for a neutral geometry.
CREATE TABLE native_wkt_text (
    id INT NOT NULL PRIMARY KEY,
    shape NVARCHAR(200) NULL
);
