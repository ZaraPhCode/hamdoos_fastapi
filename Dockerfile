FROM python:3.12-slim-noble

WORKDIR /app

# Use ParsVDS Ubuntu mirror (official repos blocked in Iran)
RUN echo "deb http://ubuntu.parsvds.com/ubuntu noble main universe" > /etc/apt/sources.list.d/parsvds.list \
    && echo "deb http://ubuntu.parsvds.com/ubuntu noble-updates main universe" >> /etc/apt/sources.list.d/parsvds.list \
    && echo "deb http://ubuntu.parsvds.com/ubuntu noble-security main universe" >> /etc/apt/sources.list.d/parsvds.list \
    && rm -f /etc/apt/sources.list.d/ubuntu.sources

# Runtime libs needed by the whole stack:
#  - gcc/libpq-dev: build deps for psycopg2/pyodbc if a wheel is unavailable
#  - unixodbc + tdsodbc + freetds: SQL Server access for the migrator
#  - postgresql-client: pg_dump/pg_restore for backups
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libpq-dev libpq5 unixodbc unixodbc-dev tdsodbc freetds-bin freetds-dev \
    postgresql-client ca-certificates \
    && printf '[FreeTDS]\nDriver=/usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so\n' >> /etc/odbcinst.ini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir awscli

COPY . .

# Create upload directories
RUN mkdir -p app/static/uploads/products app/static/uploads/medias app/static/uploads/receipts app/static/uploads/datasheets

CMD alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000