import { NextResponse } from "next/server";
import { Connection, LAMPORTS_PER_SOL, PublicKey, SystemProgram, Transaction, clusterApiUrl } from "@solana/web3.js";

const merchantWallet = process.env.NEXT_PUBLIC_SOLANA_MERCHANT_WALLET;
const rpcUrl = process.env.NEXT_PUBLIC_SOLANA_RPC_URL || clusterApiUrl("mainnet-beta");
const BACKEND_URL = process.env.STORE_BACKEND_URL ?? "http://localhost:8001/api/products/";
const connection = new Connection(rpcUrl, "confirmed");

type PostRequest = {
  account: string;
  cart: Array<{ id: string | number; quantity: number }>;
};

type ServerProduct = {
  id: string | number;
  price: string | number;
};

async function fetchTrustedPrices(): Promise<Map<string, number>> {
  const response = await fetch(BACKEND_URL, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Product source unavailable: ${response.status}`);
  }

  const payload = (await response.json()) as unknown;
  if (!Array.isArray(payload)) {
    throw new Error("Invalid product payload.");
  }

  const trustedPrices = new Map<string, number>();
  for (const item of payload as ServerProduct[]) {
    const id = String(item?.id ?? "");
    const parsedPrice = Number(item?.price);
    if (!id || !Number.isFinite(parsedPrice) || parsedPrice < 0) {
      continue;
    }
    trustedPrices.set(id, parsedPrice);
  }

  if (trustedPrices.size === 0) {
    throw new Error("No trusted prices found.");
  }

  return trustedPrices;
}

export async function POST(request: Request) {
  if (!merchantWallet) {
    return NextResponse.json({ error: "Missing NEXT_PUBLIC_SOLANA_MERCHANT_WALLET configuration." }, { status: 500 });
  }

  try {
    const { account, cart } = (await request.json()) as PostRequest;
    if (!account || !Array.isArray(cart) || cart.length === 0) {
      return NextResponse.json({ error: "Account and cart are required." }, { status: 400 });
    }

    const trustedPrices = await fetchTrustedPrices();
    const totalAmount = cart.reduce((sum, item) => {
      const quantity = Number(item.quantity);
      if (!Number.isInteger(quantity) || quantity <= 0) {
        throw new Error("Invalid cart quantity.");
      }

      const trustedPrice = trustedPrices.get(String(item.id));
      if (trustedPrice === undefined) {
        throw new Error("One or more products are unavailable.");
      }

      return sum + trustedPrice * quantity;
    }, 0);
    if (!Number.isFinite(totalAmount) || totalAmount <= 0) {
      return NextResponse.json({ error: "Computed total amount is invalid." }, { status: 400 });
    }

    const payer = new PublicKey(account);
    const recipient = new PublicKey(merchantWallet);
    const lamports = Math.round(totalAmount * LAMPORTS_PER_SOL);

    if (!Number.isFinite(lamports) || lamports <= 0) {
      return NextResponse.json({ error: "Computed lamports are invalid." }, { status: 400 });
    }

    const { blockhash } = await connection.getLatestBlockhash();
    const transaction = new Transaction({ recentBlockhash: blockhash, feePayer: payer });
    transaction.add(
      SystemProgram.transfer({
        fromPubkey: payer,
        toPubkey: recipient,
        lamports,
      }),
    );

    const serializedTransaction = transaction.serialize({ requireAllSignatures: false });
    const base64Transaction = serializedTransaction.toString("base64");

    return NextResponse.json({
      transaction: base64Transaction,
      message: "Please approve this Solana payment in your wallet.",
    });
  } catch (error) {
    console.error("Error creating Solana checkout transaction:", error);
    return NextResponse.json({ error: error instanceof Error ? error.message : "Error creating checkout transaction." }, { status: 500 });
  }
}
