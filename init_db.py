# init_db.py
"""
Database initialization script for Orcan VisionTrace
Run this script to create the database and tables
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🚀 Starting Orcan VisionTrace Database Initialization...")
print("=" * 60)

try:
    print("📝 Loading configuration...")
    from app.config import settings
    print(f"✅ Configuration loaded - DB: {settings.DB_NAME}")
    
    print("📊 Loading database models...")
    from sqlalchemy import create_engine, text
    from app.models import Base
    print("✅ Models loaded successfully")
    
except Exception as e:
    print(f"❌ Error loading modules: {e}")
    sys.exit(1)

def create_database():
    """Create the database if it doesn't exist using SQLAlchemy"""
    print(f"\n🔧 Creating database '{settings.DB_NAME}'...")
    
    try:
        # Connect to default postgres database first
        default_db_url = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/postgres"
        print(f"📡 Connecting to: {settings.DB_HOST}:{settings.DB_PORT}")
        
        try:
            engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
        except Exception as e:
            print(f"❌ Error with psycopg2 driver: {e}")
            print("🔄 Trying alternative connection method...")
            # Try without specifying driver
            default_db_url = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/postgres"
            engine = create_engine(default_db_url, isolation_level="AUTOCOMMIT")
        
        with engine.connect() as conn:
            print("✅ Connected to PostgreSQL server")
            
            # Check if database exists
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :db_name"),
                {"db_name": settings.DB_NAME}
            )
            exists = result.fetchone()
            
            if not exists:
                print(f"🆕 Creating database '{settings.DB_NAME}'...")
                conn.execute(text(f'CREATE DATABASE "{settings.DB_NAME}"'))
                print(f"✅ Database '{settings.DB_NAME}' created successfully!")
            else:
                print(f"ℹ️  Database '{settings.DB_NAME}' already exists.")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        print("\n🔍 Troubleshooting tips:")
        print("1. Make sure PostgreSQL is running")
        print("2. Check your .env file credentials")
        print("3. Try: psql -U postgres")
        return False

def create_tables():
    """Create all tables defined in the SQLAlchemy Base metadata"""
    print(f"\n📋 Creating tables in '{settings.DB_NAME}'...")
    
    try:
        # Connect to our target database
        DATABASE_URL = f"postgresql+psycopg2://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        try:
            engine = create_engine(DATABASE_URL)
        except Exception as e:
            print(f"⚠️  Trying alternative connection: {e}")
            DATABASE_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
            engine = create_engine(DATABASE_URL)
        
        print("📊 Creating tables from models...")
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # List created tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = result.fetchall()
            
            print(f"\n📋 Created {len(tables)} tables:")
            for table in tables:
                print(f"   ✓ {table[0]}")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        return False

if __name__ == "__main__":
    success = True
    
    # Step 1: Create database
    if create_database():
        print("✅ Database creation completed")
        
        # Step 2: Create tables
        if create_tables():
            print("✅ Table creation completed")
        else:
            success = False
            print("❌ Table creation failed")
    else:
        success = False
        print("❌ Database creation failed")
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Database initialization completed successfully!")
        print("\n🚀 Next steps:")
        print("1. Run: python run_backend.py")
        print("2. Backend will be available at: http://127.0.0.1:8020")
        print("3. API docs at: http://127.0.0.1:8020/docs")
        print("4. Start your React frontend on localhost:5173")
    else:
        print("💥 Database initialization failed!")
        print("\n🔍 Check the error messages above and:")
        print("1. Ensure PostgreSQL is running")
        print("2. Verify credentials in .env file")
        print("3. Test connection: psql -U postgres")