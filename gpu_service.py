import asyncio
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import threading
import time
import os
import requests

logger = logging.getLogger(__name__)

class SimpleGPUHealthMonitor:
    """Simple GPU health monitoring with 5-minute intervals"""
    
    def __init__(self, endpoint_url: str, check_interval: int = 300, timeout: float = 5.0):
        self.endpoint_url = endpoint_url
        self.check_interval = check_interval
        self.timeout = timeout
        self.is_healthy = False
        self.last_check = datetime.utcnow()
        self.last_error = ""
        self._stop_monitoring = False
        self._monitor_thread = None
        
        # Start initial health check
        self._check_health()
        
        # Start background monitoring
        self.start_monitoring()
    
    def _check_health(self) -> bool:
        """Check GPU endpoint health with proper HF endpoint handling"""
        try:
            headers = {"Content-Type": "application/json"}
            hf_token = os.getenv("HF_TOKEN")
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
            
            # Try a simple inference call instead of /health
            test_payload = {"inputs": "test"}
            
            response = requests.post(
                self.endpoint_url,  # Use base URL, not /health
                json=test_payload,
                headers=headers,
                timeout=self.timeout
            )
            
            # For HF endpoints, any response (even errors) that isn't auth failure means it's up
            if response.status_code in [200, 400, 422]:  # 400/422 = bad input but endpoint is working
                self.is_healthy = True
                self.last_error = ""
            elif response.status_code == 401:
                self.is_healthy = False
                self.last_error = "Authentication failed - check HF_TOKEN"
            else:
                self.is_healthy = False
                self.last_error = f"HTTP {response.status_code}"
                
        except Exception as e:
            self.is_healthy = False
            self.last_error = str(e)
            
        self.last_check = datetime.utcnow()
        status = "HEALTHY" if self.is_healthy else "UNHEALTHY"
        logger.info(f"GPU health check: {status} ({self.last_error if self.last_error else 'OK'})")
        
        return self.is_healthy
    
    def start_monitoring(self):
        """Start background health monitoring"""
        def monitor():
            while not self._stop_monitoring:
                time.sleep(self.check_interval)
                if not self._stop_monitoring:
                    self._check_health()
        
        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()
        logger.info(f"Started GPU health monitoring (interval: {self.check_interval}s)")
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        self._stop_monitoring = True
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status"""
        return {
            "healthy": self.is_healthy,
            "last_check": self.last_check,
            "last_error": self.last_error,
            "endpoint_url": self.endpoint_url
        }