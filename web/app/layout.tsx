import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "AI-таргетолог",
  description: "Автономный performance-таргетолог для Meta Ads",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <Sidebar />
        <main className="ml-64 min-h-screen px-8 py-8">{children}</main>
      </body>
    </html>
  );
}
