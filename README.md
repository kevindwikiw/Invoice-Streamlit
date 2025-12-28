# Invoice Admin (Next.js)

Rebuilt the Streamlit admin portal in Next.js with NextAuth authentication, Prisma + SQLite data access, and UI flows that mirror the original packages and invoice pages.

## Prerequisites
- Node.js 18+
- npm or yarn
- Existing `packages.db` SQLite file from the original app (place it at the repo root). If absent, Prisma seed will create starter data.

## Setup
1. Install dependencies:
   ```bash
   npm install
   ```
2. Copy the environment template and update secrets:
   ```bash
   cp .env.example .env
   ```
   - `DATABASE_URL` should point to the root `packages.db` (default uses `file:../packages.db` from the `prisma` folder).
   - Set `NEXTAUTH_SECRET` and optional hashed password (`AUTH_PASSWORD_HASH`, pbkdf2 format) or fallback `AUTH_PASSWORD`.
3. Generate Prisma client:
   ```bash
   npx prisma generate
   ```
4. Run database migration (creates the `packages` table if needed):
   ```bash
   npx prisma migrate deploy
   ```
5. Seed initial packages if your DB is empty:
   ```bash
   npx prisma db seed
   ```
6. Start the dev server:
   ```bash
   npm run dev
   ```

## Scripts
- `npm run dev` – start Next.js in development.
- `npm run build` / `npm start` – production build and serve.
- `npm run lint` – ESLint with Next.js defaults.
- `npm test` – Jest unit tests for shared utilities.
- `npm run test:e2e` – Playwright smoke tests (expects dev server at `localhost:3000`).
- `npm run prisma:generate` – regenerate Prisma client.
- `npm run prisma:migrate` – create a migration named `init` for local development.
- `npm run prisma:seed` – run the TypeScript seed script.

## Notes
- Authentication mirrors the Python `modules/auth.py` flow using NextAuth credentials provider with idle timeout handled via JWT maxAge. Sign in at `/login`.
- Package CRUD, counts, and factory reset map to Prisma-backed API routes using the shared `packages` table.
- Invoice utilities (totals, formatting, payment integrity, description parsing) are ported to TypeScript in `lib/invoice.ts` and used by the `/invoice` page.
- Google Drive/file upload is abstracted in `lib/storage.ts` with a stub for future provider wiring.
- Styling tokens mirror `config/theme.py` in `app/globals.css`; modal and form interactions align with the original dialogs.
