import type { NextConfig } from "next";

const BACKEND_URL = process.env.VALIDATION_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/validation/:path*",
        destination: `${BACKEND_URL}/api/validation/:path*`,
      },
    ];
  },
};

export default nextConfig;
