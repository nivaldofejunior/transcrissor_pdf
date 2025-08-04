import os
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai

# Carrega o .env do ambiente apropriado
env = os.getenv("APP_ENV", "dev")
dotenv_path = Path(f".env.{env}") if Path(f".env.{env}").exists() else Path(".env")
load_dotenv(dotenv_path=dotenv_path)

# Carrega a chave da API do Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def melhorar_pontuacao_com_gemini(texto: str) -> str:
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")
        prompt = """
Você é um assistente especializado em transformar transcrições de aulas em materiais de estudo organizados. Receberá um texto bruto, transcrito de uma aula, que pode conter:

- Frases desconexas, repetições ou quebras de linha erradas
- Pontuações incorretas
- Palavras fora de lugar (como “Círculo preenchido”)
- Elementos como nomes de arquivos, fotos ou datas irrelevantes

Sua tarefa é:

1. **Reestruturar todo o conteúdo** em parágrafos organizados e coerentes.
2. **Preservar 100% das informações** importantes, mesmo que seja necessário reescrever frases para torná-las claras.
3. **Remover** elementos repetitivos ou irrelevantes (como “Círculo preenchido”, datas de postagens, etc).
4. **Não inventar informações.** Apenas organize e reescreva de forma clara e objetiva.
5. Quando houver **conceitos-chave**, destaque-os como subtítulos ou tópicos, se possível.

Retorne o resultado final como um **texto corrido organizado**, que possa ser lido como um resumo de estudo ou apostila, com as mesmas informações da transcrição original.
"""

        response = model.generate_content([
            {"role": "user", "parts": [
                {"text": prompt},
                {"text": texto}
            ]}
        ])
        return response.text  # Também funciona: response.candidates[0].content.parts[0].text
    except Exception as e:
        print(f"[Gemini] Erro ao melhorar pontuação: {e}")
        return texto  # Retorna o texto original em caso de falha
