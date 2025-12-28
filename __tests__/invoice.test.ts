import { calculateTotals, normalizeDescText, descToLines, paymentIntegrityStatus } from '@/lib/invoice';

describe('invoice utilities', () => {
  it('calculates subtotal and grand total', () => {
    const items = [
      { id: '1', rowId: '1', description: 'A', details: '', price: 100000, qty: 2 },
      { id: '2', rowId: '2', description: 'B', details: '', price: 50000, qty: 1 },
    ];
    const totals = calculateTotals(items as any, 25000);
    expect(totals.subtotal).toBe(250000);
    expect(totals.grandTotal).toBe(225000);
  });

  it('normalizes br tags into lines', () => {
    const text = 'Line 1<br>Line 2';
    const normalized = normalizeDescText(text);
    expect(normalized).toBe('Line 1\nLine 2');
  });

  it('converts description into lines', () => {
    const lines = descToLines('- A\n- B');
    expect(lines).toEqual(['A', 'B']);
  });

  it('computes payment integrity', () => {
    const { status, balance } = paymentIntegrityStatus(1000, 250, 250, 250, 250);
    expect(status).toBe('BALANCED');
    expect(balance).toBe(0);
  });
});
