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
        Eres el Motor Central de una plataforma médica de alta precisión, especializado en extraer y estructurar historias clínicas.
        A continuación se te proporcionan {len(files)} imágenes o documentos que pertenecen a la MISMA HISTORIA CLÍNICA de un ÚNICO paciente.
        Lee todos los documentos como si fueran páginas de un solo expediente unificado.

        ════════════════════════════════════════════════
        REGLA CRÍTICA N°1 — FECHAS
        ════════════════════════════════════════════════
        Respeta las fechas EXACTAS escritas en cada hoja. Nunca inventes ni uses la fecha actual.
        Si hay múltiples evoluciones en distintos días, mapea cada una a su fecha real.

        ════════════════════════════════════════════════
        REGLA CRÍTICA N°2 — MAPEO SEMÁNTICO DE SECCIONES
        ════════════════════════════════════════════════
        Las historias clínicas en la práctica NO siempre usan los mismos nombres de sección.
        DEBES reconocer cada sección por su CONTENIDO y por cualquiera de sus ALIAS conocidos:

        ┌─────────────────────────────────────────────────────────────────────────────┐
        │ CAMPO JSON          │ ALIAS / ENCABEZADOS QUE LO IDENTIFICAN               │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ motivo_consulta     │ "Motivo de Consulta", "MC", "CC" (Chief Complaint),   │
        │                     │ "S" o "Subjetivo" (en formato SOAP), "Queja",         │
        │                     │ "Razón de Consulta", "Por qué consulta",              │
        │                     │ "Motivo de ingreso", "Jefe de queja"                  │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ enfermedad_actual   │ "Enfermedad Actual", "HEA", "Historia de la           │
        │                     │ Enfermedad Actual", "Historia de la Enfermedad",      │
        │                     │ "O" u "Objetivo" (en formato SOAP), "EA",             │
        │                     │ "Anamnesis", "Historia de la presente enfermedad"     │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ revision_sistemas   │ "Revisión por Sistemas", "RPS", "RxS", "RS",          │
        │                     │ "Interrogatorio por Aparatos y Sistemas",             │
        │                     │ "Por Aparatos", "Sistemas", "Anamnesis por Sistemas"  │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ examenes_fisicos    │ "Examen Físico", "EF", "Exploración Física",          │
        │                     │ "Exploración", "Físico", "Hallazgos al Examen",       │
        │                     │ "Hallazgos Físicos", "Examen Clínico"                 │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ analisis_medico     │ "Análisis", "A" (en formato SOAP), "Assessment",      │
        │                     │ "Impresión Clínica", "Razonamiento Clínico",          │
        │                     │ "Discusión", "Nota de Evolución", "Evolución",        │
        │                     │ "Síntesis Clínica", "Nota Médica", "Notas"            │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ diagnostico         │ "Diagnóstico", "Dx", "Impresión Diagnóstica",         │
        │                     │ "Impresiones", "Diagnósticos", "CIE-10",              │
        │                     │ "Diagnóstico Presuntivo", "Diagnóstico Definitivo"    │
        ├─────────────────────┼──────────────────────────────────────────────────────┤
        │ plan_tratamiento    │ "Plan", "P" (en formato SOAP), "Plan de Manejo",      │
        │                     │ "Conducta", "Tratamiento", "Manejo", "Indicaciones",  │
        │                     │ "Prescripción", "Formulación", "Orden Médica"         │
        └─────────────────────┴──────────────────────────────────────────────────────┘

        ════════════════════════════════════════════════
        REGLA CRÍTICA N°3 — INFERENCIA POR CONTENIDO (sin etiquetas)
        ════════════════════════════════════════════════
        Cuando la historia NO tiene etiquetas claras de sección, identifica cada bloque por
        CÓMO está escrito y QUÉ tipo de información contiene:

        → motivo_consulta:
          Es muy corto (1-3 líneas). Es la razón principal expresada por el paciente o el médico.
          Ejemplos: "Dolor abdominal", "Control post-quirúrgico", "Fiebre y tos de 3 días".

        → enfermedad_actual:
          Es un texto CORTO-MEDIANO (no el más largo). Describe al paciente en tercera persona
          con datos clínicos concretos: género, edad, tiempo de evolución, síntoma principal,
          intensidad. Usa frases como "Paciente femenino de X años que consulta por...",
          "Paciente masculino que acude refiriendo..." o similar.
          IMPORTANTE: NO incluye lo que el médico examina, solo la presentación del caso.

        → revision_sistemas:
          Captura TODO lo que el paciente SIENTE o PERCIBE subjetivamente.
          Esto incluye cualquier síntoma, molestia, sensación o percepción que el paciente reporta
          o experimenta por sí mismo, independientemente de cómo esté escrito.
          Ejemplos: dolor, náuseas, mareo, fiebre sentida, cansancio, falta de aire, palpitaciones,
          ardor, hormigueo, pérdida de apetito, sueño alterado, tristeza, ansiedad, etc.
          Frases clave del redactor: "refiere", "niega", "presenta", "dice que", "manifiesta",
          "no refiere", "siente", "nota", "percibe", "le duele", "tiene".
          PRINCIPIO FUNDAMENTAL: Si el origen de la información es el PACIENTE (lo que él siente
          o dice sentir), va aquí. No importa si el médico lo transcribe, la fuente es subjetiva.

        → examenes_fisicos:
          Captura TODO lo que es ANALIZADO, MEDIDO o DIAGNOSTICADO por el médico mediante
          algún tipo de exploración o examen clínico directo sobre el paciente.
          Esto incluye: signos vitales medidos (TA, FC, FR, Temperatura, SatO2, Glasgow, IMC,
          peso, talla), hallazgos a la inspección, palpación, percusión y auscultación,
          evaluación neurológica (ADI, reflejos, sensibilidad), exploración de piel y mucosas,
          evaluación de edemas, ruidos cardíacos o intestinales, movilidad articular, etc.
          Frases clave: "a la inspección", "a la palpación", "a la auscultación", "se evidencia",
          "se observa", "se encuentra", "presenta al examen", "TA:", "FC:", "Glasgow:", "ADI:".
          PRINCIPIO FUNDAMENTAL: Si la información proviene de un acto médico (el médico lo
          mide, lo observa, lo palpa, lo ausculta o lo evalúa), va aquí. Es objetivo y externo
          al paciente.

        → analisis_medico:
          Es el texto MÁS LARGO del documento. Integra el razonamiento clínico del médico:
          hipótesis diagnósticas, correlación de hallazgos, justificación de exámenes a pedir,
          evolución esperada, y decisiones terapéuticas. Es la "síntesis" del médico tratante.

        ════════════════════════════════════════════════
        REGLA CRÍTICA N°4 — DETECCIÓN Y ELIMINACIÓN ESTRICTA DE DUPLICADOS
        ════════════════════════════════════════════════
        ANTES DE CONSTRUIR EL JSON, debes hacer un ANÁLISIS ANTI-DUPLICACIÓN de la siguiente manera:

        PASO 1 — DETECTAR DUPLICADOS:
        Identifica cualquier fragmento, oración o dato que aparezca más de una vez en el documento
        fuente (ya sea textualmente idéntico o expresado con palabras distintas pero con el mismo
        significado clínico). Ejemplos de duplicados comunes:
          • El nombre del paciente o su edad aparece en la enfermedad_actual Y en el análisis_medico.
          • Los signos vitales se mencionan en la revisión por sistemas Y en el examen físico.
          • El motivo de consulta se repite dentro de la enfermedad_actual.
          • Un síntoma como "fiebre de 3 días" aparece en motivo_consulta Y en revisión_sistemas.
          • Un diagnóstico ya presente en "diagnostico" se vuelve a mencionar en "analisis_medico".

        PASO 2 — ASIGNAR UNA SOLA VEZ:
        Cada dato o fragmento con contenido duplicado debe aparecer ÚNICAMENTE en el campo
        más específico y apropiado para él. NO lo copies en ningún otro campo del JSON.
        La jerarquía de prioridad cuando un contenido podría encajar en más de un campo:
          1° examenes_fisicos  (más específico: el médico lo midió o exploró)
          2° revision_sistemas (el paciente lo siente o percibe)
          3° motivo_consulta   (razón puntual de la visita)
          4° enfermedad_actual (contexto clínico general del paciente)
          5° analisis_medico   (solo lo que es razonamiento del médico, no datos ya catalogados)

        PASO 3 — VERIFICAR ANTES DE FINALIZAR:
        Antes de entregar el JSON, recorre mentalmente cada campo y pregúntate:
          ¿Este contenido ya aparece en otro campo? → Si la respuesta es SÍ, elimínalo de aquí.
          ¿Este campo agrega información NUEVA que no está en ningún otro campo? → Si es NO, vacíalo.
        El JSON final NO debe contener ninguna oración, dato clínico o fragmento que se repita
        en más de un campo. Cada campo debe aportar información EXCLUSIVA y ÚNICA.

        ════════════════════════════════════════════════
        REGLA CRÍTICA N°5 — UNIFICACIÓN CRONOLÓGICA
        ════════════════════════════════════════════════
        Extrae de TODOS los documentos la información del paciente, unificando datos
        cronológicamente. Si hay múltiples fechas de evolución, captura CADA UNA como
        un ítem separado en los arrays (revision_sistemas, examenes_fisicos, paraclinicos).

        Devuelve ÚNICAMENTE el siguiente objeto JSON válido con los datos extraídos:
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
                "motivo_consulta": "El motivo principal de la consulta. Busca en: 'MC', 'CC', 'S', 'Subjetivo', 'Motivo de Consulta', 'Motivo de ingreso'. Si no hay etiqueta, identifícalo por ser el enunciado más breve que explica POR QUÉ acude el paciente.",
                "enfermedad_actual": "Descripción clínica del paciente en tercera persona con edad, género y síntoma principal. Busca en: 'HEA', 'Historia Enfermedad Actual', 'EA', 'O', 'Objetivo', 'Anamnesis'. Si no hay etiqueta, identifícalo por empezar con 'Paciente [género] de [edad] años...'.",
                "revision_sistemas": [
                    {{
                        "fecha": "Fecha exacta de esta revisión escrita en la hoja. Si no hay, pon 'No registrada'.",
                        "descripcion": "Síntomas que el paciente REFIERE o NIEGA por sistema. Busca en: 'RPS', 'RxS', 'Revisión por Sistemas', 'Interrogatorio por Aparatos'. Si no hay etiqueta, identifícalo porque usa frases como 'refiere', 'niega', 'presenta' organizadas por sistemas o aparatos."
                    }}
                ],
                "examenes_fisicos": [
                    {{
                        "fecha": "Fecha exacta del examen. Si no hay, pon 'No registrada'.",
                        "signos_vitales": "Signos vitales: TA, FC, FR, Temperatura, SatO2, Glasgow, peso, talla, IMC si aplica.",
                        "hallazgos": "Hallazgos que el MÉDICO observa al examinar al paciente. Busca en: 'EF', 'Examen Físico', 'Exploración'. Si no hay etiqueta, identifícalo porque menciona 'a la palpación', 'a la auscultación', 'ruidos', 'Glasgow', 'ADI', 'edemas', 'mucosas', etc."
                    }}
                ],
                "analisis_medico": "El razonamiento clínico COMPLETO del médico. Es el campo MÁS EXTENSO. Busca en: 'Análisis', 'A', 'Assessment', 'Nota de Evolución', 'Síntesis Clínica'. Si no hay etiqueta clara, es el bloque de texto más largo que integra todos los hallazgos y justifica decisiones clínicas.",
                "paraclinicos": [
                    {{
                        "fecha": "Fecha exacta del laboratorio o examen complementario.",
                        "tipo_examen": "Nombre del examen (Ej: Hemoglobina, Glucosa, Rayos X, Ecografía)",
                        "valor": "Valor o resultado obtenido",
                        "referencia": "Valor de referencia si está indicado"
                    }}
                ],
                "diagnostico": "Impresiones diagnósticas en estricto orden de importancia (Ej: 1. Cólico Renal 2. Embarazo). Busca en: 'Dx', 'Diagnóstico', 'Impresión Diagnóstica', 'CIE-10'.",
                "plan_tratamiento": "Conducta, plan de manejo, tratamiento o medicamentos. Busca en: 'Plan', 'P', 'Conducta', 'Manejo', 'Indicaciones', 'Formulación', 'Prescripción'."
            }}
        }}
        Si un campo no se encuentra luego de aplicar todos los criterios anteriores, asígnale "No detectado". El JSON debe ser sintácticamente perfecto.
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
