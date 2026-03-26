FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md /app/
COPY app /app/app
COPY start.sh /app/start.sh

RUN pip install --no-cache-dir .
RUN chmod +x /app/start.sh

EXPOSE 8000

CMD ["/app/start.sh"]

