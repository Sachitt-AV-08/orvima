'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, Trash2, Copy, Check, ExternalLink, Loader2, Key, Zap, Clock, AlertCircle } from 'lucide-react';
import { signOut, getSession, getUser, getSupabaseClient } from '@/lib/supabase';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

interface Session {
  id: string;
  cdp_url: string;
  ws_url: string;
  status: string;
  remaining_seconds: number;
  created: number;
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loading, setLoading] = useState(true);
  const [deploying, setDeploying] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const session = await getSession();
      if (!session?.user) {
        router.push('/auth/login');
        return;
      }

      const userData = await getUser();
      if (!userData) {
        router.push('/auth/login');
        return;
      }
      setUser(userData);

      // Load profile with plan info
      const supabase = getSupabaseClient();
      if (!supabase) {
        setProfile({ plan: 'free', api_key: '' });
      } else {
        const { data: prof } = await supabase
          .from('profiles')
          .select('*')
          .eq('id', userData.id)
          .single();
        setProfile(prof || { plan: 'free', api_key: '' });

        if (prof?.api_key) {
          setApiKey(prof.api_key);
        }
      }

      // Load sessions from backend
      const res = await fetch('http://localhost:8000/api/sessions');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions || []);
      }
    } catch (err) {
      console.error('Load data error:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeploy = async () => {
    setDeploying(true);
    setError('');

    try {
      const res = await fetch('http://localhost:8000/api/deploy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ headless: true, ttl_minutes: 60 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to deploy');
      }

      const data = await res.json();
      setSessions(prev => [{ ...data, created: Date.now() / 1000 }, ...prev]);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setDeploying(false);
    }
  };

  const handleDestroy = async (sessionId: string) => {
    try {
      await fetch(`http://localhost:8000/api/sessions/${sessionId}`, { method: 'DELETE' });
      setSessions(prev => prev.filter(s => s.id !== sessionId));
    } catch (err) {
      console.error('Destroy error:', err);
    }
  };

  const copyApiKey = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const generateApiKey = async () => {
    const supabase = getSupabaseClient();
    if (!supabase) return;
    
    const newKey = 'orv_' + Array.from(crypto.getRandomValues(new Uint8Array(24)))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');

    await supabase
      .from('profiles')
      .upsert({ id: user.id, api_key: newKey });

    setApiKey(newKey);
  };

  const handleSignOut = async () => {
    await signOut();
    router.push('/');
    router.refresh();
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-10 h-10 animate-spin text-orvima-accent" />
      </div>
    );
  }

  const plan = profile?.plan || 'free';
  const planLimits = { free: 5, pro: 50, team: 200 };
  const sessionsToday = sessions.length; // Simplified

  return (
    <div className="min-h-screen bg-orvima-bg">
      <nav className="fixed top-0 left-0 right-0 z-50 bg-orvima-bg/80 backdrop-blur-md border-b border-orvima-border">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <a href="/" className="flex items-center gap-2">
            <span className="text-2xl font-bold text-orvima-accent">Orvima</span>
            <span className="text-xs bg-orvima-accent/10 text-orvima-accent px-2 py-0.5 rounded">Dashboard</span>
          </a>
          <div className="flex items-center gap-4">
            <span className="text-sm text-orvima-textMuted">{plan.toUpperCase()}</span>
            <button onClick={handleSignOut} className="px-4 py-2 rounded-lg border border-orvima-border text-orvima-text hover:bg-orvima-card transition-colors">
              Sign Out
            </button>
          </div>
        </div>
      </nav>

      <main className="pt-24 pb-12 px-6">
        <div className="max-w-6xl mx-auto space-y-8">
          {/* Welcome + Plan */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 bg-orvima-card border border-orvima-border rounded-xl"
          >
            <div>
              <h1 className="text-2xl font-bold">Welcome back, {user?.email?.split('@')[0]}</h1>
              <p className="text-orvima-textMuted mt-1">Manage your browser sessions and API keys</p>
            </div>
            <div className="flex items-center gap-4">
              <div className={cn(
                'px-4 py-2 rounded-lg font-medium',
                plan === 'free' && 'bg-gray-500/10 text-gray-400',
                plan === 'pro' && 'bg-blue-500/10 text-blue-400',
                plan === 'team' && 'bg-purple-500/10 text-purple-400'
              )}>
                {plan.charAt(0).toUpperCase() + plan.slice(1)} Plan
              </div>
              {plan !== 'team' && (
                <a href="/pricing" className="text-sm text-orvima-accent hover:underline">Upgrade</a>
              )}
            </div>
          </motion.div>

          {/* API Key Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="p-6 bg-orvima-card border border-orvima-border rounded-xl"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Key className="w-5 h-5 text-orvima-accent" />
                API Key
              </h2>
              {!apiKey ? (
                <button onClick={generateApiKey} className="px-4 py-2 rounded-lg bg-orvima-accent text-orvima-bg font-medium hover:bg-orvima-accentHover transition-colors">
                  Generate API Key
                </button>
              ) : (
                <button onClick={copyApiKey} className="px-4 py-2 rounded-lg border border-orvima-border text-orvima-text hover:bg-orvima-card transition-colors flex items-center gap-2">
                  {copied ? <Check className="w-4 h-4 text-green-400" /> : <Copy className="w-4 h-4" />}
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              )}
            </div>

            {apiKey ? (
              <div className="flex items-center gap-2 bg-orvima-bg border border-orvima-border rounded-lg p-3 font-mono text-sm">
                <code className="flex-1 text-orvima-text">{apiKey}</code>
              </div>
            ) : (
              <p className="text-orvima-textMuted text-sm">Generate an API key to authenticate with the Orvima SaaS API</p>
            )}

            <div className="mt-4 p-3 bg-orvima-bg/50 rounded-lg text-sm text-orvima-textMuted">
              <code className="text-orvima-accent">Authorization: Bearer {apiKey || 'YOUR_API_KEY'}</code>
            </div>
          </motion.div>

          {/* Usage Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="grid md:grid-cols-3 gap-4"
          >
            <div className="p-6 bg-orvima-card border border-orvima-border rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                <Zap className="w-6 h-6 text-orvima-accent" />
                <span className="text-orvima-textMuted">Sessions Today</span>
              </div>
              <div className="text-3xl font-bold">{sessionsToday} / {planLimits[plan as keyof typeof planLimits]}</div>
              <div className="text-sm text-orvima-textMuted mt-1">
                {plan === 'free' ? 'Upgrade for more sessions' : 'Resets daily at midnight UTC'}
              </div>
            </div>

            <div className="p-6 bg-orvima-card border border-orvima-border rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                <Clock className="w-6 h-6 text-blue-400" />
                <span className="text-orvima-textMuted">Active Sessions</span>
              </div>
              <div className="text-3xl font-bold">{sessions.filter(s => s.status === 'running').length}</div>
              <div className="text-sm text-orvima-textMuted mt-1">Running now</div>
            </div>

            <div className="p-6 bg-orvima-card border border-orvima-border rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                <AlertCircle className="w-6 h-6 text-orange-400" />
                <span className="text-orvima-textMuted">Expired (Auto-cleaned)</span>
              </div>
              <div className="text-3xl font-bold">{sessions.filter(s => s.status !== 'running').length}</div>
              <div className="text-sm text-orvima-textMuted mt-1">Will be removed automatically</div>
            </div>
          </motion.div>

          {/* Deploy Session */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="p-6 bg-orvima-card border border-orvima-border rounded-xl"
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-semibold flex items-center gap-2">
                <Plus className="w-5 h-5 text-orvima-accent" />
                Deploy New Session
              </h2>
              <button
                onClick={handleDeploy}
                disabled={deploying || sessionsToday >= planLimits[plan as keyof typeof planLimits]}
                className={cn(
                  'px-6 py-2 rounded-lg font-medium transition-colors flex items-center gap-2',
                  deploying
                    ? 'bg-orvima-border text-orvima-textMuted cursor-not-allowed'
                    : sessionsToday >= planLimits[plan as keyof typeof planLimits]
                    ? 'bg-orange-500/10 text-orange-400 cursor-not-allowed'
                    : 'bg-orvima-accent text-orvima-bg hover:bg-orvima-accentHover'
                )}
              >
                {deploying ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deploying...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Deploy Session
                  </>
                )}
              </button>
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 text-sm">
                {error}
              </div>
            )}

            {sessionsToday >= planLimits[plan as keyof typeof planLimits] && (
              <p className="text-orange-400 text-sm">
                Daily limit reached. Upgrade your plan or wait for reset.
              </p>
            )}
          </motion.div>

          {/* Active Sessions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="p-6 bg-orvima-card border border-orvima-border rounded-xl"
          >
            <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
              <ExternalLink className="w-5 h-5 text-orvima-accent" />
              Your Sessions
            </h2>

            {sessions.length === 0 ? (
              <div className="text-center py-12 text-orvima-textMuted">
                <ExternalLink className="w-12 h-12 mx-auto mb-4 text-orvima-border" />
                <p>No active sessions. Deploy one to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {sessions.map((session) => (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-4 bg-orvima-bg border border-orvima-border rounded-lg"
                  >
                    <div className="flex items-center gap-4 flex-1 min-w-0">
                      <div className={cn(
                        'w-3 h-3 rounded-full',
                        session.status === 'running' ? 'bg-green-400' : 'bg-gray-500'
                      )} />
                      <div>
                        <div className="font-mono text-sm text-orvima-accent">{session.id}</div>
                        <div className="text-xs text-orvima-textMuted font-mono">{session.cdp_url}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 text-sm">
                      <span className={cn(
                        'px-2 py-1 rounded-full text-xs font-medium',
                        session.status === 'running' ? 'bg-green-500/10 text-green-400' : 'bg-gray-500/10 text-gray-400'
                      )}>
                        {session.status}
                      </span>
                      <span className="text-orvima-textMuted font-mono">
                        {formatTime(session.remaining_seconds)} left
                      </span>
                      <button
                        onClick={() => navigator.clipboard.writeText(session.cdp_url)}
                        className="p-1.5 text-orvima-textMuted hover:text-orvima-accent transition-colors"
                        title="Copy CDP URL"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDestroy(session.id)}
                        className="p-1.5 text-orvima-textMuted hover:text-red-400 transition-colors"
                        title="Destroy session"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>

          {/* Connection Example */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="p-6 bg-orvima-card border border-orvima-border rounded-xl"
          >
            <h2 className="text-xl font-semibold mb-4">Quick Connect (Playwright)</h2>
            <pre className="bg-orvima-bg border border-orvima-border rounded-lg p-4 overflow-x-auto text-sm">
<code className="text-orvima-text">from playwright.sync_api import sync_playwright

pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://localhost:9222')
page = browser.contexts[0].pages[0]
page.goto('https://example.com')
print(page.title())</code>
            </pre>
            <p className="text-orvima-textMuted text-sm mt-3">
              Replace the CDP URL with your session's URL. See <a href="https://github.com/Sachitt-AV-08/orvima/blob/main/docs/api.md" target="_blank" rel="noopener noreferrer" className="text-orvima-accent hover:underline">API docs</a> for more examples.
            </p>
          </motion.div>
        </div>
      </main>
    </div>
  );
}