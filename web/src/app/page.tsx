"use client";

import { useEffect, useRef, useState } from "react";
import { motion, Variants } from "framer-motion";
import { ArrowRight, Check, ClipboardCopy, Lock, Play, RotateCw, ShieldAlert, Zap } from "lucide-react";

const fadeUp: Variants = { hidden: { opacity: 0, y: 40, filter: "blur(8px)" }, visible: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: .85, ease: [.18,1,.3,1] } } };
const stagger: Variants = { hidden: {}, visible: { transition: { staggerChildren: .12 } } };

const terminalCommands = [
  "Fast operational sequence",
  "browse_navigate https://app.example.com/account/settings",
  "browse_snapshot → targeted profile zone",
  "browse_click selector=\"button.delete[data-account=all]\"",
  "browse_wait_for selector=\"[data-confirm-screen]\"",
  "result: interrupted by safety gate"
];

const capabilities = [
  { title: "Dom-verified truth", text: "Every step returns verified: true or verified: false. If orvima cannot prove the DOM changed, it says so instead of silently moving on.", icon: <Check size={20}/>, accent: true },
  { title: "Fail-closed safety gate", text: "Actions are classified into run, ask, and refuse. Out-of-bounds clicks are stopped before they touch the page, never after.", icon: <ShieldAlert size={20}/>, accent: false },
  { title: "Your login, your machine", text: "It attaches to your own Chrome through your own cookies and local session. Nothing is proxied through a cloud service and keys stay in your environment.", icon: <Lock size={20}/>, accent: false },
  { title: "49 tools, 8 domains", text: "Browse, mail, WhatsApp, voice, media, math, science, and the security gate form one object model you can hand directly to an MCP host.", icon: <Zap size={20}/>, accent: false },
  { title: "Visible timeline", text: "Each run has a transcript and DOM reads that make an execution reproducible instead of an anecdote hiding in a transcript box.", icon: <RotateCw size={20}/>, accent: false },
  { title: "Attach and watch", text: "Live viewport access means a human can see exactly which node was inspected, which click was withheld, and why the gate produced a pending card.", icon: <Play size={20}/>, accent: false }
];

const workflow = [
  ["Intent", "Your agent sends one structured browser request with a goal and safety scope."],
  ["Observe", "orvima captures the full DOM, target metadata and current state before anything changes."],
  ["Decide", "The safety classifier labels it run, ask, or refuse based on risk rules."],
  ["Verify", "After the action, the agent rereads and reports the real boolean instead of optimistic success."],
  ["Escalate", "High-risk actions generate a held approval with readable risk, reason, and a human decision."],
];

function CountUp({ value }: { value: number }) {
  const [current, setCurrent] = useState(0);
  useEffect(function up() {
    let frame: number;
    const start = performance.now();
    function tick(now: number) {
      const p = Math.min(1, (now - start) / 1200);
      setCurrent(Math.round(value * (1 - Math.pow(1 - p, 3))));
      if (p < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
    return function cleanup() { cancelAnimationFrame(frame); };
  }, [value]);
  return <span>{current}</span>;
}

export default function Home() {
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState(0);
  const [line, setLine] = useState(0);
  const ctaCard = useRef<HTMLDivElement | null>(null);

  useEffect(function autoplay() {
    const id = setInterval(function next() { setLine(function prev(v) { return (v + 1) % terminalCommands.length; }); }, 1900);
    return function cleanup() { clearInterval(id); };
  }, []);

  useEffect(function mouse() {
    function onMove(ev: MouseEvent) {
      if (!ctaCard.current) return;
      const rect = ctaCard.current.getBoundingClientRect();
      const x = ((ev.clientX - rect.left) / rect.width) * 100;
      const y = ((ev.clientY - rect.top) / rect.height) * 100;
      ctaCard.current.style.setProperty("--mx", `${x}%`);
      ctaCard.current.style.setProperty("--my", `${y}%`);
    }
    window.addEventListener("mousemove", onMove);
    return function cleanup() { window.removeEventListener("mousemove", onMove); };
  }, []);

  function doCopy() {
    const command = "irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex";
    navigator.clipboard?.writeText(command).catch(function noop() {});
    setCopied(true);
    setTimeout(function reset() { setCopied(false); }, 1700);
  }

  return (
    <main className="relative min-h-screen overflow-x-hidden bg-[#090a0d] text-[#f0f2f5]">
      <div className="pointer-events-none fixed inset-0 -z-10 mesh grain" />
      <div className="pointer-events-none fixed left-[12%] top-[-15%] -z-10 h-[420px] w-[420px] rounded-full bg-[#f5a524]/[.10] blur-[110px]" />
      <div className="pointer-events-none fixed right-[6%] bottom-[-8%] -z-10 h-[350px] w-[350px] rounded-full bg-emerald-300/[.06] blur-[130px]" />

      <header className="sticky top-0 z-50 border-b border-[#1e242d] bg-[#090a0d]/72 backdrop-blur-xl">
        <nav className="mx-auto flex max-w-[1240px] items-center justify-between gap-4 px-6 py-4">
          <a href="#hero" className="flex items-center gap-2 group">
            <svg className="h-7 w-7 text-[#f5a524]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 L20 8 L20 16 L12 22 L4 16 L4 8 Z"/><path d="M12 6 L12 18"/><path d="M8 12 L16 12"/></svg>
            <span className="text-lg font-semibold tracking-tight">orvima</span>
            <span className="hidden rounded-full border border-[#2a313d] px-2 py-1 text-[10px] text-[#a0a8b3] md:block">v0.2.0</span>
          </a>
          <div className="hidden items-center gap-1 text-sm md:flex">
            {[
              ["How it runs", "#workflow"],
              ["Inside", "#capabilities"],
              ["Safety", "#gate"],
              ["Install", "#install"]
            ].map(([label, href]) => (
              <a key={href} href={href} className="rounded-full px-4 py-2 text-[#a0a8b3] transition hover:bg-white/[.04] hover:text-[#f0f2f5]">{label}</a>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <a href="docs.html" className="hidden rounded-full px-4 py-2 text-sm text-[#a0a8b3] transition hover:text-[#f0f2f5] sm:block">Docs</a>
            <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="rounded-full border border-[#2a313d] px-4 py-2 text-sm transition hover:border-[#f5a524] hover:text-[#f5a524]">GitHub</a>
          </div>
        </nav>
      </header>

      <section id="hero" className="relative mx-auto grid max-w-[1240px] gap-14 px-6 pb-28 pt-16 md:grid-cols-[1.05fr_1fr] md:items-center md:pt-24">
        <motion.div initial="hidden" animate="visible" variants={stagger} className="space-y-8">
          <motion.p variants={fadeUp} className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">MIT · self-hosted · 49 tools · runs on your machine</motion.p>
          <motion.h1 variants={fadeUp} className="text-balance text-5xl font-semibold leading-[.98] tracking-tight sm:text-6xl xl:text-[6.1rem]">
            A browser agent<br />
            <span className="bg-gradient-to-r from-[#f5a524] to-[#fff1c6] bg-clip-text text-transparent">that admits its blind spots.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="max-w-xl text-lg leading-relaxed text-[#a0a8b3]">
            Most browser MCPs say <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f5a524]">ok: true</code> the second the click dispatches. orvima re-reads the page and tells you whether the state really changed. It answers <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f5a524]">verified: false</code> when it cannot tell, not <code className="rounded bg-[#111419] px-1.5 py-0.5 text-[#f0645c]">success</code> dressed up as certainty.
          </motion.p>
          <motion.div variants={fadeUp} className="flex flex-col gap-3 sm:flex-row">
            <motion.a href="#install" className="group inline-flex items-center justify-center gap-2 rounded-full bg-[#f5a524] px-7 py-3.5 text-sm font-semibold text-[#141004] shadow-xl shadow-[#f5a524]/25" whileHover={{ scale: 1.03, y: -2 }} whileTap={{ scale: .97 }}>Install now <ArrowRight size={16} className="transition group-hover:translate-x-1"/></motion.a>
            <motion.a href="#proof" className="inline-flex items-center justify-center gap-2 rounded-full border border-[#2a313d] px-7 py-3.5 text-sm font-semibold text-[#f0f2f5] transition hover:border-[#f5a524]/50" whileHover={{ scale: 1.02, y: -2 }} whileTap={{ scale: .98 }}>See the evidence</motion.a>
          </motion.div>
          <motion.ul variants={fadeUp} className="flex flex-wrap gap-2 text-xs">
            {["real DOM reads", "fail-closed approvals", "single-file audit trail", "attached browser only"].map(function(item) {
              return <li key={item} className="rounded-full border border-[#1e242d] bg-[#111419] px-3 py-1.5 text-[#a0a8b3]">{item}</li>;
            })}
          </motion.ul>
          <motion.div
            variants={fadeUp}
            className="grid grid-cols-3 gap-2 rounded-3xl border border-[#1e242d] bg-[#101318]/80 p-4 text-center shadow-2xl backdrop-blur-xl sm:max-w-sm"
          >
            {[["Tools", 49], ["Domains", 8], ["Silent lies", 0]].map(function(metric) {
              const label = metric[0] as string;
              const number = metric[1] as number;
              return (
                <div key={label} className="rounded-2xl border border-[#1e242d] bg-[#090a0d]/80 px-2 py-3">
                  <div className="text-2xl font-semibold text-[#f5a524]"><CountUp value={number} /></div>
                  <div className="mt-1 text-[11px] uppercase tracking-[.18em] text-[#a0a8b3]">{label}</div>
                </div>
              );
            })}
          </motion.div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, scale: .96, rotateX: 12 }}
          animate={{ opacity: 1, scale: 1, rotateX: 0 }}
          transition={{ duration: 1.05, ease: [.18,1,.3,1], delay: .22 }}
          className="relative [perspective:1000px]"
          style={{ transformStyle: "preserve-3d" }}
        >
          <div className="absolute inset-[-28px] rounded-[2.5rem] bg-[radial-gradient(circle_at_50%_40%,rgba(245,165,36,.16),transparent_60%)]" />
          <div className="relative overflow-hidden rounded-[2.2rem] border border-[#2a313d] bg-[#080a0e] shadow-2xl shadow-black/60">
            <div className="flex items-center justify-between border-b border-[#1e242d] px-5 py-4 text-xs text-[#a0a8b3]">
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[#f0645c]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[#f5a524]" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              </div>
              <span className="font-mono">orvima run &quot;delete everything in my account&quot;</span>
              <span className="rounded-full border border-[#2a313d] bg-[#111419] px-2.5 py-1 uppercase tracking-[.2em] text-[#a0a8b3]">live</span>
            </div>
            <div className="relative overflow-hidden p-5">
              <div className="absolute inset-0 grain opacity-20" />
              <div className="absolute left-0 right-0 top-0 h-16 overflow-hidden">
                <div className="scan-sweep absolute left-0 right-0 h-12 bg-gradient-to-b from-transparent via-[#f5a524]/[.10] to-transparent" />
              </div>
              <div className="relative font-mono text-[13px] leading-7">
                {terminalCommands.map(function(command, index) {
                  return (
                    <motion.div
                      key={command}
                      className={`flex items-start gap-3 rounded-xl px-3 py-1.5 ${index === terminalCommands.length - 1 ? "bg-[#111419]" : ""}`}
                      initial={{ opacity: 0, x: -12 }}
                      animate={index <= line ? { opacity: 1, x: 0 } : { opacity: .22, x: -12 }}
                      transition={{ duration: .45, delay: index * .1, ease: [.22,1,.36,1] }}
                    >
                      <span className={index === line ? "text-[#f5a524]" : "text-[#6b7480]"}>{">"}</span>
                      <span className={index === terminalCommands.length - 1 ? "text-[#f0645c]" : "text-[#a0a8b3]"}>{command}</span>
                    </motion.div>
                  );
                })}
              </div>
              <div className="relative mt-5 grid gap-3 sm:grid-cols-2">
                {[["classifier", "outward / destructive"], ["risk", "deletes_all_account_data"], ["allowed", "false"], ["approval", "pending / human"]].map(function(pair) {
                  return (
                    <div key={pair[0]} className="rounded-2xl border border-[#1e242d] bg-[#0f1217] px-4 py-3">
                      <div className="text-[11px] uppercase tracking-[.2em] text-[#6b7480]">{pair[0]}</div>
                      <div className="mt-1 font-mono text-sm text-[#d7dce5]">{pair[1]}</div>
                    </div>
                  );
                })}
              </div>
            </div>
            <div className="border-t border-[#1e242d] bg-[#06080b] px-5 py-4 text-sm text-[#a0a8b3]">
              <span className="text-emerald-400">●</span> The system captured the risk card; the click never executed before a human decided.
            </div>
          </div>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0, x: [0, 4, 0] }}
            transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
            className="absolute -right-4 -top-4 rounded-2xl border border-[#f5a524]/30 bg-[#111419]/90 px-4 py-3 text-xs text-[#f5a524] shadow-xl backdrop-blur-xl"
          >
            No path bypassed.
          </motion.div>
        </motion.div>
      </section>

      <section className="border-y border-[#1e242d] bg-[#07080b]/70">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-3 px-6 py-5 text-center text-sm sm:flex-row sm:justify-between sm:text-left">
          <span className="text-[#a0a8b3]">Controlled by TypeScript and protocols. Delivered from the same source.</span>
          <span className="text-[#6b7480]">No local install command. No telemetry silently declared here.</span>
        </div>
      </section>

      <motion.section id="proof" initial="hidden" whileInView="visible" viewport={{ once: true, amount: .2 }} variants={stagger} className="mx-auto max-w-[1240px] px-6 py-28">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">Proof over promise</p>
          <h2 className="mt-4 text-3xl font-semibold leading-tight sm:text-4xl">One product says a thing happened.<br/>The other can show it.</h2>
          <p className="mt-4 text-[#a0a8b3]">Left is the optimistic path of ordinary MCP code. Right is orvima: DOM reads, honest false states, and the moment a human had to click.</p>
        </motion.div>
        <div className="grid gap-5 lg:grid-cols-2">
          <motion.article variants={fadeUp} className="perspective-card rounded-[1.8rem] border border-[#1e242d] bg-[#111419]/[.82] p-7">
            <div className="mb-4 text-sm text-[#a0a8b3]">Typical browser MCP</div>
            <div className="rounded-2xl border border-[#1e242d] bg-[#0b0d12] p-4 font-mono text-[13px] text-[#a0a8b3]/70">
              <div>step 1: browse_navigate → ok</div>
              <div>step 2: browse_click → ok</div>
              <div>step 3: browse_click → ok</div>
              <div className="mt-3 text-[#f0645c]">no DOM read after any action</div>
            </div>
            <p className="mt-4 text-sm text-[#a0a8b3]">The transport succeeded. This says nothing about the web page that actually rendered.</p>
          </motion.article>
          <motion.article variants={fadeUp} className="perspective-card rounded-[1.8rem] border border-[#f5a524]/35 bg-[#111419]/[.9] p-7">
            <div className="mb-4 flex items-center justify-between text-sm text-[#f5a524]">
              <span>orvima</span>
              <Play size={16} />
            </div>
            <div className="rounded-2xl border border-[#f5a524]/15 bg-[#0b0d12] p-4 font-mono text-[13px]">
              <div className="text-[#a0a8b3]">step 1: browse_navigate → <span className="text-emerald-400">verified: true</span></div>
              <div className="text-[#a0a8b3]">step 2: browse_click → <span className="text-amber-300">verified: false</span></div>
              <div className="text-[#a0a8b3]">step 3: gate_check → <span className="text-[#f0645c]">refused</span></div>
              <div className="mt-3 text-emerald-400">state captured, approval card written, run stopped</div>
            </div>
            <p className="mt-4 text-sm text-[#a0a8b3]">Every failing edge stays in memory with evidence instead of disappearing into generated prose.</p>
          </motion.article>
        </div>
      </motion.section>

      <motion.section id="gate" initial="hidden" whileInView="visible" viewport={{ once: true, amount: .2 }} variants={stagger} className="mx-auto max-w-[1240px] px-6 py-28">
        <div className="grid gap-10 lg:grid-cols-[.95fr_1.05fr] lg:items-center">
          <motion.div variants={fadeUp} className="space-y-5">
            <p className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">The gate</p>
            <h2 className="text-4xl font-semibold leading-tight sm:text-5xl">A destructive click can be stopped before it exists.</h2>
            <p className="text-[#a0a8b3]">
              The classifier does not ask after the fact. When a selector points at something that changes outward state, it asks or refuses before an action crosses to the page, then records why. The result is not a message buried in chat, but a held card with a readable reason.
            </p>
            <div className="glass rounded-2xl border border-[#1e242d] p-5 text-sm text-[#a0a8b3]">
              <div className="mb-2 text-xs uppercase tracking-[.22em] text-[#6b7480]">human-visible record</div>
              This action carries a real risk card: risk, reason, arguments, and the exact decision a human would face when one arrives.
            </div>
          </motion.div>
          <motion.div variants={fadeUp} className="perspective-card rounded-[1.8rem] border border-[#1e242d] bg-[#111419]/[.8] p-6 pulse-glow">
            <div className="flex items-center gap-2 border-b border-[#1e242d] pb-4 text-xs text-[#a0a8b3]">
              <span className="h-2.5 w-2.5 rounded-full bg-[#f0645c]" />
              <span className="h-2.5 w-2.5 rounded-full bg-[#f5a524]" />
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
              <span className="ml-2 font-mono">held-approval.yaml</span>
            </div>
            <div className="mt-5 space-y-3 font-mono text-sm">
              <div className="rounded-xl border border-[#f0645c]/25 bg-[#0b0d12] px-4 py-3 text-[#f0645c]">allowed: false</div>
              <div className="rounded-xl border border-[#1e242d] bg-[#0b0d12] px-4 py-3 text-[#e2e7ef]">risk: deletes_all_account_data</div>
              <div className="rounded-xl border border-[#1e242d] bg-[#0b0d12] px-4 py-3 text-[#a0a8b3]">reason: destructive account selector targets all data</div>
              <div className="rounded-xl border border-[#1e242d] bg-[#0b0d12] px-4 py-3 text-[#a0a8b3]">arguments: {"{"}selector: button.delete[data-account=all]{"}"}</div>
              <div className="pt-2 text-emerald-400">visibility preserved for whoever is reviewing it</div>
            </div>
          </motion.div>
        </div>
      </motion.section>

      <motion.section id="capabilities" initial="hidden" whileInView="visible" viewport={{ once: true, amount: .2 }} variants={stagger} className="mx-auto max-w-[1240px] px-6 py-28">
        <motion.div variants={fadeUp} className="mb-12 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">Inside orvima</p>
          <h2 className="mt-4 text-3xl font-semibold sm:text-4xl">Built around verifiable behavior, not marketing language.</h2>
          <p className="mt-4 text-[#a0a8b3]">
            Six surfaces form one system. None of them requires you to trust a screenshot or a launch blog post.
          </p>
        </motion.div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {capabilities.map(function(item, index) {
            return (
              <motion.div
                key={item.title}
                variants={fadeUp}
                transition={{ delay: index * .06 }}
                className={`perspective-card relative overflow-hidden rounded-[1.6rem] border p-6 ${item.accent ? "border-[#f5a524]/30 bg-[#f5a524]/[.06]" : "border-[#1e242d] bg-[#101318]/[.82]"}`}
              >
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(245,165,36,.10),transparent_60%)]" />
                <div className={`relative inline-flex h-11 w-11 items-center justify-center rounded-2xl ${item.accent ? "bg-[#f5a524]/20 text-[#f5a524]" : "bg-[#1a1f26] text-[#f0f2f5]"}`}>{item.icon}</div>
                <h3 className="relative mt-5 text-lg font-semibold">{item.title}</h3>
                <p className="relative mt-3 text-sm leading-relaxed text-[#a0a8b3]">{item.text}</p>
                <div className="relative mt-6 h-px bg-gradient-to-r from-[#f5a524]/60 via-[#2a313d] to-transparent" />
              </motion.div>
            );
          })}
        </div>
      </motion.section>

      <motion.section id="workflow" initial="hidden" whileInView="visible" viewport={{ once: true, amount: .2 }} variants={stagger} className="mx-auto max-w-[1240px] px-6 py-28">
        <motion.div variants={fadeUp} className="mb-10 max-w-2xl">
          <p className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">How a run is produced</p>
          <h2 className="mt-4 text-3xl font-semibold sm:text-4xl">Structure sharp enough to be audited afterwards.</h2>
          <p className="mt-4 text-[#a0a8b3]">
            Your agent does not repeatedly click and hope. The system moves through the same stages every time, and strongest steps remain readable when the run ends.
          </p>
        </motion.div>
        <div className="grid gap-4 md:grid-cols-5">
          {workflow.map(function(pair, index) {
            const title = pair[0];
            const text = pair[1];
            return (
              <motion.div key={title} variants={fadeUp} transition={{ delay: index * .08 }} className="relative rounded-[1.5rem] border border-[#1e242d] bg-[#101318]/[.82] p-5">
                <div className="mb-3 inline-flex h-8 w-8 items-center justify-center rounded-full border border-[#f5a524]/30 bg-[#f5a524]/10 text-sm text-[#f5a524]">{index + 1}</div>
                {index < workflow.length - 1 && <div className="absolute top-10 right-[-10px] hidden h-px w-6 bg-[#2a313d] md:block" />}
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-[#a0a8b3]">{text}</p>
              </motion.div>
            );
          })}
        </div>
      </motion.section>

      <motion.section id="install" initial="hidden" whileInView="visible" viewport={{ once: true, amount: .2 }} variants={stagger} className="mx-auto max-w-[1240px] px-6 py-28">
        <motion.div
          ref={ctaCard}
          variants={fadeUp}
          className="relative overflow-hidden rounded-[2rem] border border-[#1e242d] bg-[#0d0f13]/90 p-8 shadow-2xl sm:p-12"
          style={{ backgroundImage: "radial-gradient(circle at var(--mx, 50%) var(--my, 50%), rgba(245,165,36,.13), transparent 30%), linear-gradient(180deg, rgba(17,20,25,.8), rgba(17,20,25,.45))" }}
        >
          <div className="absolute right-8 top-10 hidden text-[10rem] font-semibold leading-none text-white/[.03] lg:block">OR</div>
          <div className="grid gap-8 lg:grid-cols-[1.1fr_.9fr] lg:items-end">
            <div className="space-y-5">
              <p className="text-xs font-medium uppercase tracking-[.28em] text-[#a0a8b3]">Self-host in seconds</p>
              <h2 className="text-4xl font-semibold leading-tight sm:text-5xl">Install once and put the evidence where your agent can use it.</h2>
              <p className="max-w-xl text-[#a0a8b3]">
                The install stays on your machine. No cloud login demanded for the execution path, and a copied transcript remains next to the run that produced it.
              </p>
              <div className="flex flex-wrap gap-3">
                <motion.button onClick={doCopy} whileTap={{ scale: .98 }} className="inline-flex items-center gap-2 rounded-full bg-[#f5a524] px-6 py-3 text-sm font-semibold text-[#141004] shadow-xl shadow-[#f5a524]/25">
                  {copied ? <Check size={16} /> : <ClipboardCopy size={16} />} {copied ? "Copied" : "Copy install command"}
                </motion.button>
                <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="inline-flex items-center gap-2 rounded-full border border-[#2a313d] px-6 py-3 text-sm font-semibold text-[#f0f2f5] transition hover:border-[#f5a524]/50">
                  GitHub repository <ArrowRight size={16} />
                </a>
              </div>
            </div>
            <div className="space-y-3">
              <div className="flex gap-2 rounded-full border border-[#2a313d] bg-[#06080b]/90 p-1 text-xs">
                {["Windows", "macOS / Linux", "Source"].map(function(label, index) {
                  return (
                    <button key={label} onClick={function select() { setTab(index); }} className={`flex-1 rounded-full px-3 py-2 transition ${tab === index ? "bg-[#f5a524] font-semibold text-[#141004]" : "text-[#a0a8b3] hover:text-[#f0f2f5]"}`}>{label}</button>
                  );
                })}
              </div>
              <div className="rounded-2xl border border-[#1e242d] bg-[#06080b] p-5 font-mono text-sm text-[#dfe3e8]">
                {tab === 0 ? "irm https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.ps1 | iex" : tab === 1 ? "curl -fsSL https://raw.githubusercontent.com/Sachitt-AV-08/orvima/main/install.sh | bash" : "git clone https://github.com/Sachitt-AV-08/orvima\ncd orvima && uv sync"}
              </div>
              <p className="text-xs text-[#6b7480]">
                Tool count, domains, and run shapes are taken from the installed product, not from this page.
              </p>
            </div>
          </div>
          </motion.div>
      </motion.section>

      <footer className="border-t border-[#1e242d] bg-[#050608] py-10">
        <div className="mx-auto flex max-w-[1240px] flex-col gap-6 px-6 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="flex items-center gap-2 text-[#f0f2f5]">
              <svg className="h-6 w-6 text-[#f5a524]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 L20 8 L20 16 L12 22 L4 16 L4 8 Z"/><path d="M12 6 L12 18"/><path d="M8 12 L16 12"/></svg>
              <span className="font-semibold">orvima</span>
            </div>
            <p className="mt-3 max-w-sm text-sm text-[#6b7480]">
              Browser control that prefers honesty over confidence, built to keep execution close to the machine it acts on.
            </p>
          </div>
          <div className="flex flex-wrap gap-3 text-sm text-[#6b7480]">
            <a href="docs.html" className="transition hover:text-[#f0f2f5]">Docs</a>
            <a href="https://github.com/Sachitt-AV-08/orvima" target="_blank" rel="noopener" className="transition hover:text-[#f0f2f5]">Source</a>
            <span>© {new Date().getFullYear()}</span>
          </div>
        </div>
      </footer>
    </main>
  );
}
