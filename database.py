import sqlite3
import os

DB_PATH = "/data/agency.db" if os.path.exists("/data") and os.path.isdir("/data") else "agency.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        role TEXT DEFAULT 'client'
    )
    """)
    
    # Create Projects table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT DEFAULT 'My New Website',
        status TEXT DEFAULT 'Payment Pending',
        homepage_details TEXT,
        styling_references TEXT,
        content_data TEXT,
        custom_features TEXT,
        developer_prompt TEXT,
        github_repo_url TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    """)
    
    # Create Tickets table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'Open',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    """)
    
    # Create Invoices table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        amount TEXT NOT NULL,
        currency TEXT NOT NULL,
        status TEXT DEFAULT 'Paid',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    """)
    
    # Create Chat Messages table (for AI Onboarding Chat)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        sender TEXT NOT NULL, -- 'user' or 'ai'
        message TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (project_id) REFERENCES projects (id)
    )
    """)

    # Alter projects table to add revisions_left and active columns dynamically
    cursor.execute("PRAGMA table_info(projects)")
    columns = [c[1] for c in cursor.fetchall()]
    if "revisions_left" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN revisions_left INTEGER DEFAULT 2")
    if "active" not in columns:
        cursor.execute("ALTER TABLE projects ADD COLUMN active INTEGER DEFAULT 1")
    
    # Create default Admin and Client for demonstration
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO users (username, password, email, role) VALUES ('admin', 'admin123', 'admin@agency.com', 'admin')")
        cursor.execute("INSERT INTO users (username, password, email, role) VALUES ('client', 'client123', 'client@example.com', 'client')")
        
        # Create a sample project for the client
        cursor.execute("INSERT INTO projects (user_id, status) VALUES (2, 'Payment Pending')")
        
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
