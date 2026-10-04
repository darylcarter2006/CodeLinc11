# Deploying the backend to Amazon ECS (Express Mode)

ECS Express Mode runs our Docker image on Fargate and creates the HTTPS load balancer, public
URL, auto scaling and logs for us. It's the AWS-recommended replacement for App Runner, which
stopped accepting new customers on April 30, 2026.

```text
Amplify (frontend) ──HTTPS──► ECS Express URL ──► load balancer ──► Fargate task (our image)
                                                                        │ port 8080, TLS verified
                                                                        ▼
                                                                  RDS: insurance database
```

Region for everything below: **us-east-2 (Ohio)**, the same as RDS. Console labels change
occasionally, so if a name differs slightly, look for the closest match.

**Cost:** roughly $1–2 a day (Fargate task plus load balancer). Fargate isn't covered by the
free tier, so delete the service after the hackathon (step 9).

---

## 0. One-time setup on your laptop

1. **Install AWS CLI v2:** <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>
   (on Linux: download the zip, `unzip awscliv2.zip`, `sudo ./aws/install`).
2. **Sign in:** `aws configure sso` if the account uses IAM Identity Center, otherwise
   `aws configure` with an IAM user's access key. Use region `us-east-2`.
3. **Check it:** `aws sts get-caller-identity` prints the account ID.

Your AWS user needs permission for ECR, ECS, IAM roles, Secrets Manager and EC2 security groups.
If any step below says "not authorized", ask the account owner to do that step or grant access.

## 1. Store the database URL as a secret

The URL contains the database password, so it never goes into plain environment variables.

1. **Secrets Manager → Store a new secret → Other type of secret → Plaintext.**
2. Paste the URL on one line, for the `insurance` database and the `insurance_app` user, on
   port **8080**:
   ```text
   postgresql+asyncpg://insurance_app:<app-password>@codelinc11spartan.c9eyqm0aatip.us-east-2.rds.amazonaws.com:8080/insurance
   ```
3. Name it `coverage-compass/database-url`, then **Next → Next → Store**.
4. Open the secret and copy its **Secret ARN**. You need it in step 3.

If the `insurance_app` password has been shared anywhere (chat, screenshots), change it first
with `ALTER ROLE insurance_app PASSWORD '…';` and use the new one here and in your `.env`.

## 2. Build and push the image

From the repo root, on a commit you want to deploy:

```bash
backend/scripts/push-image.sh
```

The script creates the ECR repository `coverage-compass-backend` if needed, builds for
x86_64, and pushes `:<commit>` and `:latest`. Copy the printed image URI.

## 3. IAM roles

ECS needs two roles. The Express Mode console can create both with the right permissions:
choose **Create new role** when it asks.

- **Task execution role:** pulls the image, writes logs, and reads the secret. After it exists,
  open it in **IAM → Roles**, then **Add permissions → Create inline policy → JSON**:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      { "Effect": "Allow", "Action": "secretsmanager:GetSecretValue",
        "Resource": "<Secret ARN from step 1>" }
    ]
  }
  ```
- **Infrastructure role:** lets Express Mode create the load balancer, security groups and
  scaling for you.
- **Task role (later):** only needed once Bedrock is on, for `bedrock:InvokeModel` and
  `bedrock:InvokeModelWithResponseStream`. Not needed yet.

## 4. Create the Express service

**ECS → Express mode → Create** (or **Clusters → Create service → Express**).

| Setting | Value |
|---|---|
| Image URI | the URI from step 2 |
| Container port | **8000** (the default is 80; it must be changed) |
| Health check path | **`/v1/health`** (the default `/ping` doesn't exist) |
| CPU / memory | 0.5 vCPU / 1 GB |
| Scaling | min **1**, max **1** for the hackathon |
| Network | the **default VPC**, the same VPC as RDS |

**Environment variables** (plain values):

| Name | Value |
|---|---|
| `ENV` | `demo` |
| `REPOSITORY_BACKEND` | `postgres` |
| `DB_SSL_ROOT_CERT` | `/srv/certs/rds-global-bundle.pem` (baked into the image) |
| `CORS_ORIGINS` | `https://main.d2g8j1b83mvwk9.amplifyapp.com` |
| `GOOGLE_CLIENT_ID` | the Google OAuth client ID (same as `backend/.env`) |
| `FORWARDED_ALLOW_IPS` | `172.31.0.0/16` (the default VPC's range; see note) |
| `AI_PROVIDER` | `stub` (until Bedrock is wired in) |

**Secrets** (value from Secrets Manager):

| Name | Value |
|---|---|
| `DATABASE_URL` | the Secret ARN from step 1 |

Create the service. Provisioning takes a few minutes; the console then shows the service's
public **HTTPS URL**.

> **Why `FORWARDED_ALLOW_IPS`:** behind the load balancer, every request arrives from the load
> balancer's address. Trusting its network lets the app see each visitor's real IP, so the
> per-user rate limits on sign-in and chat work. Never set it to `*`: clients could then forge
> their address. If your VPC isn't the default `172.31.0.0/16`, use its CIDR (shown under
> **VPC → Your VPCs**).

## 5. Let the service reach the database

1. **ECS → your service → Networking** (or **Configuration**): note the **security group**
   attached to the tasks.
2. **RDS → codelinc11spartan → Connectivity & security →** click the database's security group
   → **Inbound rules → Edit inbound rules → Add rule**:
   - Type: **Custom TCP**, Port: **8080**
   - Source: **the tasks' security group** (start typing `sg-` and pick it). Not an IP address.
3. **Save.** Keep the existing office IP rule for laptops.

Because the tasks and RDS are in the same VPC, this traffic stays inside AWS.

## 6. Check it

```bash
curl https://<service-url>/v1/health     # {"status":"ok"}  (the app is running)
curl https://<service-url>/v1/ready      # {"status":"ok"}  (the database is reachable)
```

If `/v1/ready` returns 503, the database rule in step 5 is missing or the secret is wrong.

## 7. Point the frontend at it

1. **Amplify → your app → Hosting → Environment variables:** set `VITE_API_BASE_URL` to
   `https://<service-url>` (no trailing slash).
2. **Redeploy** the `main` branch. `VITE_*` values are baked in at build time.
3. Test Google sign-in on the Amplify site. It now goes through the backend: a row appears in
   `insurance.public.users`.

No Google Cloud change is needed: Google only checks the frontend's address, which is already
authorized.

## 8. Deploying a new version

1. Merge to `main`. If the change includes a migration, run `alembic upgrade head` against RDS
   first (see `database-setup.md`).
2. Run `backend/scripts/push-image.sh`.
3. In **ECS → your service → Update**, set the new image URI (or keep `:latest` and choose
   **Force new deployment**).

## 9. When the hackathon is over

Delete the Express service (this also removes its load balancer), then delete the ECR images
and the secret if they're no longer needed. Stop RDS too if nobody is using it.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Tasks keep restarting; "health checks failed" | Container port isn't 8000, or health path isn't `/v1/health` |
| `CannotPullContainerError` | Wrong image URI, or the image was pushed to another region |
| `ResourceInitializationError … secrets` | The execution role lacks the inline `GetSecretValue` policy (step 3) |
| Task logs show a settings error at startup | An environment variable is missing or malformed (CloudWatch → Log groups → the service's group) |
| `/v1/ready` → 503 | The RDS inbound rule for the tasks' security group is missing (step 5) |
| Browser: "blocked by CORS policy" | `CORS_ORIGINS` doesn't exactly match the Amplify URL (`https://`, no trailing slash) |
| Everyone gets "too many requests" | `FORWARDED_ALLOW_IPS` is missing or doesn't cover the VPC |
