# Imagem unica para os dois processos Python (web e ingestor). Eles compartilham o
# mesmo codigo e diferem apenas no comando, o que mantem as duas metades da plataforma
# necessariamente na mesma versao.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY platform/pyproject.toml /app/platform/
COPY platform/meliponet /app/platform/meliponet
# O contrato vive fora do pacote porque e compartilhado com o firmware; a imagem
# precisa dele para validar a telemetria na ingestao.
COPY contracts /app/contracts

RUN pip install --no-cache-dir /app/platform

WORKDIR /app/platform
