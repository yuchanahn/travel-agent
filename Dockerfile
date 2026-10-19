FROM node:24-bookworm-slim AS openbnb
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/openbnb
RUN git init && git remote add origin https://github.com/openbnb-org/mcp-server-airbnb.git \
    && git fetch --depth 1 origin d5a8f18f5978b0a33dea4b3ec130c389bad845cc \
    && git checkout --detach FETCH_HEAD \
    && npm ci --ignore-scripts --no-audit --no-fund && npm run build \
    && npm prune --omit=dev --ignore-scripts --no-audit --no-fund \
    && rm -rf .git
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=openbnb /usr/local/bin/node /usr/local/bin/node
COPY --from=openbnb /opt/openbnb /opt/openbnb
COPY config/mcp-docker.json /app/config/mcp-docker.json
ENV MCP_CONFIG_FILE=/app/config/mcp-docker.json
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
# The web runtime uses lexical-only memory indexing without embedding/torch.
# Dense/hybrid indexing remains available in the full host environment.
COPY src/travel_agent ./travel_agent
RUN useradd --uid 10001 --create-home agent \
    && mkdir -p /app/data/private/web \
    && chown -R agent:agent /app/data
USER agent
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=8s --start-period=15s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=5)"
CMD ["python", "-m", "travel_agent.web_app", "--host", "0.0.0.0", "--port", "8000"]
