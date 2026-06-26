import type { Metadata } from "next";
import { Geist, Geist_Mono, Inter_Tight } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
const interTight = Inter_Tight({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["500", "600", "700"],
});

export const metadata: Metadata = {
  title: "JobHunter — Command Center",
  description:
    "Self-hosted job search command center: scrape, score, prepare CVs and engage on LinkedIn.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="es"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${interTight.variable} h-full antialiased`}
    >
      <body className="min-h-full bg-background text-foreground">
        <Providers>
          <Sidebar />
          <div className="relative z-10 flex min-h-screen flex-col md:pl-[76px] min-w-0">
            <TopBar />
            <main className="flex-1 overflow-x-hidden p-5 lg:p-6 min-w-0">
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
