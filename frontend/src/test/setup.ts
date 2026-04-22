import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// React cere asta ca să nu logheze warning despre act() în teste async.
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
// happy-dom are window separat de globalThis — setăm pe ambele.
if (typeof window !== "undefined") {
  (window as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
}

afterEach(() => {
  cleanup();
});
