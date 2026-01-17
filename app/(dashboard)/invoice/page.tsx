import { listPackages } from '@/lib/packages';
import { InvoiceClient } from '@/components/invoice/InvoiceClient';

export const dynamic = 'force-dynamic';

export default async function InvoicePage() {
  const packages = await listPackages();
  return <InvoiceClient packages={packages} />;
}
