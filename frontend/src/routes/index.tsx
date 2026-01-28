import { createFileRoute } from "@tanstack/router";

export const Route = createFileRoute("/")({
  component: () => (
    <section>
      <h2 style={{ marginTop: 0 }}>Dashboard</h2>
      <p style={{ color: "#475569" }}>
        This is the starting point for migrating the Streamlit experience into a
        modern TypeScript + Vite frontend.
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: "1rem",
          marginTop: "1.5rem",
        }}
      >
        {[
          { label: "Packages", value: "0" },
          { label: "Invoices", value: "0" },
          { label: "Revenue", value: "Rp0" },
        ].map((card) => (
          <div
            key={card.label}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: "0.75rem",
              padding: "1rem",
              background: "#f8fafc",
            }}
          >
            <p style={{ margin: 0, color: "#64748b", fontSize: "0.875rem" }}>{card.label}</p>
            <p style={{ margin: "0.5rem 0 0", fontWeight: 700, fontSize: "1.25rem" }}>
              {card.value}
            </p>
          </div>
        ))}
      </div>
    </section>
  ),
});
