FROM python:3.12-slim

# Variáveis de ambiente úteis
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3

WORKDIR /app

# Instala dependências do sistema necessárias para TTS, PDF e áudio
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gcc build-essential \
    libmagic1 libmagic-dev \
    libglib2.0-0 libpango1.0-0 \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

# Instala o Poetry de forma robusta e fixando versão
RUN curl -sSL https://install.python-poetry.org | python3 - \
 && ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Copia arquivos de dependência primeiro para aproveitar cache
COPY pyproject.toml poetry.lock* ./

# Instala dependências do projeto (sem criar venv separado)
RUN poetry config virtualenvs.create false \
&& poetry install --no-interaction --no-ansi --no-root --with dev

# Copia o restante da aplicação
COPY . .

EXPOSE 8001

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
