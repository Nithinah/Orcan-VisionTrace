# app/models.py - Complete version with cascade delete relationships
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Float, Boolean
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
from datetime import datetime

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    credits = Column(Float, default=1500.0, nullable=False)  # Changed to Float for decimal credits
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships with cascade delete
    image_sets = relationship("ImageSet", back_populates="user", cascade="all, delete-orphan")
    data_sources = relationship("DataSource", back_populates="user", cascade="all, delete-orphan")
    search_history = relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}')>"

class ImageSet(Base):
    __tablename__ = "image_sets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="draft", nullable=False)  # draft, indexing, ready, error
    progress = Column(Integer, default=0, nullable=False)  # 0-100
    total_images = Column(Integer, default=0, nullable=False)
    indexed_images_count = Column(Integer, default=0, nullable=False)
    source_metadata = Column(Text)  # JSON string for storing upload/source metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships with cascade delete
    user = relationship("User", back_populates="image_sets")
    indexed_images = relationship("IndexedImage", back_populates="image_set", cascade="all, delete-orphan")
    faiss_indexes = relationship("FaissIndex", back_populates="image_set", cascade="all, delete-orphan")
    aws_rekognition_indexes = relationship("AwsRekognitionIndex", back_populates="image_set", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ImageSet(id={self.id}, name='{self.name}', status='{self.status}')>"

class DataSource(Base):
    __tablename__ = "data_sources"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255))  # User-friendly name
    source_type = Column(String(50), nullable=False)  # s3, gdrive, upload, local, bulk_upload
    connection_config = Column(JSON, nullable=False)  # Store connection details
    status = Column(String(50), default="connected", nullable=False)  # connected, error, disconnected
    last_sync = Column(DateTime(timezone=True))
    total_files = Column(Integer, default=0)
    total_size = Column(Integer, default=0)  # in bytes
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="data_sources")

    def __repr__(self):
        return f"<DataSource(id={self.id}, type='{self.source_type}', status='{self.status}')>"

class IndexedImage(Base):
    __tablename__ = "indexed_images"
    
    id = Column(Integer, primary_key=True, index=True)
    image_set_id = Column(Integer, ForeignKey("image_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    image_path = Column(String(1000), nullable=False)  # Full path or URL
    image_name = Column(String(255))  # Original filename
    image_size = Column(Integer)  # File size in bytes
    image_hash = Column(String(64))  # MD5 or SHA hash for deduplication
    features = Column(Text)  # JSON string of extracted features
    image_metadata = Column(JSON)  # Additional metadata (EXIF, etc.)
    source_metadata = Column(JSON)  # Source-specific metadata
    processing_status = Column(String(50), default="pending")  # pending, processed, error
    processing_error = Column(Text)
    confidence_score = Column(Float)  # Overall confidence in feature extraction
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    image_set = relationship("ImageSet", back_populates="indexed_images")

    def __repr__(self):
        return f"<IndexedImage(id={self.id}, name='{self.image_name}', status='{self.processing_status}')>"

class SearchHistory(Base):
    __tablename__ = "search_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    query_image_path = Column(String(1000))  # Path to uploaded query image
    query_image_name = Column(String(255))  # Original filename
    image_set_ids = Column(JSON)  # List of searched image set IDs
    search_parameters = Column(JSON)  # Search configuration
    results_count = Column(Integer, default=0, nullable=False)
    search_time = Column(Float)  # Time taken in seconds
    similarity_threshold = Column(Float, default=60.0)
    max_results = Column(Integer, default=25)
    search_type = Column(String(50))  # faiss, aws_rekognition, mixed
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="search_history")
    search_results = relationship("SearchResultRecord", back_populates="search_history", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<SearchHistory(id={self.id}, results={self.results_count})>"

class SearchResultRecord(Base):
    __tablename__ = "search_results"
    
    id = Column(Integer, primary_key=True, index=True)
    search_history_id = Column(Integer, ForeignKey("search_history.id", ondelete="CASCADE"), nullable=False, index=True)
    indexed_image_id = Column(Integer, ForeignKey("indexed_images.id", ondelete="CASCADE"), nullable=False, index=True)
    similarity_score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)  # Result ranking (1, 2, 3, etc.)
    search_type = Column(String(50))  # faiss, aws_rekognition
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    search_history = relationship("SearchHistory", back_populates="search_results")
    indexed_image = relationship("IndexedImage")

    def __repr__(self):
        return f"<SearchResult(similarity={self.similarity_score:.1f}%, rank={self.rank})>"

class UserSession(Base):
    __tablename__ = "user_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_token = Column(String(255), unique=True, index=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    ip_address = Column(String(45))  # Support IPv6
    user_agent = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_activity = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<UserSession(user_id={self.user_id}, active={self.is_active})>"

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), index=True)  # Nullable for system events
    log_level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, DEBUG
    log_category = Column(String(50), nullable=False)  # auth, search, indexing, system
    message = Column(Text, nullable=False)
    details = Column(JSON)  # Additional structured data
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User")

    def __repr__(self):
        return f"<SystemLog(level='{self.log_level}', category='{self.log_category}')>"

# FAISS Index Storage Table (for bulk upload indexing)
class FaissIndex(Base):
    __tablename__ = "faiss_indexes"
    
    id = Column(String(255), primary_key=True)  # UUID
    image_set_id = Column(Integer, ForeignKey("image_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    index_data = Column(Text)  # Base64 encoded FAISS index data
    image_metadata = Column(JSON, nullable=False)   # Image metadata and paths
    folder_path = Column(String(1000), nullable=False)
    processed_count = Column(Integer, nullable=False)
    failed_count = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    image_set = relationship("ImageSet", back_populates="faiss_indexes")
    user = relationship("User")

    def __repr__(self):
        return f"<FaissIndex(id={self.id}, processed={self.processed_count})>"

# AWS Rekognition Index Storage Table (for S3/GDrive indexing)
class AwsRekognitionIndex(Base):
    __tablename__ = "aws_rekognition_indexes"
    
    id = Column(String(255), primary_key=True)  # UUID
    image_set_id = Column(Integer, ForeignKey("image_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    collection_id = Column(String(255))  # AWS Rekognition Collection ID
    features_data = Column(JSON)  # Extracted features from AWS Rekognition
    source_config = Column(JSON)  # S3/GDrive source configuration
    processed_count = Column(Integer, nullable=False)
    failed_count = Column(Integer, nullable=False)
    total_cost = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    image_set = relationship("ImageSet", back_populates="aws_rekognition_indexes")
    user = relationship("User")

    def __repr__(self):
        return f"<AwsRekognitionIndex(id={self.id}, processed={self.processed_count})>"

# Add indexes for better performance
from sqlalchemy import Index

# Composite indexes for common queries
Index('idx_user_email_active', User.email, User.is_active)
Index('idx_imageset_user_status', ImageSet.user_id, ImageSet.status)
Index('idx_indexedimage_set_status', IndexedImage.image_set_id, IndexedImage.processing_status)
Index('idx_searchhistory_user_created', SearchHistory.user_id, SearchHistory.created_at.desc())
Index('idx_searchresults_search_rank', SearchResultRecord.search_history_id, SearchResultRecord.rank)
Index('idx_datasource_user_type', DataSource.user_id, DataSource.source_type)
Index('idx_systemlog_level_category_created', SystemLog.log_level, SystemLog.log_category, SystemLog.created_at.desc())
Index('idx_faiss_imageset', FaissIndex.image_set_id)
Index('idx_aws_rekognition_imageset', AwsRekognitionIndex.image_set_id)