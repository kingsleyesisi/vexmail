#!/usr/bin/env python3
"""
Database initialization script for VexMail
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app import app, db
from models import Email, EmailAttachment, EmailOperation, User, EmailThread, Notification

def init_database():
    """Initialize the database with all tables"""
    try:
        with app.app_context():
            # Create instance directory if it doesn't exist
            instance_dir = Path(app.instance_path)
            instance_dir.mkdir(exist_ok=True)
            
            # Create all tables
            db.create_all()
            
            print("✅ Database initialized successfully!")
            print(f"📁 Database location: {app.config['SQLALCHEMY_DATABASE_URI']}")
            
            # Print table information
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"📊 Created {len(tables)} tables:")
            for table in tables:
                print(f"   - {table}")
                
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_database()