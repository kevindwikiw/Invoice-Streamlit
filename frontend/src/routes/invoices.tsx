import { createFileRoute } from "@tanstack/router";

export const Route = createFileRoute("/invoices")({
  component: () => (
    <section>
      <h2 style={{ marginTop: 0 }}>Invoices</h2>
      <p style={{ color: "#475569" }}>
        Build the invoice creation flow here, including the sequence generator
        and PDF preview.
      </p>
      <div
        style={{
          marginTop: "1.5rem",
          padding: "1rem",
          borderRadius: "0.75rem",
          border: "1px dashed #94a3b8",
          background: "#f8fafc",
        }}
      >
        <p style={{ margin: 0, fontWeight: 600 }}>Next invoice preview</p>
        <p style={{ margin: "0.5rem 0 0", color: "#64748b" }}>INV00001</p>
      </div>
    </section>
  ),
});
