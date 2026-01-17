'use client';

import { useEffect, useState } from 'react';
import type { packages as PackageModel } from '@prisma/client';

export function PackageFormModal({
  mode,
  initialData,
  onClose,
  onSave,
}: {
  mode: 'add' | 'edit';
  initialData?: PackageModel;
  onClose: () => void;
  onSave: (values: Partial<PackageModel>) => Promise<void>;
}) {
  const [name, setName] = useState(initialData?.name || '');
  const [category, setCategory] = useState(initialData?.category || 'Utama');
  const [price, setPrice] = useState(initialData?.price || 0);
  const [description, setDescription] = useState(initialData?.description || '');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setName(initialData?.name || '');
    setCategory(initialData?.category || 'Utama');
    setPrice(initialData?.price || 0);
    setDescription(initialData?.description || '');
  }, [initialData]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Package name is required.');
      return;
    }
    setError(null);
    await onSave({ name: name.trim(), category, price: Number(price), description: description.trim() });
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h3>{mode === 'add' ? '➕ Add New Package' : '✏️ Edit Package'}</h3>
        <div className="form-row">
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              Package Name
            </div>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Platinum Wedding Bundle" />
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              Category
            </div>
            <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
              <option>Utama</option>
              <option>Bonus</option>
            </select>
          </label>
          <label>
            <div className="muted" style={{ marginBottom: 4 }}>
              Price (IDR)
            </div>
            <input className="input" type="number" min={0} step={50000} value={price} onChange={(e) => setPrice(Number(e.target.value))} />
            {price > 0 ? <div className="muted">Display: Rp {Math.round(price).toLocaleString('id-ID')}</div> : null}
          </label>
        </div>
        <div style={{ marginTop: 10 }}>
          <div className="muted" style={{ marginBottom: 4 }}>
            🧾 Package Details / Items
          </div>
          <textarea
            className="textarea"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder={'1 Photographer\n1 Videographer\nAlbum 20 Pages'}
          />
        </div>
        {error ? (
          <div style={{ color: '#c2410c', marginTop: 8, fontWeight: 700 }}>⚠️ {error}</div>
        ) : null}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 12 }}>
          <button className="btn primary" onClick={handleSubmit}>
            {mode === 'add' ? '➕ Create Package' : '💾 Save Changes'}
          </button>
          <button className="btn" onClick={onClose}>
            ✕ Close
          </button>
        </div>
      </div>
    </div>
  );
}
