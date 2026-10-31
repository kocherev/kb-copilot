import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { HomePage } from "@/components/home-page";

test("home page names the product and links to api health", () => {
  render(<HomePage apiUrl="http://localhost:8000/" />);

  expect(
    screen.getByRole("heading", { level: 1, name: "Knowledge base copilot" }),
  ).toBeDefined();
  expect(screen.getByRole("link", { name: "API health" }).getAttribute("href")).toBe(
    "http://localhost:8000/health",
  );
  expect(screen.getByText(/not built yet/i)).toBeDefined();
});
