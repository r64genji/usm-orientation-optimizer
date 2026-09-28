FROM node:22-bookworm-slim AS web
WORKDIR /src/web
COPY operator_dashboard/web/package.json operator_dashboard/web/package-lock.json* ./
RUN npm install
COPY operator_dashboard/web ./
RUN npm run build

FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml README.md ./
COPY usm_sim ./usm_sim
COPY operator_dashboard ./operator_dashboard
COPY --from=web /src/web/dist ./operator_dashboard/web/dist
RUN pip install --no-cache-dir . fastapi uvicorn httpx
RUN mkdir -p /data && chown -R appuser:appuser /app /data
USER appuser
ENV DASHBOARD_DATA_DIR=/data
ENV DASHBOARD_PYTHON=/usr/local/bin/python
EXPOSE 8866
CMD ["python", "-m", "operator_dashboard", "--host", "0.0.0.0", "--port", "8866"]
