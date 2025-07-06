import re

def limpar_transcricao(texto: str) -> str:
    if not texto:
        return ""

    # Remove múltiplas quebras de linha seguidas
    texto = re.sub(r'\n{2,}', '\n\n', texto)

    # Remove espaços antes de quebras de linha
    texto = re.sub(r'[ \t]+\n', '\n', texto)

    # Substitui quebras simples por espaço se for no meio de frases
    texto = re.sub(r'(?<!\n)\n(?!\n)', ' ', texto)

    # Remove espaços duplicados
    texto = re.sub(r' {2,}', ' ', texto)

    return texto.strip()
