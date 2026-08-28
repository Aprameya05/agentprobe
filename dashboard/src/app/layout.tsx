import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AgentProbe -- Agentic Readiness Score",
  description: "Point it at any URL. An AI agent attempts real tasks. You get a scored report: exactly where AI agents give up on your site.",
  openGraph: {
    title: "AgentProbe",
    description: "SEO is for Google. AgentProbe is for AI agents.",
    url: "https://agentprobe.pages.dev",
    siteName: "AgentProbe",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-[#0a0a0f] text-gray-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}
