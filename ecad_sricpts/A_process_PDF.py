import os
import re
import time
import logging
from pathlib import Path

from PyPDF2 import PdfMerger
from pypdf import PdfReader, PdfWriter

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

date_pattern = re.compile(r'\b[A-ZÇ]{3,9}/\d{4}\b')


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


def split_pdf_by_text(input_pdf_path, output_folder, split_text="VALORES EXPRESSOS"):
    logger.info(f"🔍 Processando: {os.path.basename(input_pdf_path)}")
    try:
        reader = PdfReader(input_pdf_path)
    except Exception as e:
        logger.error(f"❌ Erro ao ler PDF: {e}")
        return

    os.makedirs(output_folder, exist_ok=True)

    writer = PdfWriter()
    data_referente = None

    for page_num, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""

        current_date = extract_data_referente(page_text)
        if current_date:
            data_referente = current_date

        writer.add_page(page)

        if split_text in page_text:
            filename_date = convert_date_to_filename(data_referente) if data_referente else f"sem_data_{page_num+1}"
            file_name = f"{filename_date}.pdf"
            output_pdf_path = os.path.join(output_folder, file_name)

            with open(output_pdf_path, 'wb') as output_pdf:
                writer.write(output_pdf)

            logger.info(f"📄 Exportado: {output_pdf_path}")
            writer = PdfWriter()


def run(base_dir: str) -> str:
    """
    Espera PDFs em:
      {base_dir}/en_PDF  (opcional, vários PDFs para merge)
      {base_dir}/i_pdf   (entrada para split; aqui fica o compilado ou o PDF único)
    Saída:
      {base_dir}/s_pdf_organizados  (PDFs separados por mês)
    """
    start_time = time.time()

    base = Path(base_dir)
    input_merge_dir = base / "en_PDF"
    merged_pdf_output = base / "i_pdf" / "compilado.pdf"
    split_input_dir = base / "i_pdf"
    split_output_dir = base / "s_pdf_organizados"

    input_merge_dir.mkdir(parents=True, exist_ok=True)
    split_input_dir.mkdir(parents=True, exist_ok=True)
    split_output_dir.mkdir(parents=True, exist_ok=True)

    # Etapa 1: Merge (se tiver mais de 1 PDF no en_PDF)
    pdfs_to_merge = sorted([
        str(input_merge_dir / f)
        for f in os.listdir(input_merge_dir)
        if f.lower().endswith('.pdf')
    ])

    if len(pdfs_to_merge) >= 2:
        merged_pdf_output.parent.mkdir(parents=True, exist_ok=True)
        merge_pdfs(pdfs_to_merge, str(merged_pdf_output))
    elif len(pdfs_to_merge) == 1:
        # Se só tem um PDF no en_PDF, copiamos para i_pdf/compilado.pdf para padronizar
        merged_pdf_output.parent.mkdir(parents=True, exist_ok=True)
        src = pdfs_to_merge[0]
        with open(src, "rb") as r, open(merged_pdf_output, "wb") as w:
            w.write(r.read())

    # Etapa 2: Split (processa qualquer PDF que estiver em i_pdf)
    pdf_files = [f for f in os.listdir(split_input_dir) if f.lower().endswith('.pdf')]
    if not pdf_files:
        logger.warning("📭 Nenhum arquivo PDF encontrado para separar em i_pdf.")
    else:
        for pdf_file in pdf_files:
            input_pdf_path = str(split_input_dir / pdf_file)
            split_pdf_by_text(input_pdf_path, str(split_output_dir))

    elapsed = time.time() - start_time
    logger.info(f"✅ Split finalizado em {elapsed:.2f} segundos.")
    return str(split_output_dir)


if __name__ == "__main__":
    run(os.getcwd())
