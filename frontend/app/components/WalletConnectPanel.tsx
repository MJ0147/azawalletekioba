"use client";

import { useMemo } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { TonConnectButton, useTonWallet } from "@tonconnect/ui-react";

export default function WalletConnectPanel() {
  const { connected, publicKey } = useWallet();
  const tonWallet = useTonWallet();

  const solanaAddress = useMemo(() => {
    if (!publicKey) {
      return "Not connected";
    }
    return `${publicKey.toBase58().slice(0, 6)}...${publicKey.toBase58().slice(-6)}`;
  }, [publicKey]);

  const tonAddress = useMemo(() => {
    const address = tonWallet?.account?.address;
    if (!address) {
      return "Not connected";
    }
    return `${address.slice(0, 6)}...${address.slice(-6)}`;
  }, [tonWallet]);

  return (
    <section className="mt-8 rounded-3xl border border-ink/15 bg-white/80 p-5 shadow-sm">
      <h2 className="text-xl font-semibold text-ink">Blockchain Wallets</h2>
      <p className="mt-1 text-sm text-ink/70">Connect Phantom and Tonkeeper for checkout and vouchers.</p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <WalletMultiButton className="!bg-ink !text-canvas !rounded-xl" />
        <TonConnectButton className="!rounded-xl" />
      </div>
      <div className="mt-4 grid gap-2 text-sm text-ink/80 md:grid-cols-2">
        <p>Solana: {connected ? solanaAddress : "Not connected"}</p>
        <p>TON: {tonAddress}</p>
      </div>
    </section>
  );
}
