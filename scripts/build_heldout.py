"""Build a held-out evaluation set that is independent of the supplied 520-email sample.

Wording, company names, ports, field labels, layouts and file formats are deliberately different
from the supplied data, and every answer is known by construction (written to truth.json). Nothing
here reads the organizer dataset or its answer key. Output: artifacts/heldout/{inbox,attachments,truth.json}.

    python scripts/build_heldout.py
"""

import io
import json
import random
import re
from pathlib import Path

import openpyxl
from docx import Document
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "heldout"
R = random.Random(20260920)

FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge",
          "container_count", "gross_weight_kg"]

PARTIES = [
    "HARBOR LIGHT TRADING CO", "Zenith Polymers Pte Ltd", "Baltic Timber Export AS",
    "NORDIC HOME GOODS GMBH", "Sunrise Textile Mills Ltd", "Cedar Valley Foods LLC",
    "Orion Machinery Works", "Blue Lagoon Seafoods Inc", "KAPPA PACKAGING SDN BHD",
    "Delta Auto Parts Co., Ltd", "Meridian Chemicals Limited", "Atlas Furniture Exports",
    "Pinnacle Steel Corporation", "Lotus Garments Pvt Ltd", "Summit Electronics Corp",
]
# (canonical name, spellings a document might use). Some are not in the product's alias table.
PORTS = [
    ("Rotterdam", ["ROTTERDAM", "Rotterdam", "ROTTERDAM, NETHERLANDS", "Rotterdam, NL (NLRTM)"]),
    ("Hamburg", ["HAMBURG", "Hamburg", "HAMBURG, GERMANY"]),
    ("Colombo", ["COLOMBO", "Colombo, Sri Lanka", "COLOMBO (LKCMB)"]),
    ("Jeddah", ["JEDDAH", "Jeddah", "JEDDAH, SAUDI ARABIA"]),
    ("Durban", ["DURBAN", "Durban, South Africa"]),
    ("Santos", ["SANTOS", "Santos, Brazil", "SANTOS (BRSSZ)"]),
    ("Manila", ["MANILA", "Manila, Philippines"]),
    ("Laem Chabang", ["LAEM CHABANG", "Laem Chabang, Thailand"]),
    ("Ningbo", ["NINGBO", "Ningbo, China", "NINGBO (CNNGB)"]),
    ("Qingdao", ["QINGDAO", "Qingdao, China"]),
    ("Los Angeles", ["LOS ANGELES", "Los Angeles, USA", "LOS ANGELES (USLAX)"]),
    ("Felixstowe", ["FELIXSTOWE", "Felixstowe, UK"]),
    ("Antwerp", ["ANTWERP", "Antwerp, Belgium"]),
    ("Singapore", ["SINGAPORE", "Singapore", "PORT OF SINGAPORE (SGSIN)"]),
    ("Busan", ["BUSAN", "Busan, South Korea", "PUSAN"]),
]
LABELS = {
    "shipper": ["Shipper", "Shipper/Exporter", "Exporter", "Consignor", "Shipper Name"],
    "consignee": ["Consignee", "Consignee (Non-Negotiable)", "Receiver", "Consignee / Buyer", "Buyer (Consignee)"],
    "notify_party": ["Notify Party", "Notify", "Also Notify", "Notify Address"],
    "port_of_loading": ["Port of Loading", "Load Port", "POL", "Loading Port", "Place of Loading"],
    "port_of_discharge": ["Port of Discharge", "Discharge Port", "POD", "Destination Port", "Port of Destination"],
    "container_count": ["No. of Containers", "Container Count", "Total Containers", "Qty of Containers", "Containers Qty"],
    "gross_weight_kg": ["Gross Weight", "Gross Wt (kgs)", "Total Gross Weight (KGS)", "G.W.", "Gross Mass (KG)"],
}
SI_HEADERS = ["SHIPPING INSTRUCTIONS", "SHIPPING INSTRUCTION FORM", "Booking Instruction", "SI - Shipper's Letter of Instruction"]
BL_HEADERS = ["DRAFT BILL OF LADING", "BILL OF LADING - DRAFT", "DRAFT B/L", "B/L DRAFT FOR APPROVAL"]
SIGNERS = ["Priya Nair", "Tomas Weber", "Kenji Aoki", "Amara Okafor", "Lucas Ferreira", "Hana Kim"]
COMPANIES = ["Northwind Logistics", "Coastline Freight Services", "Evergreen Forwarding", "Oakmont Shipping Agency"]


def name_variant(name):
    return R.choice([name, name.upper(), re.sub(r"\bLtd\b", "Limited", name), re.sub(r"\bCo\.?,? Ltd\b", "Company Limited", name)])


def render_containers(n):
    return R.choice([f"{n} x 40'HC", f"{n} X 20'GP", f"{n} containers", f"{n} x 20' FCL", f"{n}x40HC"])


def render_weight(kg, label):
    if "MT" in label:
        return f"{kg / 1000:g} MT"
    if "kgs" in label.lower() or "(kg" in label.lower():
        return R.choice([f"{kg:,}", f"{kg}", f"{kg:,} KG"])
    return R.choice([f"{kg:,} KG", f"{kg} KGS", f"{kg:,}.00 KG"])


def make_shipment():
    ports = R.sample(PORTS, 2)
    parties = R.sample(PARTIES, 3)
    consignee = parties[1]
    return {
        "shipper": parties[0], "consignee": consignee,
        "notify_party": consignee if R.random() < 0.6 else parties[2],
        "port_of_loading": ports[0][0], "port_of_discharge": ports[1][0],
        "container_count": R.randint(1, 12), "gross_weight_kg": R.randrange(9000, 260000, 50),
    }


def inject_defects(ship, k):
    """Return (changed copy, defect fields). Each change is a real difference, not a format change."""
    changed, fields = dict(ship), R.sample(FIELDS, k)
    for f in fields:
        if f in ("shipper", "consignee", "notify_party"):
            changed[f] = R.choice([p for p in PARTIES if p != ship[f]])
        elif f in ("port_of_loading", "port_of_discharge"):
            changed[f] = R.choice([p[0] for p in PORTS if p[0] != ship[f]])
        elif f == "container_count":
            changed[f] = ship[f] + R.choice([-2, -1, 1, 2, 3]) if ship[f] > 2 else ship[f] + R.choice([1, 2, 3])
        else:
            changed[f] = ship[f] + R.choice([-2000, -500, 500, 1000, 1500, 2000])
    if changed["notify_party"] == ship["consignee"] and "consignee" in fields and "notify_party" not in fields:
        changed["notify_party"] = ship["notify_party"]
    return changed, sorted(f for f in fields if changed[f] != ship[f])


def port_text(canonical):
    return R.choice(dict(PORTS)[canonical])


def doc_rows(ship, role, style, blank=None):
    rows = []
    for f in FIELDS:
        label = style["labels"][f]
        if f == blank:
            value = R.choice(["", "TBA", "____"])
        elif f in ("shipper", "consignee", "notify_party"):
            value = name_variant(ship[f]) if style["vary"] else ship[f]
        elif f in ("port_of_loading", "port_of_discharge"):
            value = port_text(ship[f]) if style["vary"] else ship[f].upper()
        elif f == "container_count":
            value = render_containers(ship[f])
        else:
            value = render_weight(ship[f], label)
        rows.append((label, value))
    filler = [("Vessel / Voyage", f"MV {R.choice(['STELLA', 'AURORA', 'CAPELLA', 'ORIENT'])} V.{R.randint(100, 999)}"),
              ("Commodity", R.choice(["Plastic granules", "Timber planks", "Frozen fish", "Auto spare parts", "Cotton yarn"])),
              ("Net Weight", f"{ship['gross_weight_kg'] - R.randint(300, 900):,} KG"),
              ("Freight", R.choice(["PREPAID", "COLLECT"]))]
    R.shuffle(filler)
    rows = rows[:5] + filler[:2] + rows[5:] + filler[2:]
    return rows


def make_style(novel):
    labels = {}
    for f, opts in LABELS.items():
        labels[f] = R.choice(opts[1:]) if novel and R.random() < 0.6 else R.choice(opts[:2])
    return {"labels": labels, "vary": R.random() < 0.5}


def render_txt(header, rows):
    sep = R.choice([": ", ": ", ":\t"])
    body = [header, "=" * 40, ""] + [f"{label}{sep}{value}".rstrip() if value else f"{label}{sep}".rstrip() for label, value in rows]
    return "\n".join(body).encode("utf-8"), "txt"


def render_docx(header, rows):
    d = Document()
    d.add_paragraph(header)
    table = d.add_table(rows=len(rows), cols=2)
    for row, (label, value) in zip(table.rows, rows, strict=True):
        row.cells[0].text, row.cells[1].text = label, value
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue(), "docx"


def render_xlsx(header, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = R.choice(["Sheet1", "Form", "Data"])
    ws["A1"] = header
    for i, (label, value) in enumerate(rows, start=3):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=value)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), "xlsx"


def render_pdf_text(header, rows):
    lines = [header, ""] + [f"{label}: {value}" for label, value in rows]
    content = ["BT", "/F1 11 Tf", "16 TL", "50 790 Td"]
    for line in lines:
        esc = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        content.append(f"({esc}) Tj T*")
    content.append("ET")
    stream = "\n".join(content).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out), "pdf"


def render_pdf_scan(header, rows):
    img = Image.new("L", (1240, 1000), 255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=30)
    y = 50
    for line in [header, ""] + [f"{label}: {value}" for label, value in rows]:
        draw.text((60, y), line, fill=0, font=font)
        y += 48
    buf = io.BytesIO()
    img.save(buf, "PDF", resolution=150)
    return buf.getvalue(), "pdf"


RENDERERS = {"txt": render_txt, "docx": render_docx, "xlsx": render_xlsx, "pdf": render_pdf_text, "scan": render_pdf_scan}

COMPARE_BODIES = [
    "Hi team, could you cross-check the attached draft B/L against our SI before we release it? Ref {ref}.",
    "Please verify the draft bill of lading vs the shipping instructions and let us know of any discrepancies.",
    "Kindly review the enclosed BL draft; SI attached for reference. Revert if anything is off.",
    "Attaching SI and BL draft for {ref}. Can you confirm everything matches?",
    "We received the carrier's draft. Please compare with what we submitted (SI attached) and flag differences.",
    "Draft B/L attached - validate against the SI please. Booking {ref}.",
    "Good morning, the SI and the carrier's draft are both attached. Would you double check them for {ref}?",
]
COMPARE_SUBJECTS = ["Draft docs for booking {ref}", "RE: {ref} - please check", "Fwd: BL draft {ref}",
                    "Documents for review", "Invoice {ref} - attached documents", "{ref} / vessel docs", ""]
MISSING_BODIES = ["Please compare the attached SI and draft BL for {ref} and confirm they agree.",
                  "SI and BL draft attached for {ref}. Kindly check for any mismatch."]
DRAFT_REQUESTS = ["Could you please forward the carrier's draft B/L for {ref} once it is issued? We will check it against the SI.",
                  "Please send us the draft bill of lading for {ref} so we can verify it."]
SI_BODIES = [
    "Please could you send us the shipping instruction template for booking {ref}?",
    "We need to submit SI for {ref} - kindly provide the form.",
    "Requesting your shipping instructions format for our upcoming shipment {ref}.",
    "Can you raise a new SI for the {n} x 40HC going to {port}? Please share the instruction sheet.",
    "Kindly share the SI form so we can prepare the documents for {ref}.",
    "Our shipper needs to lodge instructions for {ref}. Please prepare the shipping instruction and revert.",
]
INVOICE_BODIES = [
    "The freight invoice {inv} shows a THC charge we did not agree. Please explain the breakdown.",
    "Requesting a credit note for the duplicate charge on invoice {inv}.",
    "Could you clarify the demurrage amount billed on {inv}? It looks higher than the free days allow.",
    "Please send the payment advice details for {inv}; our accounts cannot match the amount.",
    "We were billed twice for documentation fee, see {inv}. Kindly correct.",
    "Our finance team disputes the ocean freight total on invoice {inv}.",
]
GENERAL_BODIES = [
    ("Vessel schedule update", "Please note MV {v} ETA is revised to next Thursday due to port congestion. No action required."),
    ("Holiday notice", "Our office will be closed on Monday for the public holiday. Normal service resumes Tuesday."),
    ("Weekly ops sync", "Reminder: the weekly operations sync is at 10:00 tomorrow. Agenda attached in the calendar invite."),
    ("Automatic reply", "I am out of the office until next week with limited access to email. For urgent matters contact the desk."),
    ("Port congestion bulletin", "This week's bulletin: average waiting time at major hubs has increased slightly. For information only."),
    ("Thanks", "Thank you for the update, we have noted the new sailing date."),
    ("Team lunch", "We are organizing a team lunch on Friday - let me know if you can join."),
    ("Rate sheet published", "The updated tariff sheet is now available on the portal for your reference."),
]
SPAM = [
    ("You have been selected!", "Congratulations, you were chosen to receive a $1,000 shopping reward. Click http://bit.ly/claim-prize now to claim."),
    ("Mailbox almost full", "Your mailbox storage is 98% full. Verify your account immediately at http://webmail-verify.example to avoid suspension."),
    ("Rank #1 on Google", "Boost your SEO ranking with 500 quality backlinks for only $29. Exclusive offer ends tonight!"),
    ("Urgent business proposal", "I am a barrister representing a late client. We need a beneficiary to receive USD 12 million, you keep 30%."),
    ("Parcel on hold", "Your parcel is on hold at the depot. Pay a $2.99 customs fee here: http://track-parcel.example/pay"),
    ("Crypto signals", "Join our private group for guaranteed 300% returns on bitcoin investment. Limited seats."),
    ("Invoice attached", "Dear customer, your invoice is ready. Download the secure document at http://free-iphone.example/login now."),
    ("Re: your order", "You have won a gift card. Confirm your delivery details to claim now."),
]


def signature():
    return f"\n\nBest regards,\n{R.choice(SIGNERS)}\n{R.choice(COMPANIES)}"


def ref():
    return f"{R.choice(['BK', 'OC', 'SO'])}{R.randint(100000, 999999)}"


def main():
    for sub in ("inbox", "attachments"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)
        for old in (OUT / sub).glob("*"):
            old.unlink()
    truth, emails, counter = {}, [], [0]

    def add(category, subject, body, attachments=(), **answer):
        counter[0] += 1
        eid = f"email_h{counter[0]:03d}"
        emails.append({"email_id": eid, "from": f"user{counter[0]}@{R.choice(['acme-trade.example', 'freightline.example', 'shipco.example'])}",
                       "subject": subject, "body": body + signature(), "attachments": list(attachments)})
        truth[eid] = {"category": category, "status": "OK", "review_reason": None, "defect_fields": [], **answer}
        return eid

    def write_pair(eid, si_ship, bl_ship, fmts, *, novel, blank=None, bl_override=None):
        si_style, bl_style = make_style(novel), make_style(novel)
        paths = []
        for role, ship, style, fmt in (("SI", si_ship, si_style, fmts[0]), ("BL", bl_ship, bl_style, fmts[1])):
            header = R.choice(SI_HEADERS if role == "SI" else BL_HEADERS)
            rows = doc_rows(ship, role, style, blank=blank if role == "SI" else None)
            data, ext = RENDERERS[fmt](header, rows)
            if bl_override and role == "BL":
                data, ext = bl_override
            name = f"attachments/{eid}_{role}.{ext}"
            (OUT / name).write_bytes(data)
            paths.append(name)
        return paths

    def pair_email(defects_k, fmts, novel, subject_i=None, blank=None, bl_override=None, category_answer=None):
        ship = make_shipment()
        bl_ship, defects = (inject_defects(ship, defects_k) if defects_k else (dict(ship), []))
        r = ref()
        subject = COMPARE_SUBJECTS[subject_i if subject_i is not None else R.randrange(len(COMPARE_SUBJECTS))].format(ref=r)
        body = R.choice(COMPARE_BODIES).format(ref=r)
        eid = f"email_h{counter[0] + 1:03d}"
        paths = write_pair(eid, ship, bl_ship, fmts, novel=novel, blank=blank, bl_override=bl_override)
        answer = category_answer or ({"status": "MISMATCH", "defect_fields": defects} if defects else {})
        add("BL_COMPARISON", subject, body, paths, si=ship, bl=bl_ship, **answer)

    # 16 normal pairs (8 with real defects, 8 clean but formatted differently), mixed formats.
    plan = [(1, ("txt", "txt")), (2, ("txt", "txt")), (1, ("txt", "docx")), (1, ("xlsx", "txt")), (2, ("docx", "docx")),
            (1, ("pdf", "pdf")), (1, ("xlsx", "xlsx")), (3, ("txt", "pdf")),
            (0, ("txt", "txt")), (0, ("txt", "txt")), (0, ("docx", "txt")), (0, ("xlsx", "xlsx")),
            (0, ("pdf", "txt")), (0, ("txt", "docx")), (0, ("scan", "scan")), (0, ("txt", "txt"))]
    for i, (k, fmts) in enumerate(plan):
        pair_email(k, fmts, novel=i % 2 == 1, subject_i=4 if i in (2, 9) else (6 if i == 12 else None))
    # Missing attachment: the mail says files are attached but none are.
    for _ in range(2):
        add("BL_COMPARISON", f"Documents {ref()}", R.choice(MISSING_BODIES).format(ref=ref()), [],
            status="NEEDS_REVIEW", review_reason="missing_attachment")
    # A request for the draft to be sent: nothing to compare yet.
    add("BL_COMPARISON", f"Draft B/L request {ref()}", R.choice(DRAFT_REQUESTS).format(ref=ref()), [])
    # Wrong document type in the BL slot.
    for _ in range(2):
        ship = make_shipment()
        eid = f"email_h{counter[0] + 1:03d}"
        si_style = make_style(False)
        (OUT / f"attachments/{eid}_SI.txt").write_bytes(render_txt(R.choice(SI_HEADERS), doc_rows(ship, "SI", si_style))[0])
        inv = "COMMERCIAL INVOICE\n" + "=" * 30 + f"\nSeller: {ship['shipper']}\nBuyer: {ship['consignee']}\nTotal amount: USD {R.randint(8000, 90000):,}\nPayment terms: 30 days\n"
        (OUT / f"attachments/{eid}_BL.txt").write_text(inv, encoding="utf-8")
        add("BL_COMPARISON", f"Check docs {ref()}", R.choice(COMPARE_BODIES).format(ref=ref()),
            [f"attachments/{eid}_SI.txt", f"attachments/{eid}_BL.txt"], status="NEEDS_REVIEW", review_reason="wrong_doc_type")
    # Unreadable: the BL is a corrupt file.
    pair_email(0, ("txt", "txt"), False, bl_override=(b"%PDF-1.4 \x00\x01 this file is truncated", "pdf"),
               category_answer={"status": "NEEDS_REVIEW", "review_reason": "unreadable"})
    # Missing value: a blank on the SI.
    for f in ("port_of_discharge", "gross_weight_kg"):
        pair_email(0, ("txt", "txt"), False, blank=f, category_answer={"status": "NEEDS_REVIEW", "review_reason": "missing_value"})

    for _ in range(10):
        add("SI_REQUEST", R.choice(["Need SI for {ref}", "Shipping instructions - {ref}", "Booking {ref}", "Request: SI form"]).format(ref=ref()),
            R.choice(SI_BODIES).format(ref=ref(), n=R.randint(1, 6), port=R.choice(PORTS)[0]))
    # Misleading subjects: a comparison request under an invoice subject, and an invoice query under a BL subject.
    for _ in range(2):
        add("INVOICE_QUERY", f"BL draft {ref()} - urgent", R.choice(INVOICE_BODIES).format(inv=f"INV-{R.randint(10000, 99999)}"))
    for _ in range(8):
        add("INVOICE_QUERY", R.choice(["Invoice query {inv}", "RE: charges", "Billing question", "{inv}"]).format(inv=f"INV-{R.randint(10000, 99999)}"),
            R.choice(INVOICE_BODIES).format(inv=f"INV-{R.randint(10000, 99999)}"))
    for subject, body in R.sample(GENERAL_BODIES, 8):
        add("GENERAL", subject, body.format(v=R.choice(["STELLA", "AURORA", "CAPELLA"])))
    for subject, body in SPAM:
        add("SPAM", subject, body)

    for e in emails:
        (OUT / "inbox" / f"{e['email_id']}.json").write_text(json.dumps(e, indent=2), encoding="utf-8")
    (OUT / "truth.json").write_text(json.dumps(truth, indent=2), encoding="utf-8")
    counts = {}
    for t in truth.values():
        counts[t["category"]] = counts.get(t["category"], 0) + 1
    print(f"wrote {len(emails)} emails to {OUT}: {counts}")


if __name__ == "__main__":
    main()
