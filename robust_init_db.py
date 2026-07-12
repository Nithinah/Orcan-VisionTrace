# robust_init_db.py
"""
Robust Database Initialization for Orcan VisionTrace
This script ensures the database and tables are created properly
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
import traceback
from dotenv import load_dotenv

load_dotenv()  # This loads .env file values into environment


# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🚀 Robust Database Initialization for Orcan VisionTrace")
print("=" * 60)

def load_config():
    """Load configuration from .env or use defaults"""
    config = {
        'DB_HOST': os.getenv('DB_HOST', 'localhost'),
        'DB_PORT': os.getenv('DB_PORT', '5432'),
        'DB_NAME': os.getenv('DB_NAME', 'orcan_visiontrace'),
        'DB_USER': os.getenv('DB_USER', 'orcan_user'),  # Use postgres as default
        'DB_PASSWORD': os.getenv('DB_PASSWORD', 'orcan123')  # Common default
    }
    
    # Try to load from settings if available
    try:
        from app.config import settings
        config.update({
            'DB_HOST': settings.DB_HOST,
            'DB_PORT': settings.DB_PORT,
            'DB_NAME': settings.DB_NAME,
            'DB_USER': settings.DB_USER,
            'DB_PASSWORD': settings.DB_PASSWORD
        })
        print("✅ Loaded configuration from app.config")
    except ImportError:
        print("⚠️  Using default configuration (create .env file for custom settings)")
    
    return config

def test_postgres_connection(config):
    """Test basic PostgreSQL connection"""
    print(f"\n🔍 Testing PostgreSQL connection...")
    print(f"   Host: {config['DB_HOST']}:{config['DB_PORT']}")
    print(f"   User: {config['DB_USER']}")
    
    try:
        # Connect to postgres database (always exists)
        conn = psycopg2.connect(
            host=config['DB_HOST'],
            port=config['DB_PORT'],
            database='postgres',
            user=config['DB_USER'],
            password=config['DB_PASSWORD']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print(f"✅ PostgreSQL connection successful!")
        print(f"   Version: {version}")
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Make sure PostgreSQL is running:")
        print("   - Windows: Check Services for 'postgresql'")
        print("   - Mac: brew services start postgresql")
        print("   - Linux: sudo systemctl start postgresql")
        print("2. Verify credentials in .env file")
        print("3. Try connecting manually: psql -U postgres")
        return False

def create_database_if_not_exists(config):
    """Create the target database if it doesn't exist"""
    print(f"\n🏗️  Creating database '{config['DB_NAME']}'...")
    
    try:
        # Connect to postgres database
        conn = psycopg2.connect(
            host=config['DB_HOST'],
            port=config['DB_PORT'],
            database='postgres',
            user=config['DB_USER'],
            password=config['DB_PASSWORD']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Drop database if it exists (for clean recreation)
        print(f"🗑️  Attempting to drop database '{config['DB_NAME']}' if it exists...")
        cur.execute(f'DROP DATABASE IF EXISTS "{config["DB_NAME"]}" WITH (FORCE);')
        print(f"✅ Database '{config['DB_NAME']}' dropped (if it existed).")

        # Create database
        cur.execute(f'CREATE DATABASE "{config["DB_NAME"]}"')
        print(f"✅ Database '{config['DB_NAME']}' created successfully!")
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Failed to create database: {e}")
        return False

def create_tables_with_sqlalchemy(config):
    """Create tables using SQLAlchemy models"""
    print(f"\n📋 Creating tables using SQLAlchemy...")
    
    try:
        # Import models
        from app.models import Base
        print("✅ Models imported successfully")
        
        # Create engine
        database_url = f"postgresql://{config['DB_USER']}:{config['DB_PASSWORD']}@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"
        engine = create_engine(database_url, echo=False)
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"✅ Connected to database '{config['DB_NAME']}'")
        
        # Create all tables
        print("🔨 Creating tables from models...")
        Base.metadata.create_all(bind=engine)
        print("✅ All tables created successfully!")
        
        # List created tables
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name, 
                       (SELECT COUNT(*) FROM information_schema.columns 
                        WHERE table_name = t.table_name AND table_schema = 'public') as column_count
                FROM information_schema.tables t
                WHERE table_schema = 'public'
                ORDER BY table_name
            """))
            tables = result.fetchall()
            
            print(f"\n📊 Database Schema Summary:")
            print(f"   Database: {config['DB_NAME']}")
            print(f"   Tables: {len(tables)}")
            for table_name, column_count in tables:
                print(f"   ✓ {table_name} ({column_count} columns)")
        
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create tables: {e}")
        traceback.print_exc()
        return False

def verify_database_setup(config):
    """Verify the database setup is complete"""
    print(f"\n🧪 Verifying database setup...")
    
    try:
        from app.models import User, ImageSet, DataSource, IndexedImage
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        
        database_url = f"postgresql://{config['DB_USER']}:{config['DB_PASSWORD']}@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        # Test creating a session and querying
        db = SessionLocal()
        
        # Test each table
        tables_to_test = [
            ('users', User),
            ('image_sets', ImageSet),
            ('data_sources', DataSource),
            ('indexed_images', IndexedImage)
        ]
        
        for table_name, model_class in tables_to_test:
            try:
                count = db.query(model_class).count()
                print(f"   ✓ {table_name}: {count} records")
            except Exception as e:
                print(f"   ❌ {table_name}: Error - {e}")
                return False
        
        db.close()
        engine.dispose()
        
        print("✅ Database verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Database verification failed: {e}")
        return False

def create_sample_user(config):
    """Create a sample user for testing"""
    print(f"\n👤 Creating sample user...")
    
    try:
        from app.models import User
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import bcrypt
        
        database_url = f"postgresql://{config['DB_USER']}:{config['DB_PASSWORD']}@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        
        db = SessionLocal()
        
        # Check if sample user already exists
        existing_user = db.query(User).filter(User.email == "test@orcan.com").first()
        if existing_user:
            print("ℹ️  Sample user already exists (test@orcan.com)")
            db.close()
            return True
        
        # Create sample user
        hashed_password = bcrypt.hashpw("test123".encode('utf-8'), bcrypt.gensalt())
        
        sample_user = User(
            name="Test User",
            email="test@orcan.com",
            password_hash=hashed_password.decode('utf-8'),
            credits=1500
        )
        
        db.add(sample_user)
        db.commit()
        db.refresh(sample_user)
        
        print(f"✅ Sample user created successfully!")
        print(f"   Email: test@orcan.com")
        print(f"   Password: test123")
        print(f"   Credits: 1500")
        
        db.close()
        engine.dispose()
        return True
        
    except Exception as e:
        print(f"❌ Failed to create sample user: {e}")
        return False

def main():
    """Main initialization function"""
    print("🔧 Starting database initialization process...\n")
    
    # Step 1: Load configuration
    config = load_config()
    print(f"📋 Configuration:")
    for key, value in config.items():
        if 'PASSWORD' in key:
            print(f"   {key}: {'*' * len(str(value))}")
        else:
            print(f"   {key}: {value}")
    
    # Step 2: Test PostgreSQL connection
    if not test_postgres_connection(config):
        print("\n❌ Cannot proceed without PostgreSQL connection")
        return False
    
    # Step 3: Create database
    if not create_database_if_not_exists(config):
        print("\n❌ Cannot proceed without database")
        return False
    
    # Step 4: Create tables
    if not create_tables_with_sqlalchemy(config):
        print("\n❌ Cannot proceed without tables")
        return False
    
    # Step 5: Verify setup
    if not verify_database_setup(config):
        print("\n❌ Database verification failed")
        return False
    
    # Step 6: Create sample user (optional)
    create_sample_user(config)
    
    # Success!
    print("\n" + "=" * 60)
    print("🎉 Database initialization completed successfully!")
    print("\n🚀 Next steps:")
    print("1. Run the backend: python run_backend.py")
    print("2. Backend URL: http://127.0.0.1:8020")
    print("3. API Docs: http://127.0.0.1:8020/docs")
    print("4. Start your React frontend")
    print("\n📧 Test Login:")
    print("   Email: test@orcan.com")
    print("   Password: test123")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("\n💥 Database initialization failed!")
            print("\n🆘 Need help? Check:")
            print("1. PostgreSQL is running")
            print("2. Credentials are correct")
            print("3. Database permissions")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)