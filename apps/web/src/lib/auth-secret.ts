const PLACEHOLDERS = new Set(["", "replace-me"]);

// Better Auth only warns about a weak secret. It signs cookies and encrypts the
// JWKS private keys, so refuse to start without a real one.
export function requireAuthSecret(value: string | undefined): string {
  const secret = value?.trim() ?? "";
  if (PLACEHOLDERS.has(secret) || secret.length < 32) {
    throw new Error(
      "BETTER_AUTH_SECRET must be at least 32 random characters. Generate one with: openssl rand -hex 32",
    );
  }
  return secret;
}
