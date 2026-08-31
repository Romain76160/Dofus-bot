import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Dofus Hybrid Observer",
  description: "Hybrid network, data and vision observer dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}
