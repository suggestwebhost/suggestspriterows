import os
import math
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB Max upload limit

UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# MongoDB Connection Configuration
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
db = client['sprites_db'] 
sprites_collection = db.sprites

PER_PAGE = 12  # Number of sprites to display per page before creating a new page

@app.route('/')
def index():
    try:
        # Get current page number from request parameters (default to page 1)
        page = max(1, int(request.args.get('page', 1)))
        
        # Calculate pagination limits
        total_sprites = sprites_collection.count_documents({})
        total_pages = max(1, math.ceil(total_sprites / PER_PAGE))
        page = min(page, total_pages)  # Clamp to max pages
        
        skip_amount = (page - 1) * PER_PAGE
        
        # Query only the required subset slice from MongoDB
        sprites = list(sprites_collection.find().skip(skip_amount).limit(PER_PAGE))
        
    except Exception as e:
        return f"🚨 Database Connection Error: {str(e)}", 500
        
    return render_template(
        'index.html', 
        sprites=sprites, 
        current_page=page, 
        total_pages=total_pages,
        total_sprites=total_sprites
    )

@app.route('/upload', methods=['POST'])
def upload_sprites():
    category = request.form.get('category', 'general').strip().lower()
    tags_raw = request.form.get('tags', '')
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    
    if 'sprites' not in request.files:
        return jsonify({"error": "No file field found"}), 400
        
    uploaded_files = request.files.getlist('sprites')
    
    if not uploaded_files or (len(uploaded_files) == 1 and uploaded_files[0].filename == ''):
        return jsonify({"error": "No files selected"}), 400

    for file in uploaded_files:
        if file and file.filename != '':
            original_filename = secure_filename(file.filename)
            
            # Generate a clean title name safely
            base_name = original_filename.rsplit('.', 1)[0]
            clean_name = base_name.replace('_', ' ').replace('-', ' ').title()
            
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            file.save(file_path)
            
            image_url = f"/static/uploads/{original_filename}"
            
            sprite_data = {
                "name": clean_name,
                "filename": original_filename,
                "image_url": image_url,
                "category": category,
                "tags": tags
            }
            sprites_collection.insert_one(sprite_data)

    return redirect(url_for('index'))

# Route allowing programmatic asset direct-download streams
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

# ==================== API ENDPOINTS ====================
@app.route('/api/sprites', methods=['GET'])
def get_all_sprites():
    category = request.args.get('category')
    tag = request.args.get('tag')
    
    query = {}
    if category:
        query['category'] = category.strip().lower()
    if tag:
        query['tags'] = tag.strip().lower()
        
    sprites = list(sprites_collection.find(query))
    
    output = []
    base_url = request.url_root.rstrip('/')
    for s in sprites:
        output.append({
            "id": str(s['_id']),
            "name": s['name'],
            "category": s['category'],
            "tags": s['tags'],
            "image_url": f"{base_url}{s['image_url']}"
        })
        
    return jsonify({"count": len(output), "sprites": output})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
