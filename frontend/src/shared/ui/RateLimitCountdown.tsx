import { useEffect, useState } from "react";

interface Props {
  /** Secunde până la retry, din header-ul Retry-After. */
  seconds: number;
  /** Callback când countdown-ul ajunge la 0 (pentru a reseta UI-ul de blocare). */
  onExpire?: () => void;
  prefix?: string;
}

/**
 * Afișează „Reîncearcă în Ns" cu tick de 1s. Se oprește la 0 și apelează onExpire.
 */
export function RateLimitCountdown({ seconds, onExpire, prefix = "Reîncearcă în" }: Props) {
  const [remaining, setRemaining] = useState(seconds);

  useEffect(() => {
    setRemaining(seconds);
  }, [seconds]);

  useEffect(() => {
    if (remaining <= 0) {
      onExpire?.();
      return;
    }
    const t = setTimeout(() => setRemaining((r) => r - 1), 1000);
    return () => clearTimeout(t);
  }, [remaining, onExpire]);

  if (remaining <= 0) return null;

  return (
    <span style={{ fontWeight: 500 }}>
      {prefix} <span style={{ fontVariantNumeric: "tabular-nums" }}>{remaining}s</span>
    </span>
  );
}
