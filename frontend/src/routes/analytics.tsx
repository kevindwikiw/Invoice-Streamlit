import { createFileRoute } from "@tanstack/router";

export const Route = createFileRoute("/analytics")({
  component: () => (
    <section>
      <h2 style={{ marginTop: 0 }}>Analytics</h2>
      <p style={{ color: "#475569" }}>
        Add charts and KPIs here to mirror the Streamlit analytics dashboard.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "1rem",
          marginTop: "1.5rem",
        }}
      >
        {["Revenue", "Invoices", "Packages"].map((item) => (
          <div
            key={item}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: "0.75rem",
              padding: "1rem",
              background: "#f8fafc",
            }}
          >
            <p style={{ margin: 0, color: "#64748b", fontSize: "0.875rem" }}>{item}</p>
            <p style={{ margin: "0.5rem 0 0", fontWeight: 700, fontSize: "1.25rem" }}>
              --
            </p>
          </div>
        ))}
      </div>
    </section>
  ),
});
