import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MergeDialog } from "./MergeDialog";

const items = [
  { id: "1", label: "Store Alpha" },
  { id: "2", label: "Store Beta" },
  { id: "3", label: "Store Gamma" },
];

describe("MergeDialog", () => {
  it("renders items and blocks submit until primary + duplicate selected", async () => {
    const user = userEvent.setup();
    const onMerge = vi.fn();
    const onClose = vi.fn();

    render(
      <MergeDialog
        title="Merge stores"
        items={items}
        onClose={onClose}
        onMerge={onMerge}
        entityNoun="magazine"
      />,
    );

    expect(screen.getByText("Store Alpha")).toBeInTheDocument();

    const submitBtn = screen.getByRole("button", { name: /Consolidează/ });
    expect(submitBtn).toBeDisabled();

    // Select primary
    const radios = screen.getAllByRole("radio");
    await user.click(radios[0]);
    expect(submitBtn).toBeDisabled(); // still no duplicate

    // Check a duplicate (Beta)
    const checkboxes = screen.getAllByRole("checkbox");
    await user.click(checkboxes[1]);
    expect(submitBtn).toBeEnabled();

    await user.click(submitBtn);
    expect(onMerge).toHaveBeenCalledWith("1", ["2"]);
  });

  it("filters items by search query", async () => {
    const user = userEvent.setup();
    render(
      <MergeDialog
        title="Merge"
        items={items}
        onClose={vi.fn()}
        onMerge={vi.fn()}
        entityNoun="magazine"
      />,
    );

    const filter = screen.getByPlaceholderText(/Filtrează/);
    await user.type(filter, "beta");

    expect(screen.queryByText("Store Alpha")).not.toBeInTheDocument();
    expect(screen.getByText("Store Beta")).toBeInTheDocument();
    expect(screen.queryByText("Store Gamma")).not.toBeInTheDocument();
  });

  it("closes on backdrop click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(
      <MergeDialog
        title="Merge"
        items={items}
        onClose={onClose}
        onMerge={vi.fn()}
        entityNoun="magazine"
      />,
    );

    // First div is the backdrop
    const backdrop = container.firstChild as HTMLElement;
    await user.click(backdrop);
    expect(onClose).toHaveBeenCalled();
  });

  it("closes on Escape key", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <MergeDialog
        title="Merge"
        items={items}
        onClose={onClose}
        onMerge={vi.fn()}
        entityNoun="magazine"
      />,
    );
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });

  it("has proper dialog role + aria-labelledby on title", () => {
    render(
      <MergeDialog
        title="Consolidează magazine"
        items={items}
        onClose={vi.fn()}
        onMerge={vi.fn()}
        entityNoun="magazine"
      />,
    );
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const titleId = dialog.getAttribute("aria-labelledby");
    expect(titleId).toBeTruthy();
    const title = document.getElementById(titleId!);
    expect(title).toHaveTextContent("Consolidează magazine");
  });

  it("focuses the filter input on open", () => {
    render(
      <MergeDialog
        title="Merge"
        items={items}
        onClose={vi.fn()}
        onMerge={vi.fn()}
        entityNoun="magazine"
      />,
    );
    expect(screen.getByPlaceholderText(/Filtrează/)).toHaveFocus();
  });
});
