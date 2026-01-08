import os
import re
import time
import warnings
import logging

import PyPDF2
import pandas as pd
from openpyxl import Workbook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
warnings.filterwarnings("ignore", category=UserWarning, module='pdfminer')


def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def extract_data_referente(text):
    m = re.search(r'\b[A-ZÇ]{3,9}/\d{4}\b', text)
    return m.group(0) if m else None


def process_text(text):
    data = []
    lines = text.split('\n')
    collect = False
    total_from_pdf = 0.0
    capture_next_line = False
    data_referente = extract_data_referente(text)

    for line in lines:
        if 'OBRA' in line:
            collect = True

        if capture_next_line:
            m = re.search(r'([\d.,]+)', line)
            if m:
                s = m.group(1).replace('.', '').replace(',', '.')
                if s.count('.') > 1:
                    parts = s.split('.')
                    s = ''.join(parts[:-1]) + '.' + parts[-1]
                try:
                    total_from_pdf = float(s)
                except ValueError:
                    logging.error(f"Erro ao converter '{s}' em float.")
                capture_next_line = False

        if 'TOTAL GERAL' in line:
            capture_next_line = True

        if collect and re.match(r'^\d{2,}', line):
            parts = line.split()
            codigo = parts[0]
            try:
                idx = next(i for i, p in enumerate(parts) if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}|\d{9}$', p))
                nome = ' '.join(parts[1:idx])
                if nome:
                    rateio_raw = parts[idx]
                    rateio_tratado = rateio_raw.replace('.', '').replace(',', '.')
                    try:
                        rateio_float = float(rateio_tratado)
                        data.append([codigo, nome, rateio_float, data_referente])
                    except ValueError:
                        logging.warning(f"🔴 Linha ignorada: rateio inválido '{rateio_raw}'. Linha: '{line}'")
                        continue
            except StopIteration:
                continue

    return data, total_from_pdf


def save_to_excel(data, output_path, pdf_filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "Dados ECAD"
    ws.append(['Nome Arquivo', 'Código ECAD', 'Nome Obra', 'Rateio', 'Data'])

    total_rateio = 0.0
    for row in data:
        ws.append([pdf_filename] + row)
        total_rateio += row[2]

    wb.save(output_path)
    return total_rateio


def formatar_dataframe_obras(df: pd.DataFrame) -> pd.DataFrame:
    df["Nome Arquivo"] = df["Nome Arquivo"].astype(str)
    df["Nome Obra"] = df["Nome Obra"].astype(str)
    df["Código ECAD"] = pd.to_numeric(df["Código ECAD"], errors="coerce").fillna(0).astype(int)

    def limpar_valor_rateio(val):
        if pd.isna(val) or str(val).strip() == '---':
            return 0.0
        val = str(val).strip()
        if '.' in val and ',' not in val:
            try:
                return float(val)
            except ValueError:
                return 0.0
        val = val.replace('.', '').replace(',', '.')
        try:
            return float(val)
        except ValueError:
            return 0.0

    df["Rateio"] = df["Rateio"].apply(limpar_valor_rateio)

    def converter_data(texto):
        meses = {
            "JANEIRO": "01", "FEVEREI
