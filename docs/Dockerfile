FROM python:3.12-slim

# graphviz と日本語フォント（無いとラベルが豆腐になる）
RUN apt-get update \
    && apt-get install -y --no-install-recommends graphviz fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir diagrams==0.24.4

WORKDIR /docs
CMD ["python", "architecture.py"]
