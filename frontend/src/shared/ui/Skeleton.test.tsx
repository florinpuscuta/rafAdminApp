import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CardSkeleton, Skeleton, TableSkeleton } from "./Skeleton";

describe("Skeleton", () => {
  it("renders with default dimensions", () => {
    const { container } = render(<Skeleton />);
    const el = container.querySelector("span");
    expect(el).toBeInTheDocument();
    expect(el).toHaveStyle({ width: "100%" });
  });

  it("respects custom width/height/radius", () => {
    const { container } = render(<Skeleton width={120} height={20} radius={8} />);
    const el = container.querySelector("span");
    expect(el).toHaveStyle({ width: "120px", height: "20px", borderRadius: "8px" });
  });
});

describe("TableSkeleton", () => {
  it("renders requested rows and columns", () => {
    const { container } = render(<TableSkeleton rows={3} cols={4} />);
    expect(container.querySelectorAll("tr")).toHaveLength(3);
    expect(container.querySelectorAll("tr td")).toHaveLength(12);
  });

  it("defaults to 5×4 when no props", () => {
    const { container } = render(<TableSkeleton />);
    expect(container.querySelectorAll("tr")).toHaveLength(5);
    expect(container.querySelectorAll("tr td")).toHaveLength(20);
  });
});

describe("CardSkeleton", () => {
  it("renders three skeleton lines", () => {
    const { container } = render(<CardSkeleton />);
    // Skeleton primitive renders as a <span>
    expect(container.querySelectorAll("span")).toHaveLength(3);
  });
});
