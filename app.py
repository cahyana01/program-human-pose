import cv2
import time
import os
import numpy as np
from flask import Flask, render_template, Response, request, jsonify
from werkzeug.utils import secure_filename
import pose_logic
import database

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
database.init_db()

# Global State
state = {
    'current_movement': 'Sikap Siap', # Target for verification
    'detected_movement': 'None',
    'scores': {
        'Sikap Siap': 0.0,
        'Pukulan Dasar': 0.0
    },
    'references': {
        'Sikap Siap': [],
        'Pukulan Dasar': []
    },
    'ref_filenames': {
        'Sikap Siap': [],
        'Pukulan Dasar': []
    },
    'verification': {
        'start_time': None,
        'verified': False,
        'last_status': 'Waiting...',
        'progress': 0
    }
}

# Video Capture Global
camera = None

def load_references_from_db():
    print("Loading references from DB...")
    for mov in ['Sikap Siap', 'Pukulan Dasar']:
        refs = database.get_references(mov)
        embeddings = []
        filenames = []
        for ref in refs:
            path = os.path.join(app.config['UPLOAD_FOLDER'], ref['filepath_orig'])
            if os.path.exists(path):
                img = cv2.imread(path)
                if img is not None:
                    kpts = pose_logic.extract_keypoints(img)
                    if kpts is not None:
                        norm_kpts = pose_logic.normalize_keypoints(kpts)
                        embeddings.append(norm_kpts)
                        filenames.append(ref['filepath_annotated'])
        state['references'][mov] = embeddings
        state['ref_filenames'][mov] = filenames
    print(f"Loaded {len(state['references']['Sikap Siap'])} Sikap Siap, {len(state['references']['Pukulan Dasar'])} Pukulan Dasar")

# Initialize references on startup
load_references_from_db()

def get_camera():
    global camera
    if camera is None:
        camera = cv2.VideoCapture(0)
    return camera

def generate_frames():
    global camera
    
    while True:
        cam = get_camera()
        success, frame = cam.read()
        if not success:
            break
            
        # Resize for performance
        frame = cv2.resize(frame, (640, 480))
        
        # Single inference per frame
        annotated_frame, live_embedding, _ = pose_logic.get_skeleton_and_embedding(frame)
        
        # Multi-movement logic
        max_total_score = 0.0
        detected_mov = "None"
        
        # Check all movements for classification using the same live_embedding
        scores_map = {}
        for mov_name in ['Sikap Siap', 'Pukulan Dasar']:
            refs = state['references'].get(mov_name, [])
            # Use the optimized direct check
            _, score, _ = pose_logic.check_pose_direct(live_embedding, refs, threshold=0.0)
            state['scores'][mov_name] = float(score)
            scores_map[mov_name] = score
            
            if score > max_total_score:
                max_total_score = score
                detected_mov = mov_name

        # Confidence threshold for labeling
        if max_total_score < 0.6: 
            state['detected_movement'] = "Neutral / Unknown"
        else:
            state['detected_movement'] = detected_mov
        
        # Verification Logic (focused on 'current_movement')
        target_mov = state['current_movement']
        target_refs = state['references'].get(target_mov, [])
        target_ref_files = state['ref_filenames'].get(target_mov, [])
        
        # Re-check for target with the same embedding but with threshold and best index
        is_match, score, best_idx = pose_logic.check_pose_direct(live_embedding, target_refs, threshold=None)
        
        # Competitive check: Target must also be the best match
        is_match = is_match and (detected_mov == target_mov)
        
        # 5-second rule logic
        if is_match:
            if state['verification']['start_time'] is None:
                state['verification']['start_time'] = time.time()
                print(f"Match found for {target_mov} ({score:.2f}). Starting timer...")
            
            elapsed = time.time() - state['verification']['start_time']
            state['verification']['progress'] = min(100, (elapsed / 5.0) * 100)
            state['verification']['last_status'] = f"Holding {target_mov}... {elapsed:.1f}s"
            
            if elapsed >= 5.0 and not state['verification']['verified']:
                state['verification']['verified'] = True
                state['verification']['last_status'] = "VERIFIED!"
                # Save to history
                filename = f"verified_{int(time.time())}.jpg"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                cv2.imwrite(filepath, annotated_frame)
                
                # Best match filename
                best_ref = target_ref_files[best_idx] if best_idx != -1 and best_idx < len(target_ref_files) else ""
                database.add_record(target_mov, "Correct", filename, best_ref, float(score))
                print(f"VERIFIED: {target_mov} saved to history")
                
            # Draw Progress Bar and Info on Frame
            cv2.rectangle(annotated_frame, (50, 400), (int(50 + 5.4 * state['verification']['progress']), 430), (0, 255, 0), -1)
            cv2.putText(annotated_frame, f"Match: {score:.2f} ({target_mov})", (50, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
        else:
            state['verification']['start_time'] = None
            state['verification']['progress'] = 0
            state['verification']['verified'] = False
            state['verification']['last_status'] = f"Incorrect Pose (Need {target_mov})"
            cv2.putText(annotated_frame, f"Wait: {target_mov} ({score:.2f})", (50, 450), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

        # Draw Detection Label
        cv2.putText(annotated_frame, f"Detected: {state['detected_movement']}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)

        # Encode
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history_page')
def history_page():
    return render_template('history.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/status')
def get_status():
    return jsonify({
        'movement': state['current_movement'],
        'detected': state['detected_movement'],
        'scores': state['scores'],
        'status': state['verification']['last_status'],
        'progress': state['verification']['progress'],
        'verified': state['verification']['verified'],
        'ref_counts': {
            'Sikap Siap': len(state['references']['Sikap Siap']),
            'Pukulan Dasar': len(state['references']['Pukulan Dasar'])
        }
    })

@app.route('/set_movement', methods=['POST'])
def set_movement():
    data = request.json
    state['current_movement'] = data['movement']
    # Reset verification state
    state['verification'] = {'start_time': None, 'verified': False, 'last_status': 'Waiting...', 'progress': 0}
    return jsonify({'success': True})

@app.route('/upload_references', methods=['POST'])
def upload_references():
    try:
        movement = request.form.get('movement')
        files = request.files.getlist('files')
        
        if not movement:
            return jsonify({'error': 'Movement type missing'}), 400
        if len(files) < 1:
            return jsonify({'error': 'No files uploaded'}), 400
            
        count = 0
        for file in files:
            if file and file.filename:
                filename = secure_filename(f"ref_{int(time.time())}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Process & Annotate
                img = cv2.imread(filepath)
                if img is None: 
                    print(f"Warning: Could not read uploaded image {filename}")
                    continue
                
                # Get skeleton
                annotated_img, _, _ = pose_logic.get_skeleton_and_embedding(img)
                
                annotated_filename = f"annotated_{filename}"
                annotated_path = os.path.join(app.config['UPLOAD_FOLDER'], annotated_filename)
                cv2.imwrite(annotated_path, annotated_img)
                
                # Save to DB
                database.add_reference(movement, filename, annotated_filename)
                count += 1
        
        # Reload references to update state
        load_references_from_db()
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        print(f"Error in upload_references: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/get_references')
def api_get_references():
    movement = request.args.get('movement')
    refs = database.get_references(movement)
    return jsonify(refs)

@app.route('/delete_reference', methods=['POST'])
def delete_reference_route():
    ref_id = request.json.get('id')
    deleted = database.delete_reference(ref_id)
    if deleted:
        # Optimistically remove files (ignore errors)
        try:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], deleted['filepath_orig']))
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], deleted['filepath_annotated']))
        except:
            pass
        # Reload state
        load_references_from_db()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not found'}), 404

@app.route('/verify_image', methods=['POST'])
def verify_image():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file part'}), 400
        file = request.files['file']
        
        movement_type = request.form.get('movement', state['current_movement'])
        
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
            
        filename = secure_filename(f"test_{int(time.time())}_{file.filename}")
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        img = cv2.imread(filepath)
        if img is None:
            return jsonify({'error': 'Failed to read image (invalid format?)'}), 400

        refs = state['references'].get(movement_type, [])
        ref_files = state['ref_filenames'].get(movement_type, [])
        
        # Use efficient logic
        annotated, embedding, _ = pose_logic.get_skeleton_and_embedding(img)
        
        if embedding is None:
            # No person detected
            res_filename = f"no_pose_{int(time.time())}.jpg"
            cv2.imwrite(os.path.join(app.config['UPLOAD_FOLDER'], res_filename), img)
            return jsonify({
                'match': False,
                'score': 0.0,
                'error': 'No person or pose detected in image',
                'image_url': f"/static/uploads/{res_filename}"
            })

        is_match, score, best_idx = pose_logic.check_pose_direct(embedding, refs, threshold=None)
        
        # Save result image
        res_filename = f"result_{int(time.time())}.jpg"
        res_path = os.path.join(app.config['UPLOAD_FOLDER'], res_filename)
        cv2.imwrite(res_path, annotated)
        
        result_text = "Correct" if is_match else "Incorrect"
        best_ref = ref_files[best_idx] if best_idx != -1 and best_idx < len(ref_files) else ""
        
        database.add_record(movement_type, result_text, res_filename, best_ref, float(score))
        
        return jsonify({
            'match': is_match,
            'score': float(score),
            'image_url': f"/static/uploads/{res_filename}",
            'best_ref': f"/static/uploads/{best_ref}" if best_ref else None
        })
    except Exception as e:
        print(f"Error in verify_image: {e}")
        return jsonify({'error': 'Internal server error during processing'}), 500

@app.route('/verify_instant', methods=['POST'])
def verify_instant():
    try:
        cam = get_camera()
        success, frame = cam.read()
        if not success:
            return jsonify({'error': 'Failed to capture frame from camera'}), 500
            
        current_mov = state['current_movement']
        refs = state['references'].get(current_mov, [])
        ref_files = state['ref_filenames'].get(current_mov, [])
        
        # Consistent with live logic
        annotated, embedding, _ = pose_logic.get_skeleton_and_embedding(frame)
        
        if embedding is None:
            return jsonify({'match': False, 'score': 0.0, 'error': 'No person detected'})

        is_match, score, best_idx = pose_logic.check_pose_direct(embedding, refs, threshold=None)
        
        # Save result image
        res_filename = f"instant_{int(time.time())}.jpg"
        res_path = os.path.join(app.config['UPLOAD_FOLDER'], res_filename)
        cv2.imwrite(res_path, annotated)
        
        result_text = "Correct" if is_match else "Incorrect"
        best_ref = ref_files[best_idx] if best_idx != -1 and best_idx < len(ref_files) else ""
        
        database.add_record(current_mov, result_text, res_filename, best_ref, float(score))
        
        return jsonify({
            'match': is_match,
            'score': float(score),
            'image_url': f"/static/uploads/{res_filename}",
            'best_ref': f"/static/uploads/{best_ref}" if best_ref else None
        })
    except Exception as e:
        print(f"Error in verify_instant: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def history():
    records = database.get_history()
    return jsonify(records)

@app.route('/delete_history_item', methods=['POST'])
def delete_history_item_route():
    item_id = request.json.get('id')
    database.delete_history_item(item_id)
    return jsonify({'success': True})

@app.route('/clear_history', methods=['POST'])
def clear_history_route():
    database.clear_history()
    return jsonify({'success': True})

if __name__ == '__main__':
    import webbrowser
    import threading
    
    def open_browser():
        time.sleep(2.0)
        webbrowser.open('http://localhost:5000')
        
    threading.Thread(target=open_browser, daemon=True).start()
    
    app.run(debug=True, threaded=True, host='0.0.0.0', port=5000)
