# ecad_scripts/obras.py  (substitua este arquivo)
import re
import logging
import pandas as pd
from pypdf import PdfReader

logger = logging.getLogger(__name__)

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

def _extract_total_geral_from_pdf_text(lines):
    """
    O seu código antigo captura o TOTAL GERAL lendo a linha seguinte.
    Mantive essa lógica, mas mais defensiva.
    """
    capture_next = False
    for line in lines:
        if capture_next:
            m = re.search(r"(\d{1,3}(?:\.\d{3})*,\d{2})", line)
            if m:
                return _br_money_to_float(m.group(1))
            capture_next = False
        if "TOTAL GERAL" in (line or ""):
            capture_next = True
    return None

def parse_obras_from_pdf_bytes(pdf_bytes: bytes):
    reader = PdfReader(pdf_bytes)
    full_text = ""
    for p in reader.pages:
        full_text += (p.extract_text() or "") + "\n"

    data_referente = _extract_data_referente(full_text)
    lines = full_text.splitlines()
    total_pdf = _extract_total_geral_from_pdf_text(lines)

    rows = []
    collecting = False

    for line in lines:
        if not line:
            continue

        # seu gatilho original
        if "OBRA" in line:
            collecting = True

        if not collecting:
            continue

        # Linhas de obra normalmente começam com código numérico
        if not re.match(r"^\d{2,}\s", line.strip()):
            continue

        parts = line.split()
        codigo = parts[0]

        # achar o ÚLTIMO token monetário da linha (evita confundir com códigos)
        money_tokens = [p for p in parts if MONEY_BR.match(p)]
        if not money_tokens:
            continue

        rateio_raw = money_tokens[-1]
        try:
            rateio = _br_money_to_float(rateio_raw)
        except Exception:
            continue

        # Nome: entre o código e o primeiro token monetário encontrado
        first_money_idx = next(i for i, p in enumerate(parts) if MONEY_BR.match(p))
        nome = " ".join(parts[1:first_money_idx]).strip()
        if not nome:
            continue

        rows.append([codigo, nome, rateio, data_referente])

    df = pd.DataFrame(rows, columns=["Código ECAD", "Nome Obra", "Rateio", "DATA REFERENTE"])
    df["Código ECAD"] = pd.to_numeric(df["Código ECAD"], errors="coerce")
    df["DATA REFERENTE"] = df["DATA REFERENTE"].apply(_data_referente_to_dt)

    total_calc = float(df["Rateio"].sum()) if not df.empty else 0.0
    return df, total_calc, total_pdf

def run(pdf_bytes: bytes):
    """
    Interface simples pro seu pipeline:
    retorna df_obras e também total calculado e total do PDF.
    """
    df, total_calc, total_pdf = parse_obras_from_pdf_bytes(pdf_bytes)

    # sanity check
    if total_pdf is not None and abs(total_calc - total_pdf) > 0.50:
        logger.warning(
            f"[OBRAS] Diferença detectada. Calculado={total_calc:.2f} vs PDF={total_pdf:.2f}"
        )

    return df
