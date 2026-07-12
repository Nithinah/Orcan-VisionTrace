# simple_init_db.py
"""
Simple database initialization without psycopg2 dependency issues
"""

import subprocess
import sys
import os

print("🚀 Simple Database Setup for Orcan VisionTrace")
print("=" * 50)

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_sql_command(command):
    """Run a SQL command using psql command line tool"""
    try:
        result = subprocess.run([
            'psql', '-U', 'postgres', '-c', command
        ], capture_output=True, text=True, check=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except FileNotFoundError:
        return False, "psql command not found. Make sure PostgreSQL is installed and in PATH."

def create_database():
    """Create database using psql command"""
    print("🔧 Creating database...")
    
    # Check if database exists
    success, output = run_sql_command("SELECT datname FROM pg_database WHERE datname = 'orcan_visiontrace';")
    
    if success and 'orcan_visiontrace' in output:
        print("ℹ️  Database 'orcan_visiontrace' already exists.")
        return True
    
    # Create database
    success, output = run_sql_command("CREATE DATABASE orcan_visiontrace;")
    
    if success:
        print("✅ Database 'orcan_visiontrace' created successfully!")
        return True
    else:
        print(f"❌ Failed to create database: {output}")
        return False

def create_tables():
    """Create tables using SQLAlchemy"""
    print("📋 Creating tables...")
    
    try:
        from app.config import settings
        from app.models import Base
        from sqlalchemy import create_engine
        
        # Try different connection approaches
        DATABASE_URL = f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
        
        print(f"📡 Connecting to database...")
        engine = create_engine(DATABASE_URL)
        
        print("📊 Creating tables from models...")
        Base.metadata.create_all(bind=engine)
        
        print("✅ All tables created successfully!")
        
        # List tables
        from sqlalchemy import text
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
    print("\n📝 Checking requirements...")
    
    # Check if we can import required modules
    try:
        from app.config import settings
        print(f"✅ Configuration loaded - DB: {settings.DB_NAME}")
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        print("Make sure you have a .env file with database settings.")
        sys.exit(1)
    
    success = True
    
    # Step 1: Create database
    if create_database():
        # Step 2: Create tables
        if create_tables():
            print("\n🎉 Database setup completed successfully!")
            print("\n🚀 Next steps:")
            print("1. Run: python run_backend.py")
            print("2. Backend will be available at: http://127.0.0.1:8020")
            print("3. API docs at: http://127.0.0.1:8020/docs")
        else:
            success = False
    else:
        success = False
    
    if not success:
        print("\n💥 Setup failed!")
        print("\n🔍 Manual alternative:")
        print("1. Open PostgreSQL command line or pgAdmin")
        print("2. Run: CREATE DATABASE orcan_visiontrace;")
        print("3. Then run this script again")