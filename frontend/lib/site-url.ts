/**
 * Safely resolves the canonical site URL for production (Vercel) and local environments.
 * Handles missing protocol, Vercel system env (VERCEL_URL), trailing slashes,
 * and malformed inputs with a resilient fallback.
 */
export function getSiteUrl(): string {
  const raw =
    process.env.SITE_URL ||
    (process.env.NEXT_PUBLIC_VERCEL_URL ? `https://${process.env.NEXT_PUBLIC_VERCEL_URL}` : null) ||
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : null) ||
    "http://localhost:3000";

  try {
    const withProtocol =
      raw.startsWith("http://") || raw.startsWith("https://")
        ? raw
        : `https://${raw}`;
    const parsed = new URL(withProtocol);
    return parsed.origin;
  } catch {
    return "https://draftwise.vercel.app";
  }
}

export function getSiteUrlObject(): URL {
  try {
    return new URL(getSiteUrl());
  } catch {
    return new URL("https://draftwise.vercel.app");
  }
}
