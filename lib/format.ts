export function formatRupiah(value: number) {
  const intVal = Math.round(Number.isFinite(value) ? value : 0);
  return `Rp ${intVal.toLocaleString('id-ID')}`;
}

export function formatNumber(value: number) {
  return value.toLocaleString('id-ID');
}
