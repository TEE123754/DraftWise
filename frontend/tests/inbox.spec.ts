import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mockWorkspace } from "./fixtures";

type Row = ReturnType<typeof item>;

const LABELS: Record<string, string> = {
  needs_documents: "Needs documents",
  waiting_for_draft: "Waiting for draft",
  needs_review: "Needs review",
  mismatch_found: "Mismatch found",
  held: "Held for safety",
  spam: "Spam",
  processing: "Processing",
  checked: "Checked",
  classified: "Classified",
};
const TONES: Record<string, string> = {
  needs_documents: "yellow",
  waiting_for_draft: "yellow",
  needs_review: "yellow",
  mismatch_found: "yellow",
  held: "red",
  spam: "red",
  processing: "grey",
  checked: "green",
  classified: "green",
};
const BL = "BL_COMPARISON";
const noDocs = { count: 0, si: false, bl: false, other: 0, unread: 0 };
const both = { count: 2, si: true, bl: true, other: 0, unread: 0 };

function item(
  displayId: string,
  state: string,
  category: string | null,
  extra: { reasons?: { code: string; label: string }[]; documents?: typeof both; kind?: string; title?: string } = {},
) {
  return {
    id: `id-${displayId}`,
    display_id: displayId,
    external_id: displayId,
    subject: `Subject of ${displayId}`,
    sender: "ops@example.test",
    body_preview: `Body of ${displayId}. Please check the draft BL.`,
    category,
    classified_by: category ? ("rule" as const) : null,
    attachment_count: (extra.documents ?? noDocs).count,
    documents: extra.documents ?? noDocs,
    case: null,
    job_state: null,
    state,
    state_label: LABELS[state],
    tone: TONES[state],
    reasons: extra.reasons ?? [],
    action: { kind: extra.kind ?? "none", title: extra.title ?? `Next step for ${displayId}` },
  };
}

// email_007 is deliberately not first in "All", and first in "Needs documents": its ID must not change.
const FILLER = Array.from({ length: 30 }, (_, index) =>
  item(`email_${100 + index}`, "waiting_for_draft", BL, {
    reasons: [{ code: "awaiting_draft", label: "Asks for the draft BL to be sent; nothing to compare yet" }],
    kind: "await_draft",
  }),
);
const MAILBOX: Row[] = [
  item("M-001", "classified", "GENERAL"),
  item("email_002", "checked", BL, { documents: both, kind: "view_checks" }),
  item("email_007", "needs_documents", BL, {
    documents: { count: 1, si: true, bl: false, other: 0, unread: 0 },
    reasons: [{ code: "missing_bl", label: "Draft bill of lading not found" }],
    kind: "request_bl",
    title: "Ask the sender for the draft BL",
  }),
  item("email_010", "mismatch_found", BL, {
    documents: both,
    reasons: [{ code: "mismatch", label: "Differences in: consignee, gross weight kg" }],
    kind: "preview_corrections",
  }),
  item("email_011", "needs_review", BL, {
    documents: { count: 1, si: false, bl: false, other: 0, unread: 1 },
    reasons: [{ code: "documents_unread", label: "The documents have not been read yet" }],
    kind: "process",
    title: "Read the attached documents",
  }),
  item("email_012", "needs_review", null, {
    reasons: [{ code: "unclassified", label: "The request type could not be decided" }],
    kind: "classify",
  }),
  item("email_013", "spam", "SPAM", { kind: "confirm_spam" }),
  item("email_014", "held", "GENERAL", {
    reasons: [{ code: "safety_hold", label: "Held for safety review" }],
    kind: "review_safety",
  }),
  item("email_015", "processing", BL, { kind: "wait", documents: both }),
  item("email_016", "classified", "SI_REQUEST", { kind: "reply_si" }),
  ...FILLER,
];

const SI_FIELDS: Record<string, string> = {
  shipper: "ACME EXPORTS LTD",
  consignee: "GLOBAL BUYERS INC",
  notify_party: "GLOBAL BUYERS INC",
  port_of_loading: "SGSIN",
  port_of_discharge: "NLRTM",
  container_count: "2",
  gross_weight_kg: "22000 KG",
};
const BL_FIELDS = { ...SI_FIELDS, consignee: "GLOBAL BUYERS LLC", gross_weight_kg: "23000 KG" };
const LABEL_OF: Record<string, string> = {
  shipper: "Shipper",
  consignee: "Consignee",
  notify_party: "Notify party",
  port_of_loading: "Port of loading",
  port_of_discharge: "Port of discharge",
  container_count: "Container count",
  gross_weight_kg: "Gross weight (kg)",
};
const side = (value: string | null) =>
  value
    ? { state: "present", value, quote: `Label: ${value}` }
    : { state: "missing", value: null, quote: null };

function detailFor(row: Row) {
  const compared = row.state === "mismatch_found";
  return {
    id: row.id,
    external_id: row.external_id,
    display_id: row.display_id,
    subject: row.subject,
    sender: row.sender,
    category: row.category,
    body: `Full body of ${row.display_id}.\nGross weight: 22 MT\nPlease check the draft BL.`,
    state: row.state,
    state_label: row.state_label,
    tone: row.tone,
    reasons: row.reasons,
    action: row.action,
    documents: row.documents,
    case: row.case,
    attachments: row.documents.count
      ? [
          { id: "a1", original_name: `${row.display_id}_SI.pdf`, state: "validated" },
          ...(row.documents.count > 1 ? [{ id: "a2", original_name: `${row.display_id}_BL.pdf`, state: "validated" }] : []),
        ]
      : [],
    extractions: [
      { attachment_id: "a1", document_type: "SI" },
      ...(row.documents.count > 1 ? [{ attachment_id: "a2", document_type: "BL" }] : []),
    ],
    reference_check:
      row.documents.count === 0
        ? { status: "no_documents", cited: [] }
        : row.state === "mismatch_found"
          ? {
              status: "partial",
              cited: [
                { code: "BK12345", kind: "booking", quote: "Booking ref: BK12345", in_documents: true },
                { code: "ZZ99999", kind: "code", quote: "ZZ99999", in_documents: false },
              ],
            }
          : { status: "none_cited", cited: [] },
    classification_summary: row.category
      ? {
          category: row.category,
          ambiguous: false,
          method: "rules",
          method_label: "Rules",
          fallback_reason: null,
          reason_code: "comparison_action",
          reason: "Asks for the draft BL to be checked or compared",
          human_reason: null,
          evidence: [{ id: "current", text: "Please check the draft BL." }],
        }
      : null,
    field_table: {
      status: compared ? "MISMATCH" : null,
      documents: { si: row.documents.count > 0, bl: row.documents.count > 1 },
      rows: Object.keys(SI_FIELDS).map((field) => {
        const differs = SI_FIELDS[field] !== BL_FIELDS[field as keyof typeof BL_FIELDS];
        return {
          field,
          label: LABEL_OF[field],
          decision: compared ? (differs ? "mismatch" : "match") : null,
          explanation: compared && differs ? `${LABEL_OF[field]} differs between SI and BL.` : null,
          si: row.documents.count ? side(SI_FIELDS[field]) : { state: "no_document", value: null, quote: null },
          bl: row.documents.count > 1 ? side(BL_FIELDS[field as keyof typeof BL_FIELDS]) : { state: "no_document", value: null, quote: null },
          email:
            field === "gross_weight_kg"
              ? { ...side("22 MT"), mark: compared ? "differs" : "unchecked" }
              : { ...side(null), mark: "unchecked" },
        };
      }),
    },
  };
}

type Requests = {
  lists: URLSearchParams[];
  details: string[];
  processed: { id: string; body: unknown }[];
  /** Server-side counts to report instead of the ones computed from MAILBOX. */
  counts: Record<string, number>;
};

/** A stand-in for the inbox API that filters, counts and pages the way the real one does. */
async function mockInbox(page: Page): Promise<Requests> {
  const seen: Requests = { lists: [], details: [], processed: [], counts: {} };
  await mockWorkspace(page);
  await page.route("**/api/v1/emails**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^.*\/api\/v1/, "");
    if (path === "/emails/counts") {
      const by_state = Object.fromEntries(Object.keys(LABELS).map((state) => [state, seen.counts[state] ?? MAILBOX.filter((r) => r.state === state).length]));
      const by_category: Record<string, number> = {};
      for (const row of MAILBOX) by_category[row.category ?? "unclassified"] = (by_category[row.category ?? "unclassified"] ?? 0) + 1;
      return route.fulfill({ json: { total: MAILBOX.length, by_state, by_category } });
    }
    const process = path.match(/^\/emails\/(.+)\/process$/);
    if (process) {
      seen.processed.push({ id: process[1], body: route.request().postDataJSON() });
      return route.fulfill({ json: { state: "classifying", job_id: "job-1", email_id: process[1] } });
    }
    const one = path.match(/^\/emails\/(.+)$/);
    if (one) {
      seen.details.push(one[1]);
      const row = MAILBOX.find((r) => r.id === one[1]);
      return row ? route.fulfill({ json: detailFor(row) }) : route.fulfill({ status: 404, json: { error: { code: "NOT_FOUND", message: "Email was not found" } } });
    }
    const q = url.searchParams;
    seen.lists.push(q);
    const needle = (q.get("q") ?? "").toLowerCase();
    const wanted = MAILBOX.filter(
      (r) =>
        (!q.get("state") || r.state === q.get("state")) &&
        (!q.get("category") || r.category === q.get("category")) &&
        (q.get("unresolved") !== "true" || r.category === null) &&
        (!needle || `${r.subject} ${r.sender} ${r.display_id}`.toLowerCase().includes(needle)),
    );
    const offset = Number(q.get("offset") ?? 0);
    const limit = Number(q.get("limit") ?? 25);
    return route.fulfill({
      json: {
        items: wanted.slice(offset, offset + limit),
        total: wanted.length,
        next_cursor: wanted.length > offset + limit ? String(offset + limit) : null,
      },
    });
  });
  return seen;
}

const row = (page: Page, displayId: string) => page.locator(`[data-testid=email-row][data-display-id="${displayId}"]`);
const pill = (page: Page, name: string) => page.getByRole("group", { name: "Filter by status" }).getByRole("button", { name });
const colourOf = (page: Page, displayId: string) =>
  row(page, displayId).evaluate((element) => getComputedStyle(element).borderLeftColor);

test("every review state has its own colour, an icon-and-text chip and its reasons", async ({ page }) => {
  await mockInbox(page);
  await page.goto("/inbox");
  await expect(row(page, "email_007")).toBeVisible();

  // Text label and tone for every state, read from the row itself.
  const shown: Record<string, string> = {};
  for (const mail of MAILBOX.filter((r) => r.state !== "waiting_for_draft" || r.display_id === "email_100")) {
    const locator = row(page, mail.display_id);
    await expect(locator).toHaveAttribute("data-state", mail.state);
    await expect(locator).toHaveAttribute("data-tone", TONES[mail.state]);
    await expect(locator.getByTestId("state-chip")).toHaveText(LABELS[mail.state]);
    await expect(locator.getByTestId("state-chip").locator("svg")).toHaveCount(1);
    shown[mail.state] = await colourOf(page, mail.display_id);
  }

  // Colours: red for spam and held, one yellow for everything a person must act on, two greens, grey.
  expect(shown.spam).toBe(shown.held);
  expect(new Set([shown.needs_documents, shown.waiting_for_draft, shown.needs_review, shown.mismatch_found]).size).toBe(1);
  expect(shown.checked).not.toBe(shown.classified);
  expect(new Set([shown.spam, shown.needs_documents, shown.checked, shown.classified, shown.processing]).size).toBe(5);

  // Reasons and SI/BL chips, as words.
  await expect(row(page, "email_007").locator("[data-document=SI]")).toContainText("SI found");
  await expect(row(page, "email_007").locator("[data-document=BL]")).toContainText("BL missing");
  await expect(row(page, "email_010").locator("[data-reason=mismatch]")).toHaveText("Differences in: consignee, gross weight kg");
  await expect(row(page, "email_011").locator("[data-reason=documents_unread]")).toBeVisible();
  await expect(row(page, "email_011").locator("[data-document=SI]")).toContainText("not read yet");
  await expect(row(page, "email_012").locator("[data-reason=unclassified]")).toBeVisible();
  await expect(row(page, "email_014").locator("[data-reason=safety_hold]")).toBeVisible();
  await expect(row(page, "email_007")).toContainText("Next: Ask the sender for the draft BL");
});

test("status filters show server counts and ask the server for exactly that state", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox");
  await expect(row(page, "email_007")).toBeVisible();

  const counts = { all: MAILBOX.length, needs_documents: 1, waiting_for_draft: 30, needs_review: 2, mismatch_found: 1, held: 1, spam: 1, processing: 1, checked: 1, classified: 2 };
  await expect(page.locator("[data-count=all]")).toHaveText(String(counts.all));
  for (const [state, count] of Object.entries(counts).filter(([key]) => key !== "all"))
    await expect(page.locator(`[data-count=${state}]`)).toHaveText(String(count));

  await pill(page, "Needs review").click();
  await expect(page.getByRole("status").filter({ hasText: "Showing 2 of 2 emails matching your filters" })).toBeVisible();
  expect(seen.lists.at(-1)?.get("state")).toBe("needs_review");
  await expect(page.getByTestId("email-row")).toHaveCount(2);
  await expect(page.getByTestId("email-row").first()).toHaveAttribute("data-state", "needs_review");

  await page.getByLabel("Type").selectOption("unclassified");
  await expect(page.getByTestId("email-row")).toHaveCount(1);
  expect(seen.lists.at(-1)?.get("unresolved")).toBe("true");
  await expect(page.getByRole("option", { name: "BL comparison (35)" })).toBeAttached();
});

test("email_007 keeps its own ID under every filter and search, never a list position", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox");
  await expect(row(page, "email_007")).toBeVisible();

  const position = async () => page.getByTestId("email-row").evaluateAll((rows, id) => rows.findIndex((r) => r.getAttribute("data-display-id") === id), "email_007");
  const positions = [await position()];

  await pill(page, "Needs documents").click();
  await expect(page.getByTestId("email-row")).toHaveCount(1);
  positions.push(await position());
  await expect(row(page, "email_007")).toContainText("email_007");

  await pill(page, "All").click();
  await page.getByLabel("Type").selectOption(BL);
  await expect(row(page, "email_007")).toBeVisible();
  expect(seen.lists.at(-1)?.get("category")).toBe(BL);
  positions.push(await position());

  await page.getByLabel("Type").selectOption("all");
  await page.getByLabel("Search by subject, sender or email ID").fill("007");
  await expect(page.getByTestId("email-row")).toHaveCount(1);
  expect(seen.lists.at(-1)?.get("q")).toBe("007");
  positions.push(await position());

  expect(new Set(positions).size).toBeGreaterThan(1); // the row really did move around
  await expect(page.getByText(/\bEmail_\d{3}\b/)).toHaveCount(0);
  await expect(row(page, "email_007")).toContainText("email_007");
});

test("load more keeps the active filter and pages from where it stopped", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox");
  await pill(page, "Waiting for draft").click();
  await expect(page.getByTestId("email-row")).toHaveCount(25);
  await page.getByRole("button", { name: "Load more emails (5 left)" }).click();
  await expect(page.getByTestId("email-row")).toHaveCount(30);

  const more = seen.lists.at(-1)!;
  expect([more.get("state"), more.get("offset")]).toEqual(["waiting_for_draft", "25"]);
  // Nothing from another state slipped in, and there is nothing further to load.
  expect(await page.getByTestId("email-row").evaluateAll((rows) => rows.every((r) => r.getAttribute("data-state") === "waiting_for_draft"))).toBe(true);
  await expect(page.getByRole("button", { name: /Load more emails/ })).toHaveCount(0);
});

test("nothing is previewed until a row is chosen, and the preview follows the requested order", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox");
  await expect(row(page, "email_010")).toBeVisible();
  await expect(page.getByTestId("email-preview")).toHaveCount(0);
  expect(seen.details).toEqual([]);

  await row(page, "email_010").getByRole("button", { name: /email_010/ }).click();
  const preview = page.getByTestId("email-preview");
  await expect(preview.getByRole("heading", { level: 2, name: "Extracted info" })).toBeVisible();
  await expect(preview.getByRole("heading", { level: 2 })).toHaveText(["Email", "Attachments", "Classification", "Actions", "Extracted info"]);
  expect(seen.details).toEqual(["id-email_010"]);

  // Attachments: which file is the SI and which the BL.
  await expect(preview.getByText("email_010_SI.pdf")).toBeVisible();
  await expect(preview.getByText("Shipping instructions", { exact: true })).toBeVisible();
  await expect(preview.getByText("Draft BL", { exact: true })).toBeVisible();

  // Classification: method and evidence.
  await expect(preview.getByText("decided by Rules")).toBeVisible();
  await preview.getByText("Evidence from the email").click();
  await expect(preview.locator("section[aria-labelledby=preview-classification] blockquote")).toHaveText("Please check the draft BL.");

  // Extracted info: SI | BL | Email with a mark on every row.
  await expect(preview.getByTestId("table-summary")).toHaveText("5 of 7 fields match. Differences: consignee, gross weight (kg).");
  await expect(preview.getByRole("columnheader")).toHaveText(["Field", "SI", "BL", "Email"]);
  const weight = preview.locator("tr[data-field=gross_weight_kg]");
  await expect(weight).toContainText("Mismatch");
  await expect(weight.locator("td").nth(0)).toContainText("22000 KG");
  await expect(weight.locator("td").nth(1)).toContainText("23000 KG");
  await expect(weight.locator("td").nth(2)).toContainText("22 MT");
  await expect(weight.locator("td").nth(2)).toContainText("Differs from the documents");
  await expect(preview.locator("tr[data-field=shipper]")).toContainText("Match");
  await expect(preview.locator("tr[data-field=shipper] td").nth(2)).toContainText("Not stated");
});

test("an email with no SI or BL lists only what the email states, instead of a table of empty cells", async ({ page }) => {
  await mockInbox(page);
  await page.goto("/inbox");
  await row(page, "email_100").getByRole("button", { name: /email_100/ }).click();
  const preview = page.getByTestId("email-preview");
  await expect(preview.getByText("No files came with this email.")).toBeVisible();
  await expect(preview.getByTestId("table-summary")).toHaveText("No SI or BL has been read for this email. These are the values the email states itself.");
  await expect(preview.locator("tr[data-field]")).toHaveCount(1);
  await expect(preview.locator("tr[data-field=gross_weight_kg]")).toContainText("22 MT");
  await expect(preview.getByText("No document")).toHaveCount(2); // that one row's SI and BL cells
});

test("counts keep refreshing while emails are still being read, even when a filter hides them", async ({ page }) => {
  const seen = await mockInbox(page);
  seen.counts.processing = 3;
  await page.clock.install();
  await page.goto("/inbox");
  await expect(page.locator("[data-count=processing]")).toHaveText("3");

  await pill(page, "Spam").click(); // none of the visible rows is processing any more
  await expect(page.getByTestId("email-row")).toHaveCount(1);
  seen.counts.processing = 0;
  await page.clock.runFor(9000);
  await expect(page.locator("[data-count=processing]")).toHaveText("0");
});

test("changing a filter closes the preview instead of leaving a stale email on screen", async ({ page }) => {
  await mockInbox(page);
  await page.goto("/inbox");
  await row(page, "email_007").getByRole("button", { name: /email_007/ }).click();
  await expect(page.getByTestId("email-preview")).toContainText("email_007");
  await expect(page.getByTestId("email-preview").locator("tr[data-field=shipper] td").nth(1)).toContainText("No document");

  await pill(page, "Spam").click();
  await expect(page.getByTestId("email-row")).toHaveCount(1);
  await expect(page.getByTestId("email-preview")).toHaveCount(0);
});

test("reading documents is local: one email or a selection, always without AI", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox");

  await row(page, "email_011").getByRole("button", { name: /email_011/ }).click();
  await page.getByRole("button", { name: "Read the documents (no AI)" }).click();
  await expect(page.getByTestId("email-preview").getByRole("status").filter({ hasText: "1 email queued without AI" })).toBeVisible();
  expect(seen.processed).toEqual([{ id: "id-email_011", body: { prefer_ai: false } }]);

  seen.processed.length = 0;
  await page.getByRole("button", { name: "Select emails" }).click();
  await row(page, "email_011").getByLabel("Select email_011").check();
  await row(page, "email_012").getByLabel("Select email_012").check();
  await row(page, "email_013").getByLabel("Select email_013").check(); // spam: nothing to read
  await expect(page.getByRole("status").filter({ hasText: "3 selected; 1 cannot be read or compared." })).toBeVisible();
  await page.getByRole("button", { name: "Read without AI (2)" }).click();
  await expect(page.getByRole("status").filter({ hasText: "2 emails queued without AI" })).toBeVisible();
  expect(seen.processed.map((call) => call.id).sort()).toEqual(["id-email_011", "id-email_012"]);
  expect(seen.processed.every((call) => (call.body as { prefer_ai: boolean }).prefer_ai === false)).toBe(true);
});

test("inbox with a preview open has no accessibility violations", async ({ page }) => {
  await mockInbox(page);
  await page.goto("/inbox");
  await row(page, "email_010").getByRole("button", { name: /email_010/ }).click();
  await expect(page.getByTestId("field-table")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("filters come from the link and are written back, so a refresh or a shared link keeps the view", async ({ page }) => {
  const seen = await mockInbox(page);
  await page.goto("/inbox?state=needs_documents&category=BL_COMPARISON");
  await expect(pill(page, "Needs documents")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByLabel("Type")).toHaveValue(BL);
  await expect(row(page, "email_007")).toBeVisible();
  expect(seen.lists[0].get("state")).toBe("needs_documents"); // the very first request is already filtered

  await pill(page, "Spam").click();
  await expect.poll(() => page.url()).toContain("state=spam");
  await page.reload();
  await expect(pill(page, "Spam")).toHaveAttribute("aria-pressed", "true");

  await page.goto("/inbox?unresolved=true"); // links from before the redesign still work
  await expect(page.getByLabel("Type")).toHaveValue("unclassified");
  await page.goto("/inbox?state=bogus");
  await expect(pill(page, "All")).toHaveAttribute("aria-pressed", "true");
});

test("the preview says which references the email cites are in its own documents, in words as well as colour", async ({ page }) => {
  await mockInbox(page);
  await page.goto("/inbox");
  await row(page, "email_010").getByRole("button", { name: /email_010/ }).click();
  const refs = page.getByTestId("email-preview").getByTestId("reference-check");
  await expect(refs).toHaveAttribute("data-status", "partial");
  await expect(refs.locator("[data-reference=BK12345]")).toHaveText(/BK12345\s*in its documents/);
  await expect(refs.locator("[data-reference=ZZ99999]")).toHaveText(/ZZ99999\s*not in its documents/);
  await expect(refs).toContainText("Some of what the email cites is not in its documents.");

  await row(page, "email_007").getByRole("button", { name: /email_007/ }).click();
  await expect(page.getByTestId("reference-check")).toContainText("cites no booking, B/L or OC reference");

  await row(page, "email_100").getByRole("button", { name: /email_100/ }).click();
  await expect(page.getByTestId("reference-check")).toHaveCount(0); // no documents: nothing to check against
});
