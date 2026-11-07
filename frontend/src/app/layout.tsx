import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "n8chain — Part 2: Validation Studio",
  description:
    "Hybrid Niche Matching (convaiinnovations/laya), Content Creator & Business Suitability Verdicts, and Optimization Handoff.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#090b10] text-slate-100 antialiased">
        {children}
      </body>
    </html>
  );
}
