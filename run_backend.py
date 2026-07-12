# run_backend.py
"""
Simple script to run the Orcan VisionTrace backend
"""
import uvicorn
import os
import sys

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting Orcan VisionTrace Backend...")
    print("Backend will be available at: http://127.0.0.1:8020")
    print("API Documentation at: http://127.0.0.1:8020/docs")
    print("Frontend should run on: http://localhost:5173")
    print("\n" + "="*50)
    
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8020,
        reload=True,
        log_level="info"
    )