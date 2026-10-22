'use client';

import React from 'react';
import { motion, useMotionValue, useSpring } from 'framer-motion';
import { Send, MessageSquare, CheckCircle, Loader2, Mail, Phone } from 'lucide-react';
import { cn } from '@/lib/utils';

const demoSteps = [
  { id: 1, command: `orvima mail_send --to "hr@company.com" --subject "Application" --body "Hi, I'm applying..."`, icon: Mail, label: 'Sending email...' },
  { id: 2, command: `✓ Email sent — Message-ID: <20261021.12345@smtp.mailin.fr>`, icon: CheckCircle, label: 'Email delivered', success: true },
  { id: 3, command: `orvima whatsapp_send --to "+15551234567" --text "Hey! Ready for the demo?"`, icon: Phone, label: 'Sending WhatsApp...' },
  { id: 4, command: `✓ Message delivered — 2 blue ticks confirmed`, icon: CheckCircle, label: 'WhatsApp delivered', success: true },
  { id: 5, command: `orvima browse_navigate --url "https://github.com" --session_id "abc123"`, icon: Mail, label: 'Navigating browser...' },
  { id: 6, command: `✓ Page loaded — DOM verified: true`, icon: CheckCircle, label: 'Browser verified', success: true },
];

export function TerminalDemo() {
  const [currentStep, setCurrentStep] = React.useState(0);
  const [completedSteps, setCompletedSteps] = React.useState<Set<number>>(new Set());
  const [isRunning, setIsRunning] = React.useState(false);

  React.useEffect(() => {
    if (!isRunning) return;
    
    const interval = setInterval(() => {
      setCurrentStep(prevStep => {
        if (prevStep >= demoSteps.length - 1) {
          setIsRunning(false);
          return prevStep;
        }
        setCompletedSteps(prevCompleted => {
          const arr = Array.from(prevCompleted);
          arr.push(prevStep);
          return new Set(arr);
        });
        return prevStep + 1;
      });
    }, 2500);

    return () => clearInterval(interval);
  }, [isRunning]);

  const handleRestart = () => {
    setCurrentStep(0);
    setCompletedSteps(new Set());
    setIsRunning(true);
  };

  return (
    <div className="relative">
      <div className="bg-orvima-bg border border-orvima-border rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 bg-orvima-card border-b border-orvima-border">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-500/80" />
            <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
            <div className="w-3 h-3 rounded-full bg-green-500/80" />
          </div>
          <span className="text-xs text-orvima-textMuted ml-3 font-mono">orvima-session-abc123 ~ </span>
        </div>

        <div className="p-4 font-mono text-sm h-72 overflow-y-auto">
          {demoSteps.map((step, i) => {
            const isActive = i === currentStep && isRunning;
            const isCompleted = completedSteps.has(i);
            const showOutput = isCompleted || isActive;

            return (
              <motion.div
                key={step.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: showOutput ? 1 : 0, y: showOutput ? 0 : 10 }}
                transition={{ duration: 0.3, delay: isActive ? 0 : 0.1 }}
                className="mb-3"
              >
                <div className="flex items-start gap-3">
                  <span className="text-orvima-textMuted/50 pt-0.5">$</span>
                  <span className={cn(
                    'text-orvima-text',
                    isCompleted && 'text-orvima-textMuted',
                    step.success && 'text-green-400'
                  )}>
                    {step.command}
                  </span>
                </div>
                
                {isActive && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="ml-6 flex items-center gap-2 text-orvima-accent text-xs"
                  >
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{step.label}</span>
                  </motion.div>
                )}

                {isCompleted && step.success && (
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="ml-6 flex items-center gap-1 text-green-400 text-xs"
                  >
                    <CheckCircle className="w-3 h-3" />
                    <span>Verified ✓</span>
                  </motion.div>
                )}
              </motion.div>
            );
          })}

          {!isRunning && completedSteps.size === 0 && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-orvima-textMuted text-center py-8"
            >
              Click "Run Demo" to see Orvima in action
            </motion.div>
          )}
        </div>

        <div className="px-4 py-3 bg-orvima-card border-t border-orvima-border">
          <div className="flex items-center justify-between text-xs text-orvima-textMuted">
            <span>Session: <span className="text-orvima-accent font-mono">abc123</span></span>
            <span>CDP: <span className="font-mono">ws://localhost:9222/devtools/browser/...</span></span>
            <span>Status: <span className={cn('font-medium', isRunning ? 'text-yellow-400' : 'text-green-400')}>{isRunning ? 'Running' : 'Ready'}</span></span>
          </div>
        </div>
      </div>

      <motion.button
        onClick={handleRestart}
        disabled={isRunning}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={cn(
          'mt-6 w-full md:w-auto px-8 py-3 rounded-lg font-semibold text-lg transition-all',
          'flex items-center gap-2 justify-center',
          isRunning
            ? 'bg-orvima-border text-orvima-textMuted cursor-not-allowed'
            : 'bg-orvima-accent text-orvima-bg hover:bg-orvima-accentHover'
        )}
      >
        {isRunning ? (
          <>
            <Loader2 className="w-5 h-5 animate-spin" />
            Running Demo...
          </>
        ) : (
          <>
            <Send className="w-5 h-5" />
            Run Live Demo
          </>
        )}
      </motion.button>
    </div>
  );
}