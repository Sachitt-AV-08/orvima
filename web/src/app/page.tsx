"use client";

import { useEffect, useState } from "react";
import { motion, Variants } from "framer-motion";
import { ArrowRight, Check, Copy, Globe2, ShieldAlert, Sparkles, Terminal } from "lucide-react";

const fadeUp: Variants = { hidden: { opacity: 0, y: 32, filter: "blur(6px)" }, visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.75, ease: [0.22, 1, 0.36, 1] } } };
const stagger: Variants = { hidden: {}, visible: { transition: { staggerChildren: 0.14 } } };

const worries = ["Step 1/4: browse_navigate → ok", "Step 2/4: browse_click → ok", "Step 3/4: browse_type → ok", "Step 4/4: browse_click → ok", "result: success"];
const gateLines = ["→ browse_click Selector: button.delete[data-account=\"all\"]", "classifier: outbound / destructive", "risk: deletes_all_account_data", "allowed: false", "approval: pending_human", "click never ran."];
const stack = [{ title: "AI", caption: "Claude, Cursor, Copilot, your own agent", accent: false }, { title: "MCP", caption: "49 tools across 8 domains", accent: false }, { title: "Gate", caption: "classifier: run / ask / refuse", accent: true }, { title: "Browser", caption: "your browser at 127.0.0.1", accent: false }];
const pills = ["browse_navigate", "browse_click", "browse_type", "browse_snapshot", "browse_wait_for", "browse_extract_text", "browse_download_file"];

export default function Home() {
  const [copied, setCopied] = useState(false);
  const [idx, setIdx] = useState(0);
  const cmd = "irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex";
  useEffect(() => { const id = setInterval(() => setIdx((i) => (i + 1) % 3), 1600); return () => clearInterval(id); }, []);

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#090a0d] text-[#f0f2f5]">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="absolute -top-10 left-1/2 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-[#f5a524]/[.09] blur-[120px]" />
        <div className="absolute right-[10%] top-[40%] h-[320px] w-[320px] rounded-full bg-emerald-400/[.05] blur-[110px]" />
        <motion.div className="absolute left-[8%] top-[15%] h-[200px] w-[200px] rounded-full bg-[#f5a524]/[.04] blur-[100px]" animate={{ y: [0, -30, 0] }} transition={{ duration: 11, repeat: Infinity, ease: "easeInOut" }} />
        <div className="absolute inset-0 opacity-[.22]" style={{ backgroundImage: "linear-gradient(rgba(245,165,36,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(245,165,36,.05) 1px,transparent 1px)", backgroundSize: "64px 64px", maskImage: "radial-gradient(ellipse 70% 60% at 50% 30%, black 35%, transparent 100%)" }} />
      </div>

      <header className="sticky top-0 z-50 border-b border-[#1e242d]/80 backdrop-blur-xl bg-[#090a0d]/80">
        <nav className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-3">
          <a href="#top" className="group flex items-center gap-2 text-[#f0f2f5]">
            <svg className="h-7 w-7 text-[#f5a524]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 L20 8 L20 16 L12 22 L4 16 L4 8 Z"/><path d="M12 6 L12 18"/><path d="M8 12 L16 12"/></svg>
            <span className="text-lg font-semibold tracking-tight">orvima</span>
          </a>
          <div className="flex items-center gap-2 text-sm">
            {[["Proof", "#proof"], ["The gate", "#gate"], ["Docs", "docs.html"]].map(([label, href]) => (
              <a key={href} href={href} className="hidden rounded-md px-3 py-2 text-[#a0a8b3] transition hover:bg-[#111419] hover:text-[#f0f2f5] sm:inline-block">{label}</a>
            ))}
            <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="rounded-md border border-[#2a313d] px-3 py-2 transition hover:border-[#f5a524] hover:text-[#f5a524]">GitHub</a>
          </div>
        </nav>
      </header>

      <section id="top" className="relative mx-auto grid max-w-6xl gap-10 px-5 pb-16 pt-14 md:grid-cols-[1.05fr_1fr] md:items-start md:gap-12 md:pt-20">
        <motion.div initial="hidden" animate="visible" variants={stagger} className="space-y-7">
          <motion.p variants={fadeUp} className="text-xs font-medium uppercase tracking-[.2em] text-[#a0a8b3]">MIT · self-hosted · 49 tools · nothing leaves your machine</motion.p>
          <motion.h1 variants={fadeUp} className="text-balance text-5xl font-semibold leading-[1.05] tracking-tight sm:text-6xl">
            A browser agent that admits{" "} <span className="bg-gradient-to-r from-[#f5a524] to-[#ffcf72] bg-clip-text text-transparent"> when it isn&apos;t sure. </span>
          </motion.h1>
          <motion.p variants={fadeUp} className="max-w-xl text-lg leading-relaxed text-[#a0a8b3]">
            Most browser MCPs tell you the click worked. orvima re-reads the DOM and tells you whether it actually changed — and says{" "}
            <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f5a524]">verified: false</code>{" "} when it couldn&apos;t confirm. No guessing dressed up as success.
          </motion.p>
          <motion.div variants={fadeUp} className="flex flex-wrap items-center gap-3">
            <motion.a href="#install" className="group relative inline-flex items-center gap-2 overflow-hidden rounded-xl bg-[#f5a524] px-5 py-3 text-sm font-semibold text-[#141004] shadow-lg shadow-[#f5a524]/25" whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.98 }}>Get started <ArrowRight size={16} className="transition group-hover:translate-x-0.5" /></motion.a>
            <motion.a href="#proof" className="inline-flex items-center gap-2 rounded-xl border border-[#2a313d] px-5 py-3 text-sm font-semibold text-[#f0f2f5] transition hover:border-[#f5a524]/60" whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}>See a real run</motion.a>
          </motion.div>
          <motion.div variants={fadeUp} className="glass mt-6 flex items-center gap-3 rounded-2xl border border-[#1e242d] p-2 pr-3 shadow-glow">
            <div className="flex items-center gap-1.5 rounded-lg border border-[#2a313d] bg-[#090a0d] p-1">
              {["Windows", "macOS / Linux", "Source"].map((t, i) => (
                <button key={t} onClick={() => setIdx(i)} className={`rounded-md px-2.5 py-1.5 text-xs transition ${idx === i ? "bg-[#f5a524] font-semibold text-[#141004]" : "text-[#a0a8b3] hover:text-[#f0f2f5]"}`}>{t}</button>
              ))}
            </div>
            <code className="flex-1 truncate text-xs text-[#dfe3e8]" style={{ fontFamily: "var(--font-geist-mono, monospace)" }}>
              {idx === 0 ? "irm ... | iex" : idx === 1 ? "curl -fsSL ... | bash" : "uv sync"}
            </code>
          </motion.div>
          <motion.ul variants={fadeUp} className="flex flex-wrap gap-2 pt-2 text-xs">
            {pills.map((p) => (<li key={p} className="rounded-full border border-[#1e242d] bg-[#111419] px-3 py-1 text-[#a0a8b3] transition hover:border-[#f5a524] hover:text-[#f5a524]">{p}</li>))}
          </motion.ul>
        </motion.div>

        <motion.aside initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.2 }} className="glass relative overflow-hidden rounded-2xl border border-[#1e242d] shadow-2xl">
          <div className="flex items-center gap-2 border-b border-[#1e242d] px-4 py-3 text-xs text-[#a0a8b3]">
            <div className="flex gap-1.5"><span className="h-2.5 w-2.5 rounded-full bg-[#f0645c]" /><span className="h-2.5 w-2.5 rounded-full bg-[#f5a524]" /><span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /></div>
            <span className="ml-2 font-mono">orvima run &quot;delete everything in my account&quot;</span>
          </div>
          <div className="relative h-[360px] overflow-hidden bg-[#06080b] p-4 font-mono text-[13px] leading-7">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_60%_at_50%_0%,rgba(245,165,36,.05),transparent)]" />
            {Array.from({ length: 36 }).map((_, i) => { const d = { left: `${(i * 73) % 100}%`, top: `${(i * 37) % 100}%`, delay: (i % 12) * 0.45 }; return (<motion.span key={i} className="pointer-events-none absolute block h-[2px] w-[2px] rounded-full bg-[#f5a524]/30" style={{ left: d.left, top: d.top }} animate={{ opacity: [0.2, 0.9, 0.2], scale: [1, 1.6, 1] }} transition={{ duration: 4, repeat: Infinity, delay: d.delay }} />); })}
            <div className="relative">
              {gateLines.map((l, i) => (
                <motion.div key={l} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.6 + i * 0.45, duration: 0.4 }} className={l.includes("allowed: false") ? "text-[#f0645c] font-semibold" : l.includes("click never ran") ? "text-emerald-400" : "text-[#a0a8b3]"}>
                  <span className="mr-2 select-none text-[#6b7480]">{">"}</span>{l}
                </motion.div>
              ))}
            </div>
          </div>
          <div className="border-t border-[#1e242d] bg-[#0b0d12] px-4 py-3 text-xs text-[#a0a8b3]"><span className="text-emerald-400">●</span> Gate read the selector, judged it <span className="ml-1 text-[#f5a524]">outward</span>, stopped. The click never ran.</div>
        </motion.aside>
      </section>

      <motion.section id="proof" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="mx-auto max-w-6xl px-5 py-24">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[.2em] text-[#a0a8b3]">Proof over promises</p>
          <h2 className="text-3xl font-semibold sm:text-4xl">What a typical MCP returns vs. what orvima returns.</h2>
          <p className="mt-3 text-[#a0a8b3]">Left: a single <code>ok: true</code>, dispatched and forgotten. Right: the DOM is re-read and the verdict is <code>verified: false</code> when it could not confirm — reported, not hidden.</p>
        </motion.div>
        <div className="grid gap-5 md:grid-cols-2">
          <motion.article variants={fadeUp} className="overflow-hidden rounded-2xl border border-[#1e242d] bg-[#111419] p-5">
            <div className="mb-3 text-sm font-medium text-[#a0a8b3]">Typical browser MCP</div>
            <div className="space-y-1 font-mono text-[13px] text-[#a0a8b3]/70">{worries.map((l) => <div key={l}>{l}</div>)}</div>
            <p className="mt-4 text-sm text-[#a0a8b3]">Reports <code>ok: true</code> the moment the click is dispatched. Never re-reads the DOM.</p>
          </motion.article>
          <motion.article variants={fadeUp} className="overflow-hidden rounded-2xl border border-[#f5a524]/40 bg-[#111419] p-5">
            <div className="mb-3 text-sm font-medium text-[#f5a524]">orvima</div>
            <div className="space-y-1 font-mono text-[13px]">
              <div className="text-[#a0a8b3]">step 1/4: browse_navigate → <span className="text-emerald-400">verified: true</span></div>
              <div className="text-[#a0a8b3]">step 2/4: browse_click → <span className="text-emerald-400">verified: true</span></div>
              <div className="text-[#a0a8b3]">step 3/4: browse_type → <span className="text-amber-300">verified: false</span></div>
              <div className="text-[#a0a8b3]">step 4/4: browse_click → <span className="text-emerald-400">verified: true</span></div>
              <div className="mt-1 text-[#f0f2f5]">result: success</div>
            </div>
            <p className="mt-4 text-sm text-[#a0a8b3]">Re-reads the DOM afterwards. Returns <code>verified: false</code> when it could not confirm.</p>
          </motion.article>
        </div>
      </motion.section>

      <motion.section id="gate" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="mx-auto max-w-6xl px-5 py-24">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[.2em] text-[#a0a8b3]">The safety gate</p>
          <h2 className="text-3xl font-semibold sm:text-4xl">Refusal is the feature, not the failure.</h2>
          <p className="mt-3 text-[#a0a8b3]">The gate classifies every outbound action into run, ask, or refuse — and never silently proceeds when it can&apos;t tell.</p>
        </motion.div>
        <motion.div variants={fadeUp} className="glass rounded-2xl border border-[#1e242d] p-5 font-mono text-sm">
          <div className="mb-3 flex items-center gap-2 text-xs text-[#a0a8b3]"><span className="text-[#f0645c]">●</span> blocked · delete all account data</div>
          <div className="space-y-1.5">{gateLines.map((l) => (<div key={l} className={l.includes("allowed: false") ? "text-[#f0645c] font-semibold" : l.includes("click never ran") ? "text-emerald-400" : "text-[#a0a8b3]"}>{l}</div>))}</div>
        </motion.div>
      </motion.section>

      <motion.section id="stack" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="mx-auto max-w-6xl px-5 py-24">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[.2em] text-[#a0a8b3]">The stack</p>
          <h2 className="text-3xl font-semibold sm:text-4xl">Three parts, each honest and testable.</h2>
        </motion.div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stack.map((s, i) => (
            <motion.div key={s.title} variants={fadeUp} transition={{ delay: i * 0.08 }} whileHover={{ y: -6, scale: 1.02 }} className="relative rounded-2xl border p-5 transition" style={{ background: s.accent ? "rgba(245,165,36,.07)" : "#111419", borderColor: s.accent ? "rgba(245,165,36,.3)" : "#1e242d" }}>
              <div className={`mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl ${s.accent ? "bg-[#f5a524]/20 text-[#f5a524]" : "bg-[#1e242d] text-[#a0a8b3]"}`}>{s.accent ? <ShieldAlert size={22} /> : s.title === "AI" ? <Sparkles size={22} /> : s.title === "MCP" ? <Terminal size={22} /> : <Globe2 size={22} />}</div>
              <div className={`text-base font-semibold ${s.accent ? "text-[#f5a524]" : "text-[#f0f2f5]"}`}>{s.title}</div>
              <div className="mt-1 text-xs text-[#a0a8b3]">{s.caption}</div>
            </motion.div>
          ))}
        </div>
      </motion.section>

      <motion.section id="tools" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="mx-auto max-w-6xl px-5 py-24">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="mb-3 text-xs font-medium uppercase tracking-[.2em] text-[#a0a8b3]">Tools</p>
          <h2 className="text-3xl font-semibold sm:text-4xl">49 tools across 8 domains.</h2>
          <p className="mt-3 text-[#a0a8b3]">Browse, mail, WhatsApp, voice, media, math, science, and a fail-closed safety gate. Every component an MCP host can call.</p>
        </motion.div>
        <motion.div variants={fadeUp} className="flex flex-wrap gap-2">
          {["browse_navigate", "browse_click", "browse_type", "browse_snapshot", "browse_wait_for", "browse_extract_text", "browse_download_file", "mail_compose", "whatsapp_send", "voice_speak", "media_transcript", "math_solve", "science_metric", "gate_check"].map((p) => (
            <motion.span key={p} whileHover={{ y: -4, scale: 1.05 }} className="rounded-md border border-[#1e242d] bg-[#111419] px-3 py-1.5 font-mono text-xs text-[#a0a8b3] transition hover:border-[#f5a524] hover:text-[#f5a524]">{p}</motion.span>
          ))}
        </motion.div>
      </motion.section>

      <motion.section id="install" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={stagger} className="mx-auto max-w-6xl px-5 py-24">
        <motion.div variants={fadeUp} className="overflow-hidden rounded-3xl border border-[#1e242d] bg-gradient-to-br from-[#111419] to-[#0b0d12] p-8 md:p-12">
          <h2 className="text-3xl font-semibold sm:text-4xl">Install in one line.</h2>
          <p className="mt-3 max-w-xl text-[#a0a8b3]">Point your MCP host at a self-hosted server on your own machine. Your browser, your logins, your data.</p>
          <div className="mt-6 flex items-center gap-3 rounded-xl border border-[#2a313d] bg-[#06080b] p-3 font-mono text-sm">
            <span className="text-[#6b7480]">$</span>
            <code className="flex-1 text-[#dfe3e8]">irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex</code>
            <button onClick={() => { navigator.clipboard.writeText(cmd).catch(() => {}); setCopied(true); setTimeout(() => setCopied(false), 1400); }} className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[#2a313d] transition hover:border-[#f5a524] hover:text-[#f5a524]" aria-label="Copy install command">{copied ? <Check size={15} /> : <Copy size={15} />}</button>
          </div>
        </motion.div>
      </motion.section>

      <footer className="border-t border-[#1e242d] py-10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 text-sm text-[#6b7480]">
          <span>© {new Date().getFullYear()} orvima · MIT</span>
          <span>Self-hosted. Your browser. Your logins. Your machine.</span>
        </div>
      </footer>
    </main>
  );
}
