FROM node:22-alpine AS web
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit
COPY web/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --create-home ledger
COPY alembic.ini .
COPY migrations migrations
COPY ledger ledger
COPY --from=web /web/dist web/dist
USER ledger
EXPOSE 8000
CMD ["uvicorn", "ledger.api:app", "--host", "0.0.0.0", "--port", "8000"]
