import { Link, Outlet, createRootRoute } from "@tanstack/react-router";

export const Route = createRootRoute({
  component: () => (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <h1 className="text-lg font-semibold">Invoice Admin</h1>
          <nav className="flex gap-4 text-sm font-medium">
            <Link to="/" className="text-slate-600 hover:text-slate-900">
              Packages
            </Link>
            <Link to="/invoices" className="text-slate-600 hover:text-slate-900">
              Invoices
            </Link>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  ),
});
