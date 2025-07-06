import re

def dividir_texto_em_blocos(texto: str, limite_bytes: int = 5000) -> list[str]:
    blocos = []
    bloco_atual = ""

    def ssml_wrap(content: str) -> str:
        return "<speak>" + content.replace(".", '.<break time="500ms"/>').replace("\n", "<break time=\"700ms\"/>") + "</speak>"

    for linha in texto.splitlines(keepends=True):
        tentativa = bloco_atual + linha
        tentativa_ssml = ssml_wrap(tentativa)
        if len(tentativa_ssml.encode("utf-8")) > limite_bytes:
            blocos.append(bloco_atual.strip())
            bloco_atual = linha
        else:
            bloco_atual = tentativa

    if bloco_atual:
        blocos.append(bloco_atual.strip())

    print(f"[DEBUG] Total de blocos: {len(blocos)}")
    for i, bloco in enumerate(blocos):
        print(f"  Bloco {i+1}: {len(ssml_wrap(bloco).encode('utf-8'))} bytes (SSML incluído)")
    return blocos


def limpar_texto_para_tts(texto: str) -> str:
    """
    Limpa o texto para evitar leitura incorreta pelo TTS:
    - Remove formatação markdown (*, **, #)
    - Remove bullets e marcadores
    - Mantém pontuação e estrutura para uma boa leitura
    """
    texto = re.sub(r"(?m)^#+\s*", "", texto)                 # Remove cabeçalhos markdown (### Título)
    texto = re.sub(r"\*\*(.*?)\*\*", r"\1", texto)           # Negrito markdown
    texto = re.sub(r"\*(.*?)\*", r"\1", texto)               # Itálico markdown
    texto = re.sub(r"[*#•▪◦●]", "", texto)                   # Remove bullets e símbolos comuns
    texto = re.sub(r"\s*[-–]\s*", " ", texto)                # Remove traços como marcadores
    texto = re.sub(r"\n{2,}", "\n", texto)                   # Reduz múltiplas quebras de linha
    return texto.strip()