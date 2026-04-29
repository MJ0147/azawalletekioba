"use client";

import { useEffect, useState } from "react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { TonConnectButton, useTonWallet } from "@tonconnect/ui-react";
import { PublicKey } from "@solana/web3.js";
import { getBalance } from "../../services/idiaTokenService";
import "@solana/wallet-adapter-react-ui/styles.css";

const IDIA_DECIMALS = 9;
// Set NEXT_PUBLIC_IDIA_MINT to your deployed SPL token mint address
const IDIA_MINT = process.env.NEXT_PUBLIC_IDIA_MINT ?? "";
const IDIA_IMAGE = "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreifvopg5p2x34zliugefjubifbrv6vreh2sxnuclnuluzey5znfite";

interface ChainBalance {
  value: number | null;
  updatedAt: Date | null;
  cached: boolean;
  loading: boolean;
  error: string | null;
}

function useTonIdiaBalance(tonAddress: string | null): ChainBalance {
  const [state, setState] = useState<ChainBalance>({ value: null, updatedAt: null, cached: false, loading: false, error: null });

  useEffect(() => {
    if (!tonAddress) {
      setState({ value: null, updatedAt: null, cached: false, loading: false, error: null });
      return;
    }
    const cacheKey = `idia-balance:ton:${tonAddress}`;
    setState((s) => ({ ...s, loading: true, error: null }));

    getBalance(tonAddress)
      .then((data) => {
        const parsed = Number(data.balance);
        if (!Number.isFinite(parsed)) throw new Error("Invalid balance");
        const now = new Date();
        setState({ value: parsed, updatedAt: now, cached: false, loading: false, error: null });
        localStorage.setItem(cacheKey, JSON.stringify({ balance: parsed, updatedAt: now.toISOString() }));
      })
      .catch((err) => {
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const p = JSON.parse(cached) as { balance?: number; updatedAt?: string };
            if (typeof p.balance === "number") {
              setState({ value: p.balance, updatedAt: p.updatedAt ? new Date(p.updatedAt) : null, cached: true, loading: false, error: null });
              return;
            }
          } catch { /* ignore */ }
        }
        setState({ value: null, updatedAt: null, cached: false, loading: false, error: (err as Error).message });
      });
  }, [tonAddress]);

  return state;
}

function useSolanaIdiaBalance(connected: boolean): ChainBalance {
  const { connection } = useConnection();
  const { publicKey } = useWallet();
  const [state, setState] = useState<ChainBalance>({ value: null, updatedAt: null, cached: false, loading: false, error: null });

  useEffect(() => {
    if (!connected || !publicKey || !IDIA_MINT) {
      setState({ value: null, updatedAt: null, cached: false, loading: false, error: null });
      return;
    }

    let cancelled = false;
    const cacheKey = `idia-balance:sol:${publicKey.toBase58()}`;
    setState((s) => ({ ...s, loading: true, error: null }));

    (async () => {
      try {
        const mint = new PublicKey(IDIA_MINT);
        const tokenAccounts = await connection.getParsedTokenAccountsByOwner(publicKey, { mint });
        const amount = tokenAccounts.value[0]?.account.data.parsed?.info?.tokenAmount?.uiAmount ?? 0;
        if (cancelled) return;
        const now = new Date();
        setState({ value: amount, updatedAt: now, cached: false, loading: false, error: null });
        localStorage.setItem(cacheKey, JSON.stringify({ balance: amount * 10 ** IDIA_DECIMALS, updatedAt: now.toISOString() }));
      } catch {
        if (cancelled) return;
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          try {
            const p = JSON.parse(cached) as { balance?: number; updatedAt?: string };
            if (typeof p.balance === "number") {
              setState({ value: p.balance / 10 ** IDIA_DECIMALS, updatedAt: p.updatedAt ? new Date(p.updatedAt) : null, cached: true, loading: false, error: null });
              return;
            }
          } catch { /* ignore */ }
        }
        setState({ value: null, updatedAt: null, cached: false, loading: false, error: "Failed to fetch Solana IDIA balance" });
      }
    })();

    return () => { cancelled = true; };
  }, [connected, publicKey, connection]);

  return state;
}

function BalanceBadge({ balance }: { balance: ChainBalance }) {
  if (balance.loading) return <span className="text-slate-400 text-sm animate-pulse">Fetching…</span>;
  if (balance.error) return <span className="text-red-500 text-xs">{balance.error}</span>;
  if (balance.value === null) return <span className="text-slate-400 text-sm">—</span>;
  return (
    <span className="font-bold text-orange-600">
      {balance.value.toLocaleString(undefined, { maximumFractionDigits: 4 })} IDIA
      {balance.cached && <span className="ml-1 text-xs text-slate-400">(cached)</span>}
    </span>
  );
}

export default function WalletView() {
  const { connected, publicKey } = useWallet();
  const tonWallet = useTonWallet();

  const solanaAddress = publicKey?.toBase58() ?? null;
  const tonAddress = tonWallet?.account?.address ?? null;

  const tonBalance = useTonIdiaBalance(tonAddress);
  const solanaBalance = useSolanaIdiaBalance(connected);

  const shortAddr = (addr: string) => `${addr.slice(0, 6)}…${addr.slice(-6)}`;

  return (
    <section className="rounded-3xl border border-slate-200 bg-white/90 p-6 shadow-lg">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <img src={IDIA_IMAGE} alt="Idia Coin" className="h-10 w-10 rounded-full border border-orange-200 shadow" />
        <div>
          <h2 className="text-xl font-bold text-slate-900">Idia Coin Wallets</h2>
          <p className="text-xs text-slate-500">Connect your wallets to view IDIA balances</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* Solana Wallet */}
        <div className="rounded-2xl border border-purple-100 bg-gradient-to-br from-purple-50 to-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-purple-600">Solana</span>
            <WalletMultiButton className="!text-xs !px-3 !py-1 !rounded-xl !bg-purple-600 !text-white" />
          </div>
          {solanaAddress ? (
            <>
              <p className="text-xs text-slate-500 font-mono mb-3" title={solanaAddress}>{shortAddr(solanaAddress)}</p>
              <div className="flex items-center gap-2">
                <img src={IDIA_IMAGE} alt="IDIA" className="h-5 w-5 rounded-full" />
                <BalanceBadge balance={solanaBalance} />
              </div>
              {!IDIA_MINT && (
                <p className="mt-2 text-xs text-amber-600">Set NEXT_PUBLIC_IDIA_MINT to enable on-chain balance.</p>
              )}
              {solanaBalance.updatedAt && (
                <p className="mt-1 text-xs text-slate-400">Updated {solanaBalance.updatedAt.toLocaleTimeString()}</p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-400 mt-2">Not connected</p>
          )}
        </div>

        {/* TON Wallet */}
        <div className="rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-semibold uppercase tracking-widest text-blue-600">TON</span>
            <TonConnectButton className="!rounded-xl" />
          </div>
          {tonAddress ? (
            <>
              <p className="text-xs text-slate-500 font-mono mb-3" title={tonAddress}>{shortAddr(tonAddress)}</p>
              <div className="flex items-center gap-2">
                <img src={IDIA_IMAGE} alt="IDIA" className="h-5 w-5 rounded-full" />
                <BalanceBadge balance={tonBalance} />
              </div>
              {tonBalance.updatedAt && (
                <p className="mt-1 text-xs text-slate-400">Updated {tonBalance.updatedAt.toLocaleTimeString()}</p>
              )}
            </>
          ) : (
            <p className="text-sm text-slate-400 mt-2">Not connected</p>
          )}
        </div>
      </div>

      {/* Combined IDIA summary */}
      {(solanaBalance.value !== null || tonBalance.value !== null) && (
        <div className="mt-5 rounded-xl bg-orange-50 border border-orange-200 px-4 py-3 flex items-center justify-between">
          <span className="text-sm font-semibold text-orange-800">Total IDIA</span>
          <span className="text-lg font-extrabold text-orange-600">
            {((solanaBalance.value ?? 0) + (tonBalance.value !== null ? tonBalance.value / 10 ** IDIA_DECIMALS : 0))
              .toLocaleString(undefined, { maximumFractionDigits: 4 })} IDIA
          </span>
        </div>
      )}
    </section>
  );
}
