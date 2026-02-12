# ---- Build stage ----
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps for building wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

# ---- Runtime stage ----
FROM python:3.11-slim

WORKDIR /app

# Camoufox (Firefox-based) runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Firefox/Camoufox runtime libs
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libxt6 \
    libx11-xcb1 \
    libasound2 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libpango-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libxshmfence1 \
    libxkbcommon0 \
    # Fonts
    fonts-liberation \
    fonts-noto-cjk \
    # Misc
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY pyproject.toml ./
COPY src/ ./src/

# Install in editable mode (for entry point) + fetch Camoufox browser binary
RUN pip install --no-cache-dir -e . && \
    python -m camoufox fetch

# Default env (token passed at runtime via -e or docker-compose)
ENV MCP_HOST="0.0.0.0" \
    MCP_PORT="8897" \
    MCP_TRANSPORT="http" \
    BROWSER_POOL_SIZE="3" \
    PYTHONUNBUFFERED="1"

EXPOSE 8897

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -sf -o /dev/null -w "%{http_code}" -X POST http://localhost:8897/mcp -m 3 || exit 1

ENTRYPOINT ["python", "-m", "src.mcp_server"]
CMD ["--transport", "http", "--host", "0.0.0.0", "--port", "8897"]
