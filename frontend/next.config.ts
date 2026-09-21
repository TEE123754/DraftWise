import type { NextConfig } from "next";

// A hosted backend (Vercel calling Railway) is on another site, so browsers that block third-party
// cookies (Safari, Firefox strict, Incognito) would drop the demo session cookie. Proxying
// /api/v1 through this origin keeps the cookie first-party. Local http backends are called directly.
const backendUrl = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
const proxyApi = backendUrl.startsWith("https://");

const config: NextConfig = {
  distDir: process.env.DRAFTWISE_E2E === "true" ? ".next-test" : process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  poweredByHeader: false,
  devIndicators: false,

  // Disable source maps in production to avoid leaking source code
  productionBrowserSourceMaps: false,

  // Environment variables made available to the browser
  env: {
    SITE_URL: process.env.SITE_URL || "http://localhost:3000",
    NEXT_PUBLIC_API_BASE: proxyApi ? "" : backendUrl || "http://localhost:8000",
  },

  async rewrites() {
    return proxyApi
      ? [{ source: "/api/v1/:path*", destination: `${backendUrl}/api/v1/:path*` }]
      : [];
  },

  // Image optimisation domains (OG images)
  images: {
    domains: [],
    formats: ["image/avif", "image/webp"],
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
      // Noindex headers for private routes (belt-and-suspenders alongside metadata)
      {
        source:
          "/(dashboard|inbox|trash|cases|review|alerts|settings|completed|demo|sign-in|auth)/:path*",
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
      },
    ];
  },
};

export default config;
