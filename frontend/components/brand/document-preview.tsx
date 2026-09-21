const fields = [
  { field: "Shipper", si: "Meridian Export Co.", bl: "Meridian Export Co.", status: "match" as const },
  { field: "Consignee", si: "Northline Trading", bl: "Northline Trading", status: "match" as const },
  { field: "Notify Party", si: "Same as consignee", bl: "Same as consignee", status: "match" as const },
  { field: "Port of Loading", si: "Port Klang", bl: "Port Klang", status: "match" as const },
  { field: "Port of Discharge", si: "Singapore", bl: "Singapore", status: "match" as const },
  { field: "Container Count", si: "3", bl: "4", status: "mismatch" as const },
  { field: "Gross Weight", si: "22,000 kg", bl: "22,000 kg", status: "match" as const },
] as const;

const statusLabel: Record<string, string> = {
  match: "Matched",
  mismatch: "Mismatch",
  missing: "Missing",
  uncertain: "Uncertain",
};

/** An explicitly illustrative comparison, never presented as workspace data. */
export function DocumentPreview() {
  const matchCount = fields.filter((f) => f.status === "match").length;
  const mismatchCount = fields.filter((f) => f.status !== "match").length;

  return (
    <figure className="shipping-preview">
      <figcaption>
        <span>Document comparison</span>
        <span>Illustrative example</span>
      </figcaption>
      <div className="shipping-preview-title">
        <div>
          <h2>One draft. Seven checks.</h2>
          <p>Shipping Instructions vs Draft Bill of Lading</p>
        </div>
        <span className="document-stamp">
          {matchCount} matched
          <br />
          <strong>{mismatchCount} {mismatchCount === 1 ? "difference" : "differences"}</strong>
        </span>
      </div>
      <div className="shipping-table-wrap">
        <table>
          <caption className="sr-only">
            Example values compared across seven shipping fields
          </caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Instructions (SI)</th>
              <th scope="col">Draft (B/L)</th>
              <th scope="col">Result</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(({ field, si, bl, status }) => (
              <tr key={field} className={status !== "match" ? "shipping-difference" : ""}>
                <th scope="row">{field}</th>
                <td>{si}</td>
                <td>{bl}</td>
                <td>
                  <span className={`field-status field-status-${status}`}>
                    {statusLabel[status]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="shipping-source">
        <span>Source evidence · Shipping Instructions</span>
        <blockquote>&ldquo;Total containers: 3 x 20&apos; GP&rdquo;</blockquote>
        <p>
          The draft states 4 containers. SI specifies 3. Flag for operator review
          before requesting a correction from the carrier.
        </p>
      </div>
    </figure>
  );
}
