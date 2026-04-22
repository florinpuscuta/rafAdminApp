import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RateLimitCountdown } from "./RateLimitCountdown";

describe("RateLimitCountdown", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders initial seconds", () => {
    render(<RateLimitCountdown seconds={5} />);
    expect(screen.getByText(/Reîncearcă în/)).toBeInTheDocument();
    expect(screen.getByText("5s")).toBeInTheDocument();
  });

  it("decrements every second and calls onExpire at 0", () => {
    const onExpire = vi.fn();
    render(<RateLimitCountdown seconds={2} onExpire={onExpire} />);
    expect(screen.getByText("2s")).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1000); });
    expect(screen.getByText("1s")).toBeInTheDocument();

    act(() => { vi.advanceTimersByTime(1000); });
    // remaining=0 → effect runs, calls onExpire, component returns null
    act(() => { vi.advanceTimersByTime(0); });
    expect(screen.queryByText(/Reîncearcă/)).not.toBeInTheDocument();
    expect(onExpire).toHaveBeenCalledTimes(1);
  });

  it("renders nothing when seconds is 0", () => {
    const { container } = render(<RateLimitCountdown seconds={0} />);
    expect(container.firstChild).toBeNull();
  });
});
