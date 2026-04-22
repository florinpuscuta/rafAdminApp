import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorBoundary } from "./ErrorBoundary";

function Boom({ msg = "explode" }: { msg?: string }): React.ReactElement {
  throw new Error(msg);
}

describe("ErrorBoundary", () => {
  let errSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    // React loghează erori cu console.error — silențiem pt teste curate.
    errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    errSpy.mockRestore();
    delete (window as unknown as { Sentry?: unknown }).Sentry;
  });

  it("renders children when no error", () => {
    render(
      <ErrorBoundary>
        <p>all good</p>
      </ErrorBoundary>,
    );
    expect(screen.getByText("all good")).toBeInTheDocument();
  });

  it("renders default fallback with message on error", () => {
    render(
      <ErrorBoundary name="test">
        <Boom msg="nope" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("A apărut o eroare")).toBeInTheDocument();
    expect(screen.getByText("nope")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reîncearcă/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Înapoi la Dashboard/ })).toBeInTheDocument();
  });

  it("reset clears the error state", async () => {
    const user = userEvent.setup();
    function Toggle({ fail }: { fail: boolean }) {
      if (fail) throw new Error("x");
      return <p>recovered</p>;
    }
    // Rerender-ul cu fail=false înainte de reset nu ajută (state-ul e deja eroare).
    // Pentru a testa reset, setăm starea ca după reset să redăm copil valid.
    const { rerender } = render(
      <ErrorBoundary>
        <Toggle fail={true} />
      </ErrorBoundary>,
    );
    expect(screen.getByText("A apărut o eroare")).toBeInTheDocument();
    rerender(
      <ErrorBoundary>
        <Toggle fail={false} />
      </ErrorBoundary>,
    );
    await user.click(screen.getByRole("button", { name: /Reîncearcă/ }));
    expect(screen.getByText("recovered")).toBeInTheDocument();
  });

  it("uses custom fallback when provided", () => {
    render(
      <ErrorBoundary fallback={(err) => <div>custom: {err.message}</div>}>
        <Boom msg="custom-err" />
      </ErrorBoundary>,
    );
    expect(screen.getByText("custom: custom-err")).toBeInTheDocument();
  });

  it("reports to window.Sentry.captureException when available", () => {
    const captureException = vi.fn(() => "evt-123");
    (window as unknown as { Sentry: unknown }).Sentry = { captureException };

    render(
      <ErrorBoundary name="feature-x">
        <Boom msg="sentry test" />
      </ErrorBoundary>,
    );

    expect(captureException).toHaveBeenCalledTimes(1);
    const call = captureException.mock.calls[0] as unknown as [Error, { tags: { boundary: string } }];
    expect(call[0].message).toBe("sentry test");
    expect(call[1].tags.boundary).toBe("feature-x");
    // Event ID e afișat în UI
    expect(screen.getByText(/Referință eroare/)).toBeInTheDocument();
    expect(screen.getByText("evt-123")).toBeInTheDocument();
  });
});
