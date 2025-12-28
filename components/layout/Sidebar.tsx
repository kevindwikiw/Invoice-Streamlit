"use client";

import Link from 'next/link';
import { signOut } from 'next-auth/react';

export function Sidebar({ username, packageCount }: { username: string; packageCount: number }) {
  return (
    <aside
      style={{
        width: 260,
        background: '#fff',
        borderRight: '1px solid var(--border)',
        minHeight: '100vh',
        padding: '18px 16px',
        position: 'sticky',
        top: 0,
      }}
    >
      <div style={{ fontWeight: 800, fontSize: 18, marginBottom: 6 }}>🧭 Admin Panel</div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '12px 14px',
          border: '1px solid var(--border)',
          borderRadius: 12,
          background: '#fff',
          boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
          marginBottom: 14,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{ fontSize: 20 }}>👤</div>
          <div>
            <div style={{ fontWeight: 700, color: '#333', lineHeight: 1.2 }}>{username}</div>
            <div style={{ color: '#2ecc71', fontSize: 11, fontWeight: 600 }}>● Online</div>
          </div>
        </div>
      </div>

      <div style={{ marginTop: 12, padding: '6px 0' }}>
        <div style={{ color: '#6b7280', fontSize: 13, marginBottom: 6 }}>Total Packages</div>
        <div style={{ fontWeight: 800, fontSize: 24 }}>{packageCount}</div>
      </div>

      <nav style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Link className="btn" href="/packages">
          📦 Package Database
        </Link>
        <Link className="btn" href="/invoice">
          🧾 Create Invoice
        </Link>
        <button
          className="btn"
          type="button"
          onClick={() =>
            signOut({ callbackUrl: '/login' }).catch(() => {
              /* noop */
            })
          }
        >
          🚪 Sign Out
        </button>
      </nav>

      <div style={{ marginTop: 18, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        <details>
          <summary style={{ cursor: 'pointer', fontWeight: 700 }}>🛠️ System Tools</summary>
          <div style={{ marginTop: 8, color: 'var(--muted)' }}>Factory Reset available on Packages page.</div>
        </details>
      </div>
    </aside>
  );
}
