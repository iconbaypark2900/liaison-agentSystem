import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { ClientProviders } from "@/components/ClientProviders";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Liaison Command Center",
  description: "Agent orchestration and project decisions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0"
        />
      </head>
      <body className={`${inter.variable} font-body`}>
        <ClientProviders>{children}</ClientProviders>
      </body>
    </html>
  );
}
