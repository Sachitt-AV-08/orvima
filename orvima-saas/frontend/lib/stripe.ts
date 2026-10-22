import Stripe from 'stripe';

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2024-04-10',
});

export const PLANS = {
  free: { id: 'free', name: 'Free', price: 0, priceId: '', sessionsPerDay: 5, features: ['5 sessions/day', 'CDP URL access', 'Community support'] },
  pro: { id: 'pro', name: 'Pro', price: 1900, priceId: process.env.STRIPE_PRO_PRICE_ID, sessionsPerDay: 50, features: ['50 sessions/day', 'CDP URL access', 'Email support', 'API keys', 'Webhook events'] },
  team: { id: 'team', name: 'Team', price: 4900, priceId: process.env.STRIPE_TEAM_PRICE_ID, sessionsPerDay: 200, features: ['200 sessions/day', 'CDP URL access', 'Priority support', 'API keys', 'Webhook events', 'Custom domains', 'SSO'] },
} as const;

export type PlanId = keyof typeof PLANS;

export async function createCheckoutSession(planId: PlanId, customerEmail: string, userId: string) {
  const plan = PLANS[planId];
  if (!plan.priceId) throw new Error('Price ID not configured');

  const session = await stripe.checkout.sessions.create({
    mode: 'subscription',
    payment_method_types: ['card'],
    line_items: [{ price: plan.priceId, quantity: 1 }],
    customer_email: customerEmail,
    metadata: { userId, planId },
    success_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard?success=true`,
    cancel_url: `${process.env.NEXT_PUBLIC_APP_URL}/pricing?canceled=true`,
    allow_promotion_codes: true,
  });

  return session;
}

export async function createPortalSession(customerId: string) {
  const session = await stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${process.env.NEXT_PUBLIC_APP_URL}/dashboard`,
  });
  return session;
}