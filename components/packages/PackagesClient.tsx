'use client';

import { useEffect, useMemo, useState } from 'react';
import type { packages as PackageModel } from '@prisma/client';
import { formatRupiah } from '@/lib/format';
import { PackageFormModal } from './PackageFormModal';
import { ResetDialog } from './ResetDialog';

const CATEGORIES = ['Utama', 'Bonus'];
const CATEGORY_ALL = 'All';

const SORT_OPTIONS: Record<string, { key: keyof PackageModel; asc: boolean }> = {
  Newest: { key: 'id', asc: false },
  'Price: High → Low': { key: 'price', asc: false },
  'Price: Low → High': { key: 'price', asc: true },
  'Name: A → Z': { key: 'name', asc: true },
};

const GRID_OPTIONS = ['3 cols', '4 cols'];

export function PackagesClient({ initialPackages }: { initialPackages: PackageModel[] }) {
  const [packages, setPackages] = useState<PackageModel[]>(initialPackages);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>(CATEGORY_ALL);
  const [sort, setSort] = useState<string>('Newest');
  const [grid, setGrid] = useState<string>(GRID_OPTIONS[1]);
  const [modal, setModal] = useState<{ mode: 'add' | 'edit' | 'delete' | null; pkg?: PackageModel | null }>({
    mode: null,
    pkg: null,
  });
  const [showReset, setShowReset] = useState(false);

  useEffect(() => {
    setPackages(initialPackages);
  }, [initialPackages]);

  const filtered = useMemo(() => {
    let rows = [...packages];
    if (category !== CATEGORY_ALL) rows = rows.filter((r) => r.category === category);
    if (search) rows = rows.filter((r) => r.name.toLowerCase().includes(search.toLowerCase()));
    const sortCfg = SORT_OPTIONS[sort];
    if (sortCfg) {
      rows.sort((a, b) => {
        const aVal = a[sortCfg.key];
        const bVal = b[sortCfg.key];
        if (aVal === bVal) return 0;
        if (sortCfg.asc) return aVal < bVal ? -1 : 1;
        return aVal > bVal ? -1 : 1;
      });
    }
    return rows;
  }, [packages, search, category, sort]);

  async function refresh() {
    const res = await fetch('/api/packages');
    const json = await res.json();
    setPackages(json.data || []);
  }

  async function handleSave(values: Partial<PackageModel>) {
    if (modal.mode === 'edit' && modal.pkg) {
      await fetch(`/api/packages/${modal.pkg.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
    } else {
      await fetch('/api/packages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });
    }
    setModal({ mode: null, pkg: null });
    await refresh();
  }

  async function handleDelete() {
    if (!modal.pkg) return;
    await fetch(`/api/packages/${modal.pkg.id}`, { method: 'DELETE' });
    setModal({ mode: null, pkg: null });
    await refresh();
  }

  async function handleFactoryReset() {
    await fetch('/api/packages/reset', { method: 'DELETE' });
    setShowReset(false);
    await refresh();
  }

  const gridTemplate = grid === '4 cols' ? 'repeat(auto-fill, minmax(220px, 1fr))' : 'repeat(auto-fill, minmax(260px, 1fr))';

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 className="page-title">📦 Packages Database</h1>
          <div className="page-subtitle">Kelola katalog harga dengan rapi — konsisten nama, harga, dan itemnya.</div>
        </div>
        <button className="btn primary" onClick={() => setModal({ mode: 'add', pkg: null })}>
          ＋ Create
        </button>
      </div>

      <div className="card" style={{ marginTop: 12 }}>
        <div className="form-row">
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              🔎 Search
            </div>
            <input className="input" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search name…" />
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              🏷️ Category
            </div>
            <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
              {[CATEGORY_ALL, ...CATEGORIES].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              ↕️ Sort
            </div>
            <select className="input" value={sort} onChange={(e) => setSort(e.target.value)}>
              {Object.keys(SORT_OPTIONS).map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              🧩 Grid
            </div>
            <select className="input" value={grid} onChange={(e) => setGrid(e.target.value)}>
              {GRID_OPTIONS.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ marginTop: 8, color: 'var(--muted)' }}>
          📌 Showing <b>{filtered.length}</b> of <b>{packages.length}</b> packages.
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10 }}>
        <div className="section-title">✨ Catalog Cards</div>
        <button className="btn" onClick={() => setShowReset(true)}>
          🔴 Factory Reset
        </button>
      </div>

      <div className="grid" style={{ marginTop: 12, gridTemplateColumns: gridTemplate }}>
        {filtered.map((row) => (
          <div key={row.id} className="card" style={{ position: 'relative' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between' }}>
              <span className={`badge ${row.category === 'Utama' ? 'badge-main' : 'badge-addon'}`}>
                {row.category === 'Utama' ? '◆ MAIN' : '✨ ADD-ON'}
              </span>
              <div style={{ color: 'var(--muted)', fontSize: 12 }}>ID {row.id}</div>
            </div>
            <div style={{ fontSize: '0.95rem', fontWeight: 800, marginTop: 8 }}>{row.name}</div>
            <div style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800, marginTop: 4 }}>{formatRupiah(row.price)}</div>
            <div className="muted" style={{ marginTop: 8, whiteSpace: 'pre-wrap', lineHeight: 1.4 }}>
              {row.description || 'No details.'}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
              <button className="btn" onClick={() => setModal({ mode: 'edit', pkg: row })}>
                ✏️ Edit
              </button>
              <button className="btn" style={{ color: '#b91c1c' }} onClick={() => setModal({ mode: 'delete', pkg: row })}>
                🗑️ Delete
              </button>
            </div>
          </div>
        ))}
      </div>

      {modal.mode === 'add' || modal.mode === 'edit' ? (
        <PackageFormModal
          mode={modal.mode}
          onClose={() => setModal({ mode: null, pkg: null })}
          onSave={handleSave}
          initialData={modal.pkg || undefined}
        />
      ) : null}

      {modal.mode === 'delete' && modal.pkg ? (
        <div className="modal-backdrop">
          <div className="modal">
            <div style={{ textAlign: 'center', fontSize: 28 }}>🗑️</div>
            <h3 style={{ textAlign: 'center' }}>Delete this package?</h3>
            <p className="muted" style={{ textAlign: 'center' }}>
              "{modal.pkg.name}" will be permanently removed.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <button className="btn" onClick={() => setModal({ mode: null, pkg: null })}>
                Cancel
              </button>
              <button className="btn danger" onClick={handleDelete}>
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {showReset ? <ResetDialog onConfirm={handleFactoryReset} onCancel={() => setShowReset(false)} /> : null}
    </div>
  );
}
