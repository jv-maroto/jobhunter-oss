# JobHunter backend — imagen para uso LOCAL (docker run -p 127.0.0.1:8000:8000 ...).
# La API no tiene autenticacion por diseño (single-user, local-first): NO la
# expongas a internet tal cual.
FROM python:3.12-slim

# System deps: typst for CV generation, fonts for Pillow, node for Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    fonts-dejavu-core \
    fonts-noto-color-emoji \
    libpangoft2-1.0-0 \
    gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Typst (CV generator)
RUN curl -fsSL https://github.com/typst/typst/releases/latest/download/typst-x86_64-unknown-linux-musl.tar.xz \
    | tar -xJ --strip-components=1 -C /usr/local/bin typst-x86_64-unknown-linux-musl/typst

# Install Playwright + Chromium so trending posts get rendered as 1080x1080
# banner PNGs (og:image hero + overlay). Without this, /posts/*/image falls
# back to Pillow which can't do the banner template. Chromium is ~150 MB.
RUN npx --yes -p playwright@latest playwright install chromium --with-deps

WORKDIR /app

# Python deps (cached layer). `[onboarding]` = parsing de CV (PDF/DOCX).
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir -e ".[onboarding]"

COPY .env.example ./

ENV DATABASE_URL="sqlite:////app/data/jobhunter.db"
ENV DATA_DIR="/app/data"
RUN mkdir -p /app/data/applications /app/data/posts /app/data/cache

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
