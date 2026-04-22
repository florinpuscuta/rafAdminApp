import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PasswordStrength, scorePassword } from "./PasswordStrength";

describe("scorePassword", () => {
  it("returns level 0 for empty", () => {
    expect(scorePassword("").level).toBe(0);
  });
  it("scores short single-class as level 1", () => {
    expect(scorePassword("abcdefgh").level).toBe(1);
  });
  it("scores length+classes higher", () => {
    expect(scorePassword("MyStrong7").level).toBeGreaterThanOrEqual(3);
  });
  it("maxes out on long + all classes", () => {
    expect(scorePassword("MyStr0ng!Password#2026").level).toBe(4);
  });
  it("penalizes trivial patterns", () => {
    expect(scorePassword("password1").level).toBeLessThanOrEqual(1);
    expect(scorePassword("aaaaaaaa").level).toBeLessThanOrEqual(1);
  });
});

describe("PasswordStrength component", () => {
  it("hides when password empty by default", () => {
    const { container } = render(<PasswordStrength password="" />);
    expect(container.firstChild).toBeNull();
  });
  it("renders label when non-empty", () => {
    render(<PasswordStrength password="abcdefgh" />);
    expect(screen.getByText(/Putere:/)).toBeInTheDocument();
    expect(screen.getByText(/slabă/)).toBeInTheDocument();
  });
  it("shows 'puternică' label for strong pwd", () => {
    render(<PasswordStrength password="MyStr0ng!Password#2026" />);
    expect(screen.getByText(/puternică/)).toBeInTheDocument();
  });
});
