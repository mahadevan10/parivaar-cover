import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // Without these the dev page never hydrates when opened at 127.0.0.1 or from a phone on the same Wi-Fi.
  allowedDevOrigins: ["127.0.0.1", "10.*.*.*", "192.168.*.*", "172.*.*.*", "*.devtunnels.ms"],
  // Lets a phone on a VS Code port tunnel reach the backend through this server.
  async rewrites() {
    return [{ source: "/api/backend/:path*", destination: "http://localhost:8000/:path*" }];
  },
  turbopack: {
    // Repo root, so the app can import data from ../shared.
    root: path.join(__dirname, ".."),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
