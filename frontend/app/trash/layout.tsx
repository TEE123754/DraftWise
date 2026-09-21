import type { Metadata } from "next";
export const metadata: Metadata = {
  title: "Trash",
  description:
    "Review and restore emails removed from your DraftWise workspace.",
  robots: { index: false, follow: false },
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return children;
}
