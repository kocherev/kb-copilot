import type { BetterAuthOptions } from "better-auth";
import { nextCookies } from "better-auth/next-js";
import { jwt, organization } from "better-auth/plugins";
import { Pool } from "pg";

// The API checks this audience on every JWT.
export const API_AUDIENCE = "kb-api";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });
const baseURL = process.env.BETTER_AUTH_URL ?? "http://localhost:3000";

// Kept apart from the auth instance so startup can migrate the tables before
// Better Auth checks them.
export const authOptions = {
  baseURL,
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
  databaseHooks: {
    user: {
      create: {
        // Runs after sign-up commits, which is after its first session exists.
        after: async (user) => {
          await createPersonalOrganization(user.id, user.name);
        },
      },
    },
    session: {
      create: {
        before: async (session) => ({
          data: {
            ...session,
            activeOrganizationId: await firstOrganizationId(session.userId),
          },
        }),
      },
    },
  },
} satisfies BetterAuthOptions;

async function createPersonalOrganization(userId: string, name: string): Promise<void> {
  const { auth } = await import("@/lib/auth");
  const organization = await auth.api.createOrganization({
    body: { name: `${name}'s workspace`, slug: `personal-${userId.toLowerCase()}`, userId },
  });
  await pool.query(
    'UPDATE session SET "activeOrganizationId" = $1 WHERE "userId" = $2 AND "activeOrganizationId" IS NULL',
    [organization.id, userId],
  );
}

async function firstOrganizationId(userId: string): Promise<string | null> {
  const result = await pool.query<{ organizationId: string }>(
    'SELECT "organizationId" FROM member WHERE "userId" = $1 ORDER BY "createdAt" LIMIT 1',
    [userId],
  );
  return result.rows[0]?.organizationId ?? null;
}
