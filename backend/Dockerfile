# JobHunter backend — Fly.io optimized
FROM python:3.12-slim

# System deps: typst for CV generation, fonts for Pillow, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    libpangoft2-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Typst (CV generator)
RUN curl -fsSL https://github.com/typst/typst/releases/latest/download/typst-x86_64-unknown-linux-musl.tar.xz \
    | tar -xJ --strip-components=1 -C /usr/local/bin typst-x86_64-unknown-linux-musl/typst

WORKDIR /app

# Python deps (cached layer)
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . && pip install --no-cache-dir uvicorn[standard]

# App code
COPY app ./app
COPY .env.example ./

# Data directory — overridden by DATA_PATH env var if mounted volume available
ENV DATABASE_URL="sqlite:///./jobhunter.db"
ENV DATA_PATH="./data"
RUN mkdir -p /app/data /app/data/applications /app/data/posts /app/data/cache \
    && chmod -R 777 /app/data

EXPOSE 8000

# Disable scheduler in production by default — re-enable via env var if desired
ENV ENABLE_SCHEDULER="false"

# HF Spaces requires the app to listen on port 7860 OR be configured via app_port.
# We use 8000 + app_port: 8000 in README.md frontmatter.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
