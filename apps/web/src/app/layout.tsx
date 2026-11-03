import type { Metadata } from "next";
import { Geist_Mono, Instrument_Sans, Newsreader } from "next/font/google";

import { themeScript } from "@/lib/theme";

import "./globals.css";

const sans = Instrument_Sans({ variable: "--font-sans-face", subsets: ["latin"] });
const display = Newsreader({ variable: "--font-display-face", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono-face", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Knowledge base copilot",
  description:
    "Upload a knowledge base and talk with a support agent that can see your screen.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    // The head script sets data-theme before React hydrates, so the attribute
    // differs from the server render on purpose.
    <html
      lang="en"
      data-theme="light"
      data-gray-color="gray"
      suppressHydrationWarning
      className={`${sans.variable} ${display.variable} ${mono.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
