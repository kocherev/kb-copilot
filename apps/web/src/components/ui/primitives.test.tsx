import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Inbox } from "lucide-react";
import { afterEach, expect, test, vi } from "vitest";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { InlineError } from "@/components/ui/inline-error";
import { InlineStatus } from "@/components/ui/inline-status";
import { PageHeader } from "@/components/ui/page-header";
import { Section } from "@/components/ui/section";
import { Loading, Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";

afterEach(cleanup);

test("page header names the page and links back", () => {
  render(
    <PageHeader
      title="Northstar Desk"
      description="Shawn answers from 6 documents."
      back={{ href: "/", label: "All products" }}
      actions={<Button>Start session</Button>}
    />,
  );

  expect(screen.getByRole("heading", { level: 1, name: "Northstar Desk" })).toBeDefined();
  expect(screen.getByRole("link", { name: "All products" }).getAttribute("href")).toBe("/");
  expect(screen.getByRole("button", { name: "Start session" })).toBeDefined();
});

test("section is a region named by its heading", () => {
  render(
    <Section title="Documents" description="What Shawn can answer from.">
      <p>Body</p>
    </Section>,
  );

  const region = screen.getByRole("region", { name: "Documents" });
  expect(region.textContent).toContain("Body");
  expect(screen.getByRole("heading", { level: 2, name: "Documents" })).toBeDefined();
});

test("empty state says what goes here and offers the next step", () => {
  render(
    <EmptyState
      icon={Inbox}
      title="No documents yet"
      description="Upload your help docs so Shawn can answer from them."
      action={<Button>Upload documents</Button>}
    />,
  );

  expect(screen.getByText("No documents yet")).toBeDefined();
  expect(screen.getByRole("button", { name: "Upload documents" })).toBeDefined();
});

test("inline error is an alert and can try again", () => {
  const retry = vi.fn();
  render(<InlineError onRetry={retry}>Couldn&rsquo;t load documents.</InlineError>);

  expect(screen.getByRole("alert").textContent).toContain("load documents");
  fireEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
});

test("inline error without a retry shows no button", () => {
  render(<InlineError>Couldn&rsquo;t save.</InlineError>);

  expect(screen.queryByRole("button")).toBeNull();
});

test("a labelled spinner is a status; a bare one is hidden", () => {
  const { container } = render(
    <>
      <Spinner label="Uploading 3 files" />
      <Spinner />
    </>,
  );

  expect(screen.getByRole("status").textContent).toBe("Uploading 3 files");
  expect(container.querySelectorAll('svg[aria-hidden="true"]')).toHaveLength(2);
});

test("inline status exists before it has text", () => {
  const { rerender } = render(<InlineStatus tone="success">{null}</InlineStatus>);
  expect(screen.getByRole("status").textContent).toBe("");

  rerender(<InlineStatus tone="success">Saved</InlineStatus>);
  expect(screen.getByRole("status").textContent).toBe("Saved");
});

test("loading announces one status and hides the skeletons", () => {
  const { container } = render(
    <Loading label="Loading documents">
      <Skeleton className="h-4" />
      <Skeleton className="h-4" />
    </Loading>,
  );

  const status = screen.getByRole("status");
  expect(status.textContent).toBe("Loading documents");
  expect(status.getAttribute("aria-busy")).toBe("true");
  expect(container.querySelectorAll('[aria-hidden="true"]')).toHaveLength(2);
});
