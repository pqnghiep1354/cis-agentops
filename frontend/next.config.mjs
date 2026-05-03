/** @type {import('next').NextConfig} */
const nextConfig = {
  // API routing handled by Vercel vercel.json
  // For local dev, still proxy to localhost:8080
  async rewrites() {
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080"}/api/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
