import { Link, Outlet, createRootRoute } from "@tanstack/router";

const navigation = [
  { label: "Dashboard", to: "/" },
  { label: "Packages", to: "/packages" },
  { label: "Invoices", to: "/invoices" },
  { label: "Analytics", to: "/analytics" },
];

export const rootRoute = createRootRoute({
  component: () => (
    <div style={{ minHeight: "100vh", background: "#f8fafc", color: "#0f172a" }}>
      <header
        style={{
          background: "white",
          borderBottom: "1px solid #e2e8f0",
          padding: "1.5rem 2rem",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Invoice Admin</h1>
          <p style={{ margin: "0.25rem 0 0", color: "#64748b" }}>
            Vite + React + TypeScript starter for the Streamlit refactor
          </p>
        </div>
        <button
          type="button"
          style={{
            border: "1px solid #e2e8f0",
            background: "#f1f5f9",
            padding: "0.5rem 1rem",
            borderRadius: "999px",
            fontWeight: 600,
          }}
        >
          Admin
        </button>
      </header>
      <div style={{ display: "flex", padding: "2rem", gap: "2rem" }}>
        <aside
          style={{
            width: 240,
            background: "white",
            borderRadius: "1rem",
            border: "1px solid #e2e8f0",
            padding: "1.25rem",
            height: "fit-content",
          }}
        >
          <p style={{ marginTop: 0, fontWeight: 700 }}>Navigation</p>
          <nav style={{ display: "grid", gap: "0.75rem" }}>
            {navigation.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                style={{
                  textDecoration: "none",
                  color: "#0f172a",
                  padding: "0.5rem 0.75rem",
                  borderRadius: "0.75rem",
                  background: "#f8fafc",
                  border: "1px solid transparent",
                }}
                activeProps={{
                  style: {
                    border: "1px solid #38bdf8",
                    background: "#e0f2fe",
                  },
                }}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </aside>
        <main
          style={{
            flex: 1,
            background: "white",
            borderRadius: "1rem",
            border: "1px solid #e2e8f0",
            padding: "2rem",
          }}
        >
          <Outlet />
        </main>
      </div>
    </div>
  ),
});
