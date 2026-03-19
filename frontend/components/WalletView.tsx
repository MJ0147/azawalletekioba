"use client";

import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { useEffect, useState } from "react";
import { LAMPORTS_PER_SOL } from "@solana/web3.js";
import "@solana/wallet-adapter-react-ui/styles.css"; // Ensure styles are imported

export const WalletView = () => {
  const { connection } = useConnection();
  const { publicKey } = useWallet();
  const [balance, setBalance] = useState<number | null>(null);

  useEffect(() => {
    if (!connection || !publicKey) {
      setBalance(null);
      return;
    }

    const updateBalance = async () => {
      try {
        const bal = await connection.getBalance(publicKey);
        setBalance(bal / LAMPORTS_PER_SOL);
      } catch (e) {
        console.error("Failed to fetch balance", e);
      }
    };

    updateBalance();
    const id = connection.onAccountChange(publicKey, () => updateBalance());
    return () => {
      connection.removeAccountChangeListener(id);
    };
  }, [connection, publicKey]);

  return (
    <div className="flex flex-col items-center gap-4 p-6 border border-gray-200 rounded-xl shadow-sm bg-white dark:bg-zinc-800 dark:border-zinc-700">
        <h2 className="text-xl font-bold">Your Wallet</h2>
        <WalletMultiButton />
        {publicKey && (
            <div className="text-center mt-2">
                <p className="text-sm text-gray-500 dark:text-gray-400">Current Balance</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {balance !== null ? balance.toFixed(4) : "..."} SOL
                </p>
            </div>
        )}
    </div>
  );
};