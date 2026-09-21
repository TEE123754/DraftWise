import type { Metadata } from "next";
import { AuthProvider } from "@/components/auth-provider";
import { AppShell } from "@/components/app-shell";
import "./globals.css";
import "./document-design.css";
import "./workspace-polish.css";

const siteUrl = process.env.SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    template: "%s | DraftWise",
    default: "DraftWise: Every draft checked. Every change explained.",
  },
  description:
    "DraftWise verifies shipping documents against original instructions, highlights every mismatch with source evidence, and tracks corrections through each returned draft.",
  applicationName: "DraftWise",
  keywords: [
    "shipping document verification",
    "bill of lading comparison",
    "shipping instructions",
    "document mismatch",
    "freight document review",
  ],
  authors: [{ name: "DraftWise" }, { name: "Team Commitment Issues" }],
  openGraph: {
    type: "website",
    siteName: "DraftWise",
    images: [
      {
        url: "/opengraph-image.png",
        width: 1200,
        height: 630,
        alt: "DraftWise: Every draft checked. Every change explained.",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
  },
  robots: {
    index: true,
    follow: true,
  },
};

const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${siteUrl}/#organization`,
      name: "DraftWise",
      url: siteUrl,
      logo: {
        "@type": "ImageObject",
        url: `${siteUrl}/brand/logo.png`,
      },
      description:
        "Shipping document verification: compare every draft against original instructions with source evidence.",
    },
    {
      "@type": "WebSite",
      "@id": `${siteUrl}/#website`,
      url: siteUrl,
      name: "DraftWise",
      publisher: { "@id": `${siteUrl}/#organization` },
    },
    {
      "@type": "SoftwareApplication",
      name: "DraftWise",
      applicationCategory: "BusinessApplication",
      operatingSystem: "Web",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "USD",
        description: "Free sample demo: no account required",
      },
      url: siteUrl,
      description:
        "Compare shipping instructions against draft bills of lading. Seven-field comparison with source evidence, amendment tracking, and returned-draft re-checks.",
    },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <head>
        {/* Preconnect to Google Fonts */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        {/* Source Sans 3 */}
        <link
          href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700&display=swap"
          rel="stylesheet"
        />
        {/* JSON-LD structured data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />
        {/* Favicon */}
        <link rel="icon" href="/icon.png" type="image/png" sizes="256x256" />
        <link rel="shortcut icon" href="/favicon.ico" />
        <link rel="apple-touch-icon" href="/apple-icon.png" />
        <meta name="theme-color" content="#0b57c9" />
      </head>
      <body>
        <AuthProvider>
          <AppShell>{children}</AppShell>
        </AuthProvider>
      </body>
    </html>
  );
}
