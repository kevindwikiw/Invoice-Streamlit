import { createFileRoute } from "@tanstack/react-router";
import { useInvoices } from "../api/queries";

export const Route = createFileRoute("/invoices")({
  component: InvoicesPage,
});

function InvoicesPage() {
  const invoicesQuery = useInvoices();

  return (
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Invoice History</h2>
      {invoicesQuery.isLoading ? (
        <div className="rounded-lg border bg-white p-4">Loading invoices…</div>
      ) : invoicesQuery.isError ? (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {(invoicesQuery.error as Error).message}
        </div>
      ) : invoicesQuery.data?.length ? (
        <div className="space-y-3">
          {invoicesQuery.data.map((invoice) => (
            <div key={invoice.id} className="rounded-lg border bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="text-xs uppercase text-slate-400">{invoice.date}</div>
                  <div className="text-base font-semibold">{invoice.clientName}</div>
                  <div className="text-sm text-slate-500">{invoice.invoiceNo}</div>
                </div>
                <div className="text-base font-semibold text-emerald-600">
                  Rp{invoice.totalAmount.toLocaleString("id-ID")}
                </div>
              </div>
              <div className="mt-2 text-sm text-slate-600">{invoice.title}</div>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-lg border bg-white p-4 text-sm text-slate-500">No invoices yet.</div>
      )}
    </section>
  );
}
