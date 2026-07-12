# app/main.py - Complete file with enhanced AWS search and source type identification
from fastapi import FastAPI, Depends, HTTPException, status, File, UploadFile, Form, BackgroundTasks, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
from datetime import datetime, timedelta
import jose.jwt as jwt
import bcrypt
import asyncio
from PIL import Image
import io
import uuid
import json
import traceback
import zipfile
import tempfile
import shutil
import logging
import mimetypes
import psycopg2
from psycopg2.extras import RealDictCursor
import boto3
import base64
import time
import re
from sqlalchemy import text

from .database import get_db, engine
from .models import Base, User, ImageSet, DataSource, IndexedImage, SearchHistory, SearchResultRecord
from .schemas import (
    UserCreate, UserLogin, UserResponse, Token,
    ImageSetCreate, ImageSetResponse, SearchRequest, SearchResult,
    IndexingResult, CostCalculation, FolderUploadRequest
)
from .config import settings
from .aws_services import S3Service, RekognitionService
## from .faiss_service import FaceIndexingService
from .faiss_service import EnhancedFaceIndexingService



# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables on startup
print("Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully!")
except Exception as e:
    print(f"Error creating tables: {e}")

app = FastAPI(
    title="Orcan VisionTrace API", 
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Create uploads directory if it doesn't exist
os.makedirs("uploads", exist_ok=True)


# Mount static files directory for serving images
app.mount("/static", StaticFiles(directory="uploads"), name="static")

os.makedirs("uploads/search_queries", exist_ok=True)

# Enhanced CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

security = HTTPBearer()

# JWT Configuration
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Initialize services
s3_service = S3Service()
rekognition_service = RekognitionService()

# Initialize FAISS service
DB_CONFIG = {
    'host': settings.DB_HOST,
    'port': settings.DB_PORT,
    'database': settings.DB_NAME,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD
}

faiss_service = EnhancedFaceIndexingService(DB_CONFIG)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.JWTError as e:
        print(f"JWT Error: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def decrypt_aws_credentials(metadata):
    """Decrypt AWS credentials from stored metadata"""
    try:
        access_key = base64.b64decode(metadata.get("access_key", "").encode()).decode()
        secret_key = base64.b64decode(metadata.get("secret_key", "").encode()).decode()
        return access_key, secret_key
    except Exception as e:
        print(f"Error decrypting credentials: {e}")
        return None, None

def _get_image_url(image_path: str) -> str:
    """Convert local file path to accessible URL"""
    try:
        if os.path.exists(image_path):
            uploads_dir = os.path.abspath("uploads")
            if image_path.startswith(uploads_dir):
                relative_path = os.path.relpath(image_path, uploads_dir)
                return f"http://127.0.0.1:8020/static/{relative_path.replace(os.sep, '/')}"
            else:
                filename = os.path.basename(image_path)
                safe_filename = f"search_result_{uuid.uuid4().hex}_{filename}"
                static_path = os.path.join("uploads", "search_results", safe_filename)
                os.makedirs(os.path.dirname(static_path), exist_ok=True)
                shutil.copy2(image_path, static_path)
                return f"http://127.0.0.1:8020/static/search_results/{safe_filename}"
        else:
            return "https://placehold.co/400x400/E2E8F0/4A5568?text=NotFound"
    except Exception as e:
        print(f"Error getting image URL: {e}")
        return "https://placehold.co/400x400/E2E8F0/4A5568?text=Error"

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Orcan VisionTrace API is running!", "version": "1.0.0"}

# Health check
@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.utcnow(),
        "database": "connected"
    }

# Authentication Endpoints (keeping existing implementation)
@app.post("/api/auth/signup", response_model=UserResponse)
async def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    print(f"Signup attempt for: {user_data.email}")
    
    try:
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = bcrypt.hashpw(user_data.password.encode('utf-8'), bcrypt.gensalt())
        
        user = User(
            name=user_data.name,
            email=user_data.email,
            password_hash=hashed_password.decode('utf-8'),
            credits=1500.0
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return UserResponse(
            id=user.id,
            name=user.name,
            email=user.email,
            credits=user.credits,
            created_at=user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.email == user_data.email).first()
        
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        if not bcrypt.checkpw(user_data.password.encode('utf-8'), user.password_hash.encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        return Token(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=user.id,
                name=user.name,
                email=user.email,
                credits=user.credits,
                created_at=user.created_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/auth/me", response_model=UserResponse)
async def get_current_user(current_user: User = Depends(verify_token)):
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        credits=current_user.credits,
        created_at=current_user.created_at
    )

# Enhanced Image Sets API with source type identification
@app.post("/api/image-sets", response_model=ImageSetResponse)
async def create_image_set(
    image_set_data: ImageSetCreate,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    try:
        image_set = ImageSet(
            user_id=current_user.id,
            name=image_set_data.name,
            description=image_set_data.description,
            status="draft"
        )
        
        db.add(image_set)
        db.commit()
        db.refresh(image_set)
        
        return ImageSetResponse(
            id=image_set.id,
            name=image_set.name,
            description=image_set.description,
            status=image_set.status,
            image_count=0,
            created_at=image_set.created_at
        )
        
    except Exception as e:
        print(f"Create image set error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create image set: {str(e)}")

@app.get("/api/image-sets")
async def get_image_sets(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Enhanced to include source type identification"""
    try:
        image_sets = db.query(ImageSet).filter(ImageSet.user_id == current_user.id).all()
        
        enhanced_sets = []
        for image_set in image_sets:
            # Determine source type from metadata
            source_type = "unknown"
            source_display = "Unknown Source"
            
            if image_set.source_metadata:
                try:
                    metadata = json.loads(image_set.source_metadata)
                    if metadata.get("type") == "s3_aws_rekognition":
                        source_type = "s3_aws"
                        bucket_name = metadata.get("bucket_name", "")
                        folder_path = metadata.get("folder_path", "")
                        source_display = f"AWS S3: {bucket_name}/{folder_path}" if folder_path else f"AWS S3: {bucket_name}"
                    elif metadata.get("type") == "folder_upload":
                        source_type = "bulk_upload"
                        original_filename = metadata.get("original_filename", "")
                        source_display = f"Bulk Upload: {original_filename}"
                    elif metadata.get("type") == "gdrive":
                        source_type = "gdrive"
                        source_display = "Google Drive"
                except:
                    pass
            
            enhanced_sets.append({
                "id": image_set.id,
                "name": image_set.name,
                "description": image_set.description,
                "status": image_set.status,
                "image_count": image_set.indexed_images_count or 0,
                "created_at": image_set.created_at,
                "source_type": source_type,
                "source_display": source_display,
                "progress": image_set.progress or 0,
                "total_images": image_set.total_images or 0
            })
        
        return enhanced_sets
        
    except Exception as e:
        print(f"Get image sets error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load image sets: {str(e)}")

@app.delete("/api/image-sets/{image_set_id}")
async def delete_image_set(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Enhanced delete with proper cascade handling"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        # FIX: Use raw SQL for JSON array containment check
        try:
            # Use PostgreSQL's JSON containment operator @>
            raw_query = text("""
                SELECT * FROM search_history 
                WHERE user_id = :user_id 
                AND image_set_ids::jsonb @> :image_set_id_json
            """)
            
            search_histories_raw = db.execute(
                raw_query,
                {
                    "user_id": current_user.id,
                    "image_set_id_json": f'[{image_set_id}]'
                }
            ).fetchall()
            
            # Convert to SearchHistory objects and delete
            search_results_count = 0
            for row in search_histories_raw:
                search_item = db.query(SearchHistory).filter(SearchHistory.id == row.id).first()
                if search_item:
                    # Count results before deleting
                    count = db.query(SearchResultRecord).filter(
                        SearchResultRecord.search_history_id == search_item.id
                    ).count()
                    search_results_count += count
                    
                    # Delete history (will cascade delete search_results)
                    db.delete(search_item)
            
        except Exception as sql_error:
            logger.warning(f"JSON query failed, using fallback: {sql_error}")
            
            # Fallback - get all search histories for this user and filter in Python
            all_histories = db.query(SearchHistory).filter(
                SearchHistory.user_id == current_user.id
            ).all()
            
            search_results_count = 0
            for history in all_histories:
                try:
                    if history.image_set_ids:
                        if isinstance(history.image_set_ids, str):
                            image_set_ids = json.loads(history.image_set_ids)
                        else:
                            image_set_ids = history.image_set_ids
                        
                        if image_set_id in image_set_ids:
                            # Count and delete
                            count = db.query(SearchResultRecord).filter(
                                SearchResultRecord.search_history_id == history.id
                            ).count()
                            search_results_count += count
                            db.delete(history)
                except:
                    continue
        
        # Clean up AWS Rekognition collection if exists
        if image_set.source_metadata:
            try:
                metadata = json.loads(image_set.source_metadata)
                if metadata.get("type") == "s3_aws_rekognition":
                    collection_id = metadata.get("collection_id")
                    if collection_id:
                        try:
                            access_key, secret_key = decrypt_aws_credentials(metadata)
                            region = metadata.get("region", "us-east-1")
                            
                            if access_key and secret_key:
                                rekognition = boto3.client(
                                    'rekognition',
                                    aws_access_key_id=access_key,
                                    aws_secret_access_key=secret_key,
                                    region_name=region
                                )
                                rekognition.delete_collection(CollectionId=collection_id)
                                print(f"Deleted AWS Rekognition collection: {collection_id}")
                        except Exception as e:
                            print(f"Error deleting AWS collection: {e}")
            except:
                pass
        
        # Clean up indexes
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM faiss_indexes_b64 WHERE image_set_id = %s", (image_set_id,))
                cur.execute("DELETE FROM aws_rekognition_indexes WHERE image_set_id = %s", (image_set_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error deleting indexes: {e}")
        
        # Get indexed images count before deletion
        indexed_images_count = db.query(IndexedImage).filter(
            IndexedImage.image_set_id == image_set_id
        ).count()
        
        # Clean up uploaded files for bulk uploads
        if image_set.source_metadata:
            try:
                metadata = json.loads(image_set.source_metadata)
                if metadata.get("type") == "folder_upload":
                    extracted_path = metadata.get("extracted_path")
                    if extracted_path and os.path.exists(extracted_path):
                        set_folder = os.path.dirname(extracted_path)
                        if os.path.exists(set_folder):
                            shutil.rmtree(set_folder, ignore_errors=True)
            except Exception as e:
                print(f"Error cleaning up files: {e}")
        
        # Now delete the image set (indexed_images will cascade delete)
        db.delete(image_set)
        db.commit()
        
        return {
            "success": True, 
            "message": f"Image set '{image_set.name}' deleted successfully",
            "deleted_indexed_images": indexed_images_count,
            "deleted_search_results": search_results_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete image set: {str(e)}")

# S3 and AWS Rekognition endpoints
@app.post("/api/data-sources/s3/connect")
async def connect_s3(
    bucket_name: str = Form(...),
    folder_path: str = Form(""),
    access_key: str = Form(...),
    secret_key: str = Form(...),
    region: str = Form(...),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Connect to Amazon S3 bucket with enhanced error handling"""
    try:
        print(f"S3 connection request: bucket={bucket_name}, folder={folder_path}, region={region}")
        
        is_connected, message = await s3_service.verify_s3_connection(
            access_key, secret_key, bucket_name, folder_path, region
        )
        
        if not is_connected:
            print(f"S3 connection failed: {message}")
            raise HTTPException(status_code=400, detail=message)
        
        image_count = await s3_service.count_images(
            access_key, secret_key, bucket_name, folder_path, region
        )
        
        print(f"S3 connection successful: {image_count} images found")
        
        return {
            "success": True,
            "message": f"S3 connection successful. Found {image_count} images ready for AWS Rekognition indexing.",
            "s3_config": {
                "bucket_name": bucket_name,
                "folder_path": folder_path,
                "access_key": access_key,
                "secret_key": secret_key,
                "region": region,
                "image_count": image_count
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"S3 connection error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"S3 connection failed: {str(e)}")

@app.post("/api/s3/detect-region")
async def detect_s3_region(
    bucket_name: str = Form(...),
    access_key: str = Form(...),
    secret_key: str = Form(...),
    current_user: User = Depends(verify_token)
):
    """Auto-detect S3 bucket region"""
    try:
        print(f"Region detection request for bucket: {bucket_name}")
        
        success, region_or_error = await s3_service.detect_bucket_region(
            access_key, secret_key, bucket_name
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=region_or_error)
        
        return {
            "success": True,
            "region": region_or_error,
            "message": f"Detected region: {region_or_error}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Region detection error: {e}")
        raise HTTPException(status_code=500, detail=f"Region detection failed: {str(e)}")

@app.post("/api/s3/calculate-cost")
async def calculate_s3_cost(
    request: Request,
    current_user: User = Depends(verify_token)
):
    """Calculate cost for S3 + AWS Rekognition indexing"""
    try:
        form_data = await request.form()
        bucket_name = form_data.get('bucket_name')
        folder_path = form_data.get('folder_path', '')
        access_key = form_data.get('access_key')
        secret_key = form_data.get('secret_key')
        region = form_data.get('region', 'us-east-1')
        
        if not all([bucket_name, access_key, secret_key]):
            raise HTTPException(status_code=400, detail="Missing S3 configuration")
        
        print(f"S3 cost calculation: bucket={bucket_name}, folder={folder_path}")
        
        total_images = await s3_service.count_images(
            access_key, secret_key, bucket_name, folder_path, region
        )
        
        if total_images == 0:
            raise HTTPException(status_code=400, detail="No images found in S3 bucket/folder")
        
        # AWS Rekognition pricing tiers
        if total_images <= 1000000:
            cost_per_image = 0.001
        elif total_images <= 11000000:
            cost_per_image = 0.0008
        else:
            cost_per_image = 0.0006
            
        total_cost_usd = total_images * cost_per_image
        total_cost_credits = total_cost_usd * 1000
        
        estimated_time_minutes = max(1, int(total_images / (50 * 60)))
        
        print(f"S3 calculation result: {total_images} images, ${total_cost_usd:.3f} USD, {total_cost_credits:.0f} credits")
        
        return {
            "image_count": total_images,
            "cost": total_cost_credits,
            "cost_usd": total_cost_usd,
            "estimated_time_minutes": estimated_time_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"S3 cost calculation error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Cost calculation failed: {str(e)}")

@app.post("/api/s3/start-indexing")
async def start_s3_indexing(
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Start AWS Rekognition indexing for S3 images"""
    try:
        form_data = await request.form()
        bucket_name = form_data.get('bucket_name')
        folder_path = form_data.get('folder_path', '')
        access_key = form_data.get('access_key')
        secret_key = form_data.get('secret_key')
        region = form_data.get('region', 'us-east-1')
        image_set_id = int(form_data.get('image_set_id'))
        
        if not all([bucket_name, access_key, secret_key, region, image_set_id]):
            raise HTTPException(status_code=400, detail="Missing required parameters")
        
        print(f"Starting S3 indexing: bucket={bucket_name}, image_set={image_set_id}")
        
        total_images = await s3_service.count_images(
            access_key, secret_key, bucket_name, folder_path, region
        )
        
        cost_per_image = 0.001
        total_cost_usd = total_images * cost_per_image
        total_cost_credits = total_cost_usd * 1000
        
        if current_user.credits < total_cost_credits:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient credits. Need {total_cost_credits:.0f}, have {current_user.credits:.0f}"
            )
        
        current_user.credits -= total_cost_credits
        
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if image_set:
            image_set.status = "indexing"
            image_set.progress = 0
            image_set.total_images = total_images
        
        db.commit()
        
        background_tasks.add_task(
            process_pure_aws_indexing,
            bucket_name=bucket_name,
            folder_path=folder_path,
            access_key=access_key,
            secret_key=secret_key,
            region=region, 
            image_set_id=image_set_id,
            user_id=current_user.id,
            db_config=DB_CONFIG
        )
        
        return {
            "status": "success",
            "message": "AWS Rekognition indexing started",
            "cost": total_cost_credits,
            "cost_usd": total_cost_usd,
            "estimated_time": max(1, int(total_images / (50 * 60))),
            "total_images": total_images
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"S3 indexing start error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start indexing: {str(e)}")

# Enhanced search endpoint with real AWS integration
@app.post("/api/search")
async def search_images_enhanced(
    file: UploadFile = File(...),
    image_set_ids: str = Form(...),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Enhanced search with AWS Rekognition AND FAISS support"""
    search_start_time = time.time()
    
    try:
        print(f"Enhanced search request from user {current_user.id}")
        
        set_ids = [int(id.strip()) for id in image_set_ids.split(',') if id.strip()]
        
        user_image_sets = db.query(ImageSet).filter(
            ImageSet.id.in_(set_ids),
            ImageSet.user_id == current_user.id,
            ImageSet.status == "ready"
        ).all()
        
        if not user_image_sets:
            raise HTTPException(status_code=400, detail="No valid image sets found for search")
        
        # Separate image sets by type
        aws_image_sets = []
        bulk_image_sets = []
        
        for image_set in user_image_sets:
            if image_set.source_metadata:
                try:
                    metadata = json.loads(image_set.source_metadata)
                    if metadata.get("type") == "s3_aws_rekognition":
                        aws_image_sets.append((image_set, metadata))
                    else:
                        bulk_image_sets.append(image_set.id)
                except:
                    bulk_image_sets.append(image_set.id)
            else:
                bulk_image_sets.append(image_set.id)
        
        # Calculate search costs
        aws_search_cost = len(aws_image_sets) * 1.0  # 1 credit per AWS search
        bulk_search_cost = len(bulk_image_sets) * 0.1  # 0.1 credits per FAISS search
        total_search_cost = aws_search_cost + bulk_search_cost
        
        if current_user.credits < total_search_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient credits. Need {total_search_cost:.1f} credits, have {current_user.credits:.1f}"
            )
        
        # Deduct search credits
        current_user.credits -= total_search_cost
        db.commit()
        
        # Save query image for history
        query_image_dir = os.path.join("uploads", "search_queries")
        os.makedirs(query_image_dir, exist_ok=True)
        
        file_extension = '.jpg'
        if file.filename:
            ext = os.path.splitext(file.filename)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']:
                file_extension = ext
        
        query_filename = f"query_{uuid.uuid4().hex}{file_extension}"
        query_image_path = os.path.join(query_image_dir, query_filename)
        
        content = await file.read()
        with open(query_image_path, "wb") as buffer:
            buffer.write(content)
        
        print(f"Saved query image to: {query_image_path}")
        
        all_results = []
        aws_results_count = 0
        faiss_results_count = 0
        
        # FIX: AWS Rekognition search implementation
        if aws_image_sets:
            print(f"Searching {len(aws_image_sets)} AWS Rekognition collections")
            
            for image_set, metadata in aws_image_sets:
                try:
                    collection_id = metadata.get("collection_id")
                    access_key, secret_key = decrypt_aws_credentials(metadata)
                    region = metadata.get("region", "us-east-1")
                    bucket_name = metadata.get("bucket_name")
                    
                    if not all([collection_id, access_key, secret_key, bucket_name]):
                        print(f"Missing AWS config for image set {image_set.id}")
                        continue
                    
                    # Search faces using AWS Rekognition
                    search_result = await rekognition_service.search_faces_by_image(
                        collection_id=collection_id,
                        image_data=content,
                        max_faces=25,
                        threshold=60.0,
                        access_key=access_key,
                        secret_key=secret_key,
                        region=region
                    )
                    
                    if search_result['success'] and search_result['matches']:
                        print(f"AWS search found {len(search_result['matches'])} matches in {collection_id}")
                        
                        # Get presigned URLs for the matched images
                        for match in search_result['matches']:
                            try:
                                external_image_id = match['external_image_id']
                                
                                # Construct S3 key from external_image_id
                                folder_prefix = metadata.get("folder_path", "").strip('/')
                                if folder_prefix:
                                    s3_key = f"{folder_prefix}/{external_image_id}"
                                else:
                                    s3_key = external_image_id
                                
                                # Add common image extensions if not present
                                if not any(s3_key.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']):
                                    s3_key += '.jpg'  # Default to .jpg
                                
                                # Generate presigned URL
                                image_url = await s3_service.get_presigned_url(
                                    access_key=access_key,
                                    secret_key=secret_key,
                                    bucket_name=bucket_name,
                                    object_key=s3_key,
                                    region=region,
                                    expiration=604800  # 7 days
                                )
                                
                                if image_url:
                                    aws_result = {
                                        "image_id": str(external_image_id),
                                        "image_path": image_url,
                                        "similarity_score": float(match['similarity']),
                                        "image_set_name": image_set.name,
                                        "image_set_id": image_set.id,
                                        "filename": f"{external_image_id}.jpg",
                                        "relative_path": s3_key,
                                        "search_type": "aws_rekognition",
                                        "source_type": "s3_aws",
                                        "face_id": match['face_id'],
                                        "confidence": float(match['confidence']),
                                        "bounding_box": match['bounding_box'],
                                        "url_expires_at": (datetime.utcnow() + timedelta(days=7)).isoformat() + "Z"
                                    }
                                    
                                    all_results.append(aws_result)
                                    aws_results_count += 1
                                
                            except Exception as e:
                                print(f"Error processing AWS match {match.get('external_image_id', 'unknown')}: {e}")
                                continue
                    
                    else:
                        print(f"AWS search in {collection_id}: {search_result.get('error', 'No matches found')}")
                    
                except Exception as e:
                    print(f"Error searching AWS collection for image set {image_set.id}: {e}")
                    continue
        
        # FAISS search (existing logic)
        if bulk_image_sets:
            try:
                print(f"Searching {len(bulk_image_sets)} FAISS indexes with advanced preprocessing")
                
                # Use the enhanced search method with adaptive thresholds
                search_results = faiss_service.search_similar_faces_enhanced(
                    query_image_path=query_image_path,
                    image_set_ids=bulk_image_sets,
                    top_k=50,  # More candidates
                    similarity_threshold=0.30  # LOWERED: Very lenient base threshold (30% instead of 45%)
                )
                
                if search_results['success']:
                    print(f"FAISS search returned {len(search_results['results'])} results")
                    
                    # Enhanced query diagnostics
                    query_info = search_results.get('query_info', {})
                    strategy = str(query_info.get('strategy_used', 'unknown'))
                    quality_score = query_info.get('quality_score', 0)
                    confidence = query_info.get('confidence', 0)

                    try:
                        quality_score = float(quality_score) if quality_score is not None else 0.0
                    except (ValueError, TypeError):
                        quality_score = 0.0
                        
                    try:
                        confidence = float(confidence) if confidence is not None else 0.0
                    except (ValueError, TypeError):
                        confidence = 0.0

                    # Show detailed extraction info
                    print(f"Query extraction: {strategy} (quality: {quality_score:.2f}, confidence: {confidence:.2f})")
                    
                    # Show adaptive threshold info
                    adaptive_threshold = search_results.get('similarity_threshold_used', 0.30)
                    original_threshold = search_results.get('search_info', {}).get('original_threshold', 0.30)
                    
                    if adaptive_threshold != original_threshold:
                        print(f"Adaptive threshold applied: {original_threshold:.3f} → {adaptive_threshold:.3f}")
                    
                    # Show strategy attempts if available
                    attempts = query_info.get('attempts', [])
                    if attempts:
                        # Filter out non-dict items and only process dictionaries
                        dict_attempts = [a for a in attempts if isinstance(a, dict)]
                        successful_attempts = [a for a in dict_attempts if a.get('success', False)]
                        
                        if dict_attempts:
                            print(f"Extraction attempts: {len(dict_attempts)} tried, {len(successful_attempts)} successful")
                            for attempt in successful_attempts[:3]:  # Show top 3
                                try:
                                    strategy = attempt.get('strategy', 'unknown')
                                    faces_found = attempt.get('faces_found', 0)
                                    confidence = attempt.get('confidence', 0)
                                    print(f"  - {strategy}: {faces_found} faces, confidence {confidence:.3f}")
                                except Exception as e:
                                    print(f"  - Error displaying attempt: {e}")
                        else:
                            print(f"Extraction attempts: {len(attempts)} total (mixed types)")
                    else:
                        print("No extraction attempts recorded")
                    
                    for result in search_results['results']:
                        try:
                            image_url = _get_image_url(result['image_path'])
                            image_id = result.get('image_id', 'N/A')
                            
                            if not image_id or image_id == 'N/A':
                                filename = result.get('filename', '')
                                if filename:
                                    numbers = re.findall(r'\d+', filename)
                                    if numbers:
                                        image_id = numbers[-1]
                                    else:
                                        image_id = str(hash(result['image_path']) % 10000)
                            
                            # FIX: Properly get image set information for source display
                            image_set_name = "Unknown Set"
                            source_type = "bulk_upload"
                            source_display = "Unknown Source"
                            image_set_id = result.get('image_set_id')
                            
                            # Find the actual image set to get proper name and source info
                            for img_set in user_image_sets:
                                if img_set.id == image_set_id:
                                    image_set_name = img_set.name
                                    # Determine source type from image set metadata
                                    if hasattr(img_set, 'source_type'):
                                        source_type = img_set.source_type
                                    elif hasattr(img_set, 'source_metadata') and img_set.source_metadata:
                                        try:
                                            metadata = json.loads(img_set.source_metadata) if isinstance(img_set.source_metadata, str) else img_set.source_metadata
                                            if metadata.get("type") == "folder_upload":
                                                source_type = "bulk_upload"
                                                source_display = f"Bulk Upload: {metadata.get('original_filename', 'ZIP Folder')}"
                                            else:
                                                source_type = "bulk_upload"
                                                source_display = "Bulk Upload"
                                        except:
                                            source_type = "bulk_upload"
                                            source_display = "Bulk Upload"
                                    else:
                                        source_type = "bulk_upload"
                                        source_display = "Bulk Upload"
                                    break
                            
                            # Enhanced result with proper source information
                            enhanced_result = {
                                "image_id": str(image_id),
                                "image_path": str(image_url),
                                "similarity_score": float(result['similarity_score']),
                                "image_set_name": str(image_set_name),  # FIX: Proper image set name
                                "image_set_id": int(image_set_id),
                                "filename": str(result['filename']),
                                "relative_path": str(result['relative_path']),
                                "search_type": "faiss_enhanced",
                                "source_type": str(source_type),  # FIX: Proper source type
                                "source_display": str(source_display),  # FIX: Add source display
                                "match_confidence": str(result.get('match_confidence', 'medium')),
                                "cosine_similarity": float(result.get('cosine_similarity', 0)),
                                "l2_distance": float(result.get('l2_distance', 0)),
                                "search_method": str(result.get('search_method', 'arcface_enhanced_blurry')),
                                "adaptive_threshold_used": float(result.get('adaptive_threshold_used', adaptive_threshold)),
                                "query_quality": float(query_info.get('quality_score', 0)),
                                "query_strategy": str(query_info.get('strategy_used', 'unknown')),
                                "enhancement_applied": bool(query_info.get('enhancement_used', False))
                            }
                            
                            all_results.append(enhanced_result)
                            faiss_results_count += 1
                            
                        except Exception as e:
                            print(f"Error processing result: {e}")
                            continue
                else:
                    print(f"FAISS search failed: {search_results.get('message', 'Unknown error')}")
            
            except Exception as e:
                print(f"Enhanced FAISS search error: {e}")
                traceback.print_exc()

        
        # Sort combined results by similarity
        all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        # Store search history
        try:
            search_history = SearchHistory(
                user_id=current_user.id,
                query_image_path=query_image_path,
                query_image_name=file.filename or query_filename,
                image_set_ids=set_ids,
                search_parameters={
                    "aws_sets": len(aws_image_sets),
                    "faiss_sets": len(bulk_image_sets),
                    "similarity_threshold": 30.0
                },
                results_count=len(all_results),
                search_time=time.time() - search_start_time,
                similarity_threshold=30.0,
                max_results=25,
                search_type="mixed" if (aws_results_count > 0 and faiss_results_count > 0) else 
                        ("aws_rekognition" if aws_results_count > 0 else "faiss")
            )
            
            db.add(search_history)
            db.flush()  # Get the ID
            
            # Store individual results with COMPLETE metadata
            for idx, result in enumerate(all_results[:25]):
                # Find or create indexed image record
                indexed_image = db.query(IndexedImage).filter(
                    IndexedImage.image_set_id == result['image_set_id'],
                    IndexedImage.image_name == result['filename']
                ).first()
                
                if not indexed_image:
                    # Create indexed image record for both AWS and FAISS results
                    indexed_image = IndexedImage(
                        image_set_id=result['image_set_id'],
                        image_path=result['image_path'],
                        image_name=result['filename'],
                        # FIX: Store the COMPLETE result as metadata for search history
                        image_metadata=json.dumps({"original_result": result}),
                        processing_status="processed"
                    )
                    db.add(indexed_image)
                    db.flush()
                else:
                    # FIX: Update existing indexed image with complete result metadata
                    try:
                        existing_metadata = json.loads(indexed_image.image_metadata) if isinstance(indexed_image.image_metadata, str) else indexed_image.image_metadata or {}
                    except:
                        existing_metadata = {}
                    
                    # Store the complete search result for history retrieval
                    existing_metadata["original_result"] = result
                    indexed_image.image_metadata = json.dumps(existing_metadata)
                    db.add(indexed_image)
                    db.flush()
                
                # Store search result record
                search_result_record = SearchResultRecord(
                    search_history_id=search_history.id,
                    indexed_image_id=indexed_image.id,
                    similarity_score=result['similarity_score'],
                    rank=idx + 1,
                    search_type=result['search_type']
                )
                db.add(search_result_record)
            
            db.commit()
            
        except Exception as e:
            print(f"Error storing search history: {e}")
            # Continue even if history storage fails
        
        # Calculate search time
        search_end_time = time.time()
        search_time = search_end_time - search_start_time
        
        # Show final results summary
        print(f"Enhanced search completed: {len(all_results)} total results")
        print(f"AWS results: {aws_results_count}, FAISS results: {faiss_results_count}")
        if all_results:
            print(f"Top similarity score: {all_results[0]['similarity_score']:.1f}%")
        
        response_data = {
            "status": "success",
            "results": all_results[:25],
            "total_found": int(len(all_results)),
            "search_cost": float(total_search_cost),
            "aws_results": int(aws_results_count),
            "faiss_results": int(faiss_results_count),
            "remaining_credits": float(current_user.credits),
            "search_time": float(search_time),
            "enhanced_search": True,
            "mixed_search": aws_results_count > 0 and faiss_results_count > 0
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Enhanced search error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Enhanced search failed: {str(e)}")


# FIX 3: Add missing decrypt_aws_credentials function if not exists
def decrypt_aws_credentials(metadata):
    """Decrypt AWS credentials from stored metadata"""
    try:
        access_key = base64.b64decode(metadata.get("access_key", "").encode()).decode()
        secret_key = base64.b64decode(metadata.get("secret_key", "").encode()).decode()
        return access_key, secret_key
    except Exception as e:
        print(f"Error decrypting credentials: {e}")
        return None, None

# Search History Endpoints
@app.get("/api/search-history")
async def get_search_history(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get user's search history with pagination"""
    try:
        # Get search history from database
        search_history = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).order_by(SearchHistory.created_at.desc()).limit(50).all()
        
        history_data = []
        for search in search_history:
            # Get result count
            result_count = db.query(SearchResultRecord).filter(
                SearchResultRecord.search_history_id == search.id
            ).count()
            
            # Parse image set IDs to get names
            image_set_names = []
            if search.image_set_ids:
                set_ids = search.image_set_ids if isinstance(search.image_set_ids, list) else json.loads(search.image_set_ids)
                image_sets = db.query(ImageSet).filter(ImageSet.id.in_(set_ids)).all()
                image_set_names = [{"id": s.id, "name": s.name} for s in image_sets]
            
            history_data.append({
                "id": search.id,
                "query_image_name": search.query_image_name or "Unknown",
                "image_sets": image_set_names,
                "results_count": result_count,
                "search_type": search.search_type,
                "search_time": search.search_time,
                "similarity_threshold": search.similarity_threshold,
                "created_at": search.created_at
            })
        
        return {
            "success": True,
            "history": history_data
        }
        
    except Exception as e:
        print(f"Get search history error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get search history: {str(e)}")

@app.delete("/api/search-history/{search_id}")
async def delete_search_history_item(
    search_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Delete a specific search history item"""
    try:
        search_item = db.query(SearchHistory).filter(
            SearchHistory.id == search_id,
            SearchHistory.user_id == current_user.id
        ).first()
        
        if not search_item:
            raise HTTPException(status_code=404, detail="Search history item not found")
        
        db.delete(search_item)
        db.commit()
        
        return {"success": True, "message": "Search history item deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete search history error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete search history: {str(e)}")

@app.delete("/api/search-history")
async def clear_search_history(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Clear all search history for the current user"""
    try:
        deleted_count = db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).count()
        
        db.query(SearchHistory).filter(
            SearchHistory.user_id == current_user.id
        ).delete()
        
        db.commit()
        
        return {
            "success": True, 
            "message": f"Cleared {deleted_count} search history items"
        }
        
    except Exception as e:
        print(f"Clear search history error: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear search history: {str(e)}")

@app.get("/api/search-history/{search_id}/results")
async def get_search_history_results(
    search_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Enhanced search results retrieval with proper query image handling"""
    try:
        search_history = db.query(SearchHistory).filter(
            SearchHistory.id == search_id,
            SearchHistory.user_id == current_user.id
        ).first()
        
        if not search_history:
            raise HTTPException(status_code=404, detail="Search history not found")
        
        # Get the stored query image
        query_image_url = None
        if search_history.query_image_path and os.path.exists(search_history.query_image_path):
            relative_path = os.path.relpath(search_history.query_image_path, "uploads")
            query_image_url = f"http://127.0.0.1:8020/static/{relative_path.replace(os.sep, '/')}"
        else:
            query_image_url = f"https://placehold.co/400x400/E2E8F0/4A5568?text={search_history.query_image_name or 'Query'}"
        
        search_results = db.query(SearchResultRecord).join(IndexedImage).filter(
            SearchResultRecord.search_history_id == search_id
        ).order_by(SearchResultRecord.rank).all()
        
        results = []
        expired_count = 0
        
        for record in search_results:
            indexed_image = record.indexed_image
            
            if indexed_image.image_metadata:
                try:
                    # Handle both string and dict metadata
                    if isinstance(indexed_image.image_metadata, str):
                        metadata = json.loads(indexed_image.image_metadata)
                    else:
                        metadata = indexed_image.image_metadata
                    
                    original_result = metadata.get('original_result', {})
                    
                    # FIX: Ensure all required fields are present for display
                    if not original_result:
                        # Fallback: create result from indexed_image data
                        original_result = {
                            "image_id": indexed_image.image_name.split('.')[0] if indexed_image.image_name else f"img_{record.id}",
                            "image_path": indexed_image.image_path or "https://placehold.co/400x400/E2E8F0/4A5568?text=NotFound",
                            "similarity_score": record.similarity_score,
                            "search_type": record.search_type,
                            "source_type": "bulk_upload" if record.search_type == "faiss" else "aws_s3",
                            "source_display": "Bulk Upload (FAISS)" if record.search_type == "faiss" else "AWS S3",
                            "filename": indexed_image.image_name or "unknown.jpg",
                            "image_set_name": "Unknown Set",
                            "image_set_id": indexed_image.image_set_id
                        }
                    
                    # Handle AWS URL expiration
                    if original_result.get('search_type') == 'aws_rekognition':
                        if original_result.get('url_expires_at'):
                            try:
                                expire_time = datetime.fromisoformat(original_result['url_expires_at'].replace('Z', ''))
                                if datetime.utcnow() > expire_time:
                                    original_result['image_path'] = f"https://placehold.co/400x400/FEF3C7/F59E0B?text=Expired+AWS+{original_result.get('image_id', '')[:8]}"
                                    expired_count += 1
                            except:
                                pass
                    
                    # FIX: Ensure FAISS results have proper image paths for history display
                    if original_result.get('search_type') in ['faiss', 'faiss_enhanced'] or record.search_type == 'faiss':
                        # For FAISS results, ensure the image path is accessible
                        if 'image_path' in original_result:
                            image_path = original_result['image_path']
                            # Convert local paths to accessible URLs if needed
                            if image_path and not image_path.startswith('http'):
                                if os.path.exists(image_path):
                                    # Convert to accessible URL
                                    original_result['image_path'] = _get_image_url(image_path)
                                else:
                                    original_result['image_path'] = f"https://placehold.co/400x400/E2E8F0/4A5568?text=FAISS+{original_result.get('image_id', 'NotFound')}"
                        
                        # Ensure image_id is present
                        if not original_result.get('image_id'):
                            filename = original_result.get('filename', indexed_image.image_name or '')
                            if filename:
                                # Extract ID from filename
                                numbers = re.findall(r'\d+', filename)
                                if numbers:
                                    original_result['image_id'] = numbers[-1]
                                else:
                                    original_result['image_id'] = filename.split('.')[0]
                            else:
                                original_result['image_id'] = f"faiss_{record.id}"
                    
                    # Ensure required fields
                    if 'similarity_score' not in original_result:
                        original_result['similarity_score'] = record.similarity_score
                    if 'search_type' not in original_result:
                        original_result['search_type'] = record.search_type
                    
                    # Ensure source information is properly displayed
                    if not original_result.get('source_display'):
                        if original_result.get('search_type') in ['faiss', 'faiss_enhanced']:
                            original_result['source_type'] = 'bulk_upload'
                            original_result['source_display'] = 'Bulk Upload (FAISS)'
                        elif original_result.get('search_type') == 'aws_rekognition':
                            original_result['source_type'] = 's3_aws'
                            original_result['source_display'] = 'AWS S3'
                        else:
                            original_result['source_display'] = 'Unknown Source'
                    
                    results.append(original_result)
                    
                except Exception as e:
                    print(f"Error parsing result metadata: {e}")
                    # Create fallback result
                    results.append({
                        "image_id": f"error_{record.id}",
                        "image_path": "https://placehold.co/400x400/E2E8F0/4A5568?text=Error+Loading",
                        "similarity_score": record.similarity_score,
                        "search_type": record.search_type,
                        "source_type": "unknown",
                        "source_display": "Error Loading",
                        "filename": indexed_image.image_name or "error.jpg",
                        "image_set_name": "Error",
                        "image_set_id": indexed_image.image_set_id
                    })
        
        return {
            "success": True,
            "query_image_url": query_image_url,
            "search_history": {
                "id": search_history.id,
                "query_image_name": search_history.query_image_name,
                "search_type": search_history.search_type,
                "similarity_threshold": search_history.similarity_threshold,
                "created_at": search_history.created_at,
                "total_results": len(results)
            },
            "results": results,
            "expired_urls": expired_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get search results error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

# AWS indexing background function with credential storage
async def process_pure_aws_indexing(
    bucket_name: str, 
    folder_path: str, 
    access_key: str, 
    secret_key: str,
    region: str, 
    image_set_id: int, 
    user_id: int, 
    db_config: dict
):
    """Pure AWS indexing with credential storage for search"""
    import psycopg2
    
    try:
        print(f"Starting pure AWS indexing for image set {image_set_id} in region {region}")
        
        collection_id = f"orcan-imageset-{image_set_id}-{user_id}"
        
        rekognition = boto3.client(
            'rekognition',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        try:
            rekognition.create_collection(CollectionId=collection_id)
            print(f"Created Rekognition collection: {collection_id}")
        except rekognition.exceptions.ResourceAlreadyExistsException:
            print(f"Collection already exists: {collection_id}")
        
        image_list = await s3_service.list_images(
            access_key, secret_key, bucket_name, folder_path, region
        )
        
        total_images = len(image_list)
        processed_images = 0
        
        batch_size = 50
        for i in range(0, len(image_list), batch_size):
            batch = image_list[i:i + batch_size]
            
            for s3_image_key in batch:
                try:
                    filename = s3_image_key.split('/')[-1]
                    external_image_id = filename.split('.')[0]
                    
                    rekognition.index_faces(
                        CollectionId=collection_id,
                        Image={
                            'S3Object': {
                                'Bucket': bucket_name,
                                'Name': s3_image_key
                            }
                        },
                        ExternalImageId=external_image_id,
                        DetectionAttributes=['ALL']
                    )
                    
                    processed_images += 1
                    
                    if processed_images % 10 == 0:
                        progress = int((processed_images / total_images) * 100)
                        conn = psycopg2.connect(**db_config)
                        with conn.cursor() as cur:
                            cur.execute("""
                                UPDATE image_sets 
                                SET progress = %s, indexed_images_count = %s, updated_at = NOW()
                                WHERE id = %s
                            """, (progress, processed_images, image_set_id))
                        conn.commit()
                        conn.close()
                        
                        print(f"AWS indexing progress: {processed_images}/{total_images} ({progress}%)")
                    
                except Exception as e:
                    print(f"Error indexing image {s3_image_key}: {e}")
                    continue
            
            await asyncio.sleep(0.1)
        
        # Store credentials for search (encrypt in production)
        conn = psycopg2.connect(**db_config)
        with conn.cursor() as cur:
            encrypted_access_key = base64.b64encode(access_key.encode()).decode()
            encrypted_secret_key = base64.b64encode(secret_key.encode()).decode()
            
            cur.execute("""
                UPDATE image_sets 
                SET status = 'ready', progress = 100, 
                    indexed_images_count = %s, 
                    source_metadata = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (
                processed_images, 
                json.dumps({
                    "type": "s3_aws_rekognition",
                    "collection_id": collection_id,
                    "bucket_name": bucket_name,
                    "folder_path": folder_path,
                    "region": region,
                    "access_key": encrypted_access_key,
                    "secret_key": encrypted_secret_key
                }),
                image_set_id
            ))
        conn.commit()
        conn.close()
        
        print(f"AWS indexing completed: {processed_images} images indexed in collection {collection_id}")
        
    except Exception as e:
        print(f"AWS indexing failed for image set {image_set_id}: {e}")
        traceback.print_exc()
        
        try:
            conn = psycopg2.connect(**db_config)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE image_sets 
                    SET status = 'error', updated_at = NOW()
                    WHERE id = %s
                """, (image_set_id,))
            conn.commit()
            conn.close()
        except:
            pass

# Bulk upload endpoints
@app.post("/api/image-sets/{image_set_id}/upload-folder")
async def upload_folder(
    image_set_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Upload a folder (as ZIP) and store for processing"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        user_upload_dir = os.path.join("uploads", str(current_user.id))
        os.makedirs(user_upload_dir, exist_ok=True)
        
        set_folder_dir = os.path.join(user_upload_dir, f"imageset_{image_set_id}")
        if os.path.exists(set_folder_dir):
            shutil.rmtree(set_folder_dir)
        os.makedirs(set_folder_dir, exist_ok=True)
        
        try:
            zip_path = os.path.join(set_folder_dir, "uploaded_folder.zip")
            with open(zip_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            extract_dir = os.path.join(set_folder_dir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            image_count, image_files = faiss_service.count_images_in_folder(extract_dir)
            
            if image_count == 0:
                raise HTTPException(status_code=400, detail="No valid images found in the uploaded folder")
            
            image_set.source_metadata = json.dumps({
                "type": "folder_upload",
                "extracted_path": extract_dir,
                "original_filename": file.filename,
                "image_count": image_count,
                "uploaded_at": datetime.utcnow().isoformat()
            })
            
            db.commit()
            
            return {
                "success": True,
                "message": f"Folder uploaded successfully with {image_count} images",
                "image_count": image_count,
                "folder_path": extract_dir
            }
            
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Invalid ZIP file. Please upload a valid ZIP file containing images.")
        except Exception as e:
            if os.path.exists(set_folder_dir):
                shutil.rmtree(set_folder_dir, ignore_errors=True)
            raise e
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"Folder upload error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Folder upload failed: {str(e)}")

@app.post("/api/image-sets/{image_set_id}/calculate-cost-bulk")
async def calculate_cost_bulk_enhanced(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Calculate cost for indexing uploaded folder using FAISS"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        if not image_set.source_metadata:
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        try:
            metadata = json.loads(image_set.source_metadata)
        except:
            raise HTTPException(status_code=400, detail="Invalid metadata for this image set")
        
        if metadata.get("type") != "folder_upload":
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        image_count = metadata.get("image_count", 0)
        cost_per_image = 0.001
        total_cost = image_count * cost_per_image
        estimated_time_minutes = max(1, int(image_count / 100))
        
        return {
            "image_count": image_count,
            "cost": total_cost,
            "estimated_time_minutes": estimated_time_minutes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Cost calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Cost calculation failed: {str(e)}")

@app.post("/api/image-sets/{image_set_id}/start-indexing-bulk")
async def start_indexing_bulk(
    image_set_id: int,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Start FAISS indexing process for uploaded folder"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        if not image_set.source_metadata:
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        try:
            metadata = json.loads(image_set.source_metadata)
        except:
            raise HTTPException(status_code=400, detail="Invalid metadata for this image set")
        
        if metadata.get("type") != "folder_upload":
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        image_count = metadata.get("image_count", 0)
        cost_per_image = 0.001
        total_cost = image_count * cost_per_image
        
        if current_user.credits < total_cost:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient credits. Need {total_cost:.3f}, have {current_user.credits:.3f}"
            )
        
        current_user.credits -= total_cost
        image_set.status = "indexing"
        image_set.progress = 0
        
        db.commit()
        
        folder_path = metadata.get("extracted_path")
        
        background_tasks.add_task(
            process_faiss_indexing_background,
            image_set_id=image_set_id,
            user_id=current_user.id,
            folder_path=folder_path,
            db_config=DB_CONFIG
        )
        
        return {
            "success": True,
            "message": "FAISS indexing started",
            "cost": total_cost,
            "estimated_time": max(1, int(image_count / 100))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Start indexing error: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to start indexing: {str(e)}")

async def process_faiss_indexing_background(image_set_id: int, user_id: int, folder_path: str, db_config: dict):
    """Enhanced background task for FAISS indexing with ArcFace"""
    try:
        print(f"Starting enhanced FAISS indexing for image set {image_set_id}")
        
        bg_faiss_service = EnhancedFaceIndexingService(db_config)
        result = await bg_faiss_service.process_folder_for_indexing(
            folder_path=folder_path,
            image_set_id=image_set_id,
            user_id=user_id
        )
        
        print(f"Enhanced FAISS indexing completed for image set {image_set_id}: {result}")
        
        # Update image set with enhanced metadata
        if result.get('success'):
            conn = psycopg2.connect(**db_config)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE image_sets 
                    SET status = 'ready', 
                        progress = 100,
                        indexed_images_count = %s,
                        total_images = %s,
                        source_metadata = COALESCE(source_metadata::jsonb, '{}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    result['processed_count'],
                    result['image_count'],
                    json.dumps({
                        "index_type": result.get('index_type', 'unknown'),
                        "enhancement_used": True,
                        "arcface_model": True,
                        "processing_stats": {
                            "processed": result['processed_count'],
                            "failed": result['failed_count'],
                            "success_rate": result['processed_count'] / result['image_count'] if result['image_count'] > 0 else 0
                        }
                    }),
                    image_set_id
                ))
            conn.commit()
            conn.close()
        
    except Exception as e:
        print(f"Enhanced FAISS indexing failed for image set {image_set_id}: {e}")
        traceback.print_exc()
        
        try:
            conn = psycopg2.connect(**db_config)
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE image_sets 
                    SET status = 'error', updated_at = NOW()
                    WHERE id = %s
                """, (image_set_id,))
            conn.commit()
            conn.close()
        except:
            pass

@app.get("/api/image-sets/{image_set_id}/progress")
async def get_indexing_progress_enhanced(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get indexing progress for an image set"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        return {
            "id": image_set.id,
            "status": image_set.status,
            "progress": image_set.progress or 0,
            "indexed_images_count": image_set.indexed_images_count or 0,
            "total_images": image_set.total_images or 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get progress error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")

@app.get("/api/data-sources")
async def get_data_sources(
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get all data sources for the current user"""
    try:
        data_sources = db.query(DataSource).filter(DataSource.user_id == current_user.id).all()
        
        return [
            {
                "id": ds.id,
                "name": ds.name,
                "source_type": ds.source_type,
                "status": ds.status,
                "total_files": ds.total_files,
                "created_at": ds.created_at
            }
            for ds in data_sources
        ]
        
    except Exception as e:
        print(f"Get data sources error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load data sources: {str(e)}")

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    print(f"Unhandled exception: {exc}")
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"}
    )
@app.get("/api/image-sets/{image_set_id}/index-info")
async def get_index_info(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get detailed information about the FAISS index"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        index_info = faiss_service.get_index_info(image_set_id)
        if not index_info:
            return {"success": False, "message": "No index found for this image set"}
        
        # Get additional statistics
        stats = faiss_service.get_index_statistics(image_set_id)
        
        return {
            "success": True,
            "index_info": index_info,
            "statistics": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get index info error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get index info: {str(e)}")

@app.post("/api/image-sets/{image_set_id}/optimize-search")
async def optimize_search_parameters(
    image_set_id: int,
    recall_target: float = Form(0.95),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Optimize search parameters for better performance"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        if recall_target < 0.5 or recall_target > 1.0:
            raise HTTPException(status_code=400, detail="Recall target must be between 0.5 and 1.0")
        
        result = faiss_service.optimize_search_parameters(image_set_id, recall_target)
        
        if result['success']:
            return {
                "success": True,
                "message": result['message'],
                "optimizations": result['optimizations'],
                "recall_target": result['recall_target']
            }
        else:
            raise HTTPException(status_code=400, detail=result['message'])
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Search optimization error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to optimize search: {str(e)}")

@app.post("/api/image-sets/{image_set_id}/benchmark")
async def benchmark_search_performance(
    image_set_id: int,
    num_queries: int = Form(10),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Benchmark search performance"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        if num_queries < 1 or num_queries > 50:
            raise HTTPException(status_code=400, detail="Number of queries must be between 1 and 50")
        
        result = faiss_service.benchmark_search_performance(image_set_id, num_queries)
        
        if result['success']:
            return {
                "success": True,
                "benchmark_results": result['benchmark_results'],
                "summary": result['summary']
            }
        else:
            raise HTTPException(status_code=400, detail=result['message'])
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Benchmark error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run benchmark: {str(e)}")

@app.delete("/api/admin/cleanup-indexes")
async def cleanup_old_indexes(
    days_old: int = Form(30),
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Admin endpoint to cleanup old indexes"""
    try:
        # You might want to add admin role checking here
        # if not current_user.is_admin:
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        if days_old < 1:
            raise HTTPException(status_code=400, detail="Days must be at least 1")
        
        result = faiss_service.cleanup_old_indexes(days_old)
        
        return {
            "success": result['success'],
            "message": result['message'],
            "cleaned_count": result.get('cleaned_count', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Cleanup error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cleanup indexes: {str(e)}")

# Enhanced progress tracking with index type information
@app.get("/api/image-sets/{image_set_id}/progress")
async def get_indexing_progress_enhanced(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get enhanced indexing progress with index type information"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        progress_info = {
            "id": image_set.id,
            "status": image_set.status,
            "progress": image_set.progress or 0,
            "indexed_images_count": image_set.indexed_images_count or 0,
            "total_images": image_set.total_images or 0
        }
        
        # Add enhanced information if available
        if image_set.source_metadata:
            try:
                metadata = json.loads(image_set.source_metadata)
                progress_info.update({
                    "index_type": metadata.get("index_type", "unknown"),
                    "arcface_enhanced": metadata.get("arcface_model", False),
                    "enhancement_used": metadata.get("enhancement_used", False),
                    "processing_stats": metadata.get("processing_stats", {})
                })
            except:
                pass
        
        # If completed, get detailed index information
        if image_set.status == 'ready':
            index_info = faiss_service.get_index_info(image_set_id)
            if index_info:
                progress_info.update({
                    "index_details": {
                        "index_type": index_info.get("index_type"),
                        "processed_count": index_info.get("processed_count"),
                        "failed_count": index_info.get("failed_count"),
                        "total_cost": float(index_info.get("total_cost", 0)),
                        "created_at": index_info.get("created_at")
                    }
                })
        
        return progress_info
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get enhanced progress error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get progress: {str(e)}")

# Update the bulk upload calculation to include index type prediction
@app.post("/api/image-sets/{image_set_id}/calculate-cost-bulk")
async def calculate_cost_bulk_enhanced(
    image_set_id: int,
    current_user: User = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Calculate cost for indexing uploaded folder with index type prediction"""
    try:
        image_set = db.query(ImageSet).filter(
            ImageSet.id == image_set_id,
            ImageSet.user_id == current_user.id
        ).first()
        
        if not image_set:
            raise HTTPException(status_code=404, detail="Image set not found")
        
        if not image_set.source_metadata:
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        try:
            metadata = json.loads(image_set.source_metadata)
        except:
            raise HTTPException(status_code=400, detail="Invalid metadata for this image set")
        
        if metadata.get("type") != "folder_upload":
            raise HTTPException(status_code=400, detail="No folder uploaded for this image set")
        
        image_count = metadata.get("image_count", 0)
        cost_per_image = 0.001
        total_cost = image_count * cost_per_image
        estimated_time_minutes = max(1, int(image_count / 100))
        
        # Predict optimal index type based on image count
        faiss_service_temp = EnhancedFaceIndexingService(DB_CONFIG)
        config_name, config = faiss_service_temp._get_optimal_faiss_config(image_count)
        
        return {
            "image_count": image_count,
            "cost": total_cost,
            "estimated_time_minutes": estimated_time_minutes,
            "predicted_index_type": config['index_type'],
            "index_category": config_name,
            "performance_notes": {
                "small": "Exact search, perfect accuracy, slower for large queries",
                "medium": "Fast approximate search, high recall, good balance",
                "large": "Memory-efficient with compression, good for large datasets",
                "xlarge": "Graph-based search, excellent for very large datasets",
                "production": "Optimized for massive scale, production-ready"
            }.get(config_name, "Unknown category")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Enhanced cost calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Cost calculation failed: {str(e)}")

@app.get("/api/gpu-status")
async def get_gpu_status(current_user: User = Depends(verify_token)):
    """Get GPU service status"""
    try:
        if hasattr(faiss_service, 'gpu_monitor') and faiss_service.gpu_monitor:
            status = faiss_service.gpu_monitor.get_status()
            return {
                "gpu_enabled": faiss_service.gpu_enabled,
                "gpu_healthy": status["healthy"],
                "last_health_check": status["last_check"],
                "endpoint_url": status["endpoint_url"],
                "last_error": status.get("last_error", ""),
                "current_mode": "GPU" if faiss_service.is_gpu_available() else "CPU"
            }
        else:
            return {
                "gpu_enabled": False,
                "gpu_healthy": False,
                "current_mode": "CPU",
                "message": "GPU not configured"
            }
    except Exception as e:
        return {
            "gpu_enabled": False,
            "gpu_healthy": False,
            "current_mode": "CPU",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    print("Starting Orcan VisionTrace Backend...")
    print("Backend URL: http://127.0.0.1:8020")
    print("API Docs: http://127.0.0.1:8020/docs")
    uvicorn.run(app, host="127.0.0.1", port=8020, reload=True)