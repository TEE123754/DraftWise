// next.config.ts sets NEXT_PUBLIC_API_BASE: empty when an HTTPS backend is reached through the
// same-origin /api/v1 rewrite (so the demo cookie is first-party in every browser), otherwise
// the backend URL itself (local development).
export const API_ROOT = `${process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"}/api/v1`;
