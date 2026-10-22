'use client';

import { motion } from 'framer-motion';
import { Check, X, Zap, Shield, Key, Globe, Users } from 'lucide-react';
import { cn } from '@/lib/utils';

const plans = [
  {
    id: 'free',
    name: 'Free',
    price: 0,
    period: '/mo',
    description: 'For hobbyists & testing',
    sessionsPerDay: 5,
    features: [
      { text: '5 browser sessions/day', included: true },
      { text: 'CDP URL access', included: true },
      { text: 'Email (SMTP/IMAP) tools', included: true },
      { text: 'WhatsApp Web automation', included: true },
      { text: 'Voice (Edge TTS) tools', included: true },
      { text: 'Safety gates & verification', included: true },
      { text: 'API keys', included: false },
      { text: 'Webhook events', included: false },
      { text: 'Priority support', included: false },
    ],
    cta: 'Start Free',
    popular: false,
  },
  {
    id: 'pro',
    name: 'Pro',
    price: 19,
    period: '/mo',
    description: 'For developers & small teams',
    sessionsPerDay: 50,
    features: [
      { text: '50 browser sessions/day', included: true },
      { text: 'CDP URL access', included: true },
      { text: 'Email (SMTP/IMAP) tools', included: true },
      { text: 'WhatsApp Web automation', included: true },
      { text: 'Voice (Edge TTS) tools', included: true },
      { text: 'Safety gates & verification', included: true },
      { text: 'API keys', included: true },
      { text: 'Webhook events', included: true },
      { text: 'Email support', included: true },
    ],
    cta: 'Get Started',
    popular: true,
  },
  {
    id: 'team',
    name: 'Team',
    price: 49,
    period: '/mo',
    description: 'For companies & agencies',
    sessionsPerDay: 200,
    features: [
      { text: '200 browser sessions/day', included: true },
      { text: 'CDP URL access', included: true },
      { text: 'Email (SMTP/IMAP) tools', included: true },
      { text: 'WhatsApp Web automation', included: true },
      { text: 'Voice (Edge TTS) tools', included: true },
      { text: 'Safety gates & verification', included: true },
      { text: 'API keys', included: true },
      { text: 'Webhook events', included: true },
      { text: 'Priority support', included: true },
      { text: 'Custom domains', included: true },
      { text: 'SSO (SAML/OIDC)', included: true },
      { text: 'Dedicated infra option', included: true },
    ],
    cta: 'Contact Sales',
    popular: false,
  },
];

export function PricingCards() {
  return (
    <section id="pricing" className="py-24 px-6">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl md:text-5xl font-bold mb-4">Simple, Transparent Pricing</h2>
          <p className="text-orvima-textMuted text-lg max-w-2xl mx-auto">
            No hidden fees. No per-session charges. Cancel anytime.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {plans.map((plan, i) => (
            <motion.article
              key={plan.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              className={cn(
                'relative p-8 bg-orvima-card border rounded-2xl transition-all duration-300',
                plan.popular
                  ? 'border-orvima-accent shadow-[0_0_40px_rgba(245,165,36,0.15)] scale-105 z-10'
                  : 'border-orvima-border hover:border-orvima-accent/50'
              )}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="px-3 py-1 bg-orvima-accent text-orvima-bg text-xs font-bold rounded-full">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-6">
                <h3 className="text-xl font-semibold mb-1">{plan.name}</h3>
                <p className="text-orvima-textMuted text-sm">{plan.description}</p>
              </div>

              <div className="mb-6">
                <span className="text-5xl font-bold">{plan.price}</span>
                <span className="text-orvima-textMuted">{plan.period}</span>
              </div>

              <div className="mb-6 p-4 bg-orvima-bg/50 rounded-lg">
                <div className="flex items-center gap-2 text-orvima-accent mb-2">
                  <Zap className="w-5 h-5" />
                  <span className="font-medium">{plan.sessionsPerDay} sessions/day</span>
                </div>
                <div className="text-sm text-orvima-textMuted">
                  ~{plan.sessionsPerDay * 30}/month —{' '}
                  <span className="text-orvima-text">{plan.price === 0 ? 'Free' : `$${(plan.price / (plan.sessionsPerDay * 30)).toFixed(4)}`}/session</span>
                </div>
              </div>

              <ul className="space-y-3 mb-8">
                {plan.features.map((feature, idx) => (
                  <motion.li
                    key={idx}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: idx * 0.05 }}
                    className={cn(
                      'flex items-start gap-3 text-sm',
                      feature.included ? 'text-orvima-text' : 'text-orvima-textMuted/50'
                    )}
                  >
                    {feature.included ? (
                      <Check className="w-5 h-5 text-orvima-accent flex-shrink-0 mt-0.5" />
                    ) : (
                      <X className="w-5 h-5 text-orvima-border flex-shrink-0 mt-0.5" />
                    )}
                    <span>{feature.text}</span>
                  </motion.li>
                ))}
              </ul>

              <button
                className={cn(
                  'w-full py-3 rounded-lg font-semibold transition-all',
                  plan.popular
                    ? 'bg-orvima-accent text-orvima-bg hover:bg-orvima-accentHover'
                    : 'bg-orvima-border text-orvima-text hover:bg-orvima-border/80'
                )}
              >
                {plan.cta}
              </button>
            </motion.article>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          className="text-center text-orvima-textMuted mt-10 text-sm"
        >
          All plans include the full 49 MCP tools. Self-host on your infra — no cloud lock-in.
        </motion.p>
      </div>
    </section>
  );
}