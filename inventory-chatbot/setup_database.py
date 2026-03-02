import sqlite3
import datetime
import random

DB_NAME = 'inventory_chatbot.db'

def create_schema(cursor):
    """Creates the database schema based on the provided DDL (adapted for SQLite)."""
    schema = [
        """CREATE TABLE IF NOT EXISTS Customers (
            CustomerId INTEGER PRIMARY KEY AUTOINCREMENT,
            CustomerCode TEXT UNIQUE NOT NULL,
            CustomerName TEXT NOT NULL,
            Email TEXT,
            Phone TEXT,
            BillingAddress1 TEXT,
            BillingCity TEXT,
            BillingCountry TEXT,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            IsActive INTEGER NOT NULL DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS Vendors (
            VendorId INTEGER PRIMARY KEY AUTOINCREMENT,
            VendorCode TEXT UNIQUE NOT NULL,
            VendorName TEXT NOT NULL,
            Email TEXT,
            Phone TEXT,
            AddressLine1 TEXT,
            City TEXT,
            Country TEXT,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            IsActive INTEGER NOT NULL DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS Sites (
            SiteId INTEGER PRIMARY KEY AUTOINCREMENT,
            SiteCode TEXT UNIQUE NOT NULL,
            SiteName TEXT NOT NULL,
            AddressLine1 TEXT,
            City TEXT,
            Country TEXT,
            TimeZone TEXT,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            IsActive INTEGER NOT NULL DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS Locations (
            LocationId INTEGER PRIMARY KEY AUTOINCREMENT,
            SiteId INTEGER NOT NULL,
            LocationCode TEXT NOT NULL,
            LocationName TEXT NOT NULL,
            ParentLocationId INTEGER,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            IsActive INTEGER NOT NULL DEFAULT 1,
            UNIQUE (SiteId, LocationCode),
            FOREIGN KEY (SiteId) REFERENCES Sites(SiteId),
            FOREIGN KEY (ParentLocationId) REFERENCES Locations(LocationId)
        );""",
        """CREATE TABLE IF NOT EXISTS Items (
            ItemId INTEGER PRIMARY KEY AUTOINCREMENT,
            ItemCode TEXT UNIQUE NOT NULL,
            ItemName TEXT NOT NULL,
            Category TEXT,
            UnitOfMeasure TEXT,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            IsActive INTEGER NOT NULL DEFAULT 1
        );""",
        """CREATE TABLE IF NOT EXISTS Assets (
            AssetId INTEGER PRIMARY KEY AUTOINCREMENT,
            AssetTag TEXT UNIQUE NOT NULL,
            AssetName TEXT NOT NULL,
            SiteId INTEGER NOT NULL,
            LocationId INTEGER,
            SerialNumber TEXT,
            Category TEXT,
            Status TEXT NOT NULL DEFAULT 'Active',
            Cost DECIMAL(18,2),
            PurchaseDate DATE,
            VendorId INTEGER,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            FOREIGN KEY (SiteId) REFERENCES Sites(SiteId),
            FOREIGN KEY (LocationId) REFERENCES Locations(LocationId),
            FOREIGN KEY (VendorId) REFERENCES Vendors(VendorId)
        );""",
        """CREATE TABLE IF NOT EXISTS Bills (
            BillId INTEGER PRIMARY KEY AUTOINCREMENT,
            VendorId INTEGER NOT NULL,
            BillNumber TEXT NOT NULL,
            BillDate DATE NOT NULL,
            DueDate DATE,
            TotalAmount DECIMAL(18,2) NOT NULL,
            Currency TEXT NOT NULL DEFAULT 'USD',
            Status TEXT NOT NULL DEFAULT 'Open',
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            UNIQUE (VendorId, BillNumber),
            FOREIGN KEY (VendorId) REFERENCES Vendors(VendorId)
        );""",
        """CREATE TABLE IF NOT EXISTS PurchaseOrders (
            POId INTEGER PRIMARY KEY AUTOINCREMENT,
            PONumber TEXT NOT NULL UNIQUE,
            VendorId INTEGER NOT NULL,
            PODate DATE NOT NULL,
            Status TEXT NOT NULL DEFAULT 'Open',
            SiteId INTEGER,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            FOREIGN KEY (VendorId) REFERENCES Vendors(VendorId),
            FOREIGN KEY (SiteId) REFERENCES Sites(SiteId)
        );""",
        """CREATE TABLE IF NOT EXISTS PurchaseOrderLines (
            POLineId INTEGER PRIMARY KEY AUTOINCREMENT,
            POId INTEGER NOT NULL,
            LineNumber INTEGER NOT NULL,
            ItemId INTEGER,
            ItemCode TEXT NOT NULL,
            Description TEXT,
            Quantity DECIMAL(18,4) NOT NULL,
            UnitPrice DECIMAL(18,4) NOT NULL,
            UNIQUE (POId, LineNumber),
            FOREIGN KEY (POId) REFERENCES PurchaseOrders(POId),
            FOREIGN KEY (ItemId) REFERENCES Items(ItemId)
        );""",
        """CREATE TABLE IF NOT EXISTS SalesOrders (
            SOId INTEGER PRIMARY KEY AUTOINCREMENT,
            SONumber TEXT NOT NULL UNIQUE,
            CustomerId INTEGER NOT NULL,
            SODate DATE NOT NULL,
            Status TEXT NOT NULL DEFAULT 'Open',
            SiteId INTEGER,
            CreatedAt DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UpdatedAt DATETIME,
            FOREIGN KEY (CustomerId) REFERENCES Customers(CustomerId),
            FOREIGN KEY (SiteId) REFERENCES Sites(SiteId)
        );""",
        """CREATE TABLE IF NOT EXISTS SalesOrderLines (
            SOLineId INTEGER PRIMARY KEY AUTOINCREMENT,
            SOId INTEGER NOT NULL,
            LineNumber INTEGER NOT NULL,
            ItemId INTEGER,
            ItemCode TEXT NOT NULL,
            Description TEXT,
            Quantity DECIMAL(18,4) NOT NULL,
            UnitPrice DECIMAL(18,4) NOT NULL,
            UNIQUE (SOId, LineNumber),
            FOREIGN KEY (SOId) REFERENCES SalesOrders(SOId),
            FOREIGN KEY (ItemId) REFERENCES Items(ItemId)
        );""",
        """CREATE TABLE IF NOT EXISTS AssetTransactions (
            AssetTxnId INTEGER PRIMARY KEY AUTOINCREMENT,
            AssetId INTEGER NOT NULL,
            FromLocationId INTEGER,
            ToLocationId INTEGER,
            TxnType TEXT NOT NULL,
            Quantity INTEGER NOT NULL DEFAULT 1,
            TxnDate DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            Note TEXT,
            FOREIGN KEY (AssetId) REFERENCES Assets(AssetId),
            FOREIGN KEY (FromLocationId) REFERENCES Locations(LocationId),
            FOREIGN KEY (ToLocationId) REFERENCES Locations(LocationId)
        );"""
    ]
    for statement in schema:
        cursor.execute(statement)

def seed_data(cursor):
    """Seeds the database with sample data members."""
    # Sites
    cursor.execute("INSERT OR IGNORE INTO Sites (SiteCode, SiteName, City, Country) VALUES ('SITE01', 'Main Warehouse', 'Cairo', 'Egypt')")
    cursor.execute("INSERT OR IGNORE INTO Sites (SiteCode, SiteName, City, Country) VALUES ('SITE02', 'Alexandria Branch', 'Alexandria', 'Egypt')")
    
    # Locations
    cursor.execute("INSERT OR IGNORE INTO Locations (SiteId, LocationCode, LocationName) VALUES (1, 'LOC01', 'Aisle A1')")
    cursor.execute("INSERT OR IGNORE INTO Locations (SiteId, LocationCode, LocationName) VALUES (2, 'LOC02', 'Storage Room 1')")

    # Customers
    cursor.execute("INSERT OR IGNORE INTO Customers (CustomerCode, CustomerName, Email) VALUES ('CUST01', 'John Doe Retail', 'john@example.com')")
    cursor.execute("INSERT OR IGNORE INTO Customers (CustomerCode, CustomerName, Email) VALUES ('CUST02', 'Business Corp', 'info@bizcorp.com')")

    # Vendors
    cursor.execute("INSERT OR IGNORE INTO Vendors (VendorCode, VendorName, Email) VALUES ('VEND01', 'Tech Suppliers Inc', 'sales@techsupp.com')")
    cursor.execute("INSERT OR IGNORE INTO Vendors (VendorCode, VendorName, Email) VALUES ('VEND02', 'Global Logistics', 'support@gl-logistics.com')")

    # Items
    cursor.execute("INSERT OR IGNORE INTO Items (ItemCode, ItemName, Category, UnitOfMeasure) VALUES ('ITM01', 'Laptop Dell XPS', 'Electronics', 'Each')")
    cursor.execute("INSERT OR IGNORE INTO Items (ItemCode, ItemName, Category, UnitOfMeasure) VALUES ('ITM02', 'Office Chair', 'Furniture', 'Each')")

    # Assets
    cursor.execute("INSERT OR IGNORE INTO Assets (AssetTag, AssetName, SiteId, LocationId, Category, Status, Cost, PurchaseDate) VALUES ('AST001', 'Dell XPS Laptop 15', 1, 1, 'Electronics', 'Active', 1500.00, '2025-01-10')")
    cursor.execute("INSERT OR IGNORE INTO Assets (AssetTag, AssetName, SiteId, LocationId, Category, Status, Cost, PurchaseDate) VALUES ('AST002', 'Ergonomic Chair', 2, 2, 'Furniture', 'Active', 300.00, '2025-02-15')")
    cursor.execute("INSERT OR IGNORE INTO Assets (AssetTag, AssetName, SiteId, LocationId, Category, Status, Cost, PurchaseDate) VALUES ('AST003', 'MacBook Pro', 1, 1, 'Electronics', 'Active', 2500.00, '2024-12-05')")

    # Sales Orders
    cursor.execute("INSERT OR IGNORE INTO SalesOrders (SONumber, CustomerId, SODate, Status, SiteId) VALUES ('SO-1001', 1, '2026-02-01', 'Closed', 1)")
    cursor.execute("INSERT OR IGNORE INTO SalesOrders (SONumber, CustomerId, SODate, Status, SiteId) VALUES ('SO-1002', 2, '2026-02-20', 'Open', 2)")

    # Sales Order Lines
    cursor.execute("INSERT OR IGNORE INTO SalesOrderLines (SOId, LineNumber, ItemId, ItemCode, Quantity, UnitPrice) VALUES (1, 1, 1, 'ITM01', 5, 1600.00)")
    cursor.execute("INSERT OR IGNORE INTO SalesOrderLines (SOId, LineNumber, ItemId, ItemCode, Quantity, UnitPrice) VALUES (2, 1, 2, 'ITM02', 10, 350.00)")

def main():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    print(f"Connecting to {DB_NAME}...")
    create_schema(cursor)
    print("Schema created successfully.")
    seed_data(cursor)
    print("Sample data seeded successfully.")
    conn.commit()
    conn.close()
    print("Database setup complete.")

if __name__ == '__main__':
    main()