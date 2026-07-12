# test_db_roundtrip.py
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from psycopg2 import Binary
from app.config import settings
import faiss
import numpy as np

DB_CONFIG = {
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
    'database': settings.DB_NAME,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD
}

def debug_faiss():
    """Test if PostgreSQL BYTEA storage corrupts FAISS data"""
    print("Testing PostgreSQL BYTEA round-trip...")
    
    # Create a simple FAISS index
    embeddings = np.random.random((5, 512)).astype('float32')
    index = faiss.IndexFlatL2(512)
    index.add(embeddings)
    
    # Serialize
    original_data = faiss.serialize_index(index)
    print(f"Original data: {len(original_data)} bytes")
    
    # Store in database
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        with conn.cursor() as cur:
            # Create test table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_bytea (
                    id SERIAL PRIMARY KEY,
                    data BYTEA
                )
            """)
            
            # Clear previous test data
            cur.execute("DELETE FROM test_bytea")
            
            # Insert using Binary()
            cur.execute("INSERT INTO test_bytea (data) VALUES (%s)", (Binary(original_data),))
            conn.commit()
            
            # Retrieve data
            cur.execute("SELECT data FROM test_bytea LIMIT 1")
            result = cur.fetchone()
            
            if result:
                retrieved_data = result[0]
                print(f"Retrieved data type: {type(retrieved_data)}")
                print(f"Retrieved data length: {len(retrieved_data) if hasattr(retrieved_data, '__len__') else 'unknown'}")
                print(f"First 50 chars: {str(retrieved_data)[:50]}")
                
                # Convert based on type
                if isinstance(retrieved_data, str) and retrieved_data.startswith('\\x'):
                    # Hex string format
                    hex_string = retrieved_data[2:]
                    final_data = bytes.fromhex(hex_string)
                    print(f"Converted from hex: {len(final_data)} bytes")
                elif isinstance(retrieved_data, (bytes, bytearray)):
                    final_data = bytes(retrieved_data)
                    print(f"Direct bytes: {len(final_data)} bytes")
                else:
                    print(f"Unknown format: {type(retrieved_data)}")
                    return False
                
                # Compare data
                if final_data == original_data:
                    print("✅ Data integrity preserved")
                else:
                    print("❌ Data corruption detected")
                    print(f"Original length: {len(original_data)}")
                    print(f"Retrieved length: {len(final_data)}")
                    return False
                
                # Test FAISS deserialization
                try:
                    restored_index = faiss.deserialize_index(final_data)
                    print(f"✅ FAISS deserialization successful: {restored_index.ntotal} vectors")
                    return True
                except Exception as e:
                    print(f"❌ FAISS deserialization failed: {e}")
                    return False
                    
    finally:
        # Cleanup
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS test_bytea")
        conn.commit()
        conn.close()
    
    return False

if __name__ == "__main__":
    debug_faiss()