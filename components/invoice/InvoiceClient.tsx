'use client';

import { useMemo, useState } from 'react';
import type { packages as PackageModel } from '@prisma/client';
import { calculateTotals, descToLines, normalizeDescText, paymentIntegrityStatus } from '@/lib/invoice';
import { formatRupiah } from '@/lib/format';

const DEFAULT_INVOICE_TITLE = 'Exhibition Package 2026';
const DEFAULT_TERMS = `1. Down Payment sebesar Rp 500.000 (Lima Ratus Ribu Rupiah) saat di booth pameran
2. Termin pembayaran H+7 Pameran: Rp 500.000, H-7 prewedding: Rp 3.000.000, dan pelunasan H-7 wedding
3. Maksimal pembayaran Invoice 1 minggu dari tanggal invoice
4. Paket yang telah dipilih tidak bisa down grade
5. Melakukan pembayaran berarti menyatakan setuju dengan detail invoice. Pembayaran yang telah dilakukan tidak bisa di refund`;
const DEFAULT_BANK_INFO = {
  bank_nm: 'OCBC',
  bank_ac: '693810505794',
  bank_an: 'FANI PUSPITA NINGRUM',
};

type CartItem = {
  id: string;
  rowId: string;
  description: string;
  details: string;
  price: number;
  qty: number;
};

export function InvoiceClient({ packages }: { packages: PackageModel[] }) {
  const [cart, setCart] = useState<CartItem[]>([]);
  const [cashback, setCashback] = useState(0);
  const [title, setTitle] = useState(DEFAULT_INVOICE_TITLE);
  const [invNo, setInvNo] = useState('INV/01/2026');
  const [clientName, setClientName] = useState('');
  const [clientEmail, setClientEmail] = useState('');
  const [venue, setVenue] = useState('');
  const [weddingDate, setWeddingDate] = useState('');
  const [terms, setTerms] = useState(DEFAULT_TERMS);
  const [bankNm, setBankNm] = useState(DEFAULT_BANK_INFO.bank_nm);
  const [bankAc, setBankAc] = useState(DEFAULT_BANK_INFO.bank_ac);
  const [bankAn, setBankAn] = useState(DEFAULT_BANK_INFO.bank_an);
  const [dp1, setDp1] = useState(0);
  const [t2, setT2] = useState(0);
  const [t3, setT3] = useState(0);
  const [full, setFull] = useState(0);
  const [note, setNote] = useState('');

  const { subtotal, grandTotal } = useMemo(() => calculateTotals(cart, cashback), [cart, cashback]);

  const integrity = useMemo(() => paymentIntegrityStatus(grandTotal, dp1, t2, t3, full), [grandTotal, dp1, t2, t3, full]);

  const addToCart = (pkg: PackageModel) => {
    const rowId = String(pkg.id);
    if (cart.some((c) => c.rowId === rowId)) return;
    setCart((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        rowId,
        description: pkg.name,
        details: pkg.description || '',
        price: pkg.price,
        qty: 1,
      },
    ]);
  };

  const updateQty = (id: string, qty: number) => {
    setCart((prev) => prev.map((c) => (c.id === id ? { ...c, qty: Math.max(1, qty) } : c)));
  };

  const deleteItem = (id: string) => {
    setCart((prev) => prev.filter((c) => c.id !== id));
  };

  const autoSplit = () => {
    if (grandTotal <= 0) return;
    const q = Math.floor(grandTotal / 4);
    setDp1(q);
    setT2(q);
    setT3(q);
    setFull(grandTotal - q * 3);
  };

  const fillRemaining = () => {
    if (grandTotal <= 0) return;
    const currentPaid = dp1 + t2 + t3;
    const remaining = Math.max(0, grandTotal - currentPaid);
    setFull(remaining);
  };

  const pill = () => {
    if (integrity.status === 'BALANCED') return <span className="pill" style={{ background: '#e8f5e9', color: '#15803d' }}>BALANCED</span>;
    if (integrity.status === 'UNALLOCATED') return <span className="pill" style={{ background: '#fff7ed', color: '#c2410c' }}>UNALLOCATED</span>;
    if (integrity.status === 'OVER') return <span className="pill" style={{ background: '#fee2e2', color: '#b91c1c' }}>OVER</span>;
    return <span className="pill" style={{ background: '#eef2ff', color: '#3730a3' }}>INFO</span>;
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 380px', gap: 16 }}>
      <div>
        <h1 className="page-title">🧾 Create Invoice</h1>
        <div className="page-subtitle">Build invoices from packages with payment guidance.</div>

        <div className="card">
          <div className="section-title">Catalog</div>
          <div className="grid columns-3">
            {packages.map((pkg) => (
              <div key={pkg.id} className="card" style={{ borderColor: '#f1f5f9' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className={`badge ${pkg.category === 'Utama' ? 'badge-main' : 'badge-addon'}`}>
                    {pkg.category === 'Utama' ? '◆ MAIN' : '✨ ADD-ON'}
                  </span>
                  <span style={{ color: 'var(--muted)', fontSize: 12 }}>ID {pkg.id}</span>
                </div>
                <div style={{ fontWeight: 800, marginTop: 6 }}>{pkg.name}</div>
                <div style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800 }}>{formatRupiah(pkg.price)}</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  {descToLines(normalizeDescText(pkg.description)).slice(0, 3).join(' • ') || 'No details'}
                </div>
                <button className="btn" style={{ marginTop: 8 }} onClick={() => addToCart(pkg)}>
                  🛒 Add to cart
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="section-title">Cart</div>
          {cart.length === 0 ? <div className="muted">Add a package to begin.</div> : null}
          {cart.map((item) => (
            <div key={item.id} style={{ borderBottom: '1px solid #f1f5f9', padding: '10px 0', display: 'grid', gridTemplateColumns: '2fr 1fr 1fr 60px', gap: 8, alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 800 }}>{item.description}</div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {descToLines(normalizeDescText(item.details)).slice(0, 3).join(' • ') || 'No details'}
                </div>
              </div>
              <div style={{ fontFamily: 'ui-monospace, monospace', fontWeight: 800 }}>{formatRupiah(item.price)}</div>
              <input
                className="input"
                type="number"
                min={1}
                value={item.qty}
                onChange={(e) => updateQty(item.id, Number(e.target.value))}
              />
              <button className="btn" onClick={() => deleteItem(item.id)}>
                🗑️
              </button>
            </div>
          ))}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
            <label>
              <div className="muted" style={{ marginBottom: 4 }}>
                Cashback
              </div>
              <input className="input" type="number" min={0} step={500000} value={cashback} onChange={(e) => setCashback(Number(e.target.value))} />
            </label>
            <div className="summary" style={{ textAlign: 'right' }}>
              <div className="muted">Subtotal</div>
              <div style={{ fontWeight: 900 }}>{formatRupiah(subtotal)}</div>
              <div className="muted" style={{ marginTop: 6 }}>
                Grand Total
              </div>
              <div style={{ fontWeight: 900, fontSize: 20 }}>{formatRupiah(grandTotal)}</div>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginTop: 12 }}>
          <div className="section-title">🧩 Admin Details</div>
          <div className="form-row">
            <label>
              <div className="muted">Event / Title</div>
              <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label>
              <div className="muted">Invoice No</div>
              <input className="input" value={invNo} onChange={(e) => setInvNo(e.target.value)} />
            </label>
            <label>
              <div className="muted">Wedding Date</div>
              <input className="input" value={weddingDate} onChange={(e) => setWeddingDate(e.target.value)} placeholder="YYYY-MM-DD" />
            </label>
          </div>
          <div className="form-row">
            <label>
              <div className="muted">Client Name</div>
              <input className="input" value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="CPW & CPP" />
            </label>
            <label>
              <div className="muted">Email</div>
              <input className="input" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} placeholder="client@email.com" />
            </label>
            <label>
              <div className="muted">Venue</div>
              <input className="input" value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="Hotel/Gedung" />
            </label>
          </div>

          <div style={{ margin: '12px 0' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontWeight: 800 }}>💸 Payment Schedule</div>
                <div className="muted">{integrity.message}</div>
              </div>
              {pill()}
            </div>
            <div className="form-row" style={{ marginTop: 10 }}>
              <label>
                <div className="muted">DP 1</div>
                <input className="input" type="number" min={0} step={1000000} value={dp1} onChange={(e) => setDp1(Number(e.target.value))} />
              </label>
              <label>
                <div className="muted">Term 2</div>
                <input className="input" type="number" min={0} step={1000000} value={t2} onChange={(e) => setT2(Number(e.target.value))} />
              </label>
              <label>
                <div className="muted">Term 3</div>
                <input className="input" type="number" min={0} step={1000000} value={t3} onChange={(e) => setT3(Number(e.target.value))} />
              </label>
              <label>
                <div className="muted">Pelunasan</div>
                <input className="input" type="number" min={0} step={1000000} value={full} onChange={(e) => setFull(Number(e.target.value))} />
              </label>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
              <button className="btn" onClick={autoSplit} disabled={grandTotal <= 0}>
                Auto Split 4
              </button>
              <button className="btn" onClick={fillRemaining} disabled={grandTotal <= 0}>
                Fill Remaining → Pelunasan
              </button>
            </div>
          </div>

          <div className="form-row">
            <label>
              <div className="muted">Bank Name</div>
              <input className="input" value={bankNm} onChange={(e) => setBankNm(e.target.value)} />
            </label>
            <label>
              <div className="muted">Account</div>
              <input className="input" value={bankAc} onChange={(e) => setBankAc(e.target.value)} />
            </label>
            <label>
              <div className="muted">A/N</div>
              <input className="input" value={bankAn} onChange={(e) => setBankAn(e.target.value)} />
            </label>
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ marginBottom: 4 }}>
              Terms & Conditions
            </div>
            <textarea className="textarea" value={terms} onChange={(e) => setTerms(e.target.value)} />
          </div>

          <div style={{ marginTop: 12 }}>
            <div className="muted" style={{ marginBottom: 4 }}>
              Internal Notes
            </div>
            <textarea className="textarea" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Optional notes or delivery method" />
          </div>
        </div>
      </div>

      <div className="card" style={{ position: 'sticky', top: 12, height: 'fit-content' }}>
        <div className="section-title">Summary</div>
        <div className="muted">Grand Total</div>
        <div style={{ fontWeight: 900, fontSize: 26 }}>{formatRupiah(grandTotal)}</div>
        <div className="muted" style={{ marginTop: 12 }}>
          Items: {cart.length} • Cashback: {formatRupiah(cashback)}
        </div>
        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 10, marginTop: 10 }}>
          <div style={{ fontWeight: 800 }}>Invoice to</div>
          <div>{clientName || 'Client name not set'}</div>
          <div className="muted">{clientEmail || 'No email yet'}</div>
          <div className="muted" style={{ marginTop: 8 }}>
            Venue: {venue || '-'}
          </div>
        </div>
        <div style={{ borderTop: '1px solid #f0f0f0', paddingTop: 10, marginTop: 10 }}>
          <div style={{ fontWeight: 800 }}>Payment Plan</div>
          <ul style={{ margin: 0, paddingLeft: 18, color: 'var(--muted)' }}>
            {dp1 ? <li>DP 1: {formatRupiah(dp1)}</li> : null}
            {t2 ? <li>Term 2: {formatRupiah(t2)}</li> : null}
            {t3 ? <li>Term 3: {formatRupiah(t3)}</li> : null}
            {full ? <li>Pelunasan: {formatRupiah(full)}</li> : null}
          </ul>
        </div>
        <div style={{ marginTop: 14, display: 'grid', gap: 8 }}>
          <button className="btn primary" disabled={cart.length === 0}>
            Generate Invoice Summary
          </button>
          <div className="muted" style={{ fontSize: 13 }}>
            Exports and Drive upload are stubbed for now; wire lib/storage.ts to your provider to automate delivery.
          </div>
        </div>
        <div style={{ marginTop: 12, padding: 10, borderRadius: 12, background: '#f1f5f9' }}>
          <div style={{ fontWeight: 800 }}>Bank Info</div>
          <div className="muted">
            {bankNm} • {bankAc} • {bankAn}
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <div style={{ fontWeight: 800 }}>Notes</div>
          <div className="muted">{note || 'No internal notes.'}</div>
        </div>
      </div>
    </div>
  );
}
