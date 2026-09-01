# Shared image for the Asha Shop stack.
#
# Used by all three workloads:
#   - app       : FastAPI + uvicorn + alembic
#   - migrator  : SQL Server -> Postgres migration (needs ODBC/FreeTDS)
#   - db_backup : pg_dump + awscli (uploads to S3 / Backblaze B2)
#
# Built on the VPS (which has Docker Hub + apt + pip access):
#   docker compose -f deploy/docker-compose.prod.yml build app
# Rebuild only when requirements.txt or the base image changes; code updates
# are `git pull` + `docker compose up -d --build`.

FROM python:3.12-slim

WORKDIR /app

# Use Chabokan mirror for Debian packages (official repos blocked in Iran)
RUN echo "deb https://mirror2.chabokan.net/debian trixie main" > /etc/apt/sources.list.d/debian.sources \
    && echo "deb https://mirror2.chabokan.net/debian trixie-updates main" >> /etc/apt/sources.list.d/debian.sources \
    && echo "deb https://mirror2.chabokan.net/debian-security trixie-security main" >> /etc/apt/sources.list.d/debian.sources \
    && rm -f /etc/apt/sources.list.d/*.sources

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