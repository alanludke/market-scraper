FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config/ config/
COPY src/ src/
COPY cli.py .

# Usage:
#   docker build -t market-scraper .
#   docker run market-scraper scrape bistek --region florianopolis_costeira
#   docker run market-scraper scrape giassi --all
#   docker run market-scraper scrape --all --parallel
#
# With Azure upload:
#   docker run -e AZURE_ACCOUNT_NAME=xxx -e AZURE_ACCOUNT_KEY=yyy \
#     market-scraper scrape bistek
#
# Mount data volume to persist results:
#   docker run -v $(pwd)/data:/app/data market-scraper scrape bistek

ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
