import os
from ocr_space_client import OCRSpaceClient
from data_extractor import ClinicalDataExtractor

def process_images_in_folder(folder_path, api_key):

    results = []
    valid_extensions = ('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.pdf')
    
    if not os.path.exists(folder_path):
        print(f"Error: Folder {folder_path} does not exist.")
        return results

    client = OCRSpaceClient(api_key)
    extractor = ClinicalDataExtractor()
    
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)]
    files.sort() 

    for filename in files:
        full_path = os.path.join(folder_path, filename)
        print(f"Processing (OCR Space + Extraction): {filename}...")
        
        raw_text = client.extract_text(full_path, language='spa')

        if raw_text and not raw_text.startswith("Error:"):
            structured_data = extractor.extract(raw_text)
        else:
            print(f"Skipping extraction for {filename} due to OCR error.")
            structured_data = {k: "No disponible (Error OCR)" for k in [
                'identificacion', 'paciente', 'fecha_ingreso', 'fecha_atencion', 
                'fecha_cierre', 'fecha_nacimiento', 'telefono', 'direccion', 
                'empresa', 'contrato', 'municipio'
            ]}
        
        results.append({
            'filename': filename,
            'text': raw_text,
            'data': structured_data
        })
        
    return results
