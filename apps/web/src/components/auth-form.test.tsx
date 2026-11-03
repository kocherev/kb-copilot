import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { AuthForm } from "@/components/auth-form";

const auth = vi.hoisted(() => ({
  signIn: vi.fn(),
  signUp: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("@/lib/auth-client", () => ({
  authClient: {
    signIn: { email: auth.signIn },
    signUp: { email: auth.signUp },
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: auth.replace, refresh: () => undefined }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function fill(label: string, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

test("a rejected sign-in shows the error and stays on the page", async () => {
  auth.signIn.mockResolvedValue({
    data: null,
    error: { message: "Invalid email or password" },
  });
  render(<AuthForm mode="sign-in" />);

  fill("Email", "ada@example.com");
  fill("Password", "wrong-password");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  expect((await screen.findByRole("alert")).textContent).toBe("Invalid email or password");
  expect(auth.replace).not.toHaveBeenCalled();
  expect(screen.getByRole("link", { name: "Create an account" }).getAttribute("href")).toBe(
    "/sign-up",
  );
});

test("sign-up sends the name and opens the app", async () => {
  auth.signUp.mockResolvedValue({ data: { user: { id: "u1" } }, error: null });
  render(<AuthForm mode="sign-up" />);

  fill("Name", "Ada");
  fill("Email", "ada@example.com");
  fill("Password", "correct-horse");
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));

  await vi.waitFor(() => expect(auth.replace).toHaveBeenCalledWith("/"));
  expect(auth.signUp).toHaveBeenCalledWith({
    name: "Ada",
    email: "ada@example.com",
    password: "correct-horse",
  });
  expect(screen.queryByRole("alert")).toBeNull();
});

test("sign-in says it is working until the server answers", async () => {
  auth.signIn.mockReturnValue(new Promise(() => {}));
  render(<AuthForm mode="sign-in" />);

  fill("Email", "ada@example.com");
  fill("Password", "correct-horse");
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  const pending = await screen.findByRole("button", { name: "Signing in…" });
  expect(pending.getAttribute("aria-disabled")).toBe("true");
  fireEvent.click(pending);
  expect(auth.signIn).toHaveBeenCalledOnce();
});

test("a sign-up that cannot reach the server says what to do", async () => {
  auth.signUp.mockRejectedValue(new TypeError("Failed to fetch"));
  render(<AuthForm mode="sign-up" />);

  fill("Name", "Ada");
  fill("Email", "ada@example.com");
  fill("Password", "correct-horse");
  fireEvent.click(screen.getByRole("button", { name: "Create account" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Couldn’t create your account. Check your connection and try again.",
  );
  expect(screen.getByRole("button", { name: "Create account" })).toBeDefined();
});
