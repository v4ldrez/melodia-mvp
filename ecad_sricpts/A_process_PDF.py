def run(base_dir: str):
    input_merge_dir = os.path.join(base_dir, "en_PDF")
    merged_pdf_output = os.path.join(base_dir, "i_pdf", "compilado.pdf")
    split_input_dir = os.path.join(base_dir, "i_pdf")
    split_output_dirs = [os.path.join(base_dir, "s_pdf_organizados")]

    os.makedirs(os.path.dirname(merged_pdf_output), exist_ok=True)
    os.makedirs(input_merge_dir, exist_ok=True)
    os.makedirs(split_input_dir, exist_ok=True)

    # Etapa 1: merge dos PDFs que estiverem em en_PDF
    pdfs_to_merge = sorted([
        os.path.join(input_merge_dir, f)
        for f in os.listdir(input_merge_dir)
        if f.lower().endswith(".pdf")
    ])
    if pdfs_to_merge:
        merge_pdfs(pdfs_to_merge, merged_pdf_output)

    # Etapa 2: split dos PDFs que estiverem em i_pdf
    pdf_files = [f for f in os.listdir(split_input_dir) if f.lower().endswith(".pdf")]
    for pdf_file in pdf_files:
        input_pdf_path = os.path.join(split_input_dir, pdf_file)
        split_pdf_by_text(input_pdf_path, split_output_dirs)

    return split_output_dirs[0]  # pasta onde saem os PDFs por mês

if __name__ == "__main__":
    run(os.getcwd())
