import os
import zipfile
import json
import base64
import html
import gzip
import datetime
import uuid
import tempfile
import io
import threading
import shutil
import time
from itertools import groupby  # <--- NEU: Für die Gruppierung der Kapitel
from flask import Flask, request, send_file, jsonify, render_template_string
from weasyprint import HTML
from PIL import Image

# --- Configuration ---
BASE_TEMP_DIR = tempfile.gettempdir()
MAX_IMAGE_WIDTH = 600
JPEG_QUALITY = 70

# --- IN-MEMORY JOB STORE ---
JOBS = {}

# --- KOCHBUCH KATEGORIEN ---
COOKBOOK_ORDER = [
    "Grundrezepte", "Frühstück", "Vorspeisen", "Suppen", "Salate",
    "Hauptgerichte", "Beilagen", "Saucen, Dips & Dressings", "Desserts", "Backen"
]

app = Flask(__name__)

# --- CSS STYLES ---
CSS_STYLES = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Lato:wght@400;700&family=Merriweather:ital,wght@0,300;0,400;0,700;1,300&display=swap');
@media print { 
    @page { margin: 1.5cm; @bottom-center { content: "Page " counter(page); font-family: 'Lato', sans-serif; font-size: 9pt; color: #999; } } 
    body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .no-print { display: none; }
    .page-break { page-break-after: always; }
    .avoid-break { page-break-inside: avoid; }
    .cover-page { page-break-after: always; margin: 0; height: 100%; }
    .chapter-page { page-break-before: always; page-break-after: always; }
}
body { font-family: 'Merriweather', serif; color: #333; line-height: 1.45; margin: 0; padding: 0; background: #fff; }
.container { max-width: 900px; margin: 0 auto; padding: 20px; }

/* Cover Page */
.cover-page { text-align: center; padding: 40px 20px; border: 6px double #2c3e50; height: 85vh; display: flex; flex-direction: column; justify-content: center; align-items: center; background-color: #fdfbf7; box-sizing: border-box; margin-bottom: 0; }
.cover-subtitle { font-family: 'Lato', sans-serif; text-transform: uppercase; letter-spacing: 3px; font-size: 0.9rem; color: #e67e22; margin-bottom: 15px; }
.cover-title { font-family: 'Playfair Display', serif; font-size: 3.8rem; line-height: 1.1; color: #2c3e50; margin: 10px 0; font-style: italic; }
.cover-author { font-family: 'Playfair Display', serif; font-size: 1.3rem; color: #555; margin-top: 30px; font-weight: normal; }
.cover-author strong { display: block; font-size: 1.8rem; color: #2c3e50; margin-top: 8px; }
.cover-year { margin-top: auto; font-family: 'Lato', sans-serif; color: #999; font-size: 0.8rem; padding-top: 20px; }

/* Chapter Page Styles */
.chapter-page { display: flex; flex-direction: column; justify-content: center; align-items: center; height: 85vh; background: #2c3e50; color: #fff; text-align: center; border: 4px solid #e67e22; margin: 20px 0; }
.chapter-content-wrapper { width: 80%; }
.chapter-title { font-family: 'Playfair Display', serif; font-size: 4rem; color: #fff; border-bottom: 3px solid #e67e22; padding-bottom: 20px; margin-bottom: 20px; }

/* Chapter Mini TOC */
.chapter-toc { list-style: none; padding: 0; margin-top: 30px; text-align: center; columns: 2; column-gap: 40px; }
.chapter-toc-item { font-family: 'Lato', sans-serif; font-size: 1.1rem; margin-bottom: 10px; color: #ecf0f1; break-inside: avoid; page-break-inside: avoid; }

/* Main TOC */
.toc-container { padding: 20px 0; }
.toc-title { font-family: 'Playfair Display', serif; font-size: 2.2rem; text-align: center; color: #2c3e50; margin-bottom: 30px; border-bottom: 2px solid #e67e22; display: inline-block; padding-bottom: 8px; width: 100%; }
.toc-list { column-count: 2; column-gap: 40px; list-style: none; padding: 0; font-family: 'Lato', sans-serif; }
.toc-item { margin-bottom: 6px; break-inside: avoid; page-break-inside: avoid; font-size: 0.9rem; }
.toc-item a { text-decoration: none; color: #333; display: flex; align-items: baseline; width: 100%; }
.toc-dots { flex-grow: 1; border-bottom: 1px dotted #aaa; margin: 0 5px; position: relative; top: -4px; }
.toc-page { font-family: 'Lato', sans-serif; color: #666; font-size: 0.85rem; min-width: 25px; text-align: right; }
.toc-page::after { content: target-counter(attr(href), page); }
.toc-category-header { column-span: all; font-family: 'Playfair Display', serif; font-size: 1.2rem; color: #e67e22; margin-top: 15px; margin-bottom: 5px; font-weight: bold; border-bottom: 1px solid #eee; }

/* Recipe Layout */
.recipe-card { margin-bottom: 30px; padding-bottom: 20px; border-bottom: 1px dashed #ccc; padding-top: 10px; page-break-after: always; }
h1 { font-family: 'Playfair Display', serif; font-size: 2.0rem; color: #2c3e50; text-align: center; margin-bottom: 5px; margin-top: 0; }
.meta-info-container { text-align: center; margin-bottom: 15px; }
.meta-info { display: inline-block; font-family: 'Lato', sans-serif; font-size: 0.8rem; color: #e67e22; text-transform: uppercase; letter-spacing: 1.5px; font-weight: 700; border-top: 1px solid #e67e22; border-bottom: 1px solid #e67e22; padding: 3px 12px; }
table.layout-table { width: 100%; border-collapse: collapse; border: none; }
td { vertical-align: top; }
td.sidebar-cell { width: 30%; padding-right: 20px; }
td.main-cell { width: 70%; padding-left: 15px; border-left: 1px solid #eee; }
.sidebar-image { width: 100%; height: auto; border-radius: 4px; margin-bottom: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border: 3px solid white; }
h3 { font-family: 'Lato', sans-serif; font-size: 0.95rem; color: #2c3e50; margin-top: 0; text-transform: uppercase; border-bottom: 2px solid #e67e22; padding-bottom: 4px; margin-bottom: 8px; letter-spacing: 0.5px; }
ul { padding-left: 0; margin: 0; list-style: none; }
li { margin-bottom: 4px; font-size: 0.9rem; border-bottom: 1px dotted #ddd; padding-bottom: 2px; }
.step { margin-bottom: 8px; text-align: justify; position: relative; padding-left: 25px; font-size: 0.95rem; }
.step:before { content: attr(data-step); position: absolute; left: 0; top: 0; font-weight: bold; color: white; background: #e67e22; border-radius: 50%; width: 18px; height: 18px; text-align: center; line-height: 18px; font-size: 0.7rem; font-family: 'Lato', sans-serif; }
.notes { margin-top: 12px; padding: 10px; background: #fffcf5; font-size: 0.85rem; border-left: 3px solid #e67e22; font-style: italic; }
.footer { text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #eee; color: #888; font-family: 'Lato', sans-serif; font-size: 0.8rem; }
"""

# --- HTML FRONTEND (FIXED PROGRESS BAR) ---
INDEX_HTML = """
<!doctype html>
<html>
<head>
    <title>Paprika to PDF Converter</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f0f2f5; margin: 0; }
        .card { background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.1); width: 100%; max-width: 450px; text-align: center; box-sizing: border-box; }
        h2 { color: #2c3e50; margin-bottom: 1.5rem; }
        input[type="text"] { width: 100%; padding: 12px; margin: 8px 0 20px; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; font-size: 1rem; }
        input[type="file"] { width: 100%; padding: 10px; margin-bottom: 20px; background: #f8f9fa; border-radius: 6px; border: 1px dashed #ccc; box-sizing: border-box; }
        button { background: #e67e22; color: white; border: none; padding: 14px 28px; font-size: 1.1rem; font-weight: 600; cursor: pointer; border-radius: 6px; transition: background 0.2s; width: 100%; }
        button:hover { background: #d35400; }
        button:disabled { background: #bdc3c7; cursor: not-allowed; }
        .progress-container { display: none; margin-top: 25px; text-align: left; }
        .progress-bar-bg { background: #e9ecef; border-radius: 8px; height: 24px; overflow: hidden; box-shadow: inset 0 1px 2px rgba(0,0,0,0.1); }
        .progress-bar-fill { background: linear-gradient(90deg, #e67e22, #f39c12); height: 100%; width: 0%; transition: width 0.4s ease; display: flex; align-items: center; justify-content: center; color: white; font-size: 0.8rem; font-weight: bold; text-shadow: 0 1px 1px rgba(0,0,0,0.2); }
        .status-text { margin-top: 10px; color: #7f8c8d; font-size: 0.9rem; text-align: center; font-weight: 500; }
        .download-btn { display: none; margin-top: 20px; background: #27ae60; text-decoration: none; padding: 12px; border-radius: 6px; color: white; font-weight: bold; display: block; }
        .error-msg { color: #e74c3c; margin-top: 10px; font-weight: bold; display: none; }
    </style>
</head>
<body>
    <div class="card">
        <h2>📚 Paprika Cookbook</h2>
        <form id="uploadForm">
            <div style="text-align: left; font-size: 0.9rem; color: #555; margin-bottom: 4px;">Name for Cover:</div>
            <input type="text" name="name" value="A Food Lover" placeholder="e.g. Grandma's Kitchen">
            
            <div style="text-align: left; font-size: 0.9rem; color: #555; margin-bottom: 4px;">Select .paprikarecipes zip:</div>
            <input type="file" name="file" id="fileInput" accept=".paprikarecipes,.zip" required>
            
            <button type="submit" id="submitBtn">Start Conversion</button>
        </form>

        <div class="progress-container" id="progressBox">
            <div class="progress-bar-bg">
                <div class="progress-bar-fill" id="progressBar">0%</div>
            </div>
            <div class="status-text" id="statusText">Starting...</div>
        </div>
        
        <div id="resultArea" style="display:none;">
            <a id="downloadLink" href="#" class="download-btn" style="background:#27ae60;">Download PDF</a>
            <br>
            <button onclick="location.reload()" style="background:#95a5a6; font-size:0.9rem; border:none; padding:8px 16px; width:auto;">Start Over</button>
        </div>
        <div class="error-msg" id="errorMsg"></div>
    </div>

    <script>
        const form = document.getElementById('uploadForm');
        const progressBox = document.getElementById('progressBox');
        const progressBar = document.getElementById('progressBar');
        const statusText = document.getElementById('statusText');
        const btn = document.getElementById('submitBtn');
        const resultArea = document.getElementById('resultArea');
        const downloadLink = document.getElementById('downloadLink');
        const errorMsg = document.getElementById('errorMsg');
        
        let maxProgress = 0;

        form.addEventListener('submit', function(e) {
            e.preventDefault();
            const fileInput = document.getElementById('fileInput');
            if(!fileInput.files.length) return;

            btn.disabled = true;
            btn.style.opacity = "0.5";
            progressBox.style.display = 'block';
            errorMsg.style.display = 'none';
            resultArea.style.display = 'none';
            maxProgress = 0;
            updateBar(0, "Starting upload...");
            
            const formData = new FormData(form);
            const xhr = new XMLHttpRequest();

            xhr.upload.addEventListener("progress", function(evt) {
                if (evt.lengthComputable) {
                    const percentComplete = (evt.loaded / evt.total) * 30;
                    updateBar(percentComplete, "Uploading: " + Math.round((evt.loaded / evt.total) * 100) + "%");
                }
            }, false);

            xhr.addEventListener("load", function() {
                if (xhr.status === 200) {
                    updateBar(30, "Processing on server...");
                    const data = JSON.parse(xhr.responseText);
                    if(data.error) {
                        showError(data.error);
                    } else {
                        pollStatus(data.job_id);
                    }
                } else {
                    showError("Upload failed: " + xhr.statusText);
                }
            });

            xhr.addEventListener("error", function() {
                showError("Network error during upload.");
            });

            xhr.open("POST", "/upload");
            xhr.send(formData);
        });

        function pollStatus(jobId) {
            const interval = setInterval(() => {
                fetch('/status/' + jobId + '?t=' + new Date().getTime())
                .then(res => res.json())
                .then(data => {
                    let visualPercent = 30 + (data.progress * 0.7); 
                    updateBar(visualPercent, data.message);
                    
                    if(data.state === 'complete') {
                        clearInterval(interval);
                        updateBar(100, "Done!");
                        showSuccess(jobId, data.filename);
                    } else if (data.state === 'error') {
                        clearInterval(interval);
                        showError(data.error);
                    }
                })
                .catch(err => {
                    console.log("Polling wait...", err);
                });
            }, 2000);
        }

        function updateBar(percent, text) {
            if(percent > maxProgress) maxProgress = percent;
            if(maxProgress > 100) maxProgress = 100;
            progressBar.style.width = maxProgress + '%';
            progressBar.innerText = Math.round(maxProgress) + '%';
            if(text) statusText.innerText = text;
        }

        function showSuccess(jobId, filename) {
            setTimeout(() => {
                progressBox.style.display = 'none';
                resultArea.style.display = 'block';
                downloadLink.href = '/download/' + jobId;
                downloadLink.innerText = "Download PDF";
                statusText.innerText = "Done!";
            }, 500);
        }

        function showError(msg) {
            progressBox.style.display = 'none';
            errorMsg.innerText = "Error: " + msg;
            errorMsg.style.display = 'block';
            btn.disabled = false;
            btn.style.opacity = "1";
        }
    </script>
</body>
</html>
"""

# --- WORKER FUNCTIONS ---

def optimize_and_save_image(base64_str, output_dir):
    if not base64_str: return None
    try:
        filename = str(uuid.uuid4()) + ".jpg"
        filepath = os.path.join(output_dir, filename)
        
        img_data = base64.b64decode(base64_str)
        with Image.open(io.BytesIO(img_data)) as img:
            if img.mode in ("RGBA", "P"): img = img.convert("RGB")
            if img.width > MAX_IMAGE_WIDTH:
                ratio = MAX_IMAGE_WIDTH / float(img.width)
                new_height = int(float(img.height) * float(ratio))
                img = img.resize((MAX_IMAGE_WIDTH, new_height), Image.Resampling.LANCZOS)
            
            img.save(filepath, format="JPEG", quality=JPEG_QUALITY)
            return filepath
    except Exception as e:
        print(f"Image Error: {e}")
        return None

def process_cookbook_thread(job_id, zip_path, user_name, job_dir):
    try:
        JOBS[job_id]['status'] = 'processing'
        JOBS[job_id]['message'] = 'Extracting recipes...'
        JOBS[job_id]['progress'] = 5

        recipes = []
        img_dir = os.path.join(job_dir, "images")
        os.makedirs(img_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as z:
            all_zip_files = z.namelist()
            recipe_files = [f for f in all_zip_files if f.endswith('.paprikarecipe')]
            
            total_files = len(recipe_files)
            if total_files == 0:
                raise Exception("No .paprikarecipe files found in ZIP")

            for idx, filename in enumerate(recipe_files):
                progress = 10 + int((idx / total_files) * 60)
                JOBS[job_id]['progress'] = progress
                JOBS[job_id]['message'] = f'Processing recipe {idx+1}/{total_files}...'

                try:
                    raw_data = z.read(filename)
                    try: json_str = gzip.decompress(raw_data).decode('utf-8')
                    except: json_str = raw_data.decode('utf-8')
                    
                    data = json.loads(json_str)
                    
                    img_path = None
                    img_b64 = data.get('photo_data') or data.get('photoData')
                    
                    if not img_b64 and data.get('photo'):
                        target = os.path.basename(data['photo'])
                        found = next((f for f in all_zip_files if f.endswith(target)), None)
                        if found:
                            with z.open(found) as img_f:
                                img_b64 = base64.b64encode(img_f.read()).decode('utf-8')

                    if img_b64:
                        img_path = optimize_and_save_image(img_b64, img_dir)

                    raw_categories = data.get('categories', [])
                    primary_category = "Sonstiges"
                    found_priority = False
                    if raw_categories:
                        for priority_cat in COOKBOOK_ORDER:
                            if priority_cat in raw_categories:
                                primary_category = priority_cat
                                found_priority = True
                                break
                        if not found_priority and raw_categories:
                            primary_category = raw_categories[0]

                    recipes.append({
                        'name': data.get('name', 'Untitled'),
                        'category': primary_category,
                        'prep_time': data.get('prep_time', ''),
                        'cook_time': data.get('cook_time', ''),
                        'servings': data.get('servings', ''),
                        'image_path': img_path,
                        'ingredients_list': (data.get('ingredients') or "").split('\n'),
                        'directions_list': (data.get('directions') or "").split('\n'),
                        'notes': data.get('notes', '')
                    })
                except Exception as e:
                    print(f"Skipping corrupt recipe: {e}")

        JOBS[job_id]['message'] = 'Sorting and layout...'
        JOBS[job_id]['progress'] = 75
        
        # Sort is crucial for groupby to work later
        def recipe_sorter(r):
            cat = r['category']
            name = r['name']
            if cat in COOKBOOK_ORDER:
                return (COOKBOOK_ORDER.index(cat), name)
            return (99, cat, name)
        
        recipes.sort(key=recipe_sorter)

        JOBS[job_id]['message'] = 'Generating PDF pages...'
        JOBS[job_id]['progress'] = 80
        
        html_content = generate_full_html(recipes, user_name)
        
        html_file_path = os.path.join(job_dir, "cookbook.html")
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        del html_content
        del recipes

        JOBS[job_id]['message'] = 'Rendering PDF (this takes time)...'
        JOBS[job_id]['progress'] = 85
        
        pdf_filename = f"Cookbook_{uuid.uuid4().hex[:8]}.pdf"
        pdf_path = os.path.join(job_dir, pdf_filename)
        
        HTML(filename=html_file_path).write_pdf(pdf_path)
        
        JOBS[job_id]['filename'] = pdf_filename
        JOBS[job_id]['pdf_path'] = pdf_path
        JOBS[job_id]['progress'] = 100
        JOBS[job_id]['status'] = 'complete'
        JOBS[job_id]['message'] = 'Done!'

    except Exception as e:
        print(f"Job failed: {e}")
        JOBS[job_id]['status'] = 'error'
        JOBS[job_id]['error'] = str(e)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

def generate_full_html(recipes, user_name):
    # 1. Cover Page
    def get_cover():
        year = datetime.datetime.now().year
        return f"""<div class="cover-page"><div class="cover-subtitle">My Personal</div><div class="cover-title">Recipe<br>Collection</div><div class="cover-icon">♨</div><div class="cover-author">from<br><strong>{html.escape(user_name)}</strong></div><div class="cover-year">{year}</div></div>"""

    # 2. Main Global TOC
    def get_toc():
        list_items = ""
        last_cat = None
        # We iterate here once for global TOC and setting anchors
        for recipe in recipes:
            current_cat = recipe.get('category', 'Others')
            if current_cat != last_cat:
                list_items += f"""<li class="toc-category-header">{html.escape(current_cat)}</li>"""
                last_cat = current_cat
            
            anchor_id = f"recipe_{hash(recipe['name'])}"
            recipe['anchor_id'] = anchor_id
            
            list_items += f"""<li class="toc-item"><a href="#{anchor_id}"><span>{html.escape(recipe["name"])}</span><span class="toc-dots"></span><span class="toc-page" href="#{anchor_id}"></span></a></li>"""
        return f"""<div class="toc-container"><div class="toc-title">Table of Contents</div><ul class="toc-list">{list_items}</ul></div><div class="page-break"></div>"""

    content = [f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>{CSS_STYLES}</style></head><body><div class="container">"""]
    content.append(get_cover())
    content.append(get_toc())
    
    # 3. Recipes grouped by category
    # recipes are already sorted by category in the thread function, so groupby works.
    for category, group in groupby(recipes, key=lambda x: x['category']):
        cat_recipes = list(group)
        
        # --- A. Chapter Page with Mini-TOC ---
        mini_toc_html = ""
        for r in cat_recipes:
            mini_toc_html += f'<li class="chapter-toc-item">{html.escape(r["name"])}</li>'
        
        content.append(f"""
        <div class="chapter-page">
            <div class="chapter-content-wrapper">
                <div class="chapter-title">{html.escape(category)}</div>
                <ul class="chapter-toc">
                    {mini_toc_html}
                </ul>
            </div>
        </div>
        """)
        
        # --- B. Recipe Cards ---
        for recipe in cat_recipes:
            img_html = ""
            if recipe.get('image_path'):
                abs_path = os.path.abspath(recipe['image_path'])
                img_html = f'<img src="file://{abs_path}" class="sidebar-image">'

            ing_html = "".join([f"<li>{html.escape(i)}</li>" for i in recipe['ingredients_list'] if i.strip()])
            
            dir_html = ""
            step_count = 1
            for step in recipe['directions_list']:
                if step.strip():
                    dir_html += f'<div class="step" data-step="{step_count}">{html.escape(step)}</div>'
                    step_count += 1
                    
            meta = []
            if recipe.get('prep_time'): meta.append(f"Prep: {recipe['prep_time']}")
            if recipe.get('cook_time'): meta.append(f"Cook: {recipe['cook_time']}")
            if recipe.get('servings'): meta.append(f"Serv.: {recipe['servings']}")
            meta_html = " &nbsp;&bull;&nbsp; ".join(meta) if meta else "&nbsp;"
            
            notes_html = f'<div class="notes"><strong>Note:</strong> {html.escape(recipe["notes"])}</div>' if recipe.get('notes') else ""
            
            content.append(f"""<div class="recipe-card avoid-break" id="{recipe.get('anchor_id', '')}"><h1>{html.escape(recipe['name'])}</h1><div class="meta-info-container"><div class="meta-info">{meta_html}</div></div><table class="layout-table"><tr><td class="sidebar-cell">{img_html}<h3>Ingredients</h3><ul>{ing_html}</ul></td><td class="main-cell"><h3>Directions</h3>{dir_html}{notes_html}</td></tr></table></div>""")
    
    content.append(f'<div class="footer no-print">Compiled by {html.escape(user_name)}</div></div></body></html>')
    return "".join(content)

# --- ROUTES ---

@app.route('/')
def index():
    return render_template_string(INDEX_HTML)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    user_name = request.form.get('name', 'A Food Lover')
    
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(BASE_TEMP_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    zip_path = os.path.join(job_dir, "upload.zip")
    file.save(zip_path)
    
    JOBS[job_id] = {
        'status': 'queued',
        'progress': 0,
        'message': 'Queued...',
        'created_at': time.time()
    }
    
    thread = threading.Thread(target=process_cookbook_thread, args=(job_id, zip_path, user_name, job_dir))
    thread.daemon = True
    thread.start()
    
    return jsonify({'job_id': job_id})

@app.route('/status/<job_id>')
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'state': job['status'],
        'progress': job.get('progress', 0),
        'message': job.get('message', ''),
        'filename': job.get('filename')
    })

@app.route('/download/<job_id>')
def download_pdf(job_id):
    job = JOBS.get(job_id)
    if not job or job['status'] != 'complete':
        return "File not ready or not found", 404
    
    return send_file(
        job['pdf_path'], 
        as_attachment=True, 
        download_name=job['filename']
    )

def cleanup_jobs():
    while True:
        time.sleep(3600)
        now = time.time()
        to_delete = []
        for jid, job in JOBS.items():
            if now - job['created_at'] > 3600:
                to_delete.append(jid)
                job_dir = os.path.join(BASE_TEMP_DIR, jid)
                if os.path.exists(job_dir):
                    shutil.rmtree(job_dir, ignore_errors=True)
        
        for jid in to_delete:
            del JOBS[jid]

cleanup_thread = threading.Thread(target=cleanup_jobs, daemon=True)
cleanup_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000)) 
    app.run(host='0.0.0.0', port=port)
