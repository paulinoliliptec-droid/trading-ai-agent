FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# editável: o código fica em /app/src e ROOT (configs, data, models_artifacts) resolve para /app
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY apps ./apps
COPY configs ./configs
COPY scripts ./scripts
RUN useradd --create-home app && mkdir -p /app/data /app/reports && chown -R app /app
USER app
EXPOSE 8080
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
