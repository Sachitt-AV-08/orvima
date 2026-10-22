import { NextRequest, NextResponse } from 'next/server';
import { stripe, createCheckoutSession, PLANS } from '@/lib/stripe';
import { getSupabaseClient } from '@/lib/supabase';

export async function POST(request: NextRequest) {
  try {
    const { planId } = await request.json();

    if (!planId || !PLANS[planId as keyof typeof PLANS]) {
      return NextResponse.json({ error: 'Invalid plan' }, { status: 400 });
    }

    const supabase = getSupabaseClient();
    if (!supabase) {
      return NextResponse.json({ error: 'Supabase not configured' }, { status: 500 });
    }

    // Get user session
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const user = session.user;
    const plan = PLANS[planId as keyof typeof PLANS];

    if (plan.price === 0) {
      // Free plan - just update user metadata
      await supabase.auth.updateUser({ data: { plan: planId } });
      return NextResponse.json({ url: '/dashboard?plan=free' });
    }

    const checkoutSession = await createCheckoutSession(planId as keyof typeof PLANS, user.email || '', user.id);

    return NextResponse.json({ url: checkoutSession.url });
  } catch (error) {
    console.error('Checkout error:', error);
    return NextResponse.json({ error: 'Failed to create checkout session' }, { status: 500 });
  }
}