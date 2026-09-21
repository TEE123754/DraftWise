import type { Metadata } from "next";

export const metadata: Metadata = { title: "Completed checks" };

export default function CompletedLayout({ children }: { children: React.ReactNode }) {
  return children;
}
