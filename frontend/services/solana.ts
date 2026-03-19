import { Connection, clusterApiUrl } from "@solana/web3.js";

// Use the RPC URL from environment variables or default to mainnet-beta.
// Prioritize the server-side secret (SOLANA_RPC_URL) to keep API keys secure in API routes.
export const RPC_URL =
  process.env.SOLANA_RPC_URL ||
  process.env.NEXT_PUBLIC_SOLANA_RPC_URL ||
  clusterApiUrl("mainnet-beta");

const isPublicUrl = !process.env.SOLANA_RPC_URL && !process.env.NEXT_PUBLIC_SOLANA_RPC_URL;

if (isPublicUrl) {
  if (process.env.NODE_ENV === "production") {
    console.warn("WARNING: Production deployment using public Solana RPC URL. Rate limits may occur. Set SOLANA_RPC_URL.");
  } else {
    console.log("Using public Solana RPC URL for development.");
  }
}

export const CONNECTION = new Connection(RPC_URL, "confirmed");