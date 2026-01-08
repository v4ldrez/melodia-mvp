import os
import re
import time
import logging
import warnings

import pandas as pd
from pypdf import PdfReader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning)

# Aceita SOMENTE dinheiro BR: 1.234,56  ou 12,34  ou 123,45
MONEY_BR = re.compile(r"^\d{1,3}(?:\.\d{3})*,\d{2}$")
DATE_REF = re.compile(r"\b[A-ZÇ]{3,9}/\d{4}\b")

MESES = {
    "JANEIRO": "01", "FEVEREIRO": "02", "MARÇO": "03", "ABRIL": "04",
    "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08",
    "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12"
}

def _br_money_to_float(s: str) -> float:
    s = str(s).strip()
    s = s.replace(".", "").replace(",", ".")
    return float(s)

def _extract_data_referente(text: str):
    m = DATE_REF.search(text or "")
    return m.group(0) if m else None

def _data_referente_to_dt(dr: str):
    if not isinstance(dr, str):
        return pd.NaT
    t = dr.upper()
    for nome_mes, num_mes in MESES.items():
        if nome_mes in t:
            ano = re.search(r"\d{4}", t)
            if ano:
                return pd.to_datetime(f"01/{num_mes}/{ano.group(0)}", dayfirst=True, errors="coerce")
    return pd.NaT

def parse_obras_from_pdf_path(pdf_path: str):
    reader = PdfReader(pdf_path)
    full_text = ""
    for p in reader.pages:
        full_text += (p.extract_text() or "") + "\n"

    data_referente = _extract_data_referente(full_text)
    lines = full_text.splitlines()

    rows = []
    collecting = False

    for line in lines:
        if not line:
            continue

        if "OBRA" in line:
            collecting = True

        if not collecting:
            continue

        if not re.match(r"^\d{2,}\s", line.strip()):
            continue

        parts = line.split()
        codigo = parts[0]

        money_tokens = [p for p in parts if MONEY_BR.match(p)]
        if not money_tokens:
            continue

        rateio_raw = money_tokens[-1]
        try:
            rateio = _br_money_to_float(rateio_raw)
        except Exception:
            continue

        first_money_idx = next(i for i, p in enumerate(parts) if MONEY_BR.match(p))
        nome = " ".join(parts[1:first_money_idx]).strip()
        if not nome:
            continue

        rows.append([os.path.basename(pdf_path), codigo, nome, rateio, data_referente])

    df = pd.DataFrame(rows, columns=["Nome Arquivo", "Código ECAD", "Nome Obra", "Rateio", "Data"])
    if df.empty:
        return df

    df["Código ECAD"] = pd.to_numeric(df["Código ECAD"], errors="coerce")
    df["Rateio"] = pd.to_numeric(df["Rateio"], errors="coerce").fillna(0.0)
    df["Data"] = df["Data"].apply(_data_referente_to_dt)

    # cinto de segurança: evita valores absurdos por falha de parsing
    df = df[df["Rateio"].between(0, 1_000_000)]

    return df

def run(base_dir: str):
    """
    Lê PDFs já separados em:
      {base_dir}/s_pdf_organizados
    Retorna (df, caminho_compilado)
    """
    start = time.time()

    pdf_dir = os.path.join(base_dir, "s_pdf_organizados")
    comp_dir = os.path.join(base_dir, "s_tabelas", "compiladas")
    os.makedirs(comp_dir, exist_ok=True)

    dfs = []
    for fname in os.listdir(pdf_dir):
        if fname.lower().endswith(".pdf"):
            path = os.path.join(pdf_dir, fname)
            dfs.append(parse_obras_from_pdf_path(path))

    if not dfs:
        logger.warning("Nenhum PDF encontrado em s_pdf_organizados para obras.")
        return pd.DataFrame(), os.path.join(comp_dir, "tabela_compilada_Obras.xlsx")

    df = pd.concat([d for d in dfs if d is not None and not d.empty], ignore_index=True)
    out_path = os.path.join(comp_dir, "tabela_compilada_Obras.xlsx")
    df.to_excel(out_path, index=False)

    logger.info("Obras finalizado em %.2f s", time.time() - start)
    return df, out_path
