import { createFileRoute } from "@tanstack/router";

export const Route = createFileRoute("/packages")({
  component: () => (
    <section>
      <h2 style={{ marginTop: 0 }}>Packages</h2>
      <p style={{ color: "#475569" }}>
        List and manage packages once the API integration is wired in.
      </p>
      <ul style={{ paddingLeft: "1.25rem", color: "#0f172a" }}>
        <li>Define package tiers</li>
        <li>Assign pricing</li>
        <li>Sync with invoice forms</li>
      </ul>
    </section>
  ),
});
