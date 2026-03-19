"use client";

import { useEffect, useState } from "react";
import { getBalance } from "../../services/idiaTokenService";

export default function WalletView({ address }: { address: string }) {
  const [balance, setBalance] = useState<number | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [isCachedFallback, setIsCachedFallback] = useState(false);

  useEffect(() => {
    const cacheKey = `idia-balance:${address}`;

    getBalance(address)
      .then((data) => {
        const parsedBalance = Number(data.balance);
        if (!Number.isFinite(parsedBalance)) {
          throw new Error("Invalid balance format");
        }
        setBalance(parsedBalance);
        const nowIso = new Date().toISOString();
        setLastUpdated(new Date(nowIso));
        setIsCachedFallback(false);
        localStorage.setItem(cacheKey, JSON.stringify({ balance: parsedBalance, updatedAt: nowIso }));
      })
      .catch(() => {
        const cached = localStorage.getItem(cacheKey);
        if (!cached) {
          return;
        }

        try {
          const parsed = JSON.parse(cached) as { balance?: number; updatedAt?: string };
          if (typeof parsed.balance === "number") {
            setBalance(parsed.balance);
            setIsCachedFallback(true);
          }
          if (parsed.updatedAt) {
            setLastUpdated(new Date(parsed.updatedAt));
          }
        } catch {
          // Ignore corrupted cache entries.
        }
      });
  }, [address]);

  return (
    <div>
      <h2>Your IDIA Balance</h2>
      {balance === null ? (
        <p>Loading...</p>
      ) : (
        <p>
          {balance / 1e9} IDIA
          {lastUpdated ? ` (last updated ${lastUpdated.toLocaleTimeString()})` : ""}
        </p>
      )}
      {isCachedFallback ? <p>Offline mode: showing cached balance.</p> : null}
    </div>
  );
}
