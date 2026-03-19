import { NextResponse } from "next/server";
import crypto from "crypto";
// In a real application, you would import your database client
// import { cockroachDBClient } from "@/lib/db";

// Interface based on typical TonAPI/Blockchain webhook events
interface TonWebhookPayload {
  account_id?: string;
  tx_hash?: string;
  utime?: number;
  // The value is typically a string representing a large integer (nanotons)
  value?: string;
  [key: string]: any;
}

// Helper to verify HMAC signature (Standard pattern for webhooks)
// It's crucial to verify against the raw request body, not a re-serialized JSON object.
function verifySignature(rawBody: string, signature: string | null, secret?: string): boolean {
  if (!secret || !signature) return false;
  
  const hmac = crypto.createHmac('sha256', secret);
  const digest = hmac.update(rawBody).digest('hex');
  
  // Constant time comparison to prevent timing attacks
  try {
    return crypto.timingSafeEqual(Buffer.from(signature), Buffer.from(digest));
  } catch (error) {
    console.error("Error during signature comparison:", error);
    return false;
  }
}

// This endpoint receives real-time notifications from TonAPI
export async function POST(request: Request) {
  try {
    // Read the raw body for signature verification
    const rawBody = await request.text();
    const payload = JSON.parse(rawBody) as TonWebhookPayload;
    
    // --- SECURITY CHECK ---
    // Get the signature from headers (if provided by your notifier service)
    const signature = request.headers.get("x-ton-signature");
    
    // Only run verification if a secret is configured (Production Safety)
    if (process.env.TON_WEBHOOK_SECRET) {
      const isValid = verifySignature(rawBody, signature, process.env.TON_WEBHOOK_SECRET);
      if (!isValid) return NextResponse.json({ error: "Invalid signature" }, { status: 401 });
    }

    if (!payload || typeof payload !== 'object') {
      return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
    }

    // For production, consider using a structured logger and controlling log levels via env vars.
    if (process.env.NODE_ENV !== 'production') {
      console.log("Received TON Webhook Event:", JSON.stringify(payload, null, 2));
    }

    // Typical TonAPI webhook payload structure inspection
    // You will likely receive an array of events or a specific transaction object
    const { account_id, tx_hash, value } = payload;

    if (account_id && tx_hash) {
      // --- PRODUCTION IMPLEMENTATION ---
      // This is where you would interact with your database.
      // const order = await cockroachDBClient.order.findFirst({ where: { tx_hash_pending: tx_hash } });
      // if (order && order.total_nanotons === value) {
      //   await cockroachDBClient.order.update({
      //     where: { id: order.id },
      //     data: { status: 'COMPLETED', tx_hash_confirmed: tx_hash }
      //   });
      // }
      
      console.log(`Processing payment for account ${account_id}, Hash: ${tx_hash}`);
    }

    // Always return 200 OK quickly to acknowledge receipt
    return NextResponse.json({ received: true });
  } catch (error) {
    console.error("Error processing TON webhook:", error);
    // Return 500 so TonAPI knows to retry later if it supports retries
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 }
    );
  }
}