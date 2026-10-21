import type { NextConfig } from "next";

import { API_URL } from "./lib/api-url";

// The browser talks to this app only; /api/* is forwarded to the FastAPI service.
const api = API_URL;

const config: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

export default config;
