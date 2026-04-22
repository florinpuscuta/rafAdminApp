import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { norm, SearchInput } from "./SearchInput";

describe("norm", () => {
  it("lowercases and strips Romanian diacritics", () => {
    expect(norm("ȘtiȚă Țânțar")).toBe("stita tantar");
  });
  it("trims whitespace", () => {
    expect(norm("   hello   ")).toBe("hello");
  });
  it("is empty for empty input", () => {
    expect(norm("")).toBe("");
  });
});

describe("SearchInput", () => {
  it("calls onChange on typing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchInput value="" onChange={onChange} />);
    await user.type(screen.getByPlaceholderText(/Caută/), "a");
    expect(onChange).toHaveBeenCalledWith("a");
  });

  it("renders counter only when filtering + counts provided", () => {
    const { rerender } = render(
      <SearchInput value="" onChange={vi.fn()} total={10} visible={10} />,
    );
    expect(screen.queryByText(/din/)).not.toBeInTheDocument();

    rerender(<SearchInput value="foo" onChange={vi.fn()} total={10} visible={3} />);
    expect(screen.getByText("3 din 10")).toBeInTheDocument();
  });

  it("shows Șterge button when filtering and clears on click", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<SearchInput value="beta" onChange={onChange} />);
    await user.click(screen.getByRole("button", { name: /Șterge/ }));
    expect(onChange).toHaveBeenCalledWith("");
  });
});
