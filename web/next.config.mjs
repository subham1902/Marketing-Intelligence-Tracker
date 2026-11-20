/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow an isolated build dir (e.g. for verifying a prod build while a dev
  // server keeps using .next). Defaults to .next.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // Proxy API calls to the FastAPI backend in dev so the browser hits same-origin.
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'self'" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  async rewrites() {
    // Local default :8000; Emergent-style hosts run the backend on :8001 (set BACKEND_PORT=8001).
    const api = process.env.API_PROXY_TARGET || `http://127.0.0.1:${process.env.BACKEND_PORT || 8000}`;
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
