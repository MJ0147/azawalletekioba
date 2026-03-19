/**
 * This file provides examples of how to use the environment variables
 * injected during the build process to make API calls to backend services.
 */

/**
 * Fetches products from the store service.
 * The URL is provided by the NEXT_PUBLIC_STORE_PRODUCTS_URL environment variable.
 *
 * In production (Cloud Run), this will be a relative path like '/api/store/products/'.
 * The browser resolves this to 'https://<your-cloud-run-url>/api/store/products/',
 * and Nginx proxies the request internally to the Django service.
 */
export async function getStoreProducts() {
  const url = process.env.NEXT_PUBLIC_STORE_PRODUCTS_URL;
  if (!url) {
    throw new Error('Configuration error: NEXT_PUBLIC_STORE_PRODUCTS_URL is not defined.');
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`API call failed with status: ${response.status}`);
  }
  return response.json();
}

/**
 * Establishes a WebSocket connection to the AI chat service (Iyobo).
 * The path is provided by the NEXT_PUBLIC_IYOBO_URL environment variable (e.g., '/chat').
 */
export function connectToChat() {
  const path = process.env.NEXT_PUBLIC_IYOBO_URL;
  if (!path) {
    throw new Error('Configuration error: NEXT_PUBLIC_IYOBO_URL is not defined.');
  }

  // Construct the full WebSocket URL from the relative path.
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const wsUrl = `${protocol}//${host}${path}`;

  return new WebSocket(wsUrl);
}