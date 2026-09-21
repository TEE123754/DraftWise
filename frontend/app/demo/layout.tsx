import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Try the sample inbox",
  description:
    "Explore shipping document comparison using the provided sample inbox, without signing in.",
  robots: { index: false, follow: false },
};

export default function DemoLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
