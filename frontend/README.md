# Shorts Clipper frontend

The React + Vite frontend talks to the FastAPI backend at `http://localhost:8000`.
The Vite development server proxies `/api` requests to that backend.

## Run locally

1. Start the FastAPI backend from the project root:

   ```powershell
   uvicorn api:app --reload --host 0.0.0.0 --port 8000
   ```

2. In a second terminal, start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

3. Open the local URL printed by Vite (normally `http://localhost:5173`).

The backend must be running on `localhost:8000`. For a different backend URL,
set `VITE_API_BASE_URL` before starting Vite; the default local setup uses the
development proxy.
