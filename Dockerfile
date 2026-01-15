# Dockerfile

FROM python:3.10-slim

# Install system dependencies (ffmpeg is required)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set PYTHONPATH so 'src' module can be found
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Copy source code
COPY src/ src/
COPY input/ input/
COPY .streamlit/ .streamlit/

# Expose Streamlit port
EXPOSE 8501

# Run the app
CMD ["streamlit", "run", "src/app.py", "--server.address=0.0.0.0"]
