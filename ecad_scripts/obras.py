import os
import re
import time
import logging
import warnings

import PyPDF2
import pandas as pd
from openpyxl import Workbook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)

warnings.filterwarnings("ignore", category=UserWarning)


def extract_text_from_pdf(pdf_path):
    text = ""
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def extract_data_referente(text):
    m = re.search(r"\b[A-ZÇ]{3,9}/\d{4}\b", text)
    return m.group(0) if m else None


def process_text(text):
    data = []
    lines = text.split("\n")
    collect = False
    total_from_pdf = 0.0
    capture_next_line = False
    data_referente = extract_data_referente(text)

    for line in lines:
        if "OBRA" in line:
            collect = True

        if capture_next_line:
            m = re.search(r"([\d.,]+)", line)
            if m:
                s = m.group(1).replace(".", "").replace(",", ".")
                try:
                    total_from_pdf = float(s)
                except ValueError:
                    pass
            capture_next_line = False

        if "TOTAL GERAL" in line:
            capture_next_line = True

        if collect and re.match(r"^\d{2,}", line):
            parts = line.split()
            codigo = parts[0]
            try:
                idx = next(
                    i for i, p in enumerate(parts)
                    if re.match(r"^\d{1,3}(?:\.\d{3})*,\d{2}|\d{9}$", p)
                )
                nome = " ".join(parts[1:idx])
                rateio_raw = parts[idx]
                rateio = float(rateio_raw.replace(".", "").replace(",", "."))
                data.append([codigo, nome, rateio, data_referente])
            except Exception:
                continue

    return data, total_from_pdf


def run(base_dir: str):
    start = time.time()

    pdf_dir = os.path.join(base_dir, "s_pdf_organizados")
    out_dir = os.path.join(base_dir, "s_tabelas", "obras")
    comp_dir = os.path.join(base_dir, "s_tabelas", "compiladas")

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(comp_dir, exist_ok=True)

    all_rows = []

    for fname in os.listdir(pdf_dir):
        if not fname.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_dir, fname)
        text = extract_text_from_pdf(pdf_path)
        rows, _ = process_text(text)

        for r in rows:
            all_rows.append([fname] + r)

    if not all_rows:
        return pd.DataFrame(), None

    df = pd.DataFrame(
        all_rows,
        columns=["Nome Arquivo", "Codigo ECAD", "Nome Obra", "Rateio", "Data"]
    )

    df["Rateio"] = pd.to_numeric(df["Rateio"], errors="coerce").fillna(0)

    def conv_data(txt):
        meses = {
            "JANEIRO": "01", "FEVEREIRO": "02", "MARCO": "03", "ABRIL": "04",
            "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08",
            "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12"
        }
        if isinstance(txt, str):
            txt = txt.upper().replace("Ç", "C")
            for m, n in meses.items():
                if m in txt:
                    ano = re.search(r"\d{4}", txt)
                    if ano:
                        return pd.to_datetime(f"01/{n}/{ano.group(0)}", dayfirst=True)
        return pd.NaT

    df["Data"] = df["Data"].apply(conv_data)

    out_path = os.path.join(comp_dir, "tabela_compilada_Obras.xlsx")
    df.to_excel(out_path, index=False)

    logging.info("Obras processadas em %.2f s", time.time() - start)
    return df, out_path
