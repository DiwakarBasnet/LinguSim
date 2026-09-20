import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import HintLanguageGate from "@/components/HintLanguageGate";
import HintLanguagePicker from "@/components/HintLanguagePicker";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LinguSim",
  description: "Adaptive voice-based language simulation engine",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="border-b border-black/10 dark:border-white/10">
          <nav className="mx-auto flex max-w-6xl items-center gap-6 px-6 py-4 text-sm">
            <Link href="/" className="font-semibold tracking-tight">
              LinguSim
            </Link>
            <Link href="/" className="text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white">
              Dashboard
            </Link>
            <Link
              href="/scenarios"
              className="text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white"
            >
              Missions
            </Link>
            <Link
              href="/progress"
              className="text-black/60 hover:text-black dark:text-white/60 dark:hover:text-white"
            >
              Journey
            </Link>
            <HintLanguagePicker />
          </nav>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
          <HintLanguageGate>{children}</HintLanguageGate>
        </main>
      </body>
    </html>
  );
}
