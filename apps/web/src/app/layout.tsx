import type { Metadata } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Instrument_Sans } from "next/font/google";

import { AppShell } from "@/components/AppShell";
import { QueryProvider } from "@/lib/query";
import { SessionProvider } from "@/lib/session";

import "./globals.css";

const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-bricolage",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

const instrument = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument",
  display: "swap",
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-plex-mono",
  display: "swap",
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Mnemos — metered, revocable memory access on NEAR",
  description:
    "Keep notes encrypted in your own vault. Let an AI agent read one scope, for a price, under a daily cap, and leave a hash-only receipt on chain.",
  icons: { icon: "/icon.svg" },
};

/**
 * Applied before first paint so the page never flashes the wrong theme.
 */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem('mnemos.theme');if(t!=='light'&&t!=='dark'){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}document.documentElement.classList.toggle('dark',t==='dark');}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}): React.ReactNode {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${bricolage.variable} ${instrument.variable} ${plexMono.variable}`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="bg-canvas text-ink antialiased">
        <div className="ambient" aria-hidden="true" />
        <SessionProvider>
          <QueryProvider>
            <AppShell>{children}</AppShell>
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
