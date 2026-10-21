import "@fontsource-variable/archivo";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";

import type { Metadata } from "next";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "Invoice Block Radar",
  description:
    "Predicts which purchase order lines will hit an invoice payment block, and prepares the fix for the ones that still do.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="bar">
          <div className="bar-inner">
            <a className="brand" href="/">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="1.6" />
                <circle cx="12" cy="12" r="5.5" stroke="currentColor" strokeWidth="1.2" opacity="0.6" />
                <path d="M12 12 L19 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                <circle cx="16.5" cy="15" r="1.6" fill="currentColor" />
              </svg>
              Invoice Block Radar
            </a>
            <Nav />
            <span className="source">BPI Challenge 2019 · purchase-to-pay log, 2018</span>
          </div>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
