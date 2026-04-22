import type { ReactNode } from "react";

import { ErrorBoundary } from "./ErrorBoundary";

/**
 * Thin wrapper peste ErrorBoundary pentru uz in Routes — numele e obligatoriu
 * ca Sentry/Logs să știe care feature a explodat. Dacă o rută crapă, doar
 * conținutul acelei rute arată fallback — sidebar + restul navigației rămân
 * funcționale pentru că boundary-ul e PER rută, nu global.
 *
 * Folosire:
 *   <Route path="/sales" element={<RouteBoundary name="sales"><SalesPage/></RouteBoundary>} />
 */
export function RouteBoundary({
  name,
  children,
}: {
  name: string;
  children: ReactNode;
}) {
  return <ErrorBoundary name={name}>{children}</ErrorBoundary>;
}
