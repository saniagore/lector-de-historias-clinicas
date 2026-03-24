import os
import json
import time
import google.generativeai as genai

def process_images_in_folder(folder_path, api_key):
    """
    Processes all clinical history files (images or PDFs) in the folder using Google Gemini API.
    Extracts relevant patient data directly to JSON.
    """
    results = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.pdf', '.webp')
    
    if not os.path.exists(folder_path):
        print(f"Error: La carpeta {folder_path} no existe.")
        return results

    if not api_key or api_key == "TU_API_KEY_AQUI":
        print("Error: Por favor configura tu GEMINI_API_KEY en main.py.")
        return results

    genai.configure(api_key=api_key)
    # Using gemini-2.5-flash since it handles documents and images perfectly and fast
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]
    files.sort()

    uploaded_files = []
    print(f"\nSubiendo {len(files)} archivos al Motor de Inteligencia Artificial Médico como un solo expediente...")
    
    try:
        for filename in files:
            full_path = os.path.join(folder_path, filename)
            uf = genai.upload_file(path=full_path)
            
            while uf.state.name == "PROCESSING":
                print(".", end="", flush=True)
                time.sleep(2)
                uf = genai.get_file(uf.name)
                
            if uf.state.name == "FAILED":
                raise Exception(f"El archivo {filename} falló al procesarse.")
                
            uploaded_files.append(uf)
            
        print("\nTodos los archivos cargados en el nodo central. Extrayendo datos unificados...")
        
        prompt = f"""
        Eres el Motor Central de una plataforma médica, un asistente especializado en extraer historias clínicas sin errores.
        A continuación se te proporcionan {len(files)} imágenes o documentos que pertenecen a la MISMA HISTORIA CLÍNICA de un ÚNICO paciente.
        Lee todos los documentos como si fueran páginas de un solo expediente unificado.
        
        REGLA CRÍTICA N°1 (FECHAS):
        Es de vital urgencia médica que respetes las fechas EXACTAS de las consultas. Busca siempre la FECHA REAL (dd/mm/aaaa o YYYY/MM/DD) escrita en cada hoja de evolución, laboratorio o triaje. No puedes inventar, deducir ni usar la fecha en la que estás respondiendo. Si un documento tiene datos de hace 3 días, pon esa fecha textual. Si un paciente tiene varias evoluciones en diferentes días, mapea estrictamente cada revisión a su fecha real sin omitir ninguna.

        REGLA CRÍTICA N°2 (UNIFICACIÓN): 
        Extrae de TODOS los documentos la información más importante del paciente unificando los datos cronológicamente y en conjunto.

        Debes devolver ÚNICAMENTE un objeto JSON válido con la siguiente estructura (reemplaza los valores con la información combinada extraída):
        {{
            "texto_completo": "Todo el texto puro que logres leer u OCR de los documentos. No resumas, devuelve el texto plano tal cual está.",
            "datos": {{
                "paciente": "Nombre completo del paciente",
                "identificacion": "Número de identificación o cédula",
                "fecha_nacimiento": "Fecha de nacimiento (YYYY-MM-DD) o como aparezca",
                "telefono": "Número de teléfono celular o fijo",
                "fecha_ingreso": "Fecha exacta de ingreso encontrada en los documentos",
                "fecha_atencion": "Fecha exacta de atención médica",
                "fecha_cierre": "Fecha de cierre o salida",
                "empresa": "Ejemplo: EPS SURA",
                "contrato": "Ejemplo: EPS SURA CONTRIBUTIVO",
                "municipio": "Ciudad o municipio de atención",
                "direccion": "Dirección completa del paciente",
                "motivo_consulta": "El motivo de consulta textual o manifestado, sin importar si tiene comillas o lo anota el médico (Ej: 'vine porque me partí el brazo' o 'evaluación de control'). Es el por qué directo de la cita.",
                "enfermedad_actual": "La descripción clínica detallada del problema una vez interrogado el paciente (Ej: 'Paciente masculino de 20 años que refiere traumatismo en antebrazo tras caída... dolor 9/10').",
                "revision_sistemas": [
                    {{
                        "fecha": "Fecha exacta de esta revisión escrita en la hoja (Ej: 03/03/2026). Si de verdad no hay, pon 'No registrada'.",
                        "descripcion": "Detalles de la revisión por sistemas en esa fecha."
                    }}
                ],
                "examenes_fisicos": [
                    {{
                        "fecha": "Fecha exacta del examen (Ej: 03/03/2026). Si no hay, pon 'No registrada'.",
                        "signos_vitales": "Signos vitales registrados en esta fecha (Ej: TA 120/80, FC 80, etc.).",
                        "hallazgos": "Hallazgos clínicos positivos o relevantes."
                    }}
                ],
                "analisis_medico": "Este debe ser el campo MÁS LARGO Y COMPLETO de toda la historia. Es la síntesis total del médico elaborada una vez hecho el interrogatorio, examen físico y revisión por sistemas. (Ej: 'Paciente masculino de 20 años que sufre un traumatismo... al no haber fractura abierta ni signos de síndrome compartimental se inicia manejo analgésico con AINES y se realiza radiografía en busca de fracturas...'). Describe TODO el raciocinio clínico y el abordaje propuesto.",
                "paraclinicos": [
                    {{
                        "fecha": "Fecha exacta del laboratorio/examen (Ej: 03/03/2026).",
                        "tipo_examen": "Nombre del examen (Ej: Hemoglobina, Glucosa, Rayos X)",
                        "valor": "Valor o resultado obtenido",
                        "referencia": "Valor de referencia si está indicado"
                    }}
                ],
                "diagnostico": "Impresiones diagnósticas numeradas en estricto orden de importancia o jerarquía (Ej: 1. Cólico Renal 2. Embarazo). Solo lista los diagnósticos sin explicar si no es necesario.",
                "plan_tratamiento": "Conducta, plan a seguir, tratamiento o medicamentos recetados."
            }}
        }}
        Si algún dato clave de los 'datos' no se encuentra, debes asignarle el valor "No detectado". El JSON debe ser perfecto sintácticamente.
        """
        
        contents = uploaded_files + [prompt]
        response = model.generate_content(
            contents,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json",
            )
        )
        
        # Assuming Gemini returns JSON (with or without markdown block)
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
            
        try:
            extracted_json = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"\n--- ERROR DE JSON ---\nEl modelo generó un JSON inválido.\nFragmento: {response_text[:300]}...\n-------------------\n")
            raise e
        
        structured_data = extracted_json.get("datos", {})
        full_text = extracted_json.get("texto_completo", "No se pudo extraer el texto completo.")
        
        print("Datos extraídos correctamente.")
        
        # Delete the files from Gemini to save the user's quota/storage
        for uf in uploaded_files:
            try: genai.delete_file(uf.name)
            except: pass
            
        results.append({
            'filename': "Expediente_Clinico_Unificado",
            'text': full_text,
            'data': structured_data
        })
        
    except Exception as e:
        print(f"Error crítico en el Motor de IA procesando el expediente: {str(e)}")
        
        # Cleanup any uploaded files
        for uf in uploaded_files:
            try: genai.delete_file(uf.name)
            except: pass
            
        full_text = f"Error: {str(e)}"
        structured_data = {k: "No disponible (Error en Motor IA)" for k in [
            'identificacion', 'paciente', 'fecha_ingreso', 'fecha_atencion', 
            'fecha_cierre', 'fecha_nacimiento', 'telefono', 'direccion', 
            'empresa', 'contrato', 'municipio', 'motivo_consulta',
            'enfermedad_actual', 'analisis_medico', 
            'diagnostico', 'plan_tratamiento'
        ]}
        structured_data['paraclinicos'] = []
        structured_data['revision_sistemas'] = []
        structured_data['examenes_fisicos'] = []
        
        results.append({
            'filename': "Error_Expediente",
            'text': full_text,
            'data': structured_data
        })
        
    return results
