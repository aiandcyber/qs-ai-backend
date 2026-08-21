FROM public.ecr.aws/docker/library/python:3.12-slim

WORKDIR /app

RUN useradd -m appuser \
    && install -d -o appuser -g appuser /app/.sessions /app/fixtures

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser:appuser app/ app/
COPY --chown=appuser:appuser fixtures/ fixtures/

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
