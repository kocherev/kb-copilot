import { betterAuth } from "better-auth";

import { authOptions, pool } from "@/lib/auth-options";

export const auth = betterAuth({
  ...authOptions,
  databaseHooks: {
    session: {
      create: {
        before: async (session) => ({
          data: {
            ...session,
            activeOrganizationId: await personalOrganizationId(session.userId),
          },
        }),
      },
    },
  },
});

// Every new session gets an active org. A user without one, after sign-up or
// a failed earlier attempt, gets a personal org here.
async function personalOrganizationId(userId: string): Promise<string> {
  const found = await pool.query<{ organizationId: string }>(
    'SELECT "organizationId" FROM member WHERE "userId" = $1 ORDER BY "createdAt" LIMIT 1',
    [userId],
  );
  const existing = found.rows[0]?.organizationId;
  if (existing) {
    return existing;
  }
  const created = await auth.api.createOrganization({
    body: {
      name: "Personal workspace",
      slug: `personal-${userId.toLowerCase()}`,
      userId,
    },
  });
  return created.id;
}
