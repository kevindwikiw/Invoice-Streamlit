import { Elysia, t } from "elysia";
import { Database } from "bun:sqlite";
import type {
  ApiResponse,
  DashboardStats,
  InvoicePayload,
  InvoiceRecord,
  PackageRecord,
} from "../../shared/contract";

const db = new Database("packages.db", { create: true });

db.run(`
  CREATE TABLE IF NOT EXISTS packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT NOT NULL,
    description TEXT
  );
`);

db.run(`
  CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT NOT NULL,
    client_name TEXT NOT NULL,
    date TEXT NOT NULL,
    total_amount REAL NOT NULL,
    invoice_data TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
  );
`);

db.run(`
  CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT
  );
`);

const app = new Elysia()
  .get("/api/health", () => ({ status: "ok" }))
  .get("/api/packages", () => {
    const rows = db.query("SELECT * FROM packages ORDER BY id DESC").all() as PackageRecord[];
    return { data: rows } satisfies ApiResponse<PackageRecord[]>;
  })
  .post(
    "/api/packages",
    ({ body }) => {
      const stmt = db.query(
        "INSERT INTO packages (name, price, category, description) VALUES ($name, $price, $category, $description)"
      );
      stmt.run(body);
      const created = db.query("SELECT * FROM packages WHERE id = last_insert_rowid()")
        .get() as PackageRecord;
      return { data: created } satisfies ApiResponse<PackageRecord>;
    },
    {
      body: t.Object({
        name: t.String(),
        price: t.Number(),
        category: t.String(),
        description: t.Optional(t.String()),
      }),
    }
  )
  .put(
    "/api/packages/:id",
    ({ params, body }) => {
      const stmt = db.query(
        "UPDATE packages SET name = $name, price = $price, category = $category, description = $description WHERE id = $id"
      );
      stmt.run({ ...body, id: Number(params.id) });
      const updated = db.query("SELECT * FROM packages WHERE id = ?").get(Number(params.id)) as PackageRecord;
      return { data: updated } satisfies ApiResponse<PackageRecord>;
    },
    {
      params: t.Object({ id: t.String() }),
      body: t.Object({
        name: t.String(),
        price: t.Number(),
        category: t.String(),
        description: t.Optional(t.String()),
      }),
    }
  )
  .delete(
    "/api/packages/:id",
    ({ params }) => {
      db.query("DELETE FROM packages WHERE id = ?").run(Number(params.id));
      return { data: true } satisfies ApiResponse<boolean>;
    },
    {
      params: t.Object({ id: t.String() }),
    }
  )
  .post("/api/packages/reset", () => {
    db.query("DELETE FROM packages").run();
    return { data: true } satisfies ApiResponse<boolean>;
  })
  .get("/api/invoices", () => {
    const rows = db.query("SELECT * FROM invoices ORDER BY created_at DESC").all();
    const invoices = rows.map((row) => {
      const payload = JSON.parse(String(row.invoice_data)) as InvoicePayload;
      return {
        ...payload,
        id: Number(row.id),
        createdAt: String(row.created_at),
      } satisfies InvoiceRecord;
    });
    return { data: invoices } satisfies ApiResponse<InvoiceRecord[]>;
  })
  .get(
    "/api/invoices/:id",
    ({ params }) => {
      const row = db.query("SELECT * FROM invoices WHERE id = ?").get(Number(params.id));
      if (!row) {
        return { data: null } satisfies ApiResponse<InvoiceRecord | null>;
      }
      const payload = JSON.parse(String(row.invoice_data)) as InvoicePayload;
      return {
        data: {
          ...payload,
          id: Number(row.id),
          createdAt: String(row.created_at),
        },
      } satisfies ApiResponse<InvoiceRecord>;
    },
    {
      params: t.Object({ id: t.String() }),
    }
  )
  .post(
    "/api/invoices",
    ({ body }) => {
      const stmt = db.query(
        "INSERT INTO invoices (invoice_no, client_name, date, total_amount, invoice_data) VALUES ($invoiceNo, $clientName, $date, $totalAmount, $payload)"
      );
      stmt.run({
        invoiceNo: body.invoiceNo,
        clientName: body.clientName,
        date: body.date,
        totalAmount: body.totalAmount,
        payload: JSON.stringify(body),
      });
      const row = db.query("SELECT * FROM invoices WHERE id = last_insert_rowid()")
        .get();
      const payload = JSON.parse(String(row.invoice_data)) as InvoicePayload;
      return {
        data: {
          ...payload,
          id: Number(row.id),
          createdAt: String(row.created_at),
        },
      } satisfies ApiResponse<InvoiceRecord>;
    },
    {
      body: t.Object({
        invoiceNo: t.String(),
        clientName: t.String(),
        date: t.String(),
        title: t.String(),
        venue: t.Optional(t.String()),
        items: t.Array(
          t.Object({
            id: t.String(),
            description: t.String(),
            details: t.Optional(t.String()),
            price: t.Number(),
            quantity: t.Number(),
            total: t.Number(),
            isBundle: t.Optional(t.Boolean()),
          })
        ),
        paymentTerms: t.Array(
          t.Object({
            id: t.String(),
            label: t.String(),
            amount: t.Number(),
            locked: t.Optional(t.Boolean()),
          })
        ),
        cashback: t.Number(),
        totalAmount: t.Number(),
        metadata: t.Object({
          clientPhone: t.Optional(t.String()),
          clientEmail: t.Optional(t.String()),
          weddingDate: t.Optional(t.String()),
          bankName: t.Optional(t.String()),
          bankAccount: t.Optional(t.String()),
          bankAccountName: t.Optional(t.String()),
          terms: t.Optional(t.String()),
          footer: t.Optional(t.String()),
        }),
      }),
    }
  )
  .delete(
    "/api/invoices/:id",
    ({ params }) => {
      db.query("DELETE FROM invoices WHERE id = ?").run(Number(params.id));
      return { data: true } satisfies ApiResponse<boolean>;
    },
    {
      params: t.Object({ id: t.String() }),
    }
  )
  .get("/api/dashboard", () => {
    const revenueRow = db.query("SELECT COALESCE(SUM(total_amount), 0) as revenue FROM invoices").get();
    const countRow = db.query("SELECT COUNT(*) as count FROM invoices").get();
    const packageRow = db.query("SELECT COUNT(*) as packages FROM packages").get();
    return {
      data: {
        revenue: Number(revenueRow.revenue),
        count: Number(countRow.count),
        packages: Number(packageRow.packages),
      } satisfies DashboardStats,
    } satisfies ApiResponse<DashboardStats>;
  })
  .get("/api/config", () => {
    const rows = db.query("SELECT key, value FROM app_config").all();
    const config = rows.reduce<Record<string, string>>((acc, row) => {
      acc[String(row.key)] = String(row.value ?? "");
      return acc;
    }, {});
    return { data: config } satisfies ApiResponse<Record<string, string>>;
  })
  .put(
    "/api/config",
    ({ body }) => {
      const entries = Object.entries(body);
      const stmt = db.query("INSERT OR REPLACE INTO app_config (key, value) VALUES ($key, $value)");
      for (const [key, value] of entries) {
        stmt.run({ key, value });
      }
      return { data: body } satisfies ApiResponse<Record<string, string>>;
    },
    {
      body: t.Record(t.String(), t.String()),
    }
  );

app.listen(3001);

console.log(`Bun + Elysia API running on http://localhost:3001`);
