import os
import sys
import shutil
from pathlib import Path

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ecad_scripts.A_process_PDF import run as run_split
from ecad_scripts.categorias import run as run_categorias
from ecad_scripts.rubricas import run as run_rubricas
from ecad_scripts.obras import run as run_obras


def process_uploaded_pdf(pdf_path: str, base_dir: str, base_rubricas_path: str):
    """
    Recebe um PDF (caminho) e um base_dir isolado (workspace por upload).
    Gera:
      - PDFs separados por mês em s_pdf_organizados
      - Excels compilados em s_tabelas/compiladas
    Retorna 3 DataFrames (categorias, rubricas, obras).
    """
    base_dir = os.path.abspath(base_dir)

    en_pdf = Path(base_dir) / "en_PDF"
    i_pdf = Path(base_dir) / "i_pdf"
    en_pdf.mkdir(parents=True, exist_ok=True)
    i_pdf.mkdir(parents=True, exist_ok=True)

    # Coloca o PDF do upload em en_PDF
    target = en_pdf / Path(pdf_path).name
    if os.path.abspath(pdf_path) != str(target):
        shutil.copy2(pdf_path, target)

    # Para o split funcionar, precisa ter um PDF em i_pdf.
    # Se só tiver um PDF, copiamos para i_pdf/compilado.pdf.
    compiled = i_pdf / "compilado.pdf"
    with open(target, "rb") as r, open(compiled, "wb") as w:
        w.write(r.read())

    # 1) split em meses
    run_split(base_dir)

    # 2) extrair tabelas
    df_cat, _ = run_categorias(base_dir)
    df_rub, _ = run_rubricas(base_dir, base_rubricas_path=base_rubricas_path)
    df_obr, _ = run_obras(base_dir)

    return df_cat, df_rub, df_obr
