/**
 * DraftWise logo.
 *
 * `horizontal` (default) is the compact lockup for headers, the sidebar and
 * footers. `full` is the complete logo with its tagline, for pages where the
 * brand has room to breathe (sign-in, 404).
 */
const HEIGHTS = { sm: 40, md: 44, lg: 56 } as const;
const FULL_WIDTHS = { sm: 160, md: 220, lg: 280 } as const;

// Intrinsic sizes of the files in /public/brand, used to reserve layout space.
const HORIZONTAL = {
  src: "/brand/logo-horizontal.png",
  width: 560,
  height: 123,
};
const FULL = { src: "/brand/logo.png", width: 640, height: 483 };

export function WordMark({
  size = "md",
  variant = "horizontal",
  className = "",
}: {
  size?: "sm" | "md" | "lg";
  variant?: "horizontal" | "full";
  className?: string;
}) {
  const asset = variant === "full" ? FULL : HORIZONTAL;
  const height =
    variant === "full"
      ? Math.round((FULL_WIDTHS[size] * FULL.height) / FULL.width)
      : HEIGHTS[size];
  const width = Math.round((height * asset.width) / asset.height);

  return (
    <span className={`inline-flex items-center ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={asset.src}
        alt="DraftWise"
        width={width}
        height={height}
        decoding="async"
        style={{ display: "block", width, height: "auto", maxWidth: "100%" }}
      />
    </span>
  );
}
