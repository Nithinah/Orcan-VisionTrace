# app/faiss_service.py - Fixed version with base64 encoding to avoid BYTEA corruption
import os
import numpy as np
import faiss
import json
from PIL import Image
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import Binary
from typing import List, Tuple, Optional, Dict, Any
import uuid
import logging
from datetime import datetime
import hashlib
import base64

# Fix for OMP error
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

class FaceIndexingService:
    def __init__(self, db_config: dict):
        self.db_config = db_config
        self.resnet = None
        self.mtcnn = None
        self.logger = logging.getLogger(__name__)
        
        # FAISS parameters for scalability
        self.dimension = 512  # FaceNet embedding dimension
        self.n_list = 1000   # Number of clusters for IndexIVFFlat
        self.n_probe = 10    # Number of clusters to search
        
        self._init_models()
    
    def _init_models(self):
        """Initialize FaceNet models"""
        try:
            device = torch.device('cpu')
            
            self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(device)
            self.mtcnn = MTCNN(
                image_size=160, 
                margin=0, 
                select_largest=True, 
                post_process=True,
                device=device
            )
            self.logger.info("FaceNet models loaded successfully on CPU")
        except Exception as e:
            self.logger.error(f"Failed to load FaceNet models: {e}")
            raise
    
    def get_db_connection(self):
        """Get database connection"""
        return psycopg2.connect(**self.db_config)
    
    def img_to_embedding(self, face_tensor):
        """Convert face tensor to normalized embedding"""
        if face_tensor is None:
            return None
        
        try:
            if isinstance(face_tensor, torch.Tensor):
                if face_tensor.ndim == 3:
                    face_tensor = face_tensor.unsqueeze(0)
                face_tensor = face_tensor.to('cpu')
            
            with torch.no_grad():
                emb = self.resnet(face_tensor).squeeze(0)
                emb = emb / emb.norm()
                return emb.numpy().astype('float32')
        except Exception as e:
            self.logger.error(f"Error converting to embedding: {e}")
            return None
    
    def extract_face_embedding_from_image(self, image_path: str) -> Optional[np.ndarray]:
        """Extract face embedding from image file"""
        try:
            img = Image.open(image_path).convert("RGB")
            face_cropped_tensor = self.mtcnn(img)
            
            if face_cropped_tensor is None:
                self.logger.warning(f"No face detected in {image_path}")
                return None
            
            embedding = self.img_to_embedding(face_cropped_tensor)
            return embedding
            
        except Exception as e:
            self.logger.error(f"Error extracting face embedding from {image_path}: {e}")
            return None
    
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
    
    def _create_scalable_index(self, embeddings_array: np.ndarray):
        """Create FAISS index with enhanced validation and numpy serialization support"""
        try:
            dataset_size = embeddings_array.shape[0]
            
            # Validate input data
            if embeddings_array.dtype != np.float32:
                embeddings_array = embeddings_array.astype('float32')
            
            if not np.isfinite(embeddings_array).all():
                self.logger.error("Input contains NaN or infinite values")
                raise ValueError("Invalid embedding data")
            
            # Ensure proper normalization
            norms = np.linalg.norm(embeddings_array, axis=1)
            if np.any(norms == 0):
                self.logger.error("Zero-norm embeddings detected")
                raise ValueError("Zero-norm embeddings found")
            
            # Always use IndexFlatL2 for reliability (avoiding IVF complexity for now)
            self.logger.info(f"Creating IndexFlatL2 for {dataset_size} vectors")
            index = faiss.IndexFlatL2(self.dimension)
            
            # Add vectors
            index.add(embeddings_array)
            
            # Validate the index
            if index.ntotal != dataset_size:
                raise ValueError(f"Index size mismatch: expected {dataset_size}, got {index.ntotal}")
            
            # Test search functionality
            query = embeddings_array[0:1]
            distances, indices = index.search(query, min(3, dataset_size))
            
            if indices[0][0] != 0:
                self.logger.warning("Index search test gave unexpected results")
            
            self.logger.info(f"Index created and validated: {index.ntotal} vectors")
            return index
            
        except Exception as e:
            self.logger.error(f"Error creating FAISS index: {e}")
            raise
    
    def process_folder_for_indexing(self, folder_path: str, image_set_id: int, 
                                   user_id: int) -> Dict[str, Any]:
        """Process entire folder and create FAISS index"""
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
            embeddings = []
            metadata = []
            processed_count = 0
            failed_count = 0
            
            self.logger.info(f"Processing {image_count} images...")
            
            for i, image_path in enumerate(image_files):
                try:
                    embedding = self.extract_face_embedding_from_image(image_path)
                    
                    if embedding is None:
                        self.logger.warning(f"Failed to extract face from {image_path}")
                        failed_count += 1
                        continue
                    
                    embeddings.append(embedding)
                    
                    relative_path = os.path.relpath(image_path, folder_path)
                    file_hash = self._get_file_hash(image_path)
                    
                    metadata.append({
                        'image_path': image_path,
                        'filename': os.path.basename(image_path),
                        'relative_path': relative_path,
                        'index_in_faiss': len(embeddings) - 1,
                        'file_hash': file_hash,
                        'processed_at': datetime.utcnow().isoformat()
                    })
                    processed_count += 1
                    
                    if processed_count % 10 == 0:
                        self.logger.info(f"Processed {processed_count}/{image_count} images")
                        self._update_progress(image_set_id, int((processed_count / image_count) * 100))
                
                except Exception as e:
                    self.logger.error(f"Error processing {image_path}: {e}")
                    failed_count += 1
                    continue
            
            if not embeddings:
                return {
                    'success': False,
                    'message': 'No valid face embeddings extracted',
                    'image_count': image_count,
                    'processed_count': 0,
                    'failed_count': failed_count,
                    'cost': cost
                }
            
            # Create and validate FAISS index
            embeddings_array = np.array(embeddings).astype('float32')
            index = self._create_scalable_index(embeddings_array)
            
            # Enhanced serialization with numpy conversion for compatibility
            try:
                # Method 1: Direct FAISS serialization
                index_data_raw = faiss.serialize_index(index)
                self.logger.info(f"Raw serialized index to {len(index_data_raw)} bytes")
                
                # Method 2: Convert to numpy array for better compatibility
                index_data_np = np.frombuffer(index_data_raw, dtype=np.uint8)
                self.logger.info(f"Converted to numpy array: {index_data_np.shape}")
                
                # Convert back to bytes for storage
                index_data = index_data_np.tobytes()
                self.logger.info(f"Final serialized index: {len(index_data)} bytes")
                
                # CRITICAL: Validate serialization with both methods
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
                raise ValueError(f"Index serialization failed: {e}")
            
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
                index_type="IndexFlatL2",
                n_list=0
            )
            
            self._update_progress(image_set_id, 100)
            
            return {
                'success': True,
                'message': f'Successfully indexed {processed_count} images using IndexFlatL2',
                'index_id': index_id,
                'image_count': image_count,
                'processed_count': processed_count,
                'failed_count': failed_count,
                'cost': cost
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
                          failed_count: int, total_cost: float, index_type: str = "IndexFlatL2",
                          n_list: int = 0) -> str:
        """Store FAISS index using numpy array serialization for better compatibility"""
        
        # Pre-storage validation with enhanced error handling
        try:
            # Try multiple deserialization methods
            test_index = None
            
            # Method 1: Direct bytes
            try:
                test_index = faiss.deserialize_index(index_data)
                self.logger.info(f"Pre-storage validation (direct) PASSED: {test_index.ntotal} vectors")
            except Exception as e1:
                self.logger.warning(f"Direct deserialization failed: {e1}")
                
                # Method 2: Via numpy array
                try:
                    index_data_np = np.frombuffer(index_data, dtype=np.uint8)
                    test_index = faiss.deserialize_index(index_data_np)
                    self.logger.info(f"Pre-storage validation (numpy) PASSED: {test_index.ntotal} vectors")
                except Exception as e2:
                    self.logger.error(f"Both pre-storage validation methods failed: direct={e1}, numpy={e2}")
                    raise ValueError(f"Invalid FAISS index data before storage: {e2}")
                    
        except Exception as e:
            self.logger.error(f"Pre-storage validation FAILED: {e}")
            raise ValueError(f"Invalid FAISS index data before storage: {e}")
        
        # Store as numpy array serialized to base64 for maximum compatibility
        try:
            index_data_np = np.frombuffer(index_data, dtype=np.uint8)
            index_data_np_bytes = index_data_np.tobytes()
            index_data_b64 = base64.b64encode(index_data_np_bytes).decode('utf-8')
            self.logger.info(f"Encoded index as base64 (numpy method): {len(index_data_b64)} characters")
        except Exception as e:
            # Fallback to direct base64 encoding
            index_data_b64 = base64.b64encode(index_data).decode('utf-8')
            self.logger.info(f"Encoded index as base64 (direct method): {len(index_data_b64)} characters")
        
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
                        index_type TEXT DEFAULT 'IndexFlatL2',
                        n_list INTEGER DEFAULT 0,
                        n_probe INTEGER DEFAULT 10,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    );
                """)
                
                index_id = str(uuid.uuid4())
                cur.execute("""
                    INSERT INTO faiss_indexes_b64 
                    (id, image_set_id, user_id, index_data_b64, image_metadata, folder_path, 
                     processed_count, failed_count, total_cost, index_type, n_list, n_probe)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    index_id, image_set_id, user_id, index_data_b64,
                    json.dumps(metadata), folder_path, processed_count, 
                    failed_count, total_cost, index_type, n_list, self.n_probe
                ))
                
                # Store individual indexed images
                for img_meta in metadata:
                    cur.execute("""
                        INSERT INTO indexed_images 
                        (image_set_id, image_path, image_name, image_hash, 
                         image_metadata, processing_status, confidence_score)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        image_set_id,
                        img_meta['image_path'],
                        img_meta['filename'],
                        img_meta['file_hash'],
                        json.dumps(img_meta),
                        'processed',
                        1.0
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
            
            # Post-storage validation with multiple methods
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT index_data_b64 FROM faiss_indexes_b64 WHERE id = %s", (index_id,))
                    stored_result = cur.fetchone()
                    if stored_result:
                        stored_b64 = stored_result[0]
                        stored_data = base64.b64decode(stored_b64)
                        
                        # Try multiple deserialization approaches
                        validation_success = False
                        
                        # Method 1: Direct bytes
                        try:
                            stored_index = faiss.deserialize_index(stored_data)
                            self.logger.info(f"Post-storage validation (direct) PASSED: {stored_index.ntotal} vectors")
                            validation_success = True
                        except Exception as e1:
                            self.logger.warning(f"Post-storage direct validation failed: {e1}")
                            
                            # Method 2: Via numpy
                            try:
                                stored_data_np = np.frombuffer(stored_data, dtype=np.uint8)
                                stored_index = faiss.deserialize_index(stored_data_np)
                                self.logger.info(f"Post-storage validation (numpy) PASSED: {stored_index.ntotal} vectors")
                                validation_success = True
                            except Exception as e2:
                                self.logger.error(f"Post-storage validation failed: direct={e1}, numpy={e2}")
                        
                        if not validation_success:
                            self.logger.error("Post-storage validation failed with all methods")
                    else:
                        raise ValueError("Failed to retrieve stored index")
            except Exception as e:
                self.logger.error(f"Post-storage validation error: {e}")
                # Don't raise here, as the index might still work
            
            return index_id
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def search_similar_faces(self, query_image_path: str, image_set_ids: List[int], 
                            top_k: int = 10, similarity_threshold: float = 0.6) -> Dict[str, Any]:
        """Search for similar faces - Enhanced version with base64 decoding"""
        try:
            query_embedding = self.extract_face_embedding_from_image(query_image_path)
            
            if query_embedding is None:
                return {
                    'success': False,
                    'message': 'No face detected in query image',
                    'results': []
                }
            
            all_results = []
            
            conn = self.get_db_connection()
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    for image_set_id in image_set_ids:
                        cur.execute("""
                            SELECT index_data_b64, image_metadata, folder_path, 
                                   index_type, n_list, n_probe
                            FROM faiss_indexes_b64 
                            WHERE image_set_id = %s
                            ORDER BY created_at DESC 
                            LIMIT 1
                        """, (image_set_id,))
                        
                        result = cur.fetchone()
                        if not result:
                            self.logger.warning(f"No FAISS index found for image set {image_set_id}")
                            continue
                        
                        # Enhanced data handling with multiple deserialization attempts
                        index_data_raw = result['index_data_b64']
                        
                        try:
                            # Decode from base64
                            index_data_bytes = base64.b64decode(index_data_raw)
                            self.logger.info(f"Decoded base64 to {len(index_data_bytes)} bytes")
                            
                            # Try multiple deserialization methods
                            index = None
                            
                            # Method 1: Direct bytes deserialization
                            try:
                                index = faiss.deserialize_index(index_data_bytes)
                                self.logger.info(f"Successfully deserialized FAISS index (direct) with {index.ntotal} vectors")
                            except Exception as e1:
                                self.logger.warning(f"Direct deserialization failed: {e1}")
                                
                                # Method 2: Via numpy array (recommended by FAISS docs)
                                try:
                                    index_data_np = np.frombuffer(index_data_bytes, dtype=np.uint8)
                                    self.logger.info(f"Converted to numpy array: {index_data_np.shape}, dtype: {index_data_np.dtype}")
                                    
                                    index = faiss.deserialize_index(index_data_np)
                                    self.logger.info(f"Successfully deserialized FAISS index (numpy) with {index.ntotal} vectors")
                                except Exception as e2:
                                    self.logger.error(f"Numpy deserialization also failed: {e2}")
                                    
                                    # Method 3: Try creating fresh numpy array
                                    try:
                                        index_data_fresh = np.array(list(index_data_bytes), dtype=np.uint8)
                                        index = faiss.deserialize_index(index_data_fresh)
                                        self.logger.info(f"Successfully deserialized FAISS index (fresh numpy) with {index.ntotal} vectors")
                                    except Exception as e3:
                                        self.logger.error(f"All deserialization methods failed: direct={e1}, numpy={e2}, fresh={e3}")
                                        continue
                            
                            if index is None:
                                self.logger.error("Failed to deserialize index with all methods")
                                continue
                                
                        except Exception as e:
                            self.logger.error(f"Base64 decoding failed: {e}")
                            continue
                        
                        image_metadata = result['image_metadata']
                        
                        # Perform search
                        query_vector = query_embedding.reshape(1, -1).astype('float32')
                        distances, indices = index.search(query_vector, min(top_k, index.ntotal))
                        
                        # Process results
                        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                            if idx == -1:
                                break
                            
                            cosine_similarity = max(0, 1 - (distance / 2.0))
                            
                            if cosine_similarity >= similarity_threshold:
                                if idx < len(image_metadata):
                                    result_metadata = image_metadata[idx]
                                    all_results.append({
                                        'image_set_id': image_set_id,
                                        'similarity_score': float(cosine_similarity),
                                        'image_path': result_metadata['image_path'],
                                        'filename': result_metadata['filename'],
                                        'relative_path': result_metadata['relative_path'],
                                        'rank': i + 1,
                                        'distance': float(distance),
                                        'index_type': result.get('index_type', 'IndexFlatL2')
                                    })
                
                all_results.sort(key=lambda x: x['similarity_score'], reverse=True)
                
                return {
                    'success': True,
                    'message': f'Found {len(all_results)} matches',
                    'results': all_results[:top_k]
                }
                
            finally:
                conn.close()
                
        except Exception as e:
            self.logger.error(f"Error in search_similar_faces: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'message': f'Search failed: {str(e)}',
                'results': []
            }
    
    def get_index_info(self, image_set_id: int) -> Optional[Dict]:
        """Get information about the FAISS index for an image set"""
        conn = self.get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, processed_count, failed_count, total_cost, 
                           folder_path, index_type, n_list, n_probe, created_at
                    FROM faiss_indexes_b64 
                    WHERE image_set_id = %s
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (image_set_id,))
                
                result = cur.fetchone()
                return dict(result) if result else None
                
        except Exception as e:
            self.logger.error(f"Error getting index info: {e}")
            return None
        finally:
            conn.close()