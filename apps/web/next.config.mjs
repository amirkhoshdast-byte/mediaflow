/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // In production Caddy routes /api/* straight to the API; this rewrite keeps `next dev` working alone.
  async rewrites() {
    const api = process.env.API_INTERNAL_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/:path*` }];
  },
};
export default nextConfig;
