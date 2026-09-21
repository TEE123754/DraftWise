import type { MetadataRoute } from "next";

const siteUrl = process.env.SITE_URL || "http://localhost:3000";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/workflow", "/pricing", "/privacy", "/terms"],
        disallow: [
          "/api/",
          "/demo",
          "/sign-in",
          "/auth/",
          "/dashboard",
          "/inbox",
          "/cases/",
          "/review",
          "/alerts",
          "/settings/",
          "/completed",
        ],
      },
    ],
    sitemap: `${siteUrl}/sitemap.xml`,
    // Note: robots.txt is access control guidance, not authorization.
    // Private routes are also protected by session authentication server-side.
  };
}
