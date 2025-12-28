'use client';

import { signIn, useSession } from 'next-auth/react';
import { FormEvent, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const { status } = useSession();
  const params = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === 'authenticated') {
      router.replace('/packages');
    }
  }, [status, router]);

  useEffect(() => {
    const err = params.get('error');
    if (err) setError('Invalid credentials');
  }, [params]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    const result = await signIn('credentials', {
      username,
      password,
      redirect: false,
      callbackUrl: '/packages',
    });

    if (!result?.ok) {
      setError('Invalid credentials');
    } else {
      router.replace('/packages');
    }
  };

  return (
    <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', background: '#f3f4f6' }}>
      <div className="card" style={{ width: 420, maxWidth: '92vw' }}>
        <div style={{ textAlign: 'center', fontSize: 48 }}>🛸</div>
        <h2 style={{ textAlign: 'center', marginTop: 8 }}>Admin Portal</h2>
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>Username</div>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>Password</div>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="•••••••" />
          </label>
          {error ? (
            <div style={{ color: '#c2410c', fontWeight: 700, fontSize: 14 }}>❌ {error}</div>
          ) : null}
          <button type="submit" className="btn primary" disabled={status === 'loading'}>
            {status === 'loading' ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  );
}
