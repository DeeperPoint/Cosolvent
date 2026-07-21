import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Proxy /api/* to the backend so the browser calls a same-origin path — this makes the
  // HttpOnly SameSite=Lax session cookie work (avoids the cross-origin cookie limitation).
  async rewrites() {
    const backend = process.env.BACKEND_ORIGIN ?? "http://localhost:18000";
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
