import { createFileRoute } from "@tanstack/react-router";
import { useDashboardStats, usePackages } from "../api/queries";

export const Route = createFileRoute("/")({
  component: PackagesPage,
});

function PackagesPage() {
  const packagesQuery = usePackages();
  const statsQuery = useDashboardStats();

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border bg-white p-4">
          <div className="text-xs uppercase text-slate-400">Packages</div>
          <div className="mt-2 text-2xl font-semibold">
            {statsQuery.data?.packages ?? "-"}
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="text-xs uppercase text-slate-400">Invoices</div>
          <div className="mt-2 text-2xl font-semibold">
            {statsQuery.data?.count ?? "-"}
          </div>
        </div>
        <div className="rounded-lg border bg-white p-4">
          <div className="text-xs uppercase text-slate-400">Revenue</div>
          <div className="mt-2 text-2xl font-semibold">
            Rp{statsQuery.data?.revenue?.toLocaleString("id-ID") ?? "-"}
          </div>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Package Catalog</h2>
        {packagesQuery.isLoading ? (
          <div className="rounded-lg border bg-white p-4">Loading packages…</div>
        ) : packagesQuery.isError ? (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {(packagesQuery.error as Error).message}
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            {packagesQuery.data?.map((pkg) => (
              <div key={pkg.id} className="rounded-lg border bg-white p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm text-slate-500">{pkg.category}</div>
                    <div className="text-lg font-semibold">{pkg.name}</div>
                  </div>
                  <div className="text-base font-semibold text-emerald-600">
                    Rp{pkg.price.toLocaleString("id-ID")}
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-600 whitespace-pre-line">
                  {pkg.description || "No description."}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
