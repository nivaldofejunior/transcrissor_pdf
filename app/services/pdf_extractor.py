import fitz  # PyMuPDF

def extrair_texto_pdf(caminho_pdf: str) -> str:
    texto = ""
    try:
        with fitz.open(caminho_pdf) as doc:
            for pagina in doc:
                texto += pagina.get_text()
        return texto.strip()
    except Exception as e:
        print(f"Erro ao extrair texto do PDF: {e}")
        return ""
