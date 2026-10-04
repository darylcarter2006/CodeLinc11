# Database setup

The backend runs with an in-memory store by default. These steps switch it to PostgreSQL,
either a local Docker container or the team's Amazon RDS instance.

Run every command from the `backend/` folder.

## Option A: local Postgres in Docker

Local Docker and CI run PostgreSQL 18, the same major version as RDS.

If you created the local database before the switch from 16 to 18, its data volume
won't start under 18. Recreate it once (this deletes local data only, never RDS):

```bash
docker compose down -v
```

```bash
docker compose up -d --wait db      # --wait: return only once Postgres is ready
export DATABASE_URL=postgresql+asyncpg://insurance:localdev@localhost:5432/insurance
.venv/bin/alembic upgrade head
REPOSITORY_BACKEND=postgres .venv/bin/uvicorn app.main:app --reload
```

## Option B: Amazon RDS

The RDS instance listens on **port 8080**, not PostgreSQL's usual 5432, because the office
Wi-Fi blocks outbound 5432.

You only need to do steps 1–3 once per RDS instance. Each teammate does steps 4–6 on their
own machine.

### 1. Allow your IP

The instance's security group only accepts connections from listed IPs.

1. In the AWS console, go to **RDS → Databases → codelinc11spartan → Connectivity &
   security**.
2. Click the security group link.
3. Choose **Edit inbound rules → Add rule**.
4. Set **Type** to **Custom TCP**, **Port** to **8080**, **Source** to **My IP**, and add a
   description with your name. The office network (`148.159.64.145`) is already allowed.
5. Save.

### 2. Download the RDS certificate bundle

```bash
mkdir -p certs
curl -o certs/global-bundle.pem https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem
```

`certs/` is gitignored. Each teammate downloads their own copy.

### 3. Create the app database and user (once, using the master account)

Generate a password for the app user, and save it in your team's password manager:

```bash
openssl rand -base64 24 | tr -d '/+='
```

Connect as the master user. If `psql` isn't installed, run `sudo apt install postgresql-client`.

```bash
psql "host=codelinc11spartan.c9eyqm0aatip.us-east-2.rds.amazonaws.com port=8080 dbname=postgres user=spartanmaster sslmode=verify-full sslrootcert=certs/global-bundle.pem"
```

Then run these statements, replacing `<app-password>` with the password you generated:

```sql
CREATE ROLE insurance_app LOGIN PASSWORD '<app-password>';
CREATE DATABASE insurance OWNER insurance_app;
REVOKE ALL ON DATABASE insurance FROM PUBLIC;
\q
```

From now on the app uses `insurance_app`. Keep the master account for administration only.

### 4. Create your `.env`

Create `backend/.env`. It's gitignored; never commit it.

```dotenv
REPOSITORY_BACKEND=postgres
DATABASE_URL=postgresql+asyncpg://insurance_app:<app-password>@codelinc11spartan.c9eyqm0aatip.us-east-2.rds.amazonaws.com:8080/insurance
DB_SSL_ROOT_CERT=certs/global-bundle.pem
CORS_ORIGINS=http://localhost:5173
```

### 5. Run the migrations

Alembic reads environment variables, not `.env`, so export the file first:

```bash
set -a; source .env; set +a
.venv/bin/alembic upgrade head
.venv/bin/alembic current        # should print the newest revision, marked (head)
```

Only one person needs to run this after each new migration. It is safe to run again.

### 6. Start the API and check the database connection

```bash
.venv/bin/uvicorn app.main:app --reload
curl localhost:8000/v1/ready     # {"status":"ok"} means the database is reachable
```

## Troubleshooting

- **`psql`/`alembic` hangs, then times out:** check you're using port 8080. Otherwise your IP
  isn't in the security group (step 1), or the instance isn't publicly accessible. Check **Connectivity & security → Publicly
  accessible**.
- **`password authentication failed`:** the password in `DATABASE_URL` doesn't match, or
  it contains characters that need URL-encoding. The `openssl` command above avoids them.
- **`certificate verify failed`:** `DB_SSL_ROOT_CERT` doesn't point to the RDS bundle.
- **`DB_SSL_ROOT_CERT file not found` at startup:** the path is relative to where you run
  the command. Run from `backend/`.
- **`/v1/ready` returns 503:** the app started but can't reach the database. Check the
  items above.

## Before deploying (not needed for local development)

- Store the app password in AWS Secrets Manager and inject it into the container. Never put
  it in a task definition as plain text.
- Give the API service its own security group, and allow it on port 8080 instead of
  individual IPs.
- RDS can be stopped for up to 7 days at a time to save cost when nobody is working on it.
