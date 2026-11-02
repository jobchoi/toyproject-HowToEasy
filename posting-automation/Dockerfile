FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements-ui.txt ./
RUN python -m pip install --no-cache-dir -r requirements-ui.txt && mkdir -p /app/.local/ui
COPY posting_tool ./posting_tool
COPY examples ./examples
COPY TASKS.md ./
USER 1000:1000
CMD ["python", "-m", "uvicorn", "posting_tool.web:create_app", "--factory", "--host", "127.0.0.1", "--port", "8010", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
