'use client';

import { Hero, Features } from '@/components/Hero';
import { TerminalDemo } from '@/components/TerminalDemo';
import { PricingCards } from '@/components/PricingCards';
import { motion } from 'framer-motion';
import { Github, Twitter, MessageSquare } from 'lucide-react';
import Link from 'next/link';

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <nav className="fixed top-0 left-0 right-0 z-50 bg-orvima-bg/80 backdrop-blur-md border-b border-orvima-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-2xl font-bold text-orvima-accent">Orvima</span>
            <span className="text-xs bg-orvima-accent/10 text-orvima-accent px-2 py-0.5 rounded">v0.2.0</span>
          </Link>
          <div className="flex items-center gap-6">
            <Link href="#features" className="text-sm text-orvima-textMuted hover:text-orvima-accent transition-colors">Features</Link>
            <Link href="#pricing" className="text-sm text-orvima-textMuted hover:text-orvima-accent transition-colors">Pricing</Link>
            <Link href="/dashboard" className="px-4 py-2 rounded-lg bg-orvima-accent text-orvima-bg text-sm font-medium hover:bg-orvima-accentHover transition-colors">Dashboard</Link>
          </div>
        </div>
      </nav>

      <Hero />

      <Features />

      <section id="deploy" className="py-24 px-6 bg-orvima-card/30">
        <div className="max-w-4xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-12"
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-4">Try It Now — Free</h2>
            <p className="text-orvima-textMuted text-lg">
              Deploy a real browser session in seconds. Connect with Playwright, Puppeteer, or any CDP client.
            </p>
          </motion.div>

          <TerminalDemo />
        </div>
      </section>

      <PricingCards />

      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
          >
            <h2 className="text-4xl md:text-5xl font-bold mb-6">Ready to Give Your Agent Superpowers?</h2>
            <p className="text-orvima-textMuted text-lg mb-10 max-w-2xl mx-auto">
              Join developers building the next generation of AI agents. 49 tools. One server. Your infrastructure.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Link
                href="/auth/signup"
                className="inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-orvima-accent text-orvima-bg font-semibold text-lg hover:bg-orvima-accentHover transition-colors"
              >
                Create Free Account
              </Link>
              <a
                href="https://github.com/Sachitt-AV-08/orvima"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-8 py-4 rounded-lg border border-orvima-border text-orvima-text font-semibold text-lg hover:border-orvima-accent hover:text-orvima-accent transition-colors"
              >
                <Github className="w-5 h-5" />
                Star on GitHub
              </a>
            </div>
          </motion.div>
        </div>
      </section>

      <footer className="py-12 px-6 border-t border-orvima-border">
        <div className="max-w-6xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <h4 className="font-semibold mb-4">Orvima</h4>
              <p className="text-orvima-textMuted text-sm mb-4">
                49 MCP tools for AI agents. Browser, email, WhatsApp, voice, math, science.
              </p>
              <div className="flex gap-4">
                <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener noreferrer" className="text-orvima-textMuted hover:text-orvima-accent transition-colors">
                  <Github className="w-5 h-5" />
                </a>
                <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="text-orvima-textMuted hover:text-orvima-accent transition-colors">
                  <Twitter className="w-5 h-5" />
                </a>
                <a href="https://discord.com" target="_blank" rel="noopener noreferrer" className="text-orvima-textMuted hover:text-orvima-accent transition-colors">
                  <MessageSquare className="w-5 h-5" />
                </a>
              </div>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-sm text-orvima-textMuted">
                <li><a href="#features" className="hover:text-orvima-accent transition-colors">Features</a></li>
                <li><a href="#pricing" className="hover:text-orvima-accent transition-colors">Pricing</a></li>
                <li><a href="/dashboard" className="hover:text-orvima-accent transition-colors">Dashboard</a></li>
                <li><a href="https://github.com/Sachitt-AV-08/orvima/blob/main/docs/api.md" target="_blank" rel="noopener noreferrer" className="hover:text-orvima-accent transition-colors">API Docs</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Tools</h4>
              <ul className="space-y-2 text-sm text-orvima-textMuted">
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Browser (22 tools)</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Email (2 tools)</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">WhatsApp (5 tools)</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Voice (4 tools)</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Compute (7 tools)</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Gate (3 tools)</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-sm text-orvima-textMuted">
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Privacy Policy</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">Terms of Service</a></li>
                <li><a href="#" className="hover:text-orvima-accent transition-colors">MIT License</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-orvima-border text-center text-sm text-orvima-textMuted">
            <p>Built with <span className="text-orvima-accent">♥</span> by Sachitt. MIT Licensed. Not a clinical tool.</p>
          </div>
        </div>
      </footer>
    </main>
  );
}