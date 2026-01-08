import os
 
# === CAMINHO BASE (mude aqui se necessário) ===
BASE_DIR = r'C:\Users\guilherme.cristo\Documents\ECAD'
 
# === Subpastas relativas ao BASE_DIR ===
SUBPASTAS = [
    's_tabelas\\categorias',
    's_tabelas\\obras',
    's_tabelas\\rubricas',
    's_tabelas\\compiladas',
    'i_pdf',
    'report_pdf',
    's_pdf_organizados',
    'en_PDF'
]
 
# === Caminhos completos ===
caminhos_pastas = [os.path.join(BASE_DIR, subpasta) for subpasta in SUBPASTAS]
 
# === Deletar arquivos em cada pasta ===
for caminho_pasta in caminhos_pastas:
    for arquivo in os.listdir(caminho_pasta):
        caminho_arquivo = os.path.join(caminho_pasta, arquivo)
        if os.path.isfile(caminho_arquivo):
            os.remove(caminho_arquivo)
            print(f'Arquivo {arquivo} deletado de {caminho_pasta}.')
 
print('Todos os arquivos foram deletados.')
