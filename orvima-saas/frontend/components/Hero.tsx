'use client';

import { motion } from 'framer-motion';
import { Terminal, Send, MessageSquare, Mic2, Shield, CheckCircle, ArrowRight, Github } from 'lucide-react';
import { cn } from '@/lib/utils';

const features = [
  { icon: Terminal, title: 'Browser Automation', desc: 'Full CDP control. DOM-verified clicks, types, navigates.' },
  { icon: Send, title: 'Email (SMTP/IMAP)', desc: 'Send & read emails. Verified delivery. Templates & campaigns.' },
  { icon: MessageSquare, title: 'WhatsApp Web', desc: 'Send messages, read chats, download media. Real WhatsApp Web.' },
  { icon: Mic2, title: 'Voice (Edge TTS)', desc: '3 styles. Ultron modulation. Pitch -2.5st, reverb, metallic EQ.' },
  { icon: Shield, title: 'Safety Gates', desc: 'Destructive actions → human approval. Auto-expires. Verified badges.' },
  { icon: CheckCircle, title: '49 MCP Tools', desc: 'One server. Browser + Mail + WhatsApp + Voice + Math + Science.' },
];

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center overflow-hidden pt-20">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-orvima-accent/10 rounded-full blur-3xl animate-float" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-orvima-accent/5 rounded-full blur-3xl animate-float" style={{ animationDelay: '-3s' }} />
      </div>

      <div className="relative z-10 max-w-6xl mx-auto px-6 py-20 text-center">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="mb-12"
        >
          <span className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-orvima-card border border-orvima-border text-orvima-accent text-sm font-medium">
            <span className="w-2 h-2 bg-orvima-accent rounded-full animate-pulse" />
            Orvima v0.2.0 — 49 MCP Tools
          </span>
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight mb-8 text-balance"
        >
          Deploy browser sessions
          <br />
          <span className="text-orvima-accent">Get a CDP URL</span>
          <br />
          Connect any Playwright client
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="text-lg md:text-xl text-orvima-textMuted max-w-3xl mx-auto mb-12"
        >
          Your AI agent can browse. But can it send emails? WhatsApp? Speak?
          Orvima gives agents 49 verified tools — browser, mail, WhatsApp, voice, math, science.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3 }}
          className="flex flex-col sm:flex-row gap-4 justify-center mb-16"
        >
          <a
            href="#deploy"
            className="group inline-flex items-center gap-2 px-8 py-4 rounded-lg bg-orvima-accent text-orvima-bg font-semibold text-lg hover:bg-orvima-accentHover transition-colors"
          >
            Deploy Free Session
            <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
          </a>
          <a
            href="https://github.com/Sachitt-AV-08/orvima"
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-2 px-8 py-4 rounded-lg border border-orvima-border text-orvima-text font-semibold text-lg hover:border-orvima-accent hover:text-orvima-accent transition-colors"
          >
            <Github className="w-5 h-5" />
            View on GitHub
          </a>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="flex flex-wrap justify-center gap-3 text-sm text-orvima-textMuted"
        >
          <span className="px-3 py-1 rounded-full bg-orvima-card border border-orvima-border">MIT Licensed</span>
          <span className="px-3 py-1 rounded-full bg-orvima-card border border-orvima-border">Self-hosted</span>
          <span className="px-3 py-1 rounded-full bg-orvima-card border border-orvima-border">No cloud lock-in</span>
          <span className="px-3 py-1 rounded-full bg-orvima-card border border-orvima-border">WCAG AA</span>
        </motion.div>
      </div>

      <motion.div
        initial={{ opacity: 0, y: 40 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.5 }}
        className="absolute bottom-10 left-1/2 -translate-x-1/2 animate-bounce"
      >
        <svg className="w-6 h-6 text-orvima-textMuted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </motion.div>
    </section>
  );
}

export function Features() {
  return (
    <section id="features" className="py-24 px-6 bg-orvima-card/50">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">49 Tools. One Server.</h2>
          <p className="text-orvima-textMuted text-lg max-w-2xl mx-auto">
            Every tool DOM-verified. Every destructive action gated. Run on your infra.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, i) => (
            <motion.article
              key={feature.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1 }}
              className="group p-6 bg-orvima-card border border-orvima-border rounded-xl hover:border-orvima-accent/50 transition-all duration-300"
            >
              <div className="w-12 h-12 bg-orvima-accent/10 rounded-lg flex items-center justify-center mb-4 group-hover:bg-orvima-accent/20 transition-colors">
                <feature.icon className="w-6 h-6 text-orvima-accent" />
              </div>
              <h3 className="text-xl font-semibold mb-2">{feature.title}</h3>
              <p className="text-orvima-textMuted">{feature.desc}</p>
            </motion.article>
          ))}
        </div>
      </div>
    </section>
  );
}