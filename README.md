# Summit PT Clinic — FastAPI Backend

## Local Setup

### Step 1 — Create virtual environment
```bash
cd Desktop/summit-api
python -m venv venv
```

### Step 2 — Activate virtual environment
**Windows:**
```bash
venv\Scripts\activate
```
**Mac/Linux:**
```bash
source venv/bin/activate
```

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4 — Add Firebase Service Account Key
1. Go to **Firebase Console** → Project Settings → Service Accounts
2. Click **"Generate new private key"**
3. Download the JSON file
4. Rename it to **`serviceAccountKey.json`**
5. Place it in the `summit-api` folder (same folder as main.py)

⚠️ NEVER commit serviceAccountKey.json to GitHub!

### Step 5 — Run locally
```bash
uvicorn main:app --reload
```

API runs at: http://localhost:8000
Docs at: http://localhost:8000/docs

---

## Deploy to Railway

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "Initial FastAPI setup"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/summit-api.git
git push -u origin main
```

### Step 2 — Deploy on Railway
1. Go to https://railway.app
2. Sign up with GitHub (free)
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your `summit-api` repo
5. Railway auto-detects Python and deploys

### Step 3 — Add Firebase credentials on Railway
Since `serviceAccountKey.json` is NOT pushed to GitHub, you need to add it as an environment variable:

1. In Railway → your project → **Variables** tab
2. Add a new variable:
   - Name: `FIREBASE_CREDENTIALS`
   - Value: paste the entire contents of your `serviceAccountKey.json`

Then update `main.py` to read from env (already handled below in the production-ready version).

### Step 4 — Get your Railway URL
After deploy, Railway gives you a URL like:
`https://summit-api-production.up.railway.app`

Copy this URL — you'll need it for your React apps.

---

## API Endpoints

| Method | Endpoint | Who |
|--------|----------|-----|
| GET | `/` | Anyone |
| GET | `/health` | Anyone |
| POST | `/auth/verify` | Both |
| POST | `/attendance/time-in` | Employee |
| POST | `/attendance/time-out` | Employee |
| GET | `/attendance/me` | Employee |
| GET | `/attendance/all` | Admin |
| POST | `/attendance/bulk-timeout` | Admin |
| POST | `/leave` | Employee |
| GET | `/leave/me` | Employee |
| GET | `/leave/all` | Admin |
| PUT | `/leave/{uid}/{id}/status` | Supervisor/Super Admin |
| POST | `/overtime` | Employee |
| GET | `/overtime/me` | Employee |
| GET | `/overtime/all` | Admin |
| PUT | `/overtime/{uid}/{id}/status` | Supervisor/Super Admin |
| POST | `/reports` | Employee |
| GET | `/reports/me` | Employee |
| GET | `/reports/all` | Admin |
| PUT | `/reports/{uid}/{id}/status` | Manager/Super Admin |
| POST | `/payroll` | HR Admin/Super Admin |
| GET | `/payroll/me` | Employee |
| GET | `/payroll/{uid}` | HR Admin/Super Admin |
| GET | `/users` | Admin |
| GET | `/users/me` | Both |
| POST | `/users` | HR Admin/Super Admin |
| PUT | `/users/{uid}` | HR Admin/Super Admin |
| PUT | `/users/{uid}/status` | HR Admin/Super Admin |

---

## Test with Swagger UI
After running locally, open: http://localhost:8000/docs
You can test all endpoints directly in the browser.
