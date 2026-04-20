"use client";

import { WalletAdapterNetwork } from "@solana/wallet-adapter-base";
import { ConnectionProvider, WalletProvider } from "@solana/wallet-adapter-react";
import { WalletModalProvider } from "@solana/wallet-adapter-react-ui";
import { PhantomWalletAdapter } from "@solana/wallet-adapter-phantom";
import { SolflareWalletAdapter } from "@solana/wallet-adapter-solflare";
import { clusterApiUrl } from "@solana/web3.js";
import React, { useMemo } from "react";
import { TonConnectUIProvider } from "@tonconnect/ui-react";

export default function BlockchainProviders({
  children,
}: {
  children: React.ReactNode;
}) {
  // The network can be set to 'devnet', 'testnet', or 'mainnet-beta'.
  // In production, this should generally be Mainnet.
  const network = WalletAdapterNetwork.Mainnet;

  // You can also provide a custom RPC endpoint.
  // It uses the environment variable if set, otherwise falls back to the public cluster URL.
  const endpoint = useMemo(() => {
    if (process.env.NEXT_PUBLIC_SOLANA_RPC_URL) {
      return process.env.NEXT_PUBLIC_SOLANA_RPC_URL;
    }
    return clusterApiUrl(network);
  }, [network]);

  const wallets = useMemo(
    () => [new PhantomWalletAdapter(), new SolflareWalletAdapter()],
    [network]
  );

  // Manifest URL required by TON Connect. Ensure this file exists in your public/ folder.
  const tonManifestUrl = process.env.NEXT_PUBLIC_TON_MANIFEST_URL || "/tonconnect-manifest.json";

  return (
    <TonConnectUIProvider manifestUrl={tonManifestUrl}>
      <ConnectionProvider endpoint={endpoint}>
        <WalletProvider wallets={wallets} autoConnect>
          <WalletModalProvider>{children}</WalletModalProvider>
        </WalletProvider>
      </ConnectionProvider>
    </TonConnectUIProvider>
  );
}