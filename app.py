import os
import shutil
import json
from datetime import datetime
from bson.objectid import ObjectId
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for, flash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
import pymongo
import uuid

from main import generate_from_folder, create_pdf_from_text_results

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_123")

# Habilitar manejo seguro de contraseñas
bcrypt = Bcrypt(app)

# Configuración Sistema Archivos Vercel
if os.environ.get("VERCEL") or os.environ.get("VERCEL_URL"):
    BASE_DIR = "/tmp"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__name__))
    
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'imagenes_entrada')
OUTPUT_FILE = os.path.join(BASE_DIR, 'resultado_clinico.pdf')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def clear_upload_folder():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path): os.unlink(file_path)
        except Exception as e:
            print(f'Falló al borrar {file_path}. Razón: {e}')

# -----------------
# DATA BASE SETUP
# -----------------
MONGO_URI = os.getenv("MONGO_URI", "")
db = None
try:
    if MONGO_URI:
        # Initializing lazily. Ping is removed so cold-starts don't block.
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connect=False)
        db = client.get_database("clinica_db")
        print("MongoDB Configurado Exitosamente a la espera de peticiones!")
except Exception as e:
    print(f"ATENCIÓN: MongoDB NO está conectado. Verifica tu MONGO_URI. Error: {e}")

# -----------------
# AUTHENTICATION
# -----------------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = "Por favor inicia sesión para acceder."
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data["_id"])
        self.name = user_data["name"]
        self.email = user_data["email"]

@login_manager.user_loader
def load_user(user_id):
    if db is None: return None
    user_data = db.users.find_one({"_id": ObjectId(user_id)})
    if user_data: return User(user_data)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if db is None:
            flash("Error: Base de datos no conectada. Revisa MONGO_URI", "error")
            return render_template('login.html')
            
        user_data = db.users.find_one({"email": email})
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales inválidas', 'error')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if db is None:
            flash("Error: Base de datos no conectada. Revisa MONGO_URI", "error")
            return render_template('register.html')
            
        if db.users.find_one({"email": email}):
            flash('El correo electrónico ya está en uso.', 'error')
        else:
            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            db.users.insert_one({"name": name, "email": email, "password": hashed_pw})
            flash('Cuenta creada con éxito. Por favor inicia sesión.', 'success')
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -----------------
# APP ROUTES
# -----------------
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    historias = []
    if db is not None:
        historias = list(db.historias.find({"medico_id": current_user.id}).sort("fecha_creacion", pymongo.DESCENDING))
    return render_template('dashboard.html', historias=historias, name=current_user.name)

@app.route('/upload_ui')
@login_required
def upload_ui():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
@login_required
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No se encontraron archivos en la solicitud'}), 400
        
    files = request.files.getlist('files[]')
    if len(files) == 0 or files[0].filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        
    clear_upload_folder()
    
    saved_files = []
    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_files.append(filename)
            
    if not saved_files:
        return jsonify({'error': 'No se pudo guardar ningún archivo'}), 500

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return jsonify({'error': 'Falta GEMINI_API_KEY en tu .env'}), 500
        
    try:
        success, ocr_data = generate_from_folder(UPLOAD_FOLDER, OUTPUT_FILE, api_key)
        
        # Eliminar las imágenes físicamente del servidor una vez analizadas por seguridad
        clear_upload_folder()
        
        if success and ocr_data and os.path.exists(OUTPUT_FILE):
            record_id = None
            if db is not None:
                # El analizador nos devuelve 1 resultado unificado consolidado
                unified_data = ocr_data[0]['data']
                
                doc = {
                    "medico_id": current_user.id,
                    "paciente": unified_data.get("paciente", "Desconocido"),
                    "identificacion": unified_data.get("identificacion", "Desconocido"),
                    "diagnostico": unified_data.get("diagnostico", "Sin Diagnóstico Específico"),
                    "fecha_creacion": datetime.now(),
                    "datos_completos": unified_data
                }
                
                result = db.historias.insert_one(doc)
                record_id = str(result.inserted_id)
                
            return jsonify({
                'message': 'Proceso completado.',
                'download_url': '/download',
                'view_url': f'/view/{record_id}' if record_id else None
            }), 200
        else:
            return jsonify({'error': 'Error durante la generación de la historia clínica o no se encontraron datos válidos.'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error en el framework: {str(e)}'}), 500

@app.route('/view/<record_id>')
@login_required
def view_record(record_id):
    if db is None:
        return "Base de datos no conectada", 500
        
    record = db.historias.find_one({"_id": ObjectId(record_id), "medico_id": current_user.id})
    if not record:
        return "Registro no encontrado o no tienes permiso para verlo", 404
        
    return render_template('view.html', record=record)

@app.route('/download')
@login_required
def download_pdf():
    if os.path.exists(OUTPUT_FILE):
        return send_file(OUTPUT_FILE, as_attachment=True, download_name='Resumen_Historia_Clinica.pdf', mimetype='application/pdf')
    else:
        return "El archivo PDF no existe o se corrompió", 404

@app.route('/delete/<record_id>', methods=['POST'])
@login_required
def delete_record(record_id):
    if db is None:
        flash("Error de base de datos", "error")
        return redirect(url_for('dashboard'))
        
    result = db.historias.delete_one({"_id": ObjectId(record_id), "medico_id": current_user.id})
    if result.deleted_count > 0:
        flash("Historia clínica eliminada correctamente.", "success")
    else:
        flash("No se pudo eliminar la historia clínica. Posiblemente no tienes permisos.", "error")
        
    return redirect(url_for('dashboard'))

@app.route('/download_pdf/<record_id>')
@login_required
def download_record_pdf(record_id):
    if db is None:
        return "Base de datos no conectada", 500
        
    record = db.historias.find_one({"_id": ObjectId(record_id), "medico_id": current_user.id})
    if not record:
        return "Registro no encontrado", 404
        
    tmp_filename = f"historia_{record_id}_{uuid.uuid4().hex[:6]}.pdf"
    tmp_filepath = os.path.join(BASE_DIR, tmp_filename)
    
    try:
        mock_results = [{
            "filename": f"Paciente_{record['paciente'].replace(' ', '_')}",
            "text": "Reporte obtenido directamente desde la Base de Datos segura.",
            "data": record['datos_completos']
        }]
        create_pdf_from_text_results(mock_results, tmp_filepath)
        return send_file(tmp_filepath, as_attachment=True, download_name=f"Historia_Clinica_{record['paciente'].replace(' ', '_')}.pdf", mimetype='application/pdf')
    except Exception as e:
        return f"Error interno generando el PDF: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
