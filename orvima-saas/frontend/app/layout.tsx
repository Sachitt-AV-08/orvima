import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });
const mono = JetBrains_Mono({ subsets: ['latin'], variable: '--font-mono' });

export const metadata: Metadata = {
  title: 'Orvima — Deploy Browser Sessions, Get CDP URLs',
  description: 'Give your AI agent 49 verified MCP tools: browser, email, WhatsApp, voice, math, science. Self-hosted. MIT licensed.',
  keywords: ['MCP', 'Playwright', 'browser automation', 'AI agents', 'CDP', 'email automation', 'WhatsApp automation'],
  authors: [{ name: 'Sachitt' }],
  openGraph: {
    title: 'Orvima — Deploy Browser Sessions, Get CDP URLs',
    description: 'Give your AI agent 49 verified MCP tools. Self-hosted. MIT licensed.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-orvima-bg text-orvima-text antialiased">
        {children}
      </body>
    </html>
  );
}