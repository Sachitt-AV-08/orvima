"use client";

import { useState } from "react";
import { motion, Variants } from "framer-motion";

const ease = [0.22, 1, 0.36, 1] as const;
const rise: Variants = { hidden: { opacity: 0, y: 22 }, visible: { opacity: 1, y: 0, transition: { duration: 0.65, ease } } };
const sequence: Variants = { hidden: {}, visible: { transition: { staggerChildren: 0.1 } } };

const toolNames = ["browse_navigate", "browse_snapshot", "browse_click", "browse_type", "browse_wait_for", "mail_compose", "whatsapp_send", "voice_speak", "media_transcript", "gate_check", "browse_extract_text", "browse_download_file"];

const runLines = [
  "$ browse_navigate --url https://app.example.com/account/settings",
  "verified: true",
  "$ browse_click --selector 'button.delete[data-account=all]'",
  "classifier: destructive outward action",
  "result: held for human approval",
  "click: not executed",
];

const surfaces = [
  { name: "Browse", detail: "navigate, read, click, type, verify", tools: "11 browser tools" },
  { name: "Mail", detail: "compose and deliver from a local account", tools: "4 mail tools" },
  { name: "WhatsApp", detail: "send through a running local session", tools: "2 message tools" },
  { name: "Voice", detail: "speak and transcribe", tools: "2 voice tools" },
  { name: "Media", detail: "capture, extract, download", tools: "5 media tools" },
  { name: "Math and science", detail: "numbers, units, analysis helpers", tools: "6 compute tools" },
  { name: "Gate", detail: "run, ask, or refuse before crossing outward", tools: "multiple gate tools" },
  { name: "Router", detail: "transport and control surface", tools: "MCP plumbing" },
];

export default function Home() {
  const [tab, setTab] = useState(0);
  const [copied, setCopied] = useState(false);

  function copyCommand() {
    navigator.clipboard?.writeText("irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex").catch(function noop() {});
    setCopied(true);
    setTimeout(function reset() { setCopied(false); }, 1400);
  }

  const command = tab === 0
    ? "irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex"
    : tab === 1
      ? "curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | bash"
      : "git clone https://github.com/Sachitt-AV-08/orvima\ncd orvima && uv sync";

  return (
    <main className="min-h-screen bg-[#090a0d] text-[#f0f2f5]">
      <header className="sticky top-0 z-40 border-b border-[#1e242d] bg-[#090a0d]/82 backdrop-blur-md">
        <nav className="mx-auto flex max-w-[1160px] items-center justify-between gap-4 px-5 py-4">
          <a href="#hero" className="flex items-center gap-3">
            <svg className="h-6 w-6 text-[#f5a524]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 L20 8 L20 16 L12 22 L4 16 L4 8 Z"/><path d="M12 6 L12 18"/><path d="M8 12 L16 12"/></svg>
            <span className="text-base font-semibold tracking-tight">orvima</span>
          </a>
          <div className="hidden items-center gap-6 text-sm text-[#a0a8b3] md:flex">
            <a href="#evidence" className="transition hover:text-[#f0f2f5]">Evidence</a>
            <a href="#system" className="transition hover:text-[#f0f2f5]">System</a>
            <a href="#gate" className="transition hover:text-[#f0f2f5]">Safety</a>
            <a href="#install" className="transition hover:text-[#f0f2f5]">Install</a>
            <a href="docs.html" className="transition hover:text-[#f0f2f5]">Docs</a>
          </div>
          <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="hidden rounded-md border border-[#2a313d] px-3 py-2 text-sm text-[#f0f2f5] transition hover:border-[#f5a524] sm:block">Source</a>
        </nav>
      </header>

      <motion.section id="hero" initial="hidden" animate="visible" variants={sequence} className="mx-auto max-w-[1160px] px-5 pb-20 pt-24 md:pt-32">
        <motion.p variants={rise} className="font-mono text-xs uppercase tracking-[0.24em] text-[#6b7480]">runtime 0.2.0 / self-hosted / single-machine</motion.p>
        <motion.h1 variants={rise} className="mt-5 max-w-3xl text-[2.8rem] font-semibold leading-[1.03] tracking-tight sm:text-[4rem] md:text-[4.5rem]">
          A browser agent that reports what actually happened, not what the function call asked for.
        </motion.h1>
        <motion.p variants={rise} className="mt-6 max-w-2xl text-lg leading-relaxed text-[#a0a8b3]">
          orvima re-reads the DOM after each meaningful step and returns <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f5a524]">verified: true</code> or <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f5a524]">verified: false</code>. If it cannot prove what happened, it does not upgrade uncertainty into success.
        </motion.p>
        <motion.div variants={rise} className="mt-8 flex flex-col gap-3 sm:flex-row">
          <a href="#install" className="inline-flex items-center justify-center gap-2 rounded-md bg-[#f5a524] px-5 py-3 text-sm font-semibold text-[#141004] transition hover:bg-[#ffba3d]">Install orvima</a>
          <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="inline-flex items-center justify-center gap-2 rounded-md border border-[#2a313d] px-5 py-3 text-sm font-semibold text-[#f0f2f5] transition hover:border-[#f5a524]">Read the source</a>
        </motion.div>
        <motion.div variants={rise} className="mt-10 grid max-w-2xl gap-px overflow-hidden rounded-md border border-[#1e242d] bg-[#1e242d] text-sm">
          {[
            ["49", "tools exposed to MCP hosts"],
            ["8", "product domains"],
            ["1", "DOM read after every state change"],
          ].map(function(row) {
            return (
              <div key={row[0]} className="flex items-baseline gap-4 bg-[#0d1014] px-4 py-3">
                <span className="w-8 font-mono text-lg font-semibold text-[#f5a524]">{row[0]}</span>
                <span className="text-[#a0a8b3]">{row[1]}</span>
              </div>
            );
          })}
        </motion.div>
        <motion.div variants={rise} className="mt-16 max-w-2xl rounded-md border border-[#1e242d] bg-[#0d1014] p-5 font-mono text-xs leading-6 text-[#a0a8b3]">
          {runLines.map(function(line) {
            return (
              <div
                key={line}
                className={
                  line.includes("held") || line.includes("classifier")
                    ? "text-[#f5a524]"
                    : line.includes("verified")
                      ? "text-emerald-400"
                      : line.includes("click: not executed")
                        ? "text-[#f0645c]"
                        : ""
                }
              >
                {line}
              </div>
            );
          })}
        </motion.div>
      </motion.section>

      <motion.section id="evidence" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.25 }} variants={sequence} className="mx-auto max-w-[1160px] px-5 py-24">
        <motion.h2 variants={rise} className="max-w-2xl text-3xl font-semibold tracking-tight sm:text-4xl">The evidence is in the execution path, not only in the launch page.</motion.h2>
        <motion.p variants={rise} className="mt-4 max-w-2xl text-[#a0a8b3]">
          Ordinary execution returns a result after dispatch. orvima returns what it could confirm and keeps a transcript you can re-read.
        </motion.p>
        <div className="mt-12 grid gap-6 md:grid-cols-2">
          <div className="rounded-md border border-[#1e242d] bg-[#0d1014] p-6">
            <p className="text-sm text-[#a0a8b3]">What a typical MCP result sounds like</p>
            <div className="mt-4 space-y-2 border-l-2 border-[#2a313d] pl-4 font-mono text-sm text-[#a0a8b3]/75">
              <p>step 1: browse_navigate → ok</p>
              <p>step 2: browse_click → ok</p>
              <p>step 3: browse_click → ok</p>
              <p>result: success</p>
            </div>
            <p className="mt-4 text-sm text-[#a0a8b3]">The transport itself completed. That does not say what the page displayed.</p>
          </div>
          <div className="rounded-md border border-[#1e242d] bg-[#0d1014] p-6">
            <p className="text-sm text-[#f5a524]">What orvima keeps after the run</p>
            <div className="mt-4 space-y-2 border-l-2 border-[#f5a524]/40 pl-4 font-mono text-sm">
              <p className="text-[#a0a8b3]">step 1: browse_navigate → <span className="text-emerald-400">verified: true</span></p>
              <p className="text-[#a0a8b3]">step 2: browse_click → <span className="text-amber-300">verified: false</span></p>
              <p className="text-[#a0a8b3]">step 3: gate_check → <span className="text-[#f0645c]">refused</span></p>
              <p className="mt-3 text-[#a0a8b3]">state captured, approval card written, run stopped</p>
            </div>
            <p className="mt-4 text-sm text-[#a0a8b3]">Every edge stays in memory with evidence instead of disappearing into generated prose.</p>
          </div>
        </div>
      </motion.section>

      <motion.section id="system" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={sequence} className="mx-auto max-w-[1160px] px-5 py-24">
        <div className="grid gap-10 md:grid-cols-[0.85fr_1.15fr]">
          <motion.div variants={sequence} className="space-y-5">
            <motion.h2 variants={rise} className="text-3xl font-semibold tracking-tight sm:text-4xl">Tools shaped around execution truth.</motion.h2>
            <motion.p variants={rise} className="text-[#a0a8b3]">
              Eight domains share one object model. The tool names below are the public interface MCP hosts actually call.
            </motion.p>
            <div className="flex flex-wrap gap-2">
              {toolNames.map(function(name) {
                return (
                  <span key={name} className="rounded border border-[#1e242d] bg-[#0d1014] px-2.5 py-1 font-mono text-xs text-[#a0a8b3]">
                    {name}
                  </span>
                );
              })}
            </div>
          </motion.div>
          <div className="grid gap-0 divide-y divide-[#1e242d] border-y border-[#1e242d]">
            {surfaces.map(function(surface) {
              return (
                <div key={surface.name} className="grid grid-cols-[120px_1fr_auto] items-center gap-4 py-4 text-sm">
                  <span className="font-semibold text-[#f0f2f5]">{surface.name}</span>
                  <span className="text-[#a0a8b3]">{surface.detail}</span>
                  <span className="font-mono text-xs text-[#6b7480]">{surface.tools}</span>
                </div>
              );
            })}
          </div>
        </div>
      </motion.section>

      <motion.section id="gate" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.2 }} variants={sequence} className="mx-auto max-w-[1160px] px-5 py-24">
        <motion.div variants={sequence} className="max-w-2xl">
          <motion.p variants={rise} className="font-mono text-xs uppercase tracking-[0.24em] text-[#6b7480]">Safety gate</motion.p>
          <motion.h2 variants={rise} className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">Refusal is cheaper than cleaning up a bad action.</motion.h2>
          <motion.p variants={rise} className="mt-4 text-[#a0a8b3]">
            The classifier labels actions as run, ask, or refuse. A high-risk click is stopped before execution, and the reason is visible instead of hiding in a context trail.
          </motion.p>
        </motion.div>
        <div className="mt-10 grid gap-6 md:grid-cols-[1fr_1fr]">
          <div className="rounded-md border border-[#1e242d] bg-[#0d1014] p-6 font-mono text-sm text-[#a0a8b3]">
            <div className="mb-4 border-b border-[#1e242d] pb-3 text-[#f5a524]">held-approval.txt</div>
            <div>risk: deletes_all_account_data</div>
            <div>reason: destructive account selector targets all data</div>
            <div>action: browse_click</div>
            <div>result: not executed</div>
          </div>
          <div className="rounded-md border border-[#1e242d] bg-[#0d1014] p-6 text-sm text-[#a0a8b3]">
            <p className="font-medium text-[#f0f2f5]">Human-reviewable, not only machine-readable.</p>
            <p className="mt-4">The card preserves the selector, arguments, risk, and reason that a human would use to make the decision. A failed run can be audited later without reconstructing it from a deleted chat.</p>
            <p className="mt-4">A classifier that asks in the right place reduces unobservable state changes far more than another prompt layer.</p>
          </div>
        </div>
      </motion.section>

      <motion.section id="install" initial="hidden" whileInView="visible" viewport={{ once: true, amount: 0.25 }} variants={sequence} className="mx-auto max-w-[1160px] px-5 py-24">
        <motion.div variants={rise} className="mb-8">
          <h2 className="text-3xl font-semibold tracking-tight sm:text-4xl">Install locally and keep the evidence where the run happens.</h2>
          <p className="mt-4 max-w-2xl text-[#a0a8b3]">
            No cloud approval surface is required for the local execution path. The transcripts and run evidence stay next to the action that generated them.
          </p>
        </motion.div>
        <div className="rounded-md border border-[#1e242d] bg-[#0d1014] p-3">
          <div className="flex gap-2 rounded bg-[#090a0d] p-1 text-xs">
            {["Windows", "macOS / Linux", "Source"].map(function(label, index) {
              return (
                <button key={label} onClick={function choose() { setTab(index); }} className={"flex-1 rounded px-3 py-2 transition " + (tab === index ? "bg-[#f5a524] font-semibold text-[#141004]" : "text-[#a0a8b3] hover:text-[#f0f2f5]")}>
                  {label}
                </button>
              );
            })}
          </div>
          <div className="mt-3 flex items-center gap-3 px-3 py-3">
            <span className="font-mono text-[#6b7480]">$</span>
            <code className="flex-1 overflow-x-auto font-mono text-sm text-[#dfe3e8]">{command}</code>
            <button onClick={copyCommand} className="rounded border border-[#2a313d] px-3 py-2 text-sm text-[#f0f2f5] transition hover:border-[#f5a524]" type="button">
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
        <p className="mt-4 text-sm text-[#6b7480]">The command is the same one documented in the repository and does not include legacy placeholder steps.</p>
      </motion.section>

      <footer className="border-t border-[#1e242d] bg-[#070910]">
        <div className="mx-auto flex max-w-[1160px] flex-col gap-6 px-5 py-10 sm:flex-row sm:items-end sm:justify-between">
          <div className="space-y-3">
            <div className="flex items-center gap-2 font-semibold">
              <svg className="h-5 w-5 text-[#f5a524]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 L20 8 L20 16 L12 22 L4 16 L4 8 Z"/><path d="M12 6 L12 18"/><path d="M8 12 L16 12"/></svg>
              orvima
            </div>
            <p className="max-w-md text-sm text-[#6b7480]">
              Browser control with one principle: if the change cannot be proven, the result says so.
            </p>
          </div>
          <div className="flex flex-wrap gap-4 text-sm text-[#6b7480]">
            <a href="docs.html" className="transition hover:text-[#f0f2f5]">Documentation</a>
            <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="transition hover:text-[#f0f2f5]">Source</a>
            <span>{new Date().getFullYear()}</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
