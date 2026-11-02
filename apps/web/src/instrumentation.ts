// Check the auth secret and migrate the Better Auth tables before the server
// takes requests.
export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") {
    return;
  }
  const { requireAuthSecret } = await import("@/lib/auth-secret");
  try {
    requireAuthSecret(process.env.BETTER_AUTH_SECRET);
  } catch (error) {
    // Next keeps serving 500s after a failed hook. Exit so the container stops.
    console.error(error instanceof Error ? error.message : error);
    process.exit(1);
  }
  const { getMigrations } = await import("better-auth/db/migration");
  const { authOptions } = await import("@/lib/auth-options");
  const { runMigrations } = await getMigrations(authOptions);
  await runMigrations();
}
