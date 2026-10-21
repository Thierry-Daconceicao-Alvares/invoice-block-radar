import type { NextConfig } from "next";

// The browser talks to this app only; /api/* is forwarded to the FastAPI service.
const api = process.env.API_URL ?? "http://localhost:8000";

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default config;
