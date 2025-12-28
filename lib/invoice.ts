import { formatRupiah } from './format';

export type InvoiceItem = {
  id: string;
  rowId: string;
  description: string;
  details?: string;
  price: number;
  qty: number;
};

export type InvoiceMeta = {
  invNo: string;
  title: string;
  clientName: string;
  clientEmail?: string;
  weddingDate?: string;
  venue?: string;
  cashback: number;
  payDp1: number;
  payTerm2: number;
  payTerm3: number;
  payFull: number;
};

export function calculateTotals(items: InvoiceItem[], cashback: number) {
  const subtotal = items.reduce((acc, item) => acc + item.price * Math.max(1, item.qty), 0);
  const safeCashback = Math.max(0, cashback);
  const grandTotal = Math.max(0, subtotal - safeCashback);
  return { subtotal, grandTotal };
}

export function sanitizeText(input?: string) {
  if (!input) return '';
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

export function normalizeDescText(raw?: string) {
  if (!raw) return '';
  let s = raw.replace(/&lt;/g, '<').replace(/&gt;/g, '>');
  const out: string[] = [];
  for (let i = 0; i < s.length; i += 1) {
    if (s[i] === '<' && s.slice(i, i + 3).toLowerCase() === '<br') {
      let j = i + 3;
      while (j < s.length && s[j] !== '>') j += 1;
      if (s[j] === '>') {
        out.push('\n');
        i = j;
        continue;
      }
    }
    out.push(s[i]);
  }
  s = out.join('');
  return s.replace(/\r\n/g, '\n').replace(/\r/g, '\n').trim();
}

export function descToLines(desc?: string) {
  const lines: string[] = [];
  (desc || '')
    .split('\n')
    .map((l) => l.trim())
    .forEach((line) => {
      if (!line) return;
      const cleaned = line.replace(/^[-•·]\s*/, '').trim();
      if (cleaned) lines.push(cleaned);
    });
  return lines;
}

export function paymentIntegrityStatus(grandTotal: number, dp1: number, t2: number, t3: number, full: number) {
  const totalScheduled = dp1 + t2 + t3 + full;
  const balance = Math.floor(grandTotal) - totalScheduled;

  if (grandTotal <= 0) return { status: 'INFO', message: 'Add items to cart to calculate payments.', balance };
  if (balance === 0) return { status: 'BALANCED', message: 'Schedule matches Grand Total.', balance };
  if (balance > 0) return { status: 'UNALLOCATED', message: `${formatRupiah(balance)} remaining.`, balance };
  return { status: 'OVER', message: `${formatRupiah(Math.abs(balance))} excess.`, balance };
}
