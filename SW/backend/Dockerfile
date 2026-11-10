FROM python:3.12-slim

# Do not generate .pyc files and send the logs out unbuffered
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /code

# Dependencies first: Docker reuses this layer if requirements.txt does not change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then the code (alembic/, alembic.ini, app/)
COPY . .

EXPOSE 8000

# Default command. docker-compose.yml overrides it to apply the migrations first.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
