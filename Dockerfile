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

# Logic to run the CLI by default or keep container alive?
# Since we removed the app, let's make the entrypoint bash or python main
# User likely wants to run commands against it.
ENTRYPOINT ["python3", "-m", "src.main"]
CMD ["--help"]
