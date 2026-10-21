// Where the FastAPI service lives: API_URL when set, the public API on Render
// for deployments on Vercel, the local API otherwise.
export const API_URL =
  process.env.API_URL ??
  (process.env.VERCEL ? "https://invoice-block-radar-api.onrender.com" : "http://localhost:8000");
