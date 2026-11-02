// Create or update the Better Auth tables before the server takes requests.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") {
    return;
  }
  const { getMigrations } = await import("better-auth/db/migration");
  const { authOptions } = await import("@/lib/auth-options");
  const { runMigrations } = await getMigrations(authOptions);
  await runMigrations();
}
