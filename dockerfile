# 1. Use a minimal Python base image
FROM python:3.11-slim

# 2. Set the working directory
WORKDIR /usr/src/app

# 3. Install WeasyPrint system dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    --no-install-recommends \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 4. Copy requirements and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of the application code
COPY . .

# 6. Create the output directory
RUN mkdir -p static/downloads

# 7. Expose the port
ENV PORT 8080
EXPOSE 8080

# 8. Start command (UPDATED)
# --workers 1: Only run one process to save RAM
# --timeout 120: Allow up to 2 minutes for PDF generation before killing it
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--timeout", "120", "app:app"]
