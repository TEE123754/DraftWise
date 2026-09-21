# DraftWise Production Deployment Guide (Vercel + Railway)

This guide details the complete deployment and integration architecture for **DraftWise**:
- **Frontend**: Next.js 16 (App Router, Tailwind CSS, TypeScript) hosted on **Vercel**
- **Backend**: FastAPI + Tesseract OCR + Uvicorn container hosted on **Railway**
- **Database & Auth**: PostgreSQL + Supabase (Auth, Storage, RLS)
- **Source Repository**: [`https://github.com/TEE123754/DraftWise`](https://github.com/TEE123754/DraftWise)

---

## 1. Architecture & Integration Overview

```
 ┌─────────────────────────────────────────────────────────────┐
 │                     User Web Browser                        │
 └──────────────┬───────────────────────────────┬──────────────┘
                │                               │
        HTTPS Requests                   Bearer Token + REST
      (Next.js App Pages)                (CORS Allowed Origin)
                ▼                               ▼
 ┌─────────────────────────────┐ ┌─────────────────────────────┐
 │       Vercel (Frontend)     │ │      Railway (Backend)      │
 │  - Root Directory: frontend │ │  - Dockerfile: backend      │
 │  - Port: 443 (Serverless)   │ │  - Port: Dynamic ($PORT)    │
 └──────────────┬──────────────┘ └──────────────┬──────────────┘
                │                               │
                │     Supabase Auth / Storage   │
                └───────────────┬───────────────┘
                                ▼
                 ┌─────────────────────────────┐
                 │       Supabase Cloud        │
                 │  - PostgreSQL + Migrations  │
                 │  - Storage: originals       │
                 │  - Auth: Email / Google     │
                 └─────────────────────────────┘
```

---

## 2. Deploying Backend to Railway

### Step 2.1: Create Project on Railway
1. Go to [railway.com](https://railway.com) and log in with your GitHub account (`TEE123754`).
2. Click **+ New Project** -> **Deploy from GitHub repo**.
3. Select your repository: **`TEE123754/DraftWise`**.
4. Railway automatically detects [`railway.json`](../railway.json) in the project root and selects `docker/backend.Dockerfile`.

### Step 2.2: Generate Public Domain
1. In Railway project dashboard, select the deployed service.
2. Go to **Settings** -> **Networking**.
3. Click **Generate Domain** (e.g. `draftwise-production.up.railway.app`).
4. Note this domain: this is your `NEXT_PUBLIC_API_URL` for Vercel.

### Step 2.3: Configure Railway Environment Variables
In Railway -> **Variables**, add the following environment variables:

| Variable | Recommended Value / Notes |
| :--- | :--- |
| `ENVIRONMENT` | `production` (or `development` for relaxed origins) |
| `DATABASE_URL` | Your PostgreSQL connection string (e.g. from Supabase `postgresql://postgres:...@db...supabase.co:5432/postgres`) |
| `SUPABASE_URL` | `https://<your-project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role secret key (for storage & auth verification) |
| `STORAGE_BUCKET` | `shipping-originals` |
| `GEMINI_API_KEY` | Your Google Gemini API Key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `AI_PROVIDER` | `gemini` (or `morpheus`) |
| `ALLOWED_ORIGINS` | `https://<your-app>.vercel.app` *(must be HTTPS in production)* |
| `WORKER_ENABLED` | `true` |
| `DEMO_ENABLED` | `true` |
| `FREE_ONLY` | `true` |

> [!IMPORTANT]
> Railway's liveness check is configured in `railway.json` to hit `/health`, which responds `200 {"status":"ok","version":"pipeline-v1"}` immediately upon container startup.

---

## 3. Deploying Frontend to Vercel

### Step 3.1: Import Project into Vercel
1. Go to [vercel.com](https://vercel.com) and log in with GitHub (`TEE123754`).
2. Click **Add New...** -> **Project**.
3. Import **`TEE123754/DraftWise`**.
4. **Configure Project**:
   - **Root Directory**: Click **Edit** and select **`frontend`** (Crucial: the Next.js app lives in `frontend/`).
   - **Framework Preset**: **Next.js** (detected automatically).
   - **Build Command**: `pnpm build` (detected automatically from `pnpm-lock.yaml`).

### Step 3.2: Configure Vercel Environment Variables
Under **Environment Variables**, add:

| Variable | Value | Notes |
| :--- | :--- | :--- |
| `NEXT_PUBLIC_API_URL` | `https://<your-railway-domain>.up.railway.app` | Railway backend public URL |
| `NEXT_PUBLIC_SUPABASE_URL` | `https://<your-project-ref>.supabase.co` | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `<your-supabase-anon-key>` | Supabase anonymous public key |
| `SITE_URL` | `https://<your-app>.vercel.app` | Production site URL for SEO & metadata |

5. Click **Deploy**. Vercel will run `pnpm build` and deploy in ~1-2 minutes.

---

## 4. Cross-Origin (CORS) & Integration Sync

Once your Vercel URL is assigned (e.g., `https://draftwise.vercel.app`):
1. Go to **Railway** -> **Variables**.
2. Update `ALLOWED_ORIGINS`:
   ```bash
   ALLOWED_ORIGINS=https://draftwise.vercel.app,https://draftwise-git-main-tee123754.vercel.app
   ```
   *(Include both your production domain and preview domain if needed, separated by comma).*
3. Railway will redeploy the backend in seconds with the updated CORS policy.

---

## 5. Verification Checklist

1. **Backend Health**:
   Visit `https://<your-railway-domain>.up.railway.app/health`.
   - Expected: `{"status": "ok", "version": "pipeline-v1"}`
2. **Frontend Loading**:
   Visit `https://<your-app>.vercel.app`.
   - Expected: Glassmorphic Version B landing page renders with parallax, motion surfaces, and active navigation.
3. **Interactive Integration**:
   - Click **Get Started** or **Demo Mode**.
   - Browse the Inbox and click an email: check that the frontend communicates with the Railway backend via `/api/v1/emails` and displays document comparisons.
4. **AI & Extraction**:
   - Trigger a document verification or test an extraction: the background worker processes the job and updates the status badge.
