import re

class ClinicalDataExtractor:
    def __init__(self):
        # Specific value patterns (more robust than label-based only)
        self.value_patterns = {
            'identificacion': r'([Cc][Cc]|[Tt][Ii])\s*[-]?\s*(\d{5,12})',
            'fecha': r'(\d{4}[/-]\d{2}[/-]\d{2}(?:\s\d{2}:\d{2}(?::\d{2})?)?)',
            'telefono': r'(?<!\d)(3\d{9})(?!\d)', # 10 digit Colombian mobile starts with 3
            'correo': r'[\w\.-]+@[\w\.-]+\.\w+',
        }
        
        # Typos mapping for common OCR errors in labels
        self.typos = {
            r'Ingres[io][óo]n': 'Ingreso',
            r'Cl[ei]rre': 'Cierre',
            r'Pac[ie|l]ente': 'Paciente',
            r'Atencion': 'Atención',
            r'Naci': 'Nacimiento',
            r'Identificaci[onó]n': 'Identificación',
            r'Direcci[onó]n': 'Dirección'
        }

    def _clean_field(self, value):
        if not value or value == "No detectado":
            return "No detectado"
        
        # Remove trailing artifacts
        value = re.sub(r'[:;,\|\._\-]$', '', value).strip()
        
        # If value looks like a label or noise word, it's probably noise
        noise_labels = [
            'paciente', 'fecha', 'hora', 'tipo', 'nit', 'folio', 'historia', 
            'clinica', 'identificación', 'actual', 'nota', 'medico', 'especialista',
            'examen', 'fisico', 'evolucion', 'enfermedad', 'motivo', 'consulta'
        ]
        if value.lower() in noise_labels:
            return "No detectado"
            
        return value

    def _is_valid_name(self, name):
        if not name or name == "No detectado": return False
        name_up = name.upper()
        # Common non-name words found in OCR noise, headers or clinical findings
        excluded_words = [
            "LITOTRICIA", "BOCAGRANDE", "HISTORIA", "CLINICA", "IDENTIFICACION", 
            "EPS", "SURA", "CONTRATO", "DATOS", "PACIENTE", "CUAL", "EXAMEN", 
            "FISICO", "OTOSCOPIA", "MOTIVO", "CONSULTA", "PLAN", "TRATAMIENTO",
            "REVISION", "SISTEMAS", "ANTECEDENTES", "DIAGNOSTICO", "CONDUCTA",
            "PROFESIONAL", "ESPECIALISTA", "DOCTOR", "MEDICO", "REGISTRO", 
            "FIRMADO", "ELECTRONICAMENTE", "ATENDIDO", "LUZ MEIRA", "CODIGO", 
            "PRESTADOR", "ORDENADO", "VALORACION", "PROCEDIMIENTO", "INFORME", 
            "RESULTADOS", "ACTUAL", "IVN", "EVOLUCION", "NOTA", "ENFERMEDAD",
            "PAGINA", "USUARIO", "ESTRATO", "ESTADO", "CIVIL", "MODERADORA", 
            "RANGO", "CRA", "DIRECCION", "BOCAGRANDE CRA", "TELEFONO", "MUNICIPIO",
            "SIGNOS", "INFECCION", "NISTAGMO", "NORMAL", "PUPILAS", "PUFF", "CADA", 
            "FOSA", "NASAL", "ORAL", "GOTAS", "CAPSULA", "TABLETA", "MG", "ML", "VIA",
            "DIAS", "HORAS", "APLICAR", "ADMINISTRAR", "TRATAMIENTO", "PLAN",
            "MEMBRANA", "TIMPANICA", "INTEGRA", "CONDUCTO", "AUDITIVO", "EXTERNO",
            "PRESENTE", "EVDIENCIA", "TAPON", "CERA", "EXTRAIDO", "LUMINOSO",
            "RINOSCOPIA", "SEPTUM", "FUNCIONAL", "CORNETES", "HIPERTROFICOS",
            "MUCOSA", "HUMEDA", "OROFARINGE", "AMIGDALAS", "EUTROFICAS", "SIN",
            "ROMBERG", "PRINCIPAL", "RELACIONADO", "IMPRESION", "ESPECIFICADOS"
        ]
        if any(w in name_up for w in excluded_words):
            return False
        
        # Names shouldn't have too many numbers or symbols
        if len(re.findall(r'[0-9#\.]', name)) > 1: return False
        
        words = name.split()
        if len(words) < 2: return False
        if len(name) < 5: return False
        
        return True

    def _score_name_candidate(self, cand, text, id_match, dob_match):
        score = 0
        cand_up = cand.upper()
        idx = text.find(cand)
        
        # 1. Linguistic structure
        words = cand.split()
        if len(words) >= 3: score += 40 # Full names (3-4 words) are best
        if len(words) == 2: score += 20
        if 8 <= len(cand) <= 35: score += 20
        
        # 2. Casing (Prefer uppercase but allow mixed as fallback)
        if cand.isupper(): score += 30
        
        # 3. Anchor Proximity
        if id_match:
            dist = abs(idx - id_match.start())
            if dist < 120: score += 80  # Name is almost always very near ID
            elif dist < 300: score += 30
        
        if dob_match:
            dist = abs(idx - dob_match.start())
            if dist < 150: score += 60
            elif dist < 350: score += 20
            
        # 4. Same-Line Label Booster (Massive boost if "Paciente" is on same line)
        line_start = text.rfind('\n', 0, idx) + 1
        line_end = text.find('\n', idx)
        if line_end == -1: line_end = len(text)
        current_line = text[line_start:line_end].upper()
        
        if any(w in current_line for w in ["PACIENTE", "NOMBRE", "DATOS"]):
            score += 100
            # Extra boost if the label is strictly before the name in the same line
            label_match = re.search(r'(?:PACIENTE|NOMBRE)\s*:?', current_line)
            if label_match and label_match.start() < current_line.find(cand_up):
                score += 50
        
        # 4.1 Header Booster (HISTORIA CLINICA / HISTORIA CLÍNICA)
        pre_context_near = text[max(0, idx-60):idx].upper()
        if "HISTORIA" in pre_context_near and ("CLINICA" in pre_context_near or "CLÍNICA" in pre_context_near):
            score += 80
        
        # 5. Negative Anchors (Addresses, Professional info)
        if any(w in current_line for w in ["POR:", "PROFESIONAL", "DR.", "MEDICO", "FIRMA"]):
            score -= 150
            
        pre_context = text[max(0, idx-150):idx].upper()
        if any(w in pre_context for w in ["DIRECCION", "BOCAGRANDE", "CALLE", "CRA", "TEL"]):
            score -= 40
            
        # 6. Global Exclusions and Label protection (Accents handled)
        clinical_noise = {
            "FECHA", "INGRESO", "ATENCION", "ATENCIÓN", "CIERRE", "NACIMIENTO", 
            "IDENTIFICACION", "IDENTIFICACIÓN", "NOMBRE", "PACIENTE", "DATOS", 
            "CLINICA", "CLÍNICA", "HISTORIA", "LITOTRICIA", "BOCAGRANDE", "ACTUAL", 
            "DIRECCION", "DIRECCIÓN", "TELEFONO", "TELÉFONO", "MUNICIPIO", 
            "CONTRATO", "EMPRESA", "EPS", "SURA", "FIRMA", "PAGINA", "PÁGINA",
            "USUARIO", "RESULTADOS", "CRA", "CARRERA", "CENTRO", "MEDICO", "MÉDICO",
            "SIGNOS", "INFECCION", "INFECCIÓN", "NISTAGMO", "REFLEJO", "OJO", "OJO", 
            "OJOS", "PUPILAS", "NORMAL", "HALLAZGOS", "REVISION", "SISTEMAS",
            "PUFF", "NASAL", "FOSA", "CADA", "VIA", "ORAL", "GOTAS", "MG", "ML",
            "DURANTE", "DIAS", "HORAS", "APLICAR", "DOSIS", "RECETA", "FORMULA", 
            "MÉDICO", "PACLENTE", "PACLENT", "INGRESIÓN", "UNIDAD", "CANTIDAD",
            "NIGHT", "DAY", "TABLETS", "CAPSULES", "SPRAY", "CADA", "MINUTOS"
        }
        
        # Penalize if it contains or EXACTLY matches any noise words
        words_in_cand = set(cand_up.split())
        if words_in_cand.intersection(clinical_noise):
            score -= 500
            
        # Specific double-word labels
        if any(w in cand_up for w in ["FECHA", "INGRESO", "ATENCION", "CIERRE", "NACIMIENTO", "HORA", "PUFF EN"]):
            score -= 400
            
        # 7. Late-Document Penalty (Names are usually at the top)
        # Relaxed: only penalize if it's past 60% of the document
        relative_pos = idx / len(text)
        if relative_pos > 0.6:
            # Only allow if it's strictly near an ID or DOB
            if (id_match and abs(idx - id_match.start()) < 100) or (dob_match and abs(idx - dob_match.start()) < 100):
                pass
            else:
                score -= 60
        
        return score

    def extract(self, text):
        results = {}
        # 0. NORMALIZE WHITESPACE AT THE START (Consistency Fix)
        # This makes the real OCR text look closer to the standalone sample text
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Pre-extract anchors for scoring
        id_match = re.search(self.value_patterns['identificacion'], text)
        dob_match = re.search(r'(?:Naci|Nacido|Nacimiento).*?(\d{4}[/-]\d{2}[/-]\d{2})', text, re.IGNORECASE | re.DOTALL)
        
        # 1. Extraction by Global Patterns (High Confidence)
        
        # ID
        results['identificacion'] = f"{id_match.group(1)} {id_match.group(2)}" if id_match else "No detectado"

        # Teléfono
        tel_match = re.search(self.value_patterns['telefono'], text)
        results['telefono'] = tel_match.group(1) if tel_match else "No detectado"

        # --- SMART NAME EXTRACTION ---
        # Refined regex: names are usually 2-4 words
        caps_candidates = re.findall(r'\b[A-ZÁÉÍÓÚÑñ]{3,}(?:\s+[A-ZÁÉÍÓÚÑñ]{2,}){1,4}\b', text)
        mixed_candidates = re.findall(r'\b[A-ZÁÉÍÓÚÑñ][a-záéíóúñ]{1,}(?:\s+[A-ZÁÉÍÓÚÑñ][a-záéíóúñ]{1,}){1,3}\b', text)
        
        all_candidates = set(caps_candidates + mixed_candidates)
        scored_candidates = []
        
        for cand in all_candidates:
            if self._is_valid_name(cand):
                score = self._score_name_candidate(cand, text, id_match, dob_match)
                if score > 40: 
                    scored_candidates.append((cand, score))
        
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # DEBUG: Ver candidatos en consola durante el proceso real
        if scored_candidates:
            winner, top_score = scored_candidates[0]
            print(f"DEBUG Extracción: Candidato Ganador '{winner}' con Score {top_score}")
        else:
            print("DEBUG Extracción: No se encontraron candidatos con score > 40")
        
        final_name = scored_candidates[0][0] if scored_candidates else "No detectado"
        
        # FINAL CLEANUP: Strip pervasive headers and junk words
        if final_name != "No detectado":
            prefixes_to_strip = [
                "CLINICA", "CLÍNICA", "HISTORIA", "DATOS", "PACIENTE", "DEL", "NOMBRE", 
                "LITOTRICIA", "SURA", "EPS", "NIT", "IDENTIFICACION", "IDENTIFICACIÓN"
            ]
            words = final_name.split()
            while words and words[0].upper().strip(':') in prefixes_to_strip:
                words.pop(0)
            final_name = " ".join(words)
            if len(words) < 2: final_name = "No detectado" # Too short after stripping
            
        results['paciente'] = final_name

        # 2. Contextual Search (Labels + Vicinity)
        
        def find_best_near_label(label_regexes, search_in_text, value_regex=None):
            if isinstance(label_regexes, str):
                label_regexes = [label_regexes]
                
            best_val = "No detectado"
            
            for label_regex in label_regexes:
                matches = list(re.finditer(label_regex, search_in_text, re.IGNORECASE))
                for m in matches:
                    start_idx = m.end()
                    # Look ahead significantly to handle multi-line gaps
                    vicinity = search_in_text[start_idx:start_idx + 350]
                    
                    if value_regex:
                        v_match = re.search(value_regex, vicinity)
                        if v_match:
                            val = v_match.group(1) if v_match.groups() else v_match.group(0)
                            val = val.strip()
                            if val and len(val) > 2:
                                best_val = val
                                # If we found a structured value (date/ID), we usually trust it immediately
                                if value_regex in [self.value_patterns['fecha'], self.value_patterns['identificacion']]:
                                    return val
                    else:
                        # Improved generic line-by-line search
                        v_lines = vicinity.split('\n')
                        for line in v_lines:
                            line = line.strip()
                            if not line or len(line) < 3: continue
                            
                            # Check if this line is just another label
                            is_label = False
                            all_clinical_labels = [
                                r'Pac[ie|l]ente', r'Fecha', r'Empresa', r'Contrato', r'Municipio', 
                                r'Identificaci[oó]n', r'Direcci[oó]n', r'Nit', r'Tipo', r'Edad', 
                                r'Sexo', r'Acompañante', r'Ingreso', r'Atenci[oó]n', r'Cl[ie]rre',
                                r'Examen\s+F[ií]sico', r'Otoscopia', r'Cual', r'Motivo\s+Consulta',
                                r'Nacimiento', r'F\.?\s*Naci', r'Nombre', r'Informaci[oó]n', r'Datos',
                                r'Diagn[oó]stico', r'Tratamiento', r'Plan', r'Conducta', r'Evoluci[oó]n'
                            ]
                            for l in all_clinical_labels:
                                if re.match(r'^' + l + r'\s*:?', line, re.IGNORECASE):
                                    is_label = True
                                    break
                            
                            if is_label:
                                # If the line starts with a label, try to strip it and see if data remains
                                for l in all_clinical_labels:
                                    parts = re.split(r'^' + l + r'\s*:?', line, maxsplit=1, flags=re.IGNORECASE)
                                    if len(parts) > 1 and len(parts[1].strip()) > 3:
                                        sub_line = parts[1].strip()
                                        if not any(re.match(sl + r'\s*:?', sub_line, re.IGNORECASE) for sl in all_clinical_labels):
                                            return sub_line
                                continue 
                                
                            return line
            return best_val

        # --- FIELD EXTRACTION ---
        
        # Dates (Grouped for reliability)
        results['fecha_ingreso'] = find_best_near_label([r'Fecha[\s]de?[\s]Ingres[io][óo]n\s*:?', r'Fecha[\s]Ingreso\s*:?'], text, self.value_patterns['fecha'])
        results['fecha_atencion'] = find_best_near_label(r'Fecha[\s]Atencion\s*:?', text, self.value_patterns['fecha'])
        results['fecha_cierre'] = find_best_near_label(r'Fecha[\s]Cl?[ei]rre\s*:?', text, self.value_patterns['fecha'])
        
        # Fecha Nacimiento: more variations
        nac_labels = [r'Fecha[\s]Naci\s*:?', r'Naci[oó]\s*:?', r'F\.?\s*Nacimiento\s*:?', r'F\.?\s*Naci\s*:?', r'Edad\s*:?']
        results['fecha_nacimiento'] = find_best_near_label(nac_labels, text, self.value_patterns['fecha'])
        if results['fecha_nacimiento'] == "No detectado":
            # Very broad search for a date near word "Naci"
            match = re.search(r'Naci[a-z]*\s*:?\s*.*?(\d{4}[/-]\d{2}[/-]\d{2})', text, re.IGNORECASE | re.DOTALL)
            if match:
                results['fecha_nacimiento'] = match.group(1)
            else:
                # Fallback: any date that isn't one of the other dates
                all_dates = re.findall(r'(\d{4}[/-]\d{2}[/-]\d{2})', text)
                used_dates = [results[k] for k in ['fecha_ingreso', 'fecha_atencion', 'fecha_cierre'] if results[k] != "No detectado"]
                for d in all_dates:
                    if d not in used_dates:
                        results['fecha_nacimiento'] = d
                        break

        # Business info
        # Stop at labels or newlines (though now newlines are spaces, so we limit word count or use negative lookahead)
        results['empresa'] = find_best_near_label(r'Empresa\s*:?', text, r'([A-ZÁÍÓÚÉÑñ\s0-9]{3,25})')
        results['contrato'] = find_best_near_label(r'Contrato\s*:?', text)
        results['municipio'] = find_best_near_label(r'Municipio\s*:?', text, r'([A-ZÁÍÓÚÉÑñ]{4,20})')
        
        # Address - often multi-line
        results['direccion'] = find_best_near_label(r'Direcci[oó]n\s*:?', text)
        
        # Custom field
        results['cartagena'] = "SI" if "CARTAGENA" in text.upper() else "No detectado"

        # Final field cleaning
        for k in results:
            results[k] = self._clean_field(results[k])

        return results

if __name__ == "__main__":
    sample_text = """
    LITOTRICIA S.A.
    NIT: 8002348604
    Dirección: BOCAGRANDE CRA. 6 No. 5 - 15
    Fecha de Impresión: 2025/11/19 10:05:31
    Datos del Paciente
    Identificación:
    Fecha Ingreso: 2025/11/19
    HISTORIA CLÍNICA
    DUEÑAS FERNANDEZ MAURICIO ARTURO
    Ingreso: 1302380
    Fecha Naci: 2003-11-16
    Telefono: 3135317276
    Municipio: CARTAGENA
    Empresa: EPS SURA
    Contrato: EPS SURA: contributivo CONSOLIDADO Profesional: LUZ MEIRA MATURANA
    """
    extractor = ClinicalDataExtractor()
    data = extractor.extract(sample_text)
    print("\n--- Resultados de la Extracción Mejorada ---")
    for key, value in data.items():
        print(f"{key}: {value}")
