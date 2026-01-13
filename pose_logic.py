from ultralytics import YOLO
import cv2
import numpy as np
import json
import os

# Load model once
model = YOLO("yolov8n-pose.pt")

CONFIG_FILE = "config.json"

def load_config_threshold():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('threshold', 0.95)
        except Exception:
            return 0.95
    return 0.95

def extract_keypoints(image):
    """
    Run YOLO pose on an image (numpy array).
    Returns a list of keypoints (x, y, conf) for the primary person detected.
    """
    results = model(image, verbose=False)
    if not results:
        return None
    
    # Get keypoints for the first detected person
    # results[0].keypoints.data is a tensor of shape (N, 17, 3)
    # We take the first person (index 0)
    if results[0].keypoints is None or len(results[0].keypoints.data) == 0:
        return None
        
    kpts = results[0].keypoints.data[0].cpu().numpy() # Shape (17, 3)
    return kpts

def normalize_keypoints(kpts):
    """
    Normalize keypoints to be invariant to scale and translation.
    kpts: (17, 3) array [x, y, conf]
    """
    # We focus on body keypoints only (ignore head 0-4)
    body_indices = list(range(5, 17))
    points = kpts[body_indices, :2] # (12, 2)
    conf = kpts[body_indices, 2]
    
    # Mask low confidence points (set to 0,0)
    valid_mask = conf > 0.3
    points_valid = points[valid_mask]
    
    if len(points_valid) < 4:
        # Not enough points to normalize properly
        return np.zeros(24) # 12 points * 2
    
    # Calculate center (Midpoint of Shoulders and Hips)
    # Indices in the points array: 0,1 are original 5,6. 6,7 are original 11,12.
    # Check if these specific points are valid
    if valid_mask[0] and valid_mask[1] and valid_mask[6] and valid_mask[7]:
        shoulders = points[[0, 1]]
        hips = points[[6, 7]]
        center = np.mean(np.concatenate((shoulders, hips), axis=0), axis=0)
        torso_len = np.linalg.norm(np.mean(shoulders, axis=0) - np.mean(hips, axis=0))
        scale = torso_len if torso_len > 0.05 else np.linalg.norm(np.max(points_valid, axis=0) - np.min(points_valid, axis=0))
    else:
        # Fallback to bounding box of valid points
        min_coords = np.min(points_valid, axis=0)
        max_coords = np.max(points_valid, axis=0)
        center = (min_coords + max_coords) / 2
        scale = np.linalg.norm(max_coords - min_coords)
    
    if scale == 0: scale = 1.0

    # Normalize all points
    norm_points = (points - center) / scale
    
    # CRITICAL: Zero out points that were invalid so they don't affect similarity incorrectly
    norm_points[~valid_mask] = 0
    
    return norm_points.flatten()

def calculate_similarity(embedding_a, embedding_b):
    """
    Cosine similarity between two normalized vectors.
    """
    if embedding_a is None or embedding_b is None:
        return 0.0
    
    norm_a = np.linalg.norm(embedding_a)
    norm_b = np.linalg.norm(embedding_b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
        
    dot_product = np.dot(embedding_a, embedding_b)
    similarity = dot_product / (norm_a * norm_b)
    return max(0.0, float(similarity))

def get_skeleton_and_embedding(frame):
    """
    Runs model once and returns (annotated_frame, embedding, kpts)
    """
    results = model(frame, verbose=False)
    annotated_frame = frame.copy()
    
    if results and results[0].keypoints and len(results[0].keypoints.data) > 0:
        annotated_frame = results[0].plot()
        kpts = results[0].keypoints.data[0].cpu().numpy()
        embedding = normalize_keypoints(kpts)
        return annotated_frame, embedding, kpts
    
    return annotated_frame, None, None

def check_pose_direct(live_embedding, reference_embeddings, threshold=None):
    """
    Compare a pre-calculated embedding against references.
    """
    if threshold is None:
        threshold = load_config_threshold()
        
    if live_embedding is None or not reference_embeddings:
        return False, 0.0, -1
        
    max_sim = 0.0
    best_match_idx = -1
    for i, ref_emb in enumerate(reference_embeddings):
        sim = calculate_similarity(live_embedding, ref_emb)
        if sim > max_sim:
            max_sim = sim
            best_match_idx = i
            
    is_match = max_sim >= threshold
    return is_match, max_sim, best_match_idx

# Legacy support for check_pose (calls new efficient methods)
def check_pose(frame, reference_embeddings, threshold=None):
    if threshold is None:
        threshold = load_config_threshold()
    ann, emb, _ = get_skeleton_and_embedding(frame)
    is_match, score, idx = check_pose_direct(emb, reference_embeddings, threshold)
    return is_match, score, ann, idx
