import requests
import json

class OCRSpaceClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.url = "https://api.ocr.space/parse/image"

    def ocr_file(self, filename, language='spa'):
        payload = {
            'isOverlayRequired': False,
            'apikey': self.api_key,
            'language': language,
            'OCREngine': 2,
        }
        with open(filename, 'rb') as f:
            r = requests.post(self.url,
                              files={filename: f},
                              data=payload,
                              )
        return r.content.decode()

    def extract_text(self, filename, language='spa'):

        try:
            result = self.ocr_file(filename, language)
            result_json = json.loads(result)
            
            if result_json.get('OCRExitCode') == 1:
                parsed_results = result_json.get('ParsedResults', [])
                full_text = ""
                for res in parsed_results:
                    full_text += res.get('ParsedText', '')
                return full_text
            else:
                error_msg = result_json.get('ErrorMessage', 'Unknown error')
                print(f"OCR Space Error: {error_msg}")
                return f"Error: {error_msg}"
        except Exception as e:
            return f"Exception during OCR: {str(e)}"
