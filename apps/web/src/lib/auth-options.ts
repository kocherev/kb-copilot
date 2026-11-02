import type { BetterAuthOptions } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt, organization } from "better-auth/plugins";
import { PHASE_PRODUCTION_BUILD } from "next/constants";
import { Pool } from "pg";

import { requireAuthSecret } from "@/lib/auth-secret";

// The API checks this audience on every JWT.
export const API_AUDIENCE = "kb-api";

// Instrumentation and route handlers load this module in separate bundles.
const shared = globalThis as typeof globalThis & { kbAuthPool?: Pool };
export const pool = (shared.kbAuthPool ??= new Pool({
  connectionString: process.env.DATABASE_URL,
}));

const baseURL = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";

// Kept apart from the auth instance so startup can migrate the tables before
// Better Auth checks them.
export const authOptions = {
  baseURL,
  // `next build` evaluates this module without runtime secrets.
  secret:
    process.env.NEXT_PHASE === PHASE_PRODUCTION_BUILD
      ? undefined
      : requireAuthSecret(process.env.BETTER_AUTH_SECRET),
  database: pool,
  emailAndPassword: { enabled: true },
  plugins: [
    organization(),
    jwt({
      jwt: {
        issuer: baseURL,
        audience: API_AUDIENCE,
        // The API scopes every request to this org.
        definePayload: ({ session }) => ({
          org_id: session.activeOrganizationId ?? null,
        }),
      },
    }),
    nextCookies(),
  ],
} satisfies BetterAuthOptions;
