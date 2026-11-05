import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// Figtree for the interface (soft, geometric, very legible), EB Garamond for display (a classic old-style serif with a
// beautiful italic), Geist Mono for numbers and machine text.
// Self-hosted (SIL OFL) so builds never depend on fetching from Google Fonts.
const uiSans = localFont({
  variable: "--font-ui-sans", display: "swap",
  src: [{ path: "./fonts/DMSans-normal.woff2", weight: "300 700", style: "normal" }, { path: "./fonts/DMSans-italic.woff2", weight: "300 700", style: "italic" }],
});
const geistMono = localFont({ variable: "--font-geist-mono", src: "./fonts/GeistMono-normal.woff2", weight: "100 900", display: "swap" });
const displaySerif = localFont({
  variable: "--font-display-serif", display: "swap",
  src: [{ path: "./fonts/Fraunces-normal.woff2", weight: "300 700", style: "normal" }, { path: "./fonts/Fraunces-italic.woff2", weight: "300 700", style: "italic" }],
});

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: "Stunt Double — let the double take the hit", template: "%s · Stunt Double" },
  description: "Your AI agent rehearses every risky action on a throwaway copy of your business, inside an isolated Vultr sandbox. You approve consequences, not code.",
  icons: {
    icon: [{ url: "/favicon.ico", sizes: "32x32" }, { url: "/favicon.svg", type: "image/svg+xml" }, { url: "/favicon-96x96.png", sizes: "96x96", type: "image/png" }],
    apple: [{ url: "/apple-touch-icon.png", sizes: "180x180" }],
  },
  manifest: "/site.webmanifest",
  openGraph: { title: "Stunt Double", description: "Let the double take the hit. Approve consequences, not code.", images: ["/og.png"], type: "website" },
  twitter: { card: "summary_large_image", title: "Stunt Double", description: "Let the double take the hit.", images: ["/og.png"] },
};

export const viewport: Viewport = { themeColor: [{ media: "(prefers-color-scheme: light)", color: "#FAFAF8" }, { media: "(prefers-color-scheme: dark)", color: "#0A0A0A" }] };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${uiSans.variable} ${geistMono.variable} ${displaySerif.variable}`}>
      <body className="antialiased">
        {children}
        <Toaster position="bottom-center" />
      </body>
    </html>
  );
}
