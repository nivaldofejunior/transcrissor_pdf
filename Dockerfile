FROM python:3.12-slim

WORKDIR /app

# Instala dependências do sistema necessárias para TTS, PDF e áudio
RUN apt update && apt install -y \
    curl gcc build-essential \
    libmagic1 libmagic-dev \
    libglib2.0-dev libpango1.0-0 ffmpeg

# Copia arquivos de dependência
COPY pyproject.toml poetry.lock* ./

# Instala o Poetry de forma robusta
RUN curl -sSL https://install.python-poetry.org -o install-poetry.py && \
    python3 install-poetry.py && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry

# Instala dependências do projeto
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copia o restante da aplicação
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["sh", "-c", "poetry run uvicorn app.main:app --host 0.0.0.0 --port 8001"]
