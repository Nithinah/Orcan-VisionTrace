# app/config.py - Improved version
import os
from typing import Optional
from pathlib import Path


class Settings:
    """
    Application settings with environment variable support
    """
    
    # Database Configuration
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "orcan_visiontrace")
    DB_USER: str = os.getenv("DB_USER", "orcan_user")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "orcan123")
    
    # Application Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "orcan-visiontrace-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
    
    # AWS Configuration
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    GPU_ENDPOINT_URL: Optional[str] = os.getenv("GPU_ENDPOINT_URL")
    GPU_ENABLED: bool = os.getenv("GPU_ENABLED", "true").lower() in ("true", "1", "yes", "on")
    GPU_HEALTH_CHECK_INTERVAL: int = int(os.getenv("GPU_HEALTH_CHECK_INTERVAL", "300"))  # 5 minutes
    GPU_HEALTH_CHECK_TIMEOUT: float = float(os.getenv("GPU_HEALTH_CHECK_TIMEOUT", "5.0"))
    GPU_PROCESSING_TIMEOUT: float = float(os.getenv("GPU_PROCESSING_TIMEOUT", "120.0"))
    
    # File Upload Configuration
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))  # 50MB default
    ALLOWED_IMAGE_TYPES: list = [
        "image/jpeg", "image/jpg", "image/png", "image/gif", 
        "image/bmp", "image/tiff", "image/webp"
    ]
    ALLOWED_EXTENSIONS: list = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"]
    
    # Credits and Pricing
    INITIAL_USER_CREDITS: int = int(os.getenv("INITIAL_USER_CREDITS", "1500"))
    CREDITS_PER_IMAGE_INDEX: float = float(os.getenv("CREDITS_PER_IMAGE_INDEX", "0.1"))
    CREDITS_PER_SEARCH: float = float(os.getenv("CREDITS_PER_SEARCH", "1.0"))
    
    # Search Configuration
    DEFAULT_SIMILARITY_THRESHOLD: float = float(os.getenv("DEFAULT_SIMILARITY_THRESHOLD", "60.0"))
    MAX_SEARCH_RESULTS: int = int(os.getenv("MAX_SEARCH_RESULTS", "50"))
    DEFAULT_SEARCH_RESULTS: int = int(os.getenv("DEFAULT_SEARCH_RESULTS", "25"))
    
    # Performance Configuration
    MAX_CONCURRENT_INDEXING: int = int(os.getenv("MAX_CONCURRENT_INDEXING", "5"))
    INDEXING_BATCH_SIZE: int = int(os.getenv("INDEXING_BATCH_SIZE", "100"))
    
    # Development/Debug Configuration
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes", "on")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # CORS Configuration
    ALLOWED_ORIGINS: list = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    
    # Add any custom origins from environment
    custom_origins = os.getenv("ALLOWED_ORIGINS", "")
    if custom_origins:
        ALLOWED_ORIGINS.extend([origin.strip() for origin in custom_origins.split(",")])
    
    @property
    def database_url(self) -> str:
        """Get the complete database URL"""
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
    @property
    def upload_path(self) -> Path:
        """Get the upload directory as a Path object"""
        path = Path(self.UPLOAD_DIR)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_user_upload_path(self, user_id: int) -> Path:
        """Get the upload path for a specific user"""
        user_path = self.upload_path / str(user_id)
        user_path.mkdir(parents=True, exist_ok=True)
        return user_path
    
    def is_allowed_file(self, filename: str) -> bool:
        """Check if a file extension is allowed"""
        if not filename:
            return False
        return any(filename.lower().endswith(ext) for ext in self.ALLOWED_EXTENSIONS)
    
    def is_allowed_mime_type(self, mime_type: str) -> bool:
        """Check if a MIME type is allowed"""
        return mime_type in self.ALLOWED_IMAGE_TYPES
    
    def load_env_file(self, env_file: str = ".env"):
        """Load environment variables from a .env file"""
        env_path = Path(env_file)
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        os.environ[key] = value
            print(f"✅ Loaded environment variables from {env_file}")
        else:
            print(f"⚠️  No {env_file} file found, using default configuration")
    
    def __init__(self):
        """Initialize settings and try to load .env file"""
        self.load_env_file()
    
    def __repr__(self):
        """String representation for debugging (without sensitive data)"""
        safe_attrs = {
            'DB_HOST': self.DB_HOST,
            'DB_PORT': self.DB_PORT,
            'DB_NAME': self.DB_NAME,
            'DB_USER': self.DB_USER,
            'DEBUG': self.DEBUG,
            'LOG_LEVEL': self.LOG_LEVEL,
            'UPLOAD_DIR': self.UPLOAD_DIR,
            'MAX_FILE_SIZE': self.MAX_FILE_SIZE,
            'INITIAL_USER_CREDITS': self.INITIAL_USER_CREDITS,
        }
        return f"Settings({safe_attrs})"

# Create a global settings instance
settings = Settings()

# For backward compatibility with pydantic_settings approach
class LegacySettings:
    """Legacy settings class for backward compatibility"""
    
    def __init__(self):
        # Copy all attributes from the main settings
        for attr in dir(settings):
            if not attr.startswith('_') and not callable(getattr(settings, attr)):
                setattr(self, attr, getattr(settings, attr))
    
    class Config:
        env_file = ".env"

# Export both for flexibility
__all__ = ['settings', 'Settings', 'LegacySettings']