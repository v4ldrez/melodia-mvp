import os
import re
import time
import logging
from PyPDF2 import PdfMerger
from pypdf import PdfReader, PdfWriter
from plyer import notification


# === CONFIGURAÇÃO DE LOG ===
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# === CAMINHO BASE: altere só isso ===
BASE_PATH = r'C:\Users\guilherme.cristo\Documents\ECAD'

# === CAMINHOS DERIVADOS ===
INPUT_MERGE_DIR = os.path.join(BASE_PATH, 'en_PDF')
MERGED_PDF_OUTPUT = os.path.join(BASE_PATH, 'i_pdf', 'compilado.pdf')
SPLIT_INPUT_DIR = os.path.join(BASE_PATH, 'i_pdf')
SPLIT_OUTPUT_DIRS = [os.path.join(BASE_PATH, 's_pdf_organizados')]

# === EXPRESSÃO REGULAR ===
date_pattern = re.compile(r'\b[A-ZÇ]{3,9}/\d{4}\b')

# === FUNÇÕES ===


def merge_pdfs(pdf_list, output_path):
    logger.info(f"Iniciando merge de {len(pdf_list)} PDF(s).")
    merger = PdfMerger()
    for pdf in pdf_list:
        logger.info(f"📎 Adicionando: {os.path.basename(pdf)}")
        merger.append(pdf)
    merger.write(output_path)
    merger.close()
    logger.info(f"✅ PDF compilado salvo em: {output_path}")


def extract_data_referente(text):
    match = date_pattern.search(text)
    return match.group(0) if match else None


def convert_date_to_filename(date_str):
    month_mapping = {
        'JANEIRO': '01', 'FEVEREIRO': '02', 'MARÇO': '03', 'ABRIL': '04',
        'MAIO': '05', 'JUNHO': '06', 'JULHO': '07', 'AGOSTO': '08',
        'SETEMBRO': '09', 'OUTUBRO': '10', 'NOVEMBRO': '11', 'DEZEMBRO': '12'
    }
    try:
        month_name, year = date_str.split('/')
        return f"{year}_{month_mapping.get(month_name)}"
    except Exception as e:
        logger.warning(f"❌ Erro ao converter data '{date_str}': {e}")
        return None


def split_pdf_by_text(input_pdf_path, output_folders, split_text="VALORES EXPRESSOS"):
    logger.info(f"🔍 Processando: {os.path.basename(input_pdf_path)}")
    try:
        reader = PdfReader(input_pdf_path)
    except Exception as e:
        logger.error(f"❌ Erro ao ler PDF: {e}")
        return

    writer = PdfWriter()
    data_referente = None

    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""

        current_date = extract_data_referente(page_text)
        if current_date:
            data_referente = current_date

        writer.add_page(page)

        if split_text in page_text:
            filename_date = convert_date_to_filename(
                data_referente) if data_referente else f"sem_data_{page_num+1}"
            file_name = f"{filename_date}.pdf"

            for folder in output_folders:
                os.makedirs(folder, exist_ok=True)
                output_pdf_path = os.path.join(folder, file_name)

                if os.path.exists(output_pdf_path):
                    logger.warning(
                        f"⚠️ Arquivo sobrescrito: {output_pdf_path}")

                with open(output_pdf_path, 'wb') as output_pdf:
                    writer.write(output_pdf)

                logger.info(f"📄 Exportado: {output_pdf_path}")

            writer = PdfWriter()

# === EXECUÇÃO PRINCIPAL ===


def main():
    start_time = time.time()
    logger.info("🚀 Iniciando o processamento...")

    # Etapa 1: Merge
    os.makedirs(os.path.dirname(MERGED_PDF_OUTPUT), exist_ok=True)
    pdfs_to_merge = sorted([
        os.path.join(INPUT_MERGE_DIR, f)
        for f in os.listdir(INPUT_MERGE_DIR)
        if f.lower().endswith('.pdf')
    ])

    if pdfs_to_merge:
        merge_pdfs(pdfs_to_merge, MERGED_PDF_OUTPUT)
    else:
        logger.warning("📭 Nenhum PDF encontrado para mesclagem.")

    # Etapa 2: Split
    pdf_files = [
        f for f in os.listdir(SPLIT_INPUT_DIR)
        if f.lower().endswith('.pdf')
    ]

    if not pdf_files:
        logger.warning("📭 Nenhum arquivo PDF encontrado para separar.")
    else:
        for pdf_file in pdf_files:
            input_pdf_path = os.path.join(SPLIT_INPUT_DIR, pdf_file)
            split_pdf_by_text(input_pdf_path, SPLIT_OUTPUT_DIRS)

    elapsed = time.time() - start_time
    logger.info(f"✅ Processamento finalizado em {elapsed:.2f} segundos.")

    notification.notify(
        title='Meses Separados',
        message='Processamento finalizado!',
        timeout=10
    )


if __name__ == "__main__":
    main()
