import os
from fpdf import FPDF
from dotenv import load_dotenv
from gemini_processor import process_images_in_folder

load_dotenv()

class OCRToPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'REPORTE MÉDICO ESTRUCTURADO', border=0, new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', border=0, align='C')

def create_pdf_from_text_results(results, output_filename):
    pdf = OCRToPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Custom colors
    PRIMARY_COLOR = (41, 128, 185) # Medical blue
    SECONDARY_COLOR = (236, 240, 241) # Light gray
    TEXT_COLOR = (44, 62, 80) # Dark blue-gray

    def clean_str(s):
        if not isinstance(s, str): return str(s)
        try:
            return s.encode('latin-1', 'replace').decode('latin-1')
        except:
            return s.encode('ascii', 'replace').decode('ascii')

    for item in results:
        pdf.add_page()
        filename = item['filename']
        text = item['text']
        data = item.get('data', {})
        
        # PRINT MUY CLARO DE LOS DATOS QUE RECIBE EL PDF
        print(f"\n>>> DATOS ENVIADOS AL PDF PARA EL ARCHIVO: {filename}")
        import json
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("<<< FIN DE DATOS\n")
        
        # Section Header - Filename
        pdf.set_fill_color(*PRIMARY_COLOR)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", 'B', 12)
        pdf.cell(0, 10, f"HISTORIA CLÍNICA - REF: {clean_str(filename.upper())}", new_x="LMARGIN", new_y="NEXT", border=0, fill=True, align='C')
        pdf.ln(5)

        # Structured Data Section
        pdf.set_text_color(*TEXT_COLOR)
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_draw_color(*PRIMARY_COLOR)
        pdf.cell(0, 8, " 1. DATOS DE FILIACIÓN", new_x="LMARGIN", new_y="NEXT", border="B")
        pdf.ln(3)

        # Grid config
        label_w = 40
        
        fields = [
            ('Paciente', 'paciente'),
            ('Identificaci\xf3n', 'identificacion'), # latin-1 for Identificación
            ('Fecha Nacimiento', 'fecha_nacimiento'),
            ('Tel\xe9fono', 'telefono'), # latin-1 for Teléfono
            ('Fecha Ingreso', 'fecha_ingreso'),
            ('Fecha Atenci\xf3n', 'fecha_atencion'),
            ('Fecha Cierre', 'fecha_cierre'),
            ('Empresa', 'empresa'),
            ('Contrato', 'contrato'),
            ('Municipio', 'municipio'),
            ('Direcci\xf3n', 'direccion')
        ]

        pdf.set_fill_color(*SECONDARY_COLOR)
        toggle_fill = False
        
        for label, key in fields:
            val = str(data.get(key, "No detectado"))
            val = clean_str(val)
            
            # Row setup
            pdf.set_font("helvetica", 'B', 9)
            pdf.set_fill_color(*SECONDARY_COLOR)
            
            # 1. Store starting coordinates
            start_y = pdf.get_y()
            start_x = pdf.l_margin
            
            # 2. Draw Label
            pdf.set_xy(start_x, start_y)
            pdf.cell(label_w, 7, f"  {label}:", border=0, fill=toggle_fill)
            
            # 3. Draw Value (Multi-line)
            pdf.set_font("helvetica", size=9)
            val_w = pdf.epw - label_w
            pdf.set_xy(start_x + label_w, start_y)
            
            # Determine how many lines the value will take to calculate the shaded background height
            # But multi_cell already handles fill if we provide it.
            pdf.multi_cell(val_w, 7, val, border=0, fill=toggle_fill, align='L')
            
            # 4. Final adjustments: Move to the bottom of this row
            # If multi_cell pushed Y further down, we stay there. 
            # If not (single line), we force an increment of at least 7
            new_y = pdf.get_y()
            if new_y < start_y + 7:
                pdf.set_y(start_y + 7)
            
            toggle_fill = not toggle_fill
            pdf.set_x(pdf.l_margin)

        pdf.ln(3)
        
        def draw_numbered_section(number, title, text_val):
            val = clean_str(text_val)
            if not val or val.lower() in ['no detectado', 'no registrado', 'no disponible', 'no reportado', 'error gemini', '[]']:
                return
            
            pdf.set_text_color(*PRIMARY_COLOR)
            pdf.set_fill_color(*SECONDARY_COLOR)
            pdf.set_font("helvetica", 'B', 10)
            pdf.cell(0, 7, f" {number}. {title.upper()}", new_x="LMARGIN", new_y="NEXT", fill=True, border=0)
            
            pdf.set_font("helvetica", size=9)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 5, val, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # 2. MOTIVO DE CONSULTA
        val_motivo_p = clean_str(data.get('motivo_consulta_paciente', 'No registrado'))
        val_motivo_m = clean_str(data.get('motivo_consulta_medico', 'No registrado'))
        
        has_p = val_motivo_p.lower() not in ['no detectado', 'no registrado', 'error gemini']
        has_m = val_motivo_m.lower() not in ['no detectado', 'no registrado', 'error gemini']
        
        if has_p or has_m:
            pdf.set_text_color(*PRIMARY_COLOR)
            pdf.set_fill_color(*SECONDARY_COLOR)
            pdf.set_font("helvetica", 'B', 10)
            pdf.cell(0, 7, " 2. MOTIVO DE CONSULTA", new_x="LMARGIN", new_y="NEXT", fill=True, border=0)
            
            pdf.set_font("helvetica", size=9)
            pdf.set_text_color(40, 40, 40)
            if has_p:
                pdf.set_font("helvetica", 'I', 9)
                pdf.multi_cell(0, 5, f"Paciente: {val_motivo_p}", new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1)
            if has_m:
                pdf.set_font("helvetica", size=9)
                pdf.multi_cell(0, 5, f"Médico: {val_motivo_m}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # 3. ENFERMEDAD ACTUAL
        draw_numbered_section("3", "ENFERMEDAD ACTUAL", data.get('enfermedad_actual', ''))
        
        # 4. REVISIÓN POR SISTEMAS
        val_revision_raw = data.get('revision_sistemas', [])
        if isinstance(val_revision_raw, str) and val_revision_raw.lower() not in ['no detectado', 'no registrado', '[]']:
            val_revision_raw = [{"fecha": "Fecha principal", "descripcion": val_revision_raw}]
        
        if isinstance(val_revision_raw, list) and len(val_revision_raw) > 0:
            pdf.set_text_color(*PRIMARY_COLOR)
            pdf.set_fill_color(*SECONDARY_COLOR)
            pdf.set_font("helvetica", 'B', 10)
            pdf.cell(0, 7, " 4. REVISIÓN POR SISTEMAS", new_x="LMARGIN", new_y="NEXT", fill=True, border=0)
            
            for item in val_revision_raw:
                fecha = clean_str(str(item.get('fecha', 'Fecha no registrada')))
                desc = clean_str(str(item.get('descripcion', '')))
                
                if desc and desc.lower() not in ['no detectado', 'no registrado']:
                    pdf.set_font("helvetica", 'B', 9)
                    pdf.set_text_color(*PRIMARY_COLOR)
                    pdf.cell(0, 6, f" Fecha: {fecha}", new_x="LMARGIN", new_y="NEXT")
                    
                    pdf.set_font("helvetica", size=9)
                    pdf.set_text_color(40, 40, 40)
                    pdf.multi_cell(0, 5, desc, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(4)

        # 5. EXAMEN FÍSICO
        val_examenes_raw = data.get('examenes_fisicos', [])
        # Backwards compatibility check
        old_examen = str(data.get('hallazgos_examen_fisico', ''))
        if not val_examenes_raw and old_examen.lower() not in ['no detectado', 'no registrado', '']:
            val_examenes_raw = [{"fecha": "Fecha principal", "signos_vitales": str(data.get('signos_vitales', '')), "hallazgos": old_examen}]
            
        if isinstance(val_examenes_raw, list) and len(val_examenes_raw) > 0:
            valid_examenes = [e for e in val_examenes_raw if e.get('hallazgos', '').lower() not in ['no detectado', 'no registrado', ''] or e.get('signos_vitales', '').lower() not in ['no detectado', 'no registrado', '']]
            
            if len(valid_examenes) > 0:
                pdf.set_text_color(*PRIMARY_COLOR)
                pdf.set_fill_color(*SECONDARY_COLOR)
                pdf.set_font("helvetica", 'B', 10)
                pdf.cell(0, 7, " 5. EXAMEN FÍSICO", new_x="LMARGIN", new_y="NEXT", fill=True, border=0)
                
                for item in valid_examenes:
                    fecha = clean_str(str(item.get('fecha', 'Fecha no registrada')))
                    signos = clean_str(str(item.get('signos_vitales', '')))
                    hallazgos = clean_str(str(item.get('hallazgos', '')))
                    
                    pdf.set_font("helvetica", 'B', 9)
                    pdf.set_text_color(*PRIMARY_COLOR)
                    pdf.cell(0, 6, f" Fecha: {fecha}", new_x="LMARGIN", new_y="NEXT")
                    
                    pdf.set_font("helvetica", size=9)
                    pdf.set_text_color(40, 40, 40)
                    
                    if signos and signos.lower() not in ['no registrado', 'no detectado', '']:
                        pdf.set_font("helvetica", 'B', 9)
                        pdf.cell(0, 5, " Signos Vitales:", new_x="LMARGIN", new_y="NEXT")
                        pdf.set_font("helvetica", size=9)
                        pdf.multi_cell(0, 5, f" {signos}", new_x="LMARGIN", new_y="NEXT")
                        pdf.ln(1)
                        
                    if hallazgos and hallazgos.lower() not in ['no registrado', 'no detectado', '']:
                        pdf.multi_cell(0, 5, hallazgos, new_x="LMARGIN", new_y="NEXT")
                        
                    pdf.ln(2)
                pdf.ln(2)

        # 6. PARACLÍNICOS (Table version)
        val_paraclinicos = data.get('paraclinicos', [])
        
        # Backward compatibility format mapping or direct array mapping
        if isinstance(val_paraclinicos, str) and val_paraclinicos.lower() not in ['no detectado', 'no registrado', 'no disponible', 'no reportado', 'error gemini', '[]']:
            val_paraclinicos = [{"tipo_examen": val_paraclinicos, "valor": "-", "referencia": "-"}]

        if isinstance(val_paraclinicos, list) and len(val_paraclinicos) > 0:
            pdf.set_text_color(*PRIMARY_COLOR)
            pdf.set_fill_color(*SECONDARY_COLOR)
            pdf.set_font("helvetica", 'B', 10)
            pdf.cell(0, 7, " 6. PARACLÍNICOS", new_x="LMARGIN", new_y="NEXT", fill=True, border=0)
            
            pdf.set_font("helvetica", size=9)
            pdf.set_text_color(40, 40, 40)
            
            with pdf.table(col_widths=(25, 65, 45, 55), text_align="CENTER", borders_layout="ALL", first_row_as_headings=True) as table:
                # Add table header
                row = table.row()
                row.cell("Fecha")
                row.cell("Tipo de examen")
                row.cell("Valor del examen")
                row.cell("Valor de referencia")
                
                # Add rows from data
                for p in val_paraclinicos:
                    row = table.row()
                    row.cell(clean_str(str(p.get("fecha", "-"))))
                    row.cell(clean_str(str(p.get("tipo_examen", "-"))))
                    row.cell(clean_str(str(p.get("valor", "-"))))
                    row.cell(clean_str(str(p.get("referencia", "-"))))
            pdf.ln(4)
            
        # 7. DIAGNÓSTICO
        draw_numbered_section("7", "IMPRESIONES DIAGNÓSTICAS", data.get('diagnostico', ''))
        
        # 8. ANÁLISIS DEL CASO
        draw_numbered_section("8", "ANÁLISIS DEL CASO", data.get('analisis_medico', ''))
        
        # 9. PLAN DE MANEJO
        draw_numbered_section("9", "PLAN DE MANEJO", data.get('plan_tratamiento', ''))

    pdf.output(output_filename)
    print(f"PDF generado con éxito: {output_filename}")

def generate_from_folder(input_folder, output_file, api_key):
    print("Iniciando procesamiento con Google Gemini API...")
    ocr_results = process_images_in_folder(input_folder, api_key)

    if not ocr_results:
        print("No se encontraron imágenes para procesar.")
        return False

    print(f"Generando PDF: {output_file}...")
    create_pdf_from_text_results(ocr_results, output_file)
    return True

def main():
    INPUT_FOLDER = 'imagenes_entrada'
    OUTPUT_FILE = 'resultado_clinico.pdf'
    
    # Extraer la llave de Gemini desde el entorno o archivo `.env`
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    if not GEMINI_API_KEY:
        print("Error: No se encontró la GEMINI_API_KEY en el archivo .env")
        return

    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"He creado la carpeta '{INPUT_FOLDER}'. Por favor, coloca tus imágenes/PDFs ahí.")
        return

    generate_from_folder(INPUT_FOLDER, OUTPUT_FILE, GEMINI_API_KEY)

if __name__ == "__main__":
    main()
