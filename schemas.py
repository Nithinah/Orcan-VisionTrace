# app/schemas.py - Updated schemas
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime

# User schemas
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    credits: float
    created_at: datetime
    
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# Image Set schemas
class ImageSetCreate(BaseModel):
    name: str
    description: Optional[str] = ""

class ImageSetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    status: str
    image_count: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Folder Upload schemas
class FolderUploadRequest(BaseModel):
    folder_path: str

class CostCalculation(BaseModel):
    image_count: int
    cost: float
    estimated_time_minutes: int

class IndexingResult(BaseModel):
    status: str
    message: str
    progress: Optional[int] = 0
    index_id: Optional[str] = None
    processed_count: Optional[int] = 0
    failed_count: Optional[int] = 0

# Search schemas
class SearchRequest(BaseModel):
    image_set_ids: List[int]

class SearchResult(BaseModel):
    image_id: int
    image_path: str
    similarity_score: float
    image_set_name: str
    filename: Optional[str] = None
    relative_path: Optional[str] = None

class SearchResponse(BaseModel):
    status: str
    results: List[SearchResult]
    total_found: int

# FAISS Index schemas
class IndexInfo(BaseModel):
    id: str
    processed_count: int
    failed_count: int
    total_cost: float
    folder_path: str
    created_at: datetime

class BulkUploadResponse(BaseModel):
    success: bool
    message: str
    image_count: int
    folder_path: str

class IndexInfoResponse(BaseModel):
    success: bool
    index_info: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = None

class OptimizationResponse(BaseModel):
    success: bool
    message: str
    optimizations: Optional[Dict[str, Any]] = None
    recall_target: Optional[float] = None

class BenchmarkResponse(BaseModel):
    success: bool
    benchmark_results: Optional[List[Dict[str, Any]]] = None
    summary: Optional[Dict[str, Any]] = None