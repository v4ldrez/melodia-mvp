import os
import time
import re
import warnings
import logging

import pdfplumber
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
warnings.filterwarnings("ignore", category=UserWarning, module="pdfminer")
logging.getLogger("pdfminer").setLevel(logging.ERROR)

date_pattern = re.compile(r'\b[A-ZÇ]{3,9}/\d{4}\b')
numeric_pattern = re.compile(r'^\d{1,3}(?:\.\d{3})*,\d{2}$')


def extract_data_referente(text):
    match = date_pattern.search(text)
    return match.group(0) if match else None


def process_pdf(pdf_path: str, pasta_excel: str):
    filename = os.path.basename(pdf_path)
    logging.info(f"🔍 Processando categorias: {filename}")

    start_page = end_page = None
    data_referente = None
    page_texts = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            page_texts.append(text)

            if (d := extract_data_referente(text)):
                data_referente = d

            if start_page is None and "POR CATEGORIA" in text:
                start_page = i
            if start_page and " POR RUBRICA" in text:
                end_page = i
                break

    if start_page is None or end_page is None:
        logging.error(f"❌ Tabela POR CATEGORIA não encontrada em: {filename}")
        return

    segments = []
    for i in range(start_page, end_page + 1):
        txt = page_texts[i - 1]
        if i == start_page:
            idx = txt.find("POR CATEGORIA")
            txt = txt[idx:] if idx != -1 else txt
        if i == end_page:
            idx = txt.find("POR RUBRICA")
            txt = txt[: idx + len("POR RUBRICA")] if idx != -1 else txt
        segments.append(txt)

    combined = "\n".join(segments).splitlines()

    header = [
        "CATEGORIA", "DISTRIBUIÇÃO", "LIBERAÇÃO CRÉD. RETIDO",
        "LIBERAÇÃO DE PENDENTE", "LIBERAÇÃO DE PARÂMETRO",
        "AJUSTES", "TOTAL GERAL", "DATA REFERENTE"
    ]
    data = []
    exclude = False

    for line in combined:
        if line.startswith("EXEC. - NÚM. DE EXECUÇÕES"):
            exclude = True
        if line.startswith("OBRA RUBRICA PERÍODO RENDIMENTO % RATEIO CORREÇÃO EXEC (OC)"):
            exclude = False
            continue
        if exclude or not line.strip() or line.startswith(("POR CATEGORIA", "TOTAL")):
            continue

        parts = line.split()
        nome_parts, valores = [], []

        for p in parts:
            if numeric_pattern.match(p) or p == "---":
                valores.append(p)
            else:
                nome_parts.append(p)

        nome = " ".join(nome_parts)
        while len(valores) < len(header) - 2:
            valores.insert(0, "---")
        valores.append(data_referente)

        data.append([nome] + valores)

    df = pd.DataFrame(data, columns=header)

    nome_excel = f"tabela_extraida_{os.path.splitext(filename)[0]}.xlsx"
    caminho_excel = os.path.join(pasta_excel, nome_excel)
    df.to_excel(caminho_excel, index=False)
    logging.info(f"✅ Exportado para: {caminho_excel}")


def compilar_excels(pasta_excel: str) -> pd.DataFrame:
    arquivos = [f for f in os.listdir(pasta_excel) if f.lower().endswith(".xlsx")]
    logging.info(f"📄 {len(arquivos)} arquivos encontrados (categorias).")

    dfs = []
    for arquivo in arquivos:
        caminho = os.path.join(pasta_excel, arquivo)
        try:
            dfs.append(pd.read_excel(caminho))
        except Exception as e:
            logging.error(f"Erro ao ler {arquivo}: {e}")

    if not dfs:
        return pd.DataFrame()

    compilado = pd.concat(dfs, ignore_index=True)

    if "TOTAL GERAL" in compilado.columns:
        compilado = compilado[compilado["TOTAL GERAL"] != "---"]

    return compilado


def formatar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    colunas_numericas = [
        "DISTRIBUIÇÃO",
        "LIBERAÇÃO CRÉD. RETIDO",
        "LIBERAÇÃO DE PENDENTE",
        "LIBERAÇÃO DE PARÂMETRO",
        "AJUSTES",
        "TOTAL GERAL"
    ]

    def limpar_valor(val):
        if pd.isna(val) or str(val).strip() == "---":
            return 0.0
        val = str(val).strip()
        if "." in val and "," not in val:
            try:
                return float(val)
            except ValueError:
                return 0.0
        val = val.replace(".", "").replace(",", ".")
        try:
            return float(val)
        except ValueError:
            return 0.0

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].apply(limpar_valor)

    if "DATA REFERENTE" in df.columns:
        def converter_data(texto):
            meses = {
                "JANEIRO": "01", "FEVEREIRO": "02", "MARÇO": "03", "ABRIL": "04",
                "MAIO": "05", "JUNHO": "06", "JULHO": "07", "AGOSTO": "08",
                "SETEMBRO": "09", "OUTUBRO": "10", "NOVEMBRO": "11", "DEZEMBRO": "12"
            }
            if isinstance(texto, str):
                texto = texto.upper()
                for nome_mes, num_mes in meses.items():
                    if nome_mes in texto:
                        match = re.search(r'\d{4}', texto)
                        if match:
                            return pd.to_datetime(f"01/{num_mes}/{match.group(0)}", dayfirst=True, errors='coerce')
            return pd.NaT

        df["DATA REFERENTE"] = df["DATA REFERENTE"].apply(converter_data)

    return df


def run(base_dir: str):
    inicio = time.time()

    pasta_pdfs = os.path.join(base_dir, "s_pdf_organizados")
    pasta_excel = os.path.join(base_dir, "s_tabelas", "categorias")
    arquivo_compilado = os.path.join(base_dir, "s_tabelas", "compiladas", "tabela_compilada_categorias.xlsx")

    os.makedirs(pasta_excel, exist_ok=True)
    os.makedirs(os.path.dirname(arquivo_compilado), exist_ok=True)

    for arquivo in os.listdir(pasta_pdfs):
        if arquivo.lower().endswith(".pdf"):
            process_pdf(os.path.join(pasta_pdfs, arquivo), pasta_excel)

    df_compilado = compilar_excels(pasta_excel)
    df_compilado = formatar_dataframe(df_compilado)

    if not df_compilado.empty:
        df_compilado.to_excel(arquivo_compilado, index=False)
        logging.info(f"📁 Compilado categorias salvo em: {arquivo_compilado}")
    else:
        logging.warning("⚠️ Compilado categorias vazio.")

    duracao = time.time() - inicio
    logging.info(f"⏱️ Categorias finalizado em: {duracao:.2f} s")
    return df_compilado, arquivo_compilado


if __name__ == "__main__":
    run(os.getcwd())
