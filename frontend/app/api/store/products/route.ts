import { NextResponse } from "next/server";

// STORE_BACKEND_URL is a server-side-only variable pointing at the Django store
// service. Set it in Cloud Run / .env.local. Falls back to the local dev default.
const BACKEND_URL =
  process.env.STORE_BACKEND_URL ?? "http://localhost:8001/api/products/";

export async function GET() {
  try {
    const response = await fetch(BACKEND_URL, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend returned ${response.status}` },
        { status: response.status },
      );
    }

    const data: unknown = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json(
      { error: "Could not reach the store backend." },
      { status: 502 },
    );
  }
}
