FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
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
