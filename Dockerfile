FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies (needed for psycopg2 and other packages)
RUN apt-get update && apt-get install -y gcc libpq-dev

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full source code
COPY . .

# Set PYTHONPATH so Python can find modules
ENV PYTHONPATH=/app

# Expose FastAPI's default port
EXPOSE 8000

# Start the FastAPI app (assuming app/main.py with `app = FastAPI()`)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8008", "--reload"]
