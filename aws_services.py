# app/aws_services.py - Complete Enhanced S3 and Rekognition services with Auto-detect Region
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import List, Tuple, Optional, Dict, Any
import io
import json
import numpy as np
from PIL import Image
import base64
import asyncio

class S3Service:
    def __init__(self):
        pass
    
    def get_s3_client(self, access_key: str, secret_key: str, region: str = None):
        """Get S3 client with optional region"""
        if region:
            return boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
        else:
            # For region detection, don't specify region
            return boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key
            )
    
    async def detect_bucket_region(self, access_key: str, secret_key: str, bucket_name: str) -> Tuple[bool, str]:
        """Auto-detect the region of an S3 bucket"""
        try:
            # Use a minimal S3 client without region to get bucket location
            s3_client = self.get_s3_client(access_key, secret_key)
            
            response = s3_client.get_bucket_location(Bucket=bucket_name)
            region = response.get('LocationConstraint')
            
            # AWS returns None for us-east-1, empty string for some cases
            if region is None or region == '':
                region = 'us-east-1'
            
            print(f"Auto-detected bucket region: {region}")
            return True, region
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False, "Bucket not found"
            elif error_code == '403':
                return False, "Access denied - check credentials"
            else:
                return False, f"AWS Error: {e.response['Error']['Message']}"
        except Exception as e:
            return False, f"Region detection failed: {str(e)}"
    
    async def verify_s3_connection(self, access_key: str, secret_key: str, bucket_name: str, folder_path: str = "", region: str = None) -> Tuple[bool, str]:
        """Verify S3 connection and bucket access"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            # Test bucket access
            s3_client.head_bucket(Bucket=bucket_name)
            
            # Test list objects (with folder path if provided)
            prefix = folder_path.strip('/') + '/' if folder_path else ''
            response = s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=1
            )
            
            return True, "Connection successful"
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                return False, "Bucket not found"
            elif error_code == '403':
                return False, "Access denied - check credentials and permissions"
            else:
                return False, f"AWS Error: {e.response['Error']['Message']}"
        except NoCredentialsError:
            return False, "Invalid AWS credentials"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
    
    async def count_images(self, access_key: str, secret_key: str, bucket_name: str, folder_path: str = "", region: str = None) -> int:
        """Count images in S3 bucket/folder - ENHANCED VERSION"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            prefix = folder_path.strip('/') + '/' if folder_path else ''
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
            
            count = 0
            paginator = s3_client.get_paginator('list_objects_v2')
            
            print(f"Counting images in bucket: {bucket_name}, prefix: '{prefix}', region: {region}")
            
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    print(f"Found {len(page['Contents'])} objects in this page")
                    for obj in page['Contents']:
                        key = obj['Key'].lower()
                        # Skip folders/directories
                        if key.endswith('/'):
                            continue
                        # Check if the key ends with any of the image extensions
                        if any(key.endswith(ext) for ext in image_extensions):
                            count += 1
                            if count <= 10:  # Log first 10 images found
                                print(f"Found image: {obj['Key']}")
                        else:
                            if count <= 5:  # Log first 5 non-images for debugging
                                print(f"Skipped non-image: {obj['Key']}")
                else:
                    print("No 'Contents' in this page")
            
            print(f"Total images found: {count}")
            return count
            
        except Exception as e:
            print(f"Error counting images: {e}")
            return 0
    
    async def list_images(self, access_key: str, secret_key: str, bucket_name: str, folder_path: str = "", region: str = None) -> List[str]:
        """List all image files in S3 bucket/folder - ENHANCED VERSION"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            prefix = folder_path.strip('/') + '/' if folder_path else ''
            image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
            
            images = []
            paginator = s3_client.get_paginator('list_objects_v2')
            
            print(f"Listing images in bucket: {bucket_name}, prefix: '{prefix}', region: {region}")
            
            for page in paginator.paginate(Bucket=bucket_name, Prefix=prefix):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        key = obj['Key']
                        key_lower = key.lower()
                        
                        # Skip folders/directories
                        if key.endswith('/'):
                            continue
                            
                        # Check if the key ends with any of the image extensions
                        if any(key_lower.endswith(ext) for ext in image_extensions):
                            images.append(key)  # Use original key, not lowercase
                            
                            if len(images) <= 10:  # Log first 10 images
                                print(f"Listed image: {key}")
            
            print(f"Total images listed: {len(images)}")
            return images
            
        except Exception as e:
            print(f"Error listing images: {e}")
            return []
    
    async def get_image(self, access_key: str, secret_key: str, bucket_name: str, object_key: str, region: str = None) -> bytes:
        """Get image data from S3"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
            return response['Body'].read()
            
        except Exception as e:
            print(f"Error getting image {object_key}: {e}")
            return b''
    
    async def get_presigned_url(self, access_key: str, secret_key: str, bucket_name: str, object_key: str, region: str = None, expiration: int = 3600) -> str:
        """Generate a presigned URL for S3 object access"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            response = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': object_key},
                ExpiresIn=expiration
            )
            
            return response
            
        except Exception as e:
            print(f"Error generating presigned URL for {object_key}: {e}")
            return ""
    
    async def batch_get_images(self, access_key: str, secret_key: str, bucket_name: str, object_keys: List[str], region: str = None) -> Dict[str, bytes]:
        """Get multiple images from S3 in batch"""
        try:
            s3_client = self.get_s3_client(access_key, secret_key, region)
            
            results = {}
            for key in object_keys:
                try:
                    response = s3_client.get_object(Bucket=bucket_name, Key=key)
                    results[key] = response['Body'].read()
                except Exception as e:
                    print(f"Error getting image {key}: {e}")
                    results[key] = b''
            
            return results
            
        except Exception as e:
            print(f"Error in batch get images: {e}")
            return {}


class RekognitionService:
    def __init__(self):
        self.rekognition_client = None
    
    def get_rekognition_client(self, access_key: str = None, secret_key: str = None, region: str = "us-east-1"):
        """Get Rekognition client with optional custom credentials and region"""
        if access_key and secret_key:
            return boto3.client(
                'rekognition',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
        else:
            # Use default credentials from environment/IAM role
            return boto3.client('rekognition', region_name=region)
    
    async def create_collection(self, collection_id: str, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> bool:
        """Create a new Rekognition collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            rekognition.create_collection(CollectionId=collection_id)
            print(f"Created Rekognition collection: {collection_id} in region: {region}")
            return True
            
        except rekognition.exceptions.ResourceAlreadyExistsException:
            print(f"Collection already exists: {collection_id}")
            return True
        except Exception as e:
            print(f"Error creating collection {collection_id}: {e}")
            return False
    
    async def delete_collection(self, collection_id: str, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> bool:
        """Delete a Rekognition collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            rekognition.delete_collection(CollectionId=collection_id)
            print(f"Deleted Rekognition collection: {collection_id}")
            return True
            
        except Exception as e:
            print(f"Error deleting collection {collection_id}: {e}")
            return False
    
    async def index_face_from_s3(self, collection_id: str, bucket_name: str, s3_key: str, 
                                external_image_id: str = None, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Index a face directly from S3 into Rekognition collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            if not external_image_id:
                external_image_id = s3_key.split('/')[-1].split('.')[0]
            
            response = rekognition.index_faces(
                CollectionId=collection_id,
                Image={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': s3_key
                    }
                },
                ExternalImageId=external_image_id,
                DetectionAttributes=['ALL'],
                MaxFaces=10,
                QualityFilter='AUTO'
            )
            
            return {
                'success': True,
                'face_records': response.get('FaceRecords', []),
                'unindexed_faces': response.get('UnindexedFaces', []),
                'external_image_id': external_image_id
            }
            
        except Exception as e:
            print(f"Error indexing face from S3 {s3_key}: {e}")
            return {
                'success': False,
                'error': str(e),
                'external_image_id': external_image_id
            }
    
    async def index_face_from_bytes(self, collection_id: str, image_data: bytes, 
                                   external_image_id: str, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Index a face from image bytes into Rekognition collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            response = rekognition.index_faces(
                CollectionId=collection_id,
                Image={'Bytes': image_data},
                ExternalImageId=external_image_id,
                DetectionAttributes=['ALL'],
                MaxFaces=10,
                QualityFilter='AUTO'
            )
            
            return {
                'success': True,
                'face_records': response.get('FaceRecords', []),
                'unindexed_faces': response.get('UnindexedFaces', []),
                'external_image_id': external_image_id
            }
            
        except Exception as e:
            print(f"Error indexing face from bytes: {e}")
            return {
                'success': False,
                'error': str(e),
                'external_image_id': external_image_id
            }
    
    async def search_faces_by_image(self, collection_id: str, image_data: bytes, 
                                   max_faces: int = 25, threshold: float = 60.0, 
                                   access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Search for faces in collection using query image"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            response = rekognition.search_faces_by_image(
                CollectionId=collection_id,
                Image={'Bytes': image_data},
                MaxFaces=max_faces,
                FaceMatchThreshold=threshold
            )
            
            matches = []
            for face_match in response.get('FaceMatches', []):
                matches.append({
                    'similarity': face_match['Similarity'],
                    'face_id': face_match['Face']['FaceId'],
                    'external_image_id': face_match['Face']['ExternalImageId'],
                    'confidence': face_match['Face']['Confidence'],
                    'bounding_box': face_match['Face']['BoundingBox']
                })
            
            return {
                'success': True,
                'matches': matches,
                'searched_face': response.get('SearchedFaceBoundingBox'),
                'searched_face_confidence': response.get('SearchedFaceConfidence'),
                'total_matches': len(matches)
            }
            
        except Exception as e:
            print(f"Error searching faces in collection {collection_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    async def search_faces_by_s3_image(self, collection_id: str, bucket_name: str, s3_key: str,
                                      max_faces: int = 25, threshold: float = 60.0,
                                      access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Search for faces in collection using S3 image"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            response = rekognition.search_faces_by_image(
                CollectionId=collection_id,
                Image={
                    'S3Object': {
                        'Bucket': bucket_name,
                        'Name': s3_key
                    }
                },
                MaxFaces=max_faces,
                FaceMatchThreshold=threshold
            )
            
            matches = []
            for face_match in response.get('FaceMatches', []):
                matches.append({
                    'similarity': face_match['Similarity'],
                    'face_id': face_match['Face']['FaceId'],
                    'external_image_id': face_match['Face']['ExternalImageId'],
                    'confidence': face_match['Face']['Confidence'],
                    'bounding_box': face_match['Face']['BoundingBox']
                })
            
            return {
                'success': True,
                'matches': matches,
                'searched_face': response.get('SearchedFaceBoundingBox'),
                'searched_face_confidence': response.get('SearchedFaceConfidence'),
                'total_matches': len(matches)
            }
            
        except Exception as e:
            print(f"Error searching faces with S3 image {s3_key}: {e}")
            return {
                'success': False,
                'error': str(e),
                'matches': []
            }
    
    async def list_faces_in_collection(self, collection_id: str, max_results: int = 1000,
                                      access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """List all faces in a collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            faces = []
            next_token = None
            
            while True:
                params = {
                    'CollectionId': collection_id,
                    'MaxResults': min(max_results - len(faces), 4096)  # AWS limit is 4096
                }
                
                if next_token:
                    params['NextToken'] = next_token
                
                response = rekognition.list_faces(**params)
                
                faces.extend(response.get('Faces', []))
                next_token = response.get('NextToken')
                
                if not next_token or len(faces) >= max_results:
                    break
            
            return {
                'success': True,
                'faces': faces,
                'total_faces': len(faces)
            }
            
        except Exception as e:
            print(f"Error listing faces in collection {collection_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'faces': []
            }
    
    async def delete_faces_from_collection(self, collection_id: str, face_ids: List[str],
                                         access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Delete specific faces from a collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            # AWS allows deleting up to 4096 faces at once
            deleted_faces = []
            
            for i in range(0, len(face_ids), 4096):
                batch = face_ids[i:i + 4096]
                
                response = rekognition.delete_faces(
                    CollectionId=collection_id,
                    FaceIds=batch
                )
                
                deleted_faces.extend(response.get('DeletedFaces', []))
            
            return {
                'success': True,
                'deleted_faces': deleted_faces,
                'total_deleted': len(deleted_faces)
            }
            
        except Exception as e:
            print(f"Error deleting faces from collection {collection_id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'deleted_faces': []
            }
    
    async def get_collection_info(self, collection_id: str, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Get information about a collection"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            response = rekognition.describe_collection(CollectionId=collection_id)
            
            return {
                'success': True,
                'collection_arn': response.get('CollectionARN'),
                'face_count': response.get('FaceCount'),
                'face_model_version': response.get('FaceModelVersion'),
                'creation_timestamp': response.get('CreationTimestamp')
            }
            
        except Exception as e:
            print(f"Error getting collection info for {collection_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def extract_features(self, image_data: bytes, access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Extract comprehensive features from image using AWS Rekognition"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            # Detect faces
            faces_response = rekognition.detect_faces(
                Image={'Bytes': image_data},
                Attributes=['ALL']
            )
            
            # Detect labels (objects, scenes, activities)
            labels_response = rekognition.detect_labels(
                Image={'Bytes': image_data},
                MaxLabels=50,
                MinConfidence=70
            )
            
            # Detect text
            text_response = rekognition.detect_text(
                Image={'Bytes': image_data}
            )
            
            # Extract moderation labels
            moderation_response = rekognition.detect_moderation_labels(
                Image={'Bytes': image_data},
                MinConfidence=60
            )
            
            # Compile features
            features = {
                'faces': [
                    {
                        'bounding_box': face['BoundingBox'],
                        'confidence': face['Confidence'],
                        'age_range': face.get('AgeRange', {}),
                        'gender': face.get('Gender', {}),
                        'emotions': face.get('Emotions', []),
                        'landmarks': face.get('Landmarks', []),
                        'pose': face.get('Pose', {}),
                        'quality': face.get('Quality', {}),
                        'smile': face.get('Smile', {}),
                        'eyeglasses': face.get('Eyeglasses', {}),
                        'sunglasses': face.get('Sunglasses', {}),
                        'beard': face.get('Beard', {}),
                        'mustache': face.get('Mustache', {}),
                        'eyes_open': face.get('EyesOpen', {}),
                        'mouth_open': face.get('MouthOpen', {})
                    }
                    for face in faces_response.get('FaceDetails', [])
                ],
                'labels': [
                    {
                        'name': label['Name'],
                        'confidence': label['Confidence'],
                        'instances': label.get('Instances', []),
                        'categories': label.get('Categories', []),
                        'parents': label.get('Parents', [])
                    }
                    for label in labels_response.get('Labels', [])
                ],
                'text': [
                    {
                        'detected_text': text['DetectedText'],
                        'confidence': text['Confidence'],
                        'type': text['Type'],
                        'id': text.get('Id'),
                        'parent_id': text.get('ParentId'),
                        'bounding_box': text.get('Geometry', {}).get('BoundingBox', {}),
                        'polygon': text.get('Geometry', {}).get('Polygon', [])
                    }
                    for text in text_response.get('TextDetections', [])
                ],
                'moderation': [
                    {
                        'name': mod['Name'],
                        'confidence': mod['Confidence'],
                        'parent_name': mod.get('ParentName', '')
                    }
                    for mod in moderation_response.get('ModerationLabels', [])
                ]
            }
            
            return features
            
        except Exception as e:
            print(f"Error extracting features: {e}")
            return {
                'faces': [],
                'labels': [],
                'text': [],
                'moderation': [],
                'error': str(e)
            }
    
    async def compare_features(self, features1: Dict[str, Any], features2: Dict[str, Any]) -> float:
        """Compare two feature sets and return similarity score (0-100)"""
        try:
            similarity_scores = []
            
            # Compare labels with enhanced weighting
            labels1 = {label['name'].lower(): label['confidence'] for label in features1.get('labels', [])}
            labels2 = {label['name'].lower(): label['confidence'] for label in features2.get('labels', [])}
            
            common_labels = set(labels1.keys()) & set(labels2.keys())
            if common_labels:
                # Calculate label similarity based on common labels and their confidence
                label_overlap = len(common_labels) / max(len(labels1), len(labels2))
                weighted_confidence = sum(
                    min(labels1[label], labels2[label]) for label in common_labels
                ) / len(common_labels)
                
                label_similarity = (label_overlap * 50) + (weighted_confidence * 0.5)
                similarity_scores.append(('labels', label_similarity, 0.4))  # 40% weight
            
            # Compare face count and characteristics
            faces1 = features1.get('faces', [])
            faces2 = features2.get('faces', [])
            
            if faces1 or faces2:
                face_count_similarity = 100 - abs(len(faces1) - len(faces2)) * 25
                face_count_similarity = max(0, face_count_similarity)
                
                # Compare face attributes if both have faces
                if faces1 and faces2:
                    # Compare age ranges, gender, emotions
                    attr_similarities = []
                    
                    for f1 in faces1[:3]:  # Compare up to 3 faces
                        best_match = 0
                        for f2 in faces2[:3]:
                            face_sim = 0
                            
                            # Age similarity
                            age1 = f1.get('age_range', {})
                            age2 = f2.get('age_range', {})
                            if age1 and age2:
                                age_diff = abs((age1.get('Low', 0) + age1.get('High', 0))/2 - 
                                             (age2.get('Low', 0) + age2.get('High', 0))/2)
                                age_sim = max(0, 100 - age_diff * 2)
                                face_sim += age_sim * 0.3
                            
                            # Gender similarity
                            gender1 = f1.get('gender', {}).get('Value', '')
                            gender2 = f2.get('gender', {}).get('Value', '')
                            if gender1 and gender2:
                                gender_sim = 100 if gender1 == gender2 else 20
                                face_sim += gender_sim * 0.2
                            
                            # Emotion similarity
                            emotions1 = {e['Type']: e['Confidence'] for e in f1.get('emotions', [])}
                            emotions2 = {e['Type']: e['Confidence'] for e in f2.get('emotions', [])}
                            if emotions1 and emotions2:
                                common_emotions = set(emotions1.keys()) & set(emotions2.keys())
                                if common_emotions:
                                    emotion_sim = sum(
                                        min(emotions1[e], emotions2[e]) for e in common_emotions
                                    ) / len(common_emotions)
                                    face_sim += emotion_sim * 0.5
                            
                            best_match = max(best_match, face_sim)
                        
                        attr_similarities.append(best_match)
                    
                    if attr_similarities:
                        avg_face_attr_sim = sum(attr_similarities) / len(attr_similarities)
                        face_similarity = (face_count_similarity + avg_face_attr_sim) / 2
                    else:
                        face_similarity = face_count_similarity
                else:
                    face_similarity = face_count_similarity
                
                similarity_scores.append(('faces', face_similarity, 0.3))  # 30% weight
            
            # Compare text content
            text1 = set(text['detected_text'].lower().strip() for text in features1.get('text', []) 
                        if text.get('type') == 'WORD')
            text2 = set(text['detected_text'].lower().strip() for text in features2.get('text', []) 
                        if text.get('type') == 'WORD')
            
            if text1 or text2:
                if text1 and text2:
                    common_text = text1 & text2
                    text_similarity = (len(common_text) / max(len(text1), len(text2))) * 100
                    similarity_scores.append(('text', text_similarity, 0.2))  # 20% weight
            
            # Compare moderation labels
            mod1 = set(mod['name'].lower() for mod in features1.get('moderation', []))
            mod2 = set(mod['name'].lower() for mod in features2.get('moderation', []))
            
            if mod1 or mod2:
                if mod1 and mod2:
                    common_mod = mod1 & mod2
                    mod_similarity = (len(common_mod) / max(len(mod1), len(mod2))) * 100
                    similarity_scores.append(('moderation', mod_similarity, 0.1))  # 10% weight
            
            # Calculate weighted average
            if similarity_scores:
                total_weight = sum(weight for _, _, weight in similarity_scores)
                if total_weight > 0:
                    final_similarity = sum(score * weight for _, score, weight in similarity_scores) / total_weight
                    return min(99.9, max(0, final_similarity))  # Cap at 99.9%
            
            return 0.0
            
        except Exception as e:
            print(f"Error comparing features: {e}")
            return 0.0
    
    async def compare_faces_direct(self, image1_data: bytes, image2_data: bytes, 
                                  access_key: str = None, secret_key: str = None, region: str = "us-east-1") -> float:
        """Compare faces in two images directly using Rekognition"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            response = rekognition.compare_faces(
                SourceImage={'Bytes': image1_data},
                TargetImage={'Bytes': image2_data},
                SimilarityThreshold=60
            )
            
            if response.get('FaceMatches'):
                # Return highest similarity score
                return max(match['Similarity'] for match in response['FaceMatches'])
            
            return 0.0
            
        except Exception as e:
            print(f"Error comparing faces directly: {e}")
            return 0.0
    
    async def batch_index_faces_from_s3(self, collection_id: str, bucket_name: str, 
                                       s3_keys: List[str], access_key: str = None, 
                                       secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Batch index multiple faces from S3 objects"""
        try:
            rekognition = self.get_rekognition_client(access_key, secret_key, region)
            
            results = []
            errors = []
            
            for s3_key in s3_keys:
                try:
                    external_image_id = s3_key.split('/')[-1].split('.')[0]
                    
                    response = rekognition.index_faces(
                        CollectionId=collection_id,
                        Image={
                            'S3Object': {
                                'Bucket': bucket_name,
                                'Name': s3_key
                            }
                        },
                        ExternalImageId=external_image_id,
                        DetectionAttributes=['ALL'],
                        MaxFaces=10,
                        QualityFilter='AUTO'
                    )
                    
                    results.append({
                        's3_key': s3_key,
                        'external_image_id': external_image_id,
                        'face_records': response.get('FaceRecords', []),
                        'unindexed_faces': response.get('UnindexedFaces', []),
                        'success': True
                    })
                    
                except Exception as e:
                    errors.append({
                        's3_key': s3_key,
                        'error': str(e),
                        'success': False
                    })
            
            return {
                'success': True,
                'results': results,
                'errors': errors,
                'total_processed': len(s3_keys),
                'successful_indexes': len(results),
                'failed_indexes': len(errors)
            }
            
        except Exception as e:
            print(f"Error in batch indexing: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'errors': []
            }
    
    async def get_face_search_analytics(self, collection_id: str, access_key: str = None, 
                                      secret_key: str = None, region: str = "us-east-1") -> Dict[str, Any]:
        """Get analytics about face search performance in a collection"""
        try:
            collection_info = await self.get_collection_info(collection_id, access_key, secret_key, region)
            
            if not collection_info['success']:
                return collection_info
            
            faces_info = await self.list_faces_in_collection(collection_id, max_results=100, 
                                                           access_key=access_key, secret_key=secret_key, region=region)
            
            if not faces_info['success']:
                return faces_info
            
            # Analyze face quality distribution
            quality_scores = []
            confidence_scores = []
            
            for face in faces_info['faces'][:100]:  # Sample first 100 faces
                if 'Quality' in face:
                    quality_scores.append(face['Quality'].get('Brightness', 0))
                    quality_scores.append(face['Quality'].get('Sharpness', 0))
                confidence_scores.append(face.get('Confidence', 0))
            
            analytics = {
                'success': True,
                'collection_id': collection_id,
                'total_faces': collection_info.get('face_count', 0),
                'face_model_version': collection_info.get('face_model_version'),
                'avg_confidence': sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                'avg_quality': sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                'creation_date': collection_info.get('creation_timestamp'),
                'sample_size': len(faces_info['faces'])
            }
            
            return analytics
            
        except Exception as e:
            print(f"Error getting search analytics for {collection_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }