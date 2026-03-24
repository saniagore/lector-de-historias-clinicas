import os
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import shutil
from dotenv import load_dotenv
from main import generate_from_folder

load_dotenv()

app = Flask(__name__)

# Configuración: Vercel solo permite escribir en /tmp
if os.environ.get("VERCEL") or os.environ.get("VERCEL_URL"):
    BASE_DIR = "/tmp"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__name__))
    
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'imagenes_entrada')
OUTPUT_FILE = os.path.join(BASE_DIR, 'resultado_clinico.pdf')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Asegurarse de que la carpeta existe
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Función para limpiar la carpeta de entrada
def clear_upload_folder():
    for filename in os.listdir(UPLOAD_FOLDER):
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Falló al borrar {file_path}. Razón: {e}')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No se encontraron archivos en la solicitud'}), 400
        
    files = request.files.getlist('files[]')
    
    if len(files) == 0 or files[0].filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo'}), 400
        
    # Limpiar carpeta para que no se mezclen historias clínicas
    clear_upload_folder()
    
    # Guardar archivos nuevos
    saved_files = []
    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            saved_files.append(filename)
            
    if not saved_files:
        return jsonify({'error': 'No se pudo guardar ningún archivo'}), 500

    # API key desde entorno (.env)
    api_key = os.getenv("GEMINI_API_KEY", "")
    
    if not api_key:
        return jsonify({'error': 'La API Key de Gemini no está configurada.'}), 500
        
    try:
        # Ejecutar nuestra lógica en main.py
        success = generate_from_folder(UPLOAD_FOLDER, OUTPUT_FILE, api_key)
        
        if success and os.path.exists(OUTPUT_FILE):
            # Retornamos la URL de descarga directa
            return jsonify({
                'message': 'Historia clínica generada con éxito.',
                'download_url': '/download'
            }), 200
        else:
            return jsonify({'error': 'Error durante la generación de la historia clínica o no se encontraron datos válidos.'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error en el procesamiento: {str(e)}'}), 500

@app.route('/download', methods=['GET'])
def download_pdf():
    if os.path.exists(OUTPUT_FILE):
        return send_file(OUTPUT_FILE, as_attachment=True, download_name='Resumen_Historia_Clinica.pdf', mimetype='application/pdf')
    else:
        return "El archivo no existe", 404

if __name__ == '__main__':
    # Habilitar web server
    app.run(debug=True, port=5000)
