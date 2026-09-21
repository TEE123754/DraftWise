import type { NextConfig } from "next";

const config: NextConfig = {
  distDir: process.env.DRAFTWISE_E2E === "true" ? ".next-test" : process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
  poweredByHeader: false,
  devIndicators: false,

  // Disable source maps in production to avoid leaking source code
  productionBrowserSourceMaps: false,

  // Environment variables made available to the browser
  env: {
    SITE_URL: process.env.SITE_URL || "http://localhost:3000",
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
