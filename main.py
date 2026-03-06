import os
from fpdf import FPDF
from ocr_processor import process_images_in_folder

class OCRToPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'Documento de Historia Clínica - Procesado por OCR', border=0, new_x="LMARGIN", new_y="NEXT", align='C')
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
        pdf.cell(0, 10, f"DOCUMENTO: {clean_str(filename.upper())}", new_x="LMARGIN", new_y="NEXT", border=0, fill=True, align='C')
        pdf.ln(5)

        # Structured Data Section
        pdf.set_text_color(*TEXT_COLOR)
        pdf.set_font("helvetica", 'B', 11)
        pdf.set_draw_color(*PRIMARY_COLOR)
        pdf.cell(0, 8, " INFORMACIÓN PRINCIPAL DEL PACIENTE", new_x="LMARGIN", new_y="NEXT", border="B")
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

        pdf.ln(10)

        # Full Text Section
        pdf.set_font("helvetica", 'B', 11)
        pdf.cell(0, 8, " TEXTO COMPLETO RECONOCIDO (OCR)", new_x="LMARGIN", new_y="NEXT", border="B")
        pdf.ln(3)
        
        pdf.set_font("helvetica", size=8)
        pdf.set_text_color(100, 100, 100)
        
        clean_text = clean_str(text)
        pdf.multi_cell(0, 4, clean_text)

    pdf.output(output_filename)
    print(f"PDF generado con éxito: {output_filename}")

def main():
    INPUT_FOLDER = 'imagenes_entrada'
    OUTPUT_FILE = 'resultado_clinico.pdf'
    
    # OCR Space API Key
    OCR_API_KEY = "K88534196088957"

    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        print(f"He creado la carpeta '{INPUT_FOLDER}'. Por favor, coloca tus imágenes ahí.")
        return

    print("Iniciando procesamiento OCR con OCR Space API...")
    ocr_results = process_images_in_folder(INPUT_FOLDER, OCR_API_KEY)

    if not ocr_results:
        print("No se encontraron imágenes para procesar.")
        return

    print(f"Generando PDF: {OUTPUT_FILE}...")
    create_pdf_from_text_results(ocr_results, OUTPUT_FILE)

if __name__ == "__main__":
    main()
