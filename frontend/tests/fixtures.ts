import type { Page } from "@playwright/test";

export const caseId = "10000000-0000-4000-8000-000000000001";
const workspaceId = "20000000-0000-4000-8000-000000000001";
const fields = [
  "shipper",
  "consignee",
  "notify_party",
  "port_of_loading",
  "port_of_discharge",
  "container_count",
  "gross_weight_kg",
];
const report = {
  id: "report-1",
  status: "MISMATCH",
  complete: true,
  comparisons: fields.map((field) => ({
    field,
    si: {
      raw: field === "gross_weight_kg" ? "22000 KG" : "Example",
      normalized: "22000",
      extraction_id: "si-1",
    },
    bl: {
      raw: field === "gross_weight_kg" ? "23000 KG" : "Example",
      normalized: "23000",
      extraction_id: "bl-2",
    },
    decision: field === "gross_weight_kg" ? "mismatch" : "match",
    confidence: 1,
    severity: "high",
    explanation: "The gross weight changed in the returned draft.",
    evidence_ids: [],
  })),
};
export const detail = {
  case: {
    id: caseId,
    email_id: "email-1",
    reference: "BK-2026-041",
    version: 3,
    readiness: "changes_required",
    updated_at: new Date().toISOString(),
    open_issue_count: 1,
    latest_report_id: "report-1",
    next_action: {
      kind: "preview_corrections",
      title: "Preview the correction request",
      fields: ["gross_weight_kg"],
    },
  },
  latest_report: report,
  active_sources: { si_extraction_id: "si-1", bl_extraction_id: "bl-2" },
  available_sources: [
    {
      id: "si-1",
      attachment_id: "a1",
      document_type: "SI",
      original_name: "Instructions.pdf",
      revision: 1,
    },
    {
      id: "bl-2",
      attachment_id: "a2",
      document_type: "BL",
      original_name: "Returned draft.pdf",
      revision: 2,
    },
  ],
  issues: [
    {
      id: "issue-weight",
      field: "gross_weight_kg",
      state: "open",
      source_report_id: "report-1",
    },
  ],
  rounds: [2, 1].map((round_number) => ({
    id: `round-${round_number}`,
    round_number,
    created_at: new Date().toISOString(),
    summary: {
      fields: fields.map((field) => ({
        field,
        change:
          field === "gross_weight_kg"
            ? "regressed"
            : field === "container_count"
              ? "fixed"
              : "unchanged_match",
        current_decision: field === "gross_weight_kg" ? "mismatch" : "match",
      })),
    },
  })),
};

export async function mockWorkspace(page: Page) {
  const payload = Buffer.from(
    JSON.stringify({
      sub: "30000000-0000-4000-8000-000000000001",
      exp: Math.floor(Date.now() / 1000) + 3600,
      aud: "authenticated",
      role: "authenticated",
    }),
  ).toString("base64url");
  await page.addInitScript(
    ({ token, workspace }) => {
      localStorage.setItem("shipping-workspace", workspace);
      localStorage.setItem(
        "sb-127-auth-token",
        JSON.stringify({
          access_token: token,
          refresh_token: "test-refresh",
          expires_at: Math.floor(Date.now() / 1000) + 3600,
          expires_in: 3600,
          token_type: "bearer",
          user: {
            id: "30000000-0000-4000-8000-000000000001",
            email: "reviewer@example.test",
            aud: "authenticated",
            role: "authenticated",
          },
        }),
      );
    },
    { token: `eyJhbGciOiJIUzI1NiJ9.${payload}.test`, workspace: workspaceId },
  );
  await page.route("http://127.0.0.1:54321/rest/v1/memberships**", (route) =>
    route.fulfill({
      json: [
        {
          workspace_id: workspaceId,
          role: "reviewer",
          workspaces: { name: "Test Shipping Team" },
        },
      ],
    }),
  );
  await page.route("http://127.0.0.1:8000/api/v1/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith("/previews"))
      return route.fulfill({
        json: {
          id: "preview-1",
          case_version: 3,
          changes: [
            { field: "gross_weight_kg", current: "23000", required: "22000" },
          ],
          remaining_fields: [],
          remaining_blocker_count: 0,
          expires_at: new Date(Date.now() + 1800000).toISOString(),
          suggested_message:
            "Please amend gross weight from 23000 kg to 22000 kg and return the draft.",
        },
      });
    if (path.endsWith(`/cases/${caseId}`))
      return route.fulfill({ json: detail });
    if (path.endsWith("/cases"))
      return route.fulfill({
        json: { items: [detail.case], next_cursor: null },
      });
    return route.fulfill({ json: { blocks: [] } });
  });
}
