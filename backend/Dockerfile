FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG APP_VERSION=0.0.0-dev
ARG APP_COMMIT=desconocido
ARG APP_BUILT_AT=
ENV APP_VERSION=$APP_VERSION APP_COMMIT=$APP_COMMIT APP_BUILT_AT=$APP_BUILT_AT
WORKDIR /srv

COPY pyproject.toml ./
COPY app ./app
RUN pip install .

# Usuario sin privilegios; escucha en $PORT (8100 por defecto).
RUN useradd --system --no-create-home guazu
USER guazu
ENV PORT=8100
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/v1/salud')"]
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
