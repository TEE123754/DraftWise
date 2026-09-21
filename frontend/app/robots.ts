import type { MetadataRoute } from "next";
import { getSiteUrl } from "@/lib/site-url";

export default function robots(): MetadataRoute.Robots {
  const siteUrl = getSiteUrl();
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
