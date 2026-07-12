# app/faiss_service.py - Complete Enhanced version with GPU integration and advanced preprocessing
import os
import numpy as np
import faiss
import json
from PIL import Image, ImageOps
import cv2
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Tuple, Optional, Dict, Any
import uuid
import logging
from datetime import datetime
import hashlib
import base64
import re
import tempfile
import insightface
from insightface.app import FaceAnalysis
import traceback
import httpx
import asyncio
from .gpu_service import SimpleGPUHealthMonitor
from .config import settings

# Add this after the settings import in faiss_service.py
print(f"DEBUG - GPU_ENABLED: {settings.GPU_ENABLED}")
print(f"DEBUG - GPU_ENDPOINT_URL: {settings.GPU_ENDPOINT_URL}")
print(f"DEBUG - Combined check: {settings.GPU_ENABLED and settings.GPU_ENDPOINT_URL}")

# Fix for OMP error
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class EnhancedFaceIndexingService:
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.face_app = None
        self.logger = logging.getLogger(__name__)
        
        # ArcFace parameters
        self.dimension = 512  # ArcFace embedding dimension
        
        # GPU configuration - NEW INTEGRATION
        self.gpu_enabled = settings.GPU_ENABLED and settings.GPU_ENDPOINT_URL
        self.gpu_monitor = None
        
        if self.gpu_enabled:
            self.gpu_monitor = SimpleGPUHealthMonitor(
                endpoint_url=settings.GPU_ENDPOINT_URL,
                check_interval=settings.GPU_HEALTH_CHECK_INTERVAL,
                timeout=settings.GPU_HEALTH_CHECK_TIMEOUT
            )
            self.logger.info(f"GPU acceleration enabled: {settings.GPU_ENDPOINT_URL}")
        else:
            self.logger.info("GPU acceleration disabled - using CPU only")
        
        # Enhanced similarity thresholds for better matching
        self.similarity_thresholds = {
            'very_strict': 0.85,    # Almost identical faces
            'strict': 0.75,         # Same person, different conditions
            'normal': 0.65,         # Good match, some variation
            'relaxed': 0.55,        # Similar faces, aging/lighting
            'loose': 0.45           # Broader matching
        }
        
        # FAISS parameters for different scales
        self.faiss_configs = {
            'small': {  # < 1,000 images
                'index_type': 'IndexFlatL2',
                'params': {}
            },
            'medium': {  # 1,000 - 50,000 images
                'index_type': 'IndexIVFFlat',
                'params': {
                    'nlist': lambda n: max(4, min(n // 39, 100)),
                    'nprobe': 10
                }
            },
            'large': {  # 50,000 - 500,000 images
                'index_type': 'IndexIVFPQ',
                'params': {
                    'nlist': lambda n: max(100, min(n // 39, 1000)),
                    'nprobe': 32,
                    'm': 64,  # Number of subquantizers
                    'nbits': 8  # Number of bits per subquantizer
                }
            },
            'xlarge': {  # 500,000 - 5,000,000 images
                'index_type': 'IndexHNSW',
                'params': {
                    'M': 32,  # Number of bi-directional links for each node
                    'efConstruction': 200,  # Size of the dynamic candidate list
                    'efSearch': 64  # Size of the dynamic candidate list during search
                }
            },
            'production': {  # > 5,000,000 images
                'index_type': 'ProductionIVFPQ',
                'params': {
                    'nlist': lambda n: max(1000, min(n // 39, 4096)),
                    'nprobe': 128,
                    'm': 128,
                    'nbits': 8
                }
            }
        }
        
        self._init_models()
    
    def _init_models(self):
        """Initialize ArcFace models with optimized settings"""
        try:
            # Initialize InsightFace with ArcFace - CPU mode with optimizations
            self.face_app = FaceAnalysis(
                providers=['CPUExecutionProvider'],
                allowed_modules=['detection', 'recognition']
            )
            self.face_app.prepare(ctx_id=-1, det_size=(640, 640))
            self.logger.info("ArcFace models loaded successfully on CPU")
        except Exception as e:
            self.logger.error(f"Failed to load ArcFace models: {e}")
            raise

    def is_gpu_available(self) -> bool:
        """Simple check: Is GPU healthy and enabled?"""
        return self.gpu_enabled and self.gpu_monitor and self.gpu_monitor.is_healthy

    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)

    def enhance_image_quality_advanced(self, image, aggressive=False):
        """Advanced image quality improvement with multiple strategies - same as Streamlit"""
        if isinstance(image, Image.Image):
            image = ImageOps.exif_transpose(image)
            img_cv = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        else:
            img_cv = image.copy()
        
        if aggressive:
            # AGGRESSIVE ENHANCEMENT for very blurry/poor images
            # 1. Strong noise reduction with larger filter
            img_cv = cv2.bilateralFilter(img_cv, 15, 90, 90)
            
            # 2. Histogram equalization for better contrast
            lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            img_cv = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            # 3. Stronger sharpening kernel
            sharpening_kernel = np.array([[-1,-1,-1], [-1, 12,-1], [-1,-1,-1]])
            img_cv = cv2.filter2D(img_cv, -1, sharpening_kernel)
            
            # 4. Gamma correction for low-light CCTV images
            gamma = 1.4
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            img_cv = cv2.LUT(img_cv, table)
            
            # 5. Additional unsharp masking for better face details
            gaussian = cv2.GaussianBlur(img_cv, (0, 0), 3.0)
            img_cv = cv2.addWeighted(img_cv, 1.8, gaussian, -0.8, 0)
            
        else:
            # STANDARD ENHANCEMENT (same as Streamlit)
            # 1. Noise reduction
            img_cv = cv2.bilateralFilter(img_cv, 9, 75, 75)
            
            # 2. Sharpening
            sharpening_kernel = np.array([[-1,-1,-1], [-1, 9,-1], [-1,-1,-1]])
            img_cv = cv2.filter2D(img_cv, -1, sharpening_kernel)
            
            # 3. CLAHE contrast enhancement
            lab = cv2.cvtColor(img_cv, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            l = clahe.apply(l)
            enhanced = cv2.merge([l, a, b])
            img_cv = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            # 4. Unsharp masking for face details
            gaussian = cv2.GaussianBlur(img_cv, (0, 0), 2.0)
            img_cv = cv2.addWeighted(img_cv, 1.5, gaussian, -0.5, 0)
            
            # 5. Gamma correction
            gamma = 1.2
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
            img_cv = cv2.LUT(img_cv, table)
        
        img_enhanced = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_enhanced)

    def enhance_image_quality(self, image, aggressive=False):
        """Enhanced image quality improvement with aggressive mode - legacy method"""
        return self.enhance_image_quality_advanced(image, aggressive)

    def calculate_image_quality(self, image):
        """Calculate image quality score using blur detection"""
        if isinstance(image, Image.Image):
            img_array = np.array(image)
        else:
            img_array = image
        
        # Convert to grayscale
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        
        # Calculate Laplacian variance (blur detection)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        # Normalize to 0-1 scale
        quality_score = min(blur_score / 1000.0, 1.0)
        
        return quality_score

    async def extract_face_embeddings_batch_gpu(self, image_paths: List[str]) -> List[Tuple[Optional[np.ndarray], Dict]]:
        """GPU batch processing with simple fallback"""
        if not self.is_gpu_available():
            # CPU fallback
            self.logger.info("Using CPU for face extraction (GPU not available)")
            return self._extract_batch_cpu(image_paths)
        
        try:
            # Prepare batch data
            images_data = []
            valid_paths = []
            
            for path in image_paths:
                try:
                    with open(path, 'rb') as f:
                        img_data = base64.b64encode(f.read()).decode()
                        images_data.append(img_data)
                        valid_paths.append(path)
                except Exception as e:
                    self.logger.warning(f"Error reading {path}: {e}")
                    continue
            
            if not images_data:
                return [(None, {'error': 'No valid images'}) for _ in image_paths]
            
            # Call GPU endpoint
            payload = {
                "images": images_data,
                "enhance_quality": True,
                "aggressive_enhancement": True
            }
            
            async with httpx.AsyncClient(timeout=settings.GPU_PROCESSING_TIMEOUT) as client:
                response = await client.post(
                    f"{settings.GPU_ENDPOINT_URL}/extract_embeddings_batch",
                    json=payload
                )
                
                if response.status_code != 200:
                    raise Exception(f"GPU endpoint error: {response.status_code}")
                
                result = response.json()
                
                # Process GPU results
                processed_results = []
                for i, (embedding_data, extraction_info) in enumerate(zip(result["embeddings"], result["extraction_info"])):
                    if embedding_data:
                        embedding = np.array(embedding_data, dtype='float32')
                        processed_results.append((embedding, extraction_info))
                    else:
                        processed_results.append((None, extraction_info))
                
                self.logger.info(f"GPU batch processing: {result['successful']}/{result['total_processed']} successful")
                return processed_results
                
        except Exception as e:
            self.logger.warning(f"GPU processing failed, falling back to CPU: {e}")
            # Immediate CPU fallback
            return self._extract_batch_cpu(image_paths)
    
    def _extract_batch_cpu(self, image_paths: List[str]) -> List[Tuple[Optional[np.ndarray], Dict]]:
        """CPU batch processing (existing logic)"""
        results = []
        for path in image_paths:
            embedding, info = self.extract_face_embedding_from_image_advanced(path)
            results.append((embedding, info))
        return results

    def extract_face_embedding_from_image_advanced(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """Advanced face extraction with multiple enhancement strategies - same as Streamlit"""
        extraction_info = {
            'strategy_used': None,
            'quality_score': 0,
            'face_count': 0,
            'confidence': 0,
            'enhancement_used': False,
            'attempts': []
        }
        
        try:
            img = Image.open(image_path).convert("RGB")
            quality = self.calculate_image_quality(img)
            extraction_info['quality_score'] = quality
            
            # MULTIPLE PROCESSING STRATEGIES (same as Streamlit)
            strategies = [
                ('original', img, False),
                ('enhanced_standard', self.enhance_image_quality_advanced(img, aggressive=False), True),
                ('enhanced_aggressive', self.enhance_image_quality_advanced(img, aggressive=True), True),
            ]
            
            # If very poor quality, try additional strategies
            if quality < 0.2:
                # Add upscaling strategy for very poor images
                upscaled_img = img.resize((img.width * 2, img.height * 2), Image.LANCZOS)
                strategies.append(('upscaled_enhanced', self.enhance_image_quality_advanced(upscaled_img, aggressive=True), True))
            
            best_embedding = None
            best_confidence = 0
            
            for strategy_name, processed_img, enhanced in strategies:
                try:
                    img_array = np.array(processed_img)
                    faces = self.face_app.get(img_array)
                    extraction_info['face_count'] = len(faces)
                    
                    attempt_info = {
                        'strategy': strategy_name,
                        'faces_found': len(faces),
                        'confidence': 0,
                        'success': False
                    }
                    
                    if len(faces) == 0:
                        extraction_info['attempts'].append(attempt_info)
                        continue
                    
                    # Get the best face (largest bounding box area)
                    face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
                    
                    # Calculate enhanced face confidence
                    bbox_area = (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
                    img_area = img_array.shape[0] * img_array.shape[1]
                    face_size_ratio = bbox_area / img_area
                    
                    # Enhanced confidence calculation considering face size and detection quality
                    face_confidence = min(face_size_ratio * 2.0, 1.0)  # Boost confidence for larger faces
                    
                    # Additional confidence boost for enhanced images that found faces
                    if enhanced and len(faces) > 0:
                        face_confidence *= 1.2  # 20% boost for successful enhancement
                    
                    attempt_info.update({
                        'confidence': face_confidence,
                        'bbox_area': bbox_area,
                        'face_size_ratio': face_size_ratio,
                        'success': True
                    })
                    
                    if face_confidence > best_confidence:
                        embedding = face.embedding
                        embedding = embedding / np.linalg.norm(embedding)
                        best_embedding = embedding.astype('float32')
                        best_confidence = face_confidence
                        extraction_info['strategy_used'] = strategy_name
                        extraction_info['confidence'] = face_confidence
                        extraction_info['enhancement_used'] = enhanced
                        
                        self.logger.info(f"Face extraction successful: {strategy_name} (confidence: {face_confidence:.3f})")
                        
                        # For very good results, stop trying more strategies
                        if face_confidence > 0.3:  # Higher threshold than before
                            break
                    
                    extraction_info['attempts'].append(attempt_info)
                    
                except Exception as e:
                    attempt_info.update({
                        'error': str(e),
                        'success': False
                    })
                    extraction_info['attempts'].append(attempt_info)
                    self.logger.debug(f"Strategy {strategy_name} failed: {e}")
                    continue
            
            return best_embedding, extraction_info
            
        except Exception as e:
            self.logger.error(f"Error extracting face embedding from {image_path}: {e}")
            return None, extraction_info

    def extract_face_embedding_from_image(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """Extract face embedding with multiple strategies and metadata - uses advanced method"""
        return self.extract_face_embedding_from_image_advanced(image_path)

    def extract_face_embedding_from_array(self, img_array: np.ndarray) -> Tuple[Optional[np.ndarray], Dict]:
        """Extract face embedding from numpy array with multiple strategies"""
        extraction_info = {
            'strategy_used': None,
            'quality_score': 0,
            'face_count': 0,
            'confidence': 0,
            'enhancement_used': False
        }
        
        try:
            quality = self.calculate_image_quality(img_array)
            extraction_info['quality_score'] = quality
            
            # Multiple processing strategies
            strategies = [
                ('original', img_array, False),
                ('enhanced', np.array(self.enhance_image_quality_advanced(Image.fromarray(img_array))), True),
                ('aggressive', np.array(self.enhance_image_quality_advanced(Image.fromarray(img_array), aggressive=True)), True)
            ]
            
            best_embedding = None
            best_confidence = 0
            
            for strategy_name, processed_array, enhanced in strategies:
                try:
                    faces = self.face_app.get(processed_array)
                    extraction_info['face_count'] = len(faces)
                    
                    if len(faces) == 0:
                        continue
                    
                    face = max(faces, key=lambda x: (x.bbox[2] - x.bbox[0]) * (x.bbox[3] - x.bbox[1]))
                    
                    bbox_area = (face.bbox[2] - face.bbox[0]) * (face.bbox[3] - face.bbox[1])
                    face_confidence = min(bbox_area / (processed_array.shape[0] * processed_array.shape[1]), 1.0)
                    
                    if face_confidence > best_confidence:
                        embedding = face.embedding
                        embedding = embedding / np.linalg.norm(embedding)
                        best_embedding = embedding.astype('float32')
                        best_confidence = face_confidence
                        extraction_info['strategy_used'] = strategy_name
                        extraction_info['confidence'] = face_confidence
                        extraction_info['enhancement_used'] = enhanced
                        
                        if face_confidence > 0.1:
                            break
                    
                except Exception as e:
                    self.logger.debug(f"Array strategy {strategy_name} failed: {e}")
                    continue
            
            return best_embedding, extraction_info
            
        except Exception as e:
            self.logger.error(f"Error extracting face embedding from array: {e}")
            return None, extraction_info

    def search_similar_faces_enhanced(self, query_image_path: str, image_set_ids: List[int], 
                                    top_k: int = 25, similarity_threshold: float = 0.45) -> Dict[str, Any]:
        """Enhanced face matching with adaptive thresholds for blurry images"""
        try:
            # Extract query embedding with advanced preprocessing
            query_embedding, query_info = self.extract_face_embedding_from_image_advanced(query_image_path)
            
            if query_embedding is None:
                return {
                    'success': False,
                    'message': 'No face detected in query image even after enhancement',
                    'results': [],
                    'query_info': query_info
                }
            
            all_results = []
            search_info = {
                'total_indexes_searched': 0,
                'total_vectors_searched': 0,
                'search_time': 0,
                'query_enhancement': query_info
            }
            
            # ADAPTIVE THRESHOLD based on query quality
            adaptive_threshold = similarity_threshold
            
            # Lower threshold for poor quality queries (like in Streamlit)
            if query_info['quality_score'] < 0.3:  # Very poor quality
                adaptive_threshold *= 0.7  # Much more lenient
                self.logger.info(f"Poor quality query detected, lowering threshold to {adaptive_threshold:.3f}")
            elif query_info['quality_score'] < 0.5:  # Moderate quality
                adaptive_threshold *= 0.8
                self.logger.info(f"Moderate quality query, lowering threshold to {adaptive_threshold:.3f}")
            
            # Additional threshold reduction for enhanced images
            if query_info['enhancement_used']:
                adaptive_threshold *= 0.9  # 10% more lenient for enhanced
                self.logger.info(f"Enhanced query image, threshold adjusted to {adaptive_threshold:.3f}")
            
            # For very low confidence extractions, be even more lenient
            if query_info['confidence'] < 0.1:
                adaptive_threshold *= 0.6  # Very lenient for poor extractions
                self.logger.info(f"Low confidence extraction, very lenient threshold: {adaptive_threshold:.3f}")
            
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    for image_set_id in image_set_ids:
                        cur.execute("""
                            SELECT index_data_b64, image_metadata, folder_path, 
                                index_type, index_params
                            FROM faiss_indexes_b64 
                            WHERE image_set_id = %s
                            ORDER BY created_at DESC 
                            LIMIT 1
                        """, (image_set_id,))
                        
                        result = cur.fetchone()
                        if not result:
                            self.logger.warning(f"No FAISS index found for image set {image_set_id}")
                            continue
                        
                        try:
                            index_data_raw = result['index_data_b64']
                            index_data_bytes = base64.b64decode(index_data_raw)
                            index_data_np = np.frombuffer(index_data_bytes, dtype=np.uint8)
                            index = faiss.deserialize_index(index_data_np)
                            
                            search_info['total_indexes_searched'] += 1
                            search_info['total_vectors_searched'] += index.ntotal
                            
                            self.logger.info(f"Loaded index with {index.ntotal} vectors for search")
                            
                        except Exception as e:
                            self.logger.error(f"Error deserializing index: {e}")
                            continue
                        
                        # ENHANCED SEARCH with multiple similarity calculations
                        image_metadata = result['image_metadata']
                        query_vector = query_embedding.reshape(1, -1).astype('float32')
                        
                        # Search with LARGER k to get more candidates (especially for blurry images)
                        search_k = min(top_k * 5, index.ntotal)  # 5x more candidates instead of 3x
                        distances, indices = index.search(query_vector, search_k)
                        
                        candidates_found = 0
                        
                        # Process results with ENHANCED similarity scoring for blurry images
                        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                            if idx == -1:
                                break
                                
                            candidates_found += 1
                            
                            # Enhanced similarity calculation (same as Streamlit)
                            cosine_similarity = 1 - (distance / 2.0)
                            cosine_similarity = max(0, min(1, cosine_similarity))
                            
                            # Apply adaptive threshold
                            final_threshold = adaptive_threshold
                            
                            if cosine_similarity >= final_threshold:
                                if idx < len(image_metadata):
                                    result_metadata = image_metadata[idx]
                                    
                                    # Calculate final score with ENHANCED confidence weighting
                                    final_score = cosine_similarity * 100
                                    
                                    # BOOST SCORES for enhanced queries (like Streamlit)
                                    if query_info['enhancement_used']:
                                        final_score *= 1.1  # 10% boost for enhanced queries
                                    
                                    # Extra boost for low-quality queries that found matches
                                    if query_info['quality_score'] < 0.3 and cosine_similarity > 0.4:
                                        final_score *= 1.15  # 15% boost for poor quality that still matched
                                    
                                    # Cap the score
                                    final_score = min(final_score, 99.9)
                                    
                                    all_results.append({
                                        'image_set_id': int(image_set_id),
                                        'image_id': str(result_metadata.get('image_id', f'img_{idx}')),
                                        'similarity_score': float(final_score),
                                        'cosine_similarity': float(cosine_similarity),
                                        'l2_distance': float(distance),
                                        'image_path': str(result_metadata['image_path']),
                                        'filename': str(result_metadata['filename']),
                                        'relative_path': str(result_metadata['relative_path']),
                                        'rank': int(i + 1),
                                        'search_method': 'arcface_enhanced_blurry_optimized',
                                        'match_confidence': 'high' if cosine_similarity > 0.7 else 
                                                        'medium' if cosine_similarity > 0.5 else 'low',
                                        'adaptive_threshold_used': float(final_threshold),
                                        'query_quality': float(query_info['quality_score']),
                                        'enhancement_boost_applied': query_info['enhancement_used']
                                    })
                        
                        self.logger.info(f"Processed {candidates_found} candidates, found {len([r for r in all_results if r['image_set_id'] == image_set_id])} matches above threshold")
                
                # Sort by similarity and apply filtering
                all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
                
                # Apply diversity filtering (but be more lenient for poor quality queries)
                diversity_threshold = 2.0 if query_info['quality_score'] > 0.3 else 1.0
                filtered_results = self._apply_diversity_filter_enhanced(all_results, top_k, diversity_threshold)
                
                self.logger.info(f"Enhanced search found {len(filtered_results)} results from {len(all_results)} candidates")
                
                return {
                    'success': True,
                    'message': f'Found {len(filtered_results)} enhanced matches (adaptive threshold: {adaptive_threshold:.3f})',
                    'results': filtered_results,
                    'search_info': {
                        'total_indexes_searched': int(search_info['total_indexes_searched']),
                        'total_vectors_searched': int(search_info['total_vectors_searched']),
                        'adaptive_threshold_used': float(adaptive_threshold),
                        'original_threshold': float(similarity_threshold),
                        'query_enhancement': {
                            k: float(v) if isinstance(v, (int, float)) else str(v) if v is not None else v
                            for k, v in query_info.items()
                        }
                    },
                    'query_info': {
                        k: float(v) if isinstance(v, (int, float)) else str(v) if v is not None else v
                        for k, v in query_info.items()
                    },
                    'similarity_threshold_used': float(adaptive_threshold)
                }
                
            finally:
                conn.close()
                
        except Exception as e:
            self.logger.error(f"Error in enhanced search: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Enhanced search failed: {str(e)}',
                'results': [],
                'query_info': {
                    k: float(v) if isinstance(v, (int, float)) else str(v) if v is not None else v
                    for k, v in (query_info.items() if 'query_info' in locals() else {})
                }
            }

    def search_similar_faces(self, query_image_path: str, image_set_ids: List[int], 
                       top_k: int = 25, similarity_threshold: float = 0.45) -> Dict[str, Any]:
        """Enhanced face matching - now uses the advanced method"""
        return self.search_similar_faces_enhanced(query_image_path, image_set_ids, top_k, similarity_threshold)

    def _apply_diversity_filter_enhanced(self, results: List[Dict], max_results: int, diversity_threshold: float = 2.0) -> List[Dict]:
        """Enhanced diversity filtering that's more lenient for poor quality queries"""
        if len(results) <= max_results:
            return results
        
        # For poor quality queries, be less strict about diversity
        if any(r.get('query_quality', 1.0) < 0.3 for r in results):
            # Take more top results for poor quality queries
            filtered = results[:max(max_results // 3 * 2, 1)]  # Take top 2/3
            remaining = results[len(filtered):]
        else:
            # Standard approach
            filtered = results[:max(1, max_results // 2)]
            remaining = results[len(filtered):]
        
        # Add diverse results from remaining
        for result in remaining:
            if len(filtered) >= max_results:
                break
            
            # Check diversity with the provided threshold
            is_diverse = True
            for existing in filtered:
                if (result['image_set_id'] == existing['image_set_id'] and 
                    abs(result['similarity_score'] - existing['similarity_score']) < diversity_threshold):
                    is_diverse = False
                    break
            
            if is_diverse:
                filtered.append(result)
        
        return filtered[:max_results]

    def _apply_diversity_filter(self, results: List[Dict], max_results: int) -> List[Dict]:
        """Apply diversity filtering to avoid too many very similar results"""
        return self._apply_diversity_filter_enhanced(results, max_results, 2.0)

    # Keep all other methods from original service
    def count_images_in_folder(self, folder_path: str) -> Tuple[int, List[str]]:
        """Count valid image files in folder"""
        if not os.path.exists(folder_path):
            return 0, []
        
        valid_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp')
        image_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(valid_extensions):
                    full_path = os.path.join(root, file)
                    image_files.append(full_path)
        
        return len(image_files), image_files
    
    def calculate_cost(self, image_count: int, cost_per_image: float = 0.001) -> float:
        """Calculate indexing cost"""
        return image_count * cost_per_image
    
    def _extract_image_id_from_filename(self, filename: str) -> str:
        """Extract or generate image ID from filename"""
        try:
            # Try to extract numbers from filename
            numbers = re.findall(r'\d+', os.path.basename(filename))
            if numbers:
                # Take the longest number sequence
                longest_number = max(numbers, key=len)
                return longest_number
            else:
                # Generate ID from filename hash
                file_hash = hashlib.md5(filename.encode()).hexdigest()
                # Take first 4 characters and convert to number
                return str(int(file_hash[:4], 16))
        except:
            # Fallback to random 4-digit number
            return str(hash(filename) % 10000)
    
    def _get_optimal_faiss_config(self, dataset_size: int) -> Tuple[str, Dict]:
        """Get optimal FAISS configuration based on dataset size"""
        if dataset_size < 1000:
            return 'small', self.faiss_configs['small']
        elif dataset_size < 50000:
            return 'medium', self.faiss_configs['medium']
        elif dataset_size < 500000:
            return 'large', self.faiss_configs['large']
        elif dataset_size < 5000000:
            return 'xlarge', self.faiss_configs['xlarge']
        else:
            return 'production', self.faiss_configs['production']
    
    def _create_faiss_index(self, embeddings_array: np.ndarray) -> Tuple[faiss.Index, str, Dict]:
        """Create optimal FAISS index based on dataset size"""
        dataset_size = embeddings_array.shape[0]
        config_name, config = self._get_optimal_faiss_config(dataset_size)
        
        # Initialize index variable to avoid scope issues
        index = None
        params = {}
        
        # Validate input data
        if embeddings_array.dtype != np.float32:
            embeddings_array = embeddings_array.astype('float32')
        
        if not np.isfinite(embeddings_array).all():
            self.logger.error("Input contains NaN or infinite values")
            raise ValueError("Invalid embedding data")
        
        # Ensure proper normalization for cosine similarity
        norms = np.linalg.norm(embeddings_array, axis=1)
        if np.any(norms == 0):
            self.logger.error("Zero-norm embeddings detected")
            raise ValueError("Zero-norm embeddings found")
        
        self.logger.info(f"Creating {config['index_type']} for {dataset_size} vectors")
        
        try:
            if config['index_type'] == 'IndexFlatL2':
                # Flat index for exact cosine similarity search
                index = faiss.IndexFlatL2(self.dimension)
                params = {}
                
            elif config['index_type'] == 'IndexIVFFlat':
                # IVF with flat quantizer
                nlist = config['params']['nlist'](dataset_size)
                quantizer = faiss.IndexFlatL2(self.dimension)
                index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist, faiss.METRIC_INNER_PRODUCT)
                params = {'nlist': nlist, 'nprobe': config['params']['nprobe']}
                
            elif config['index_type'] == 'IndexIVFPQ':
                # IVF with product quantization
                nlist = config['params']['nlist'](dataset_size)
                m = config['params']['m']
                quantizer = faiss.IndexFlatL2(self.dimension)
                index = faiss.IndexIVFPQ(quantizer, self.dimension, nlist, m, config['params']['nbits'])
                params = {
                    'nlist': nlist, 
                    'nprobe': config['params']['nprobe'],
                    'm': m,
                    'nbits': config['params']['nbits']
                }
                
            elif config['index_type'] == 'IndexHNSW':
                # HNSW index for large datasets
                index = faiss.IndexHNSWFlat(self.dimension, config['params']['M'])
                index.hnsw.efConstruction = config['params']['efConstruction']
                index.hnsw.efSearch = config['params']['efSearch']
                params = {
                    'M': config['params']['M'],
                    'efConstruction': config['params']['efConstruction'],
                    'efSearch': config['params']['efSearch']
                }
                
            elif config['index_type'] == 'ProductionIVFPQ':
                # Production-scale IVFPQ with optimized parameters
                nlist = config['params']['nlist'](dataset_size)
                m = config['params']['m']
                quantizer = faiss.IndexFlatL2(self.dimension)
                index = faiss.IndexIVFPQ(quantizer, self.dimension, nlist, m, config['params']['nbits'])
                params = {
                    'nlist': nlist,
                    'nprobe': config['params']['nprobe'],
                    'm': m,
                    'nbits': config['params']['nbits']
                }
            else:
                # Fallback case - this might be where your error occurs
                self.logger.warning(f"Unknown index type: {config['index_type']}, falling back to IndexFlatL2")
                index = faiss.IndexFlatL2(self.dimension)
                config_name = 'fallback_flat'
                params = {}
            
            # Ensure index was created
            if index is None:
                raise ValueError(f"Failed to create index for type: {config['index_type']}")
            
            # Wrap with IDMap for robust ID management
            index_with_ids = faiss.IndexIDMap(index)
            
            # Train index if required
            if hasattr(index, 'is_trained') and not index.is_trained:
                self.logger.info(f"Training {config['index_type']} index...")
                try:
                    index.train(embeddings_array)
                    self.logger.info("Index training completed successfully")
                except Exception as e:
                    self.logger.error(f"Index training failed: {e}")
                    # Fallback to flat index
                    self.logger.info("Falling back to IndexFlatL2")
                    index = faiss.IndexFlatL2(self.dimension)
                    index_with_ids = faiss.IndexIDMap(index)
                    config_name = 'fallback_flat'
                    params = {}
            
            return index_with_ids, f"{config_name}_{config['index_type']}", params
            
        except Exception as e:
            self.logger.error(f"Error creating index: {e}")
            # Final fallback
            self.logger.info("Using final fallback: IndexFlatL2")
            index = faiss.IndexFlatL2(self.dimension)
            index_with_ids = faiss.IndexIDMap(index)
            return index_with_ids, "fallback_IndexFlatL2", {}

    def _set_search_parameters(self, index: faiss.Index, params: Dict):
        """Set optimal search parameters for the index"""
        base = index.index if hasattr(index, 'index') else index
        
        if hasattr(base, 'nprobe'):  # IVF-based indices
            base.nprobe = params.get('nprobe', 10)
            self.logger.info(f"Set nprobe to {base.nprobe}")
        
        if hasattr(base, 'efSearch'):  # HNSW indices
            base.efSearch = params.get('efSearch', 64)
            self.logger.info(f"Set efSearch to {base.efSearch}")
    
    async def process_folder_for_indexing(self, folder_path: str, image_set_id: int, 
                               user_id: int) -> Dict[str, Any]:
        """Process entire folder and create FAISS index with GPU support and progress tracking"""
        try:
            image_count, image_files = self.count_images_in_folder(folder_path)
            
            if image_count == 0:
                return {
                    'success': False,
                    'message': 'No valid images found in folder',
                    'image_count': 0,
                    'cost': 0
                }
            
            cost = self.calculate_cost(image_count)
            all_embeddings = []
            metadata = []
            processed_count = 0
            failed_count = 0
            
            processing_mode = "GPU" if self.is_gpu_available() else "CPU"
            self.logger.info(f"Starting {processing_mode} processing of {image_count} images...")
            
            # Choose batch size based on processing mode
            batch_size = 50 if self.is_gpu_available() else 10
            
            for i in range(0, len(image_files), batch_size):
                batch_files = image_files[i:i + batch_size]
                
                # Process batch - GPU first, CPU fallback
                if self.is_gpu_available():
                    batch_results = await self.extract_face_embeddings_batch_gpu(batch_files)
                else:
                    batch_results = self._extract_batch_cpu(batch_files)
                
                # Process results
                for j, (embedding, extraction_info) in enumerate(batch_results):
                    image_path = batch_files[j]
                    
                    if embedding is not None:
                        all_embeddings.append(embedding)
                        
                        # Create metadata
                        relative_path = os.path.relpath(image_path, folder_path)
                        file_hash = self._get_file_hash(image_path)
                        image_id = self._extract_image_id_from_filename(image_path)
                        
                        # FIX: Convert numpy types to Python native types for JSON serialization
                        metadata_item = {
                            'image_id': str(image_id),
                            'image_path': str(image_path),
                            'filename': str(os.path.basename(image_path)),
                            'relative_path': str(relative_path),
                            'index_in_faiss': int(len(all_embeddings) - 1),
                            'file_hash': str(file_hash),
                            'processed_at': datetime.utcnow().isoformat(),
                            'extraction_info': {
                                'strategy_used': str(extraction_info.get('strategy_used', processing_mode.lower())),
                                'quality_score': float(extraction_info.get('quality_score', 0.0)),
                                'face_count': int(extraction_info.get('face_count', 0)),
                                'confidence': float(extraction_info.get('confidence', 0.0)),
                                'enhancement_used': bool(extraction_info.get('enhancement_used', False)),
                                'processing_mode': processing_mode
                            }
                        }
                        
                        metadata.append(metadata_item)
                        processed_count += 1
                    else:
                        failed_count += 1
                
                # Update progress
                if processed_count % 25 == 0:
                    progress = int(((i + batch_size) / len(image_files)) * 80)
                    self.logger.info(f"Processed {processed_count}/{image_count} images using {processing_mode}")
                    self._update_progress(image_set_id, progress)
            
            if not all_embeddings:
                return {
                    'success': False,
                    'message': 'No valid face embeddings extracted',
                    'image_count': image_count,
                    'processed_count': 0,
                    'failed_count': failed_count,
                    'cost': cost
                }
            
            # Create optimal FAISS index
            embeddings_array = np.array(all_embeddings).astype('float32')
            index, index_type, index_params = self._create_faiss_index(embeddings_array)
            
            # Generate explicit IDs for robust ID management
            ids = np.arange(len(all_embeddings)).astype('int64')
            
            # Add embeddings with explicit IDs
            self.logger.info(f"Adding {len(all_embeddings)} embeddings to {index_type} index...")
            try:
                index.add_with_ids(embeddings_array, ids)
                self.logger.info(f"Successfully added {len(all_embeddings)} embeddings to index")
            except Exception as e:
                self.logger.error(f"Failed to add embeddings: {e}")
                return {'success': False, 'message': f"Index creation failed: {e}"}
            
            # Update metadata with the explicit IDs - FIX: Ensure all values are JSON serializable
            for i, meta in enumerate(metadata):
                meta["id"] = int(ids[i])
            
            # Set optimal search parameters
            self._set_search_parameters(index, index_params)
            
            # Serialize and store index
            try:
                # Serialize the FAISS index
                index_data_raw = faiss.serialize_index(index)
                self.logger.info(f"Raw serialized index to {len(index_data_raw)} bytes")
                
                # Convert to numpy array for better compatibility
                index_data_np = np.frombuffer(index_data_raw, dtype=np.uint8)
                self.logger.info(f"Converted to numpy array: shape {index_data_np.shape}, dtype {index_data_np.dtype}")
                
                # Convert back to bytes for storage
                index_data = index_data_np.tobytes()
                self.logger.info(f"Final serialized index: {len(index_data)} bytes")
                
                # CRITICAL: Validate serialization
                try:
                    # Test direct deserialization
                    validation_index = faiss.deserialize_index(index_data)
                    self.logger.info(f"Direct serialization validation PASSED: {validation_index.ntotal} vectors")
                except Exception as e1:
                    self.logger.warning(f"Direct deserialization failed: {e1}")
                    
                    # Try numpy-based deserialization
                    try:
                        index_data_np_reload = np.frombuffer(index_data, dtype=np.uint8)
                        validation_index = faiss.deserialize_index(index_data_np_reload)
                        self.logger.info(f"Numpy-based serialization validation PASSED: {validation_index.ntotal} vectors")
                    except Exception as e2:
                        self.logger.error(f"Both serialization methods failed: direct={e1}, numpy={e2}")
                        raise ValueError(f"Index serialization produced invalid data: {e2}")
                        
            except Exception as e:
                self.logger.error(f"Serialization process failed: {e}")
                return {'success': False, 'message': f"Index serialization failed: {e}"}
            
            # Store in database
            index_id = self._store_index_in_db(
                image_set_id=image_set_id,
                user_id=user_id,
                index_data=index_data,
                metadata=metadata,
                folder_path=folder_path,
                processed_count=processed_count,
                failed_count=failed_count,
                total_cost=cost,
                index_type=f"{processing_mode}_{index_type}",
                index_params=index_params
            )
            
            self._update_progress(image_set_id, 100)
            
            return {
                'success': True,
                'message': f'Successfully indexed {processed_count} images using {processing_mode} processing',
                'index_id': index_id,
                'image_count': image_count,
                'processed_count': processed_count,
                'failed_count': failed_count,
                'cost': float(cost),
                'index_type': f"{processing_mode}_{index_type}",
                'processing_mode': processing_mode
            }
            
        except Exception as e:
            self.logger.error(f"Error in process_folder_for_indexing: {e}")
            return {
                'success': False,
                'message': f'Indexing failed: {str(e)}',
                'image_count': 0,
                'cost': 0
            }
    
    def _get_file_hash(self, file_path: str) -> str:
        """Generate MD5 hash of file for deduplication"""
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _update_progress(self, image_set_id: int, progress: int):
        """Update indexing progress in database"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE image_sets 
                    SET progress = %s, updated_at = NOW()
                    WHERE id = %s
                """, (progress, image_set_id))
            conn.commit()
            conn.close()
        except Exception as e:
            self.logger.error(f"Error updating progress: {e}")
    
    def _store_index_in_db(self, image_set_id: int, user_id: int, index_data: bytes,
                  metadata: List[Dict], folder_path: str, processed_count: int,
                  failed_count: int, total_cost: float, index_type: str,
                  index_params: Dict) -> str:
        """Store FAISS index in database with enhanced metadata"""
        
        # Pre-storage validation with proper numpy handling
        try:
            # Convert bytes to numpy array for FAISS compatibility
            if isinstance(index_data, bytes):
                index_data_np = np.frombuffer(index_data, dtype=np.uint8)
                test_index = faiss.deserialize_index(index_data_np)
            else:
                test_index = faiss.deserialize_index(index_data)
            self.logger.info(f"Pre-storage validation PASSED: {test_index.ntotal} vectors")
        except Exception as e:
            self.logger.error(f"Pre-storage validation FAILED: {e}")
            raise ValueError(f"Invalid FAISS index data before storage: {e}")
        
        # Store as base64 for database compatibility
        try:
            # Ensure we're working with bytes for base64 encoding
            if isinstance(index_data, bytes):
                index_data_b64 = base64.b64encode(index_data).decode('utf-8')
            else:
                # If it's already a numpy array, convert to bytes first
                index_data_bytes = index_data.tobytes() if hasattr(index_data, 'tobytes') else bytes(index_data)
                index_data_b64 = base64.b64encode(index_data_bytes).decode('utf-8')
            
            self.logger.info(f"Encoded {index_type} index as base64: {len(index_data_b64)} characters")
        except Exception as e:
            self.logger.error(f"Base64 encoding failed: {e}")
            raise ValueError(f"Failed to encode index data: {e}")
        
        # FIX: Ensure all parameters are JSON serializable
        def make_json_serializable(obj):
            """Convert numpy/other types to JSON serializable types"""
            if isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [make_json_serializable(item) for item in obj]
            elif isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, (np.bool_, bool)):
                return bool(obj)
            elif hasattr(obj, '__dict__'):
                return str(obj)  # For complex objects, convert to string
            else:
                return obj
        
        # Clean metadata and index_params
        clean_metadata = make_json_serializable(metadata)
        clean_index_params = make_json_serializable(index_params)
        
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS faiss_indexes_b64 (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        image_set_id INTEGER REFERENCES image_sets(id),
                        user_id INTEGER REFERENCES users(id),
                        index_data_b64 TEXT NOT NULL,
                        image_metadata JSONB NOT NULL,
                        folder_path TEXT NOT NULL,
                        processed_count INTEGER NOT NULL,
                        failed_count INTEGER NOT NULL,
                        total_cost DECIMAL(10,4) NOT NULL,
                        index_type TEXT NOT NULL,
                        index_params JSONB NOT NULL,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                
                index_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO faiss_indexes_b64 
                    (id, image_set_id, user_id, index_data_b64, image_metadata, folder_path, 
                    processed_count, failed_count, total_cost, index_type, index_params)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    index_id, image_set_id, user_id, index_data_b64,
                    json.dumps(clean_metadata), folder_path, processed_count, 
                    failed_count, float(total_cost), index_type, json.dumps(clean_index_params)
                ))
                
                # Store individual indexed images with clean metadata
                for img_meta in clean_metadata:
                    cur.execute("""
                        INSERT INTO indexed_images 
                        (image_set_id, image_path, image_name, image_hash, 
                        image_metadata, processing_status, confidence_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (
                        image_set_id,
                        str(img_meta['image_path']),
                        str(img_meta['filename']),
                        str(img_meta['file_hash']),
                        json.dumps(img_meta),
                        'processed',
                        float(img_meta.get('extraction_info', {}).get('confidence', 1.0))
                    ))
                
                # Update image set status
                cur.execute("""
                    UPDATE image_sets 
                    SET status = 'ready', 
                        progress = 100,
                        indexed_images_count = %s,
                        total_images = %s,
                        updated_at = NOW()
                WHERE id = %s
                """, (processed_count, processed_count + failed_count, image_set_id))
                
            conn.commit()
            self.logger.info(f"Successfully stored {index_type} index with ID: {index_id}")
            return index_id
            
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database storage failed: {e}")
            raise e
        finally:
            conn.close()

    def get_index_info(self, image_set_id: int) -> Optional[Dict[str, Any]]:
        """Get detailed information about a FAISS index"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM faiss_indexes_b64 
                    WHERE image_set_id = %s
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (image_set_id,))
                
                result = cur.fetchone()
                if not result:
                    return None
                
                return {
                    'index_id': result['id'],
                    'index_type': result['index_type'],
                    'processed_count': result['processed_count'],
                    'failed_count': result['failed_count'],
                    'total_cost': float(result['total_cost']),
                    'folder_path': result['folder_path'],
                    'created_at': result['created_at'],
                    'updated_at': result['updated_at'],
                    'index_params': result['index_params']
                }
            
        except Exception as e:
            self.logger.error(f"Error getting index info: {e}")
            return None
        finally:
            conn.close()

    def get_index_statistics(self, image_set_id: int) -> Dict[str, Any]:
        """Get statistical information about the index"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Get basic stats
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_images,
                        AVG(confidence_score) as avg_confidence,
                        MIN(confidence_score) as min_confidence,
                        MAX(confidence_score) as max_confidence
                    FROM indexed_images 
                    WHERE image_set_id = %s AND processing_status = 'processed'
                """, (image_set_id,))
                
                stats = cur.fetchone()
                
                # Get processing mode distribution
                cur.execute("""
                    SELECT 
                        image_metadata->>'extraction_info'->>'processing_mode' as mode,
                        COUNT(*) as count
                    FROM indexed_images 
                    WHERE image_set_id = %s
                    GROUP BY image_metadata->>'extraction_info'->>'processing_mode'
                """, (image_set_id,))
                
                mode_stats = cur.fetchall()
                
                return {
                    'total_images': int(stats['total_images']) if stats['total_images'] else 0,
                    'avg_confidence': float(stats['avg_confidence']) if stats['avg_confidence'] else 0.0,
                    'min_confidence': float(stats['min_confidence']) if stats['min_confidence'] else 0.0,
                    'max_confidence': float(stats['max_confidence']) if stats['max_confidence'] else 0.0,
                    'processing_modes': {row['mode']: int(row['count']) for row in mode_stats if row['mode']}
                }
            
        except Exception as e:
            self.logger.error(f"Error getting index statistics: {e}")
            return {}
        finally:
            conn.close()