import { getSupabase } from "@/lib/supabase";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const supabase = getSupabase();
  const session = supabase
    ? (await supabase.auth.getSession()).data.session
    : null;
  const demo = sessionStorage.getItem("draftwise-demo-workspace");
  const workspace = demo || localStorage.getItem("shipping-workspace");
  if ((!session && !demo) || !workspace)
    throw new ApiError(
      401,
      "AUTH_REQUIRED",
      "Sign in and select a workspace to continue.",
    );
  const headers = new Headers(options.headers);
  if (demo) headers.set("X-Demo-Mode", "true");
  else if (session)
    headers.set("Authorization", `Bearer ${session.access_token}`);
  headers.set("X-Workspace-Id", workspace);
  if (options.body) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("Idempotency-Key", crypto.randomUUID());
  const result = await fetch(
    `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/v1${path}`,
    { ...options, headers, credentials: "include", cache: "no-store" },
  );
  const body = await result.json().catch(() => null);
  if (!result.ok)
    throw new ApiError(
      result.status,
      body?.error?.code || "REQUEST_FAILED",
      body?.error?.message ||
        "The request could not be completed. Please try again.",
    );
  return body as T;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api(path, { method: "POST", body: JSON.stringify(body) });
}

export function get<T>(path: string): Promise<T> {
  return api(path, { method: "GET" });
}

export function del<T>(path: string): Promise<T> {
  return api(path, { method: "DELETE" });
}

export function patch<T>(path: string, body: unknown): Promise<T> {
  return api(path, { method: "PATCH", body: JSON.stringify(body) });
}

export async function waitForJob(
  jobId: string,
  signal?: AbortSignal,
): Promise<unknown> {
  for (let attempt = 0; attempt < 150; attempt++) {
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    const job = await api<{
      state: string;
      result: unknown;
      error_code?: string;
    }>(`/jobs/${jobId}`, { signal });
    if (job.state === "succeeded" || job.state === "needs_review")
      return job.result;
    if (job.state === "failed" || job.state === "cancelled")
      throw new Error(
        `Processing stopped (${job.error_code || job.state}). Your documents are saved; retry from the case.`,
      );
    await new Promise<void>((resolve) =>
      setTimeout(resolve, attempt < 10 ? 2000 : 10000),
    );
  }
  throw new Error(
    "Processing is taking longer than expected. Your job is saved and will continue in the background.",
  );
}

export async function uploadDocument(
  emailId: string,
  file: File,
): Promise<string> {
  if (file.size > 20 * 1024 * 1024)
    throw new Error("Choose a document smaller than 20 MB.");
  const types: Record<string, string> = {
    txt: "text/plain",
    pdf: "application/pdf",
    docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  };
  const mime = types[file.name.split(".").pop()?.toLowerCase() || ""];
  if (!mime) throw new Error("Choose a PDF, Word, Excel or text document.");
  const reserved = await post<{ attachment_id: string; upload_url: string }>(
    "/uploads",
    {
      email_id: emailId,
      filename: file.name,
      mime_type: mime,
      byte_size: file.size,
    },
  );
  const upload = await fetch(reserved.upload_url, {
    method: "PUT",
    body: file,
    headers: { "Content-Type": mime },
  });
  if (!upload.ok) throw new Error("Upload did not finish. Please try again.");
  const hash = await crypto.subtle.digest("SHA-256", await file.arrayBuffer());
  const sha256 = Array.from(new Uint8Array(hash), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  await post(`/uploads/${reserved.attachment_id}/complete`, { sha256 });
  return reserved.attachment_id;
}
