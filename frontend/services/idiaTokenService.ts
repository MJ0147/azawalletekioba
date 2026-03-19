const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;
// e.g. "https://api.ekioba.com" set in your .env

if (!BACKEND_URL) {
  if (process.env.NODE_ENV === 'production') {
    throw new Error("NEXT_PUBLIC_BACKEND_URL is not set. Service cannot function.");
  } else {
    console.warn("NEXT_PUBLIC_BACKEND_URL is not set. API calls may fail.");
  }
}

// Define types for API responses for better type safety
export interface TokenInfo {
  name: string;
  symbol: string;
  decimals: number;
  totalSupply: string;
}

export interface Balance {
  balance: string;
}

// A generic fetch wrapper for robust error handling and typing
async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  // Use URL constructor for safe path joining
  const url = new URL(endpoint, BACKEND_URL || "http://localhost").toString();
  
  // Default timeout of 10 seconds
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 10000);

  try {
    const res = await fetch(url, {
      signal: controller.signal,
      cache: "no-store", // Ensure we don't serve stale data for balances
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });

    if (!res.ok) {
      // Try to parse a structured error from the backend, otherwise throw a generic error
      const errorBody = await res.json().catch(() => ({ message: "An unknown API error occurred" }));
      throw new Error(errorBody.detail || errorBody.message || `Request failed with status ${res.status}`);
    }

    return res.json() as Promise<T>;
  } catch (error) {
    console.error(`API call to ${url} failed:`, error);
    // Re-throw to allow UI components to handle it (e.g., show a toast notification)
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function getTokenInfo(): Promise<TokenInfo> {
  return fetchApi<TokenInfo>("/api/ton/token-info");
}

export async function getBalance(address: string): Promise<Balance> {
  return fetchApi<Balance>(`/api/ton/idia-balance/${address}`);
}

// Best Practice: Use string for financial amounts to avoid floating point precision errors
// The backend should handle parsing this string into the correct BigInt/Nano units.
export async function transferIdia(to: string, amount: string) {
  return fetchApi("/api/ton/transfer-idia", {
    method: "POST",
    body: JSON.stringify({ to_address: to, amount }),
  });
}

export async function estimateGas() {
  return fetchApi("/api/ton/estimate-gas");
}

export async function verifyContract() {
  return fetchApi("/api/ton/verify-contract");
}
