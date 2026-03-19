"use client";

import { useEffect, useState } from "react";
import Checkout from "./Checkout";

type Product = {
  id: string;
  name: string;
  price: string | number;
  stock?: number;
  description?: string;
  image?: string;
  category?: "jewelry" | "fashion" | "art" | "craft" | "food";
};

type CartItem = Product & {
  quantity: number;
};

function asPriceNumber(value: string | number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function asMoney(value: number): string {
  return `Idia ${new Intl.NumberFormat("en-NG", { maximumFractionDigits: 2 }).format(value)}`;
}

const PRODUCTS: Product[] = [
  {
    id: "1",
    name: "Bronze Head of Oba Ozolua",
    description: "A miniature replica of the famous Oba Ozolua 14th-15th century Edo bronze casting.",
    price: 25000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
  },
  {
    id: "2",
    name: "Ivory Mask Pendant",
    description: "Inspired by the Queen Mother Idia mask, symbol of protection.",
    price: 28000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreibsg5ra3vkzf4o42xiyqncvopam5cmueeaa7n3fmxy7jncetnvozu",
  },
  {
    id: "3",
    name: "Royal Vintage of Oba Ovonramen",
    description: "Traditional Royal Vintage of Oba Ovonramen Nogbasi",
    price: 99000,
    category: "fashion",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiclb35ofqhxaizqvmjbktdugdvxxkymlrrypqtc4o7rvkh5serxm4",
  },
  {
    id: "4",
    name: "Coral Bead",
    description: "Coral beads representing royalty and status.",
    price: 10000,
    category: "fashion",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreih5dzvbn7rdt3lonovlnyq5kxzlr76ji4citkyrfdqfwjpgk46qsy",
  },
  {
    id: "5",
    name: "Bronze Head Pendant of Oba Ohenzae",
    description: "Oba Ohenzae 1641-1661",
    price: 27000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreicctqssx7pxyrpnw6lfl2ltpdfypagrwpnul6llu2rp5irdgholfu",
  },
  {
    id: "7",
    name: "Bronze Head Pendant of Oba Ehengbuda",
    description: "Oba Ehengbuda (The trado Medicine) 1578-1606",
    price: 25000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreihhhcng74p7mf5augnvhwvg6n6jnppcjkjkoeywlwxhsdvgf5tiuu",
  },
  {
    id: "6",
    name: "Edo Baba Shirt",
    description: "Wooden ceremonial sword used in dancing for the Oba.",
    price: 21000,
    category: "fashion",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreic7hsidssy74ijfsm2u6frxyirtarfzpx5r324h2npcmzbfqerhgy",
  },
  {
    id: "8",
    name: "Benin Bronze Plaque (Leopard)",
    description:
      "A commemorative plaque inspired by classic Benin bronze reliefs featuring the royal leopard motif.",
    price: 45000,
    category: "art",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
  },
  {
    id: "9",
    name: "Ukhure Staff Mini Replica",
    description: "Hand-finished ceremonial staff replica inspired by traditional Benin court craftwork.",
    price: 18000,
    category: "craft",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreic7hsidssy74ijfsm2u6frxyirtarfzpx5r324h2npcmzbfqerhgy",
  },
  {
    id: "10",
    name: "Coral Bead Crown Miniature",
    description: "A miniature crown-inspired pendant celebrating coral bead regalia and Edo royalty.",
    price: 32000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreih5dzvbn7rdt3lonovlnyq5kxzlr76ji4citkyrfdqfwjpgk46qsy",
  },
  {
    id: "11",
    name: "Benin Bronze Plaque (Royal Court)",
    description: "Decorative wall plaque inspired by Benin royal court scenes and classic relief art.",
    price: 52000,
    category: "art",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafkreiahf52abfi6nzgnkhw5i2gcvxap4aszgk254lqt4qx6wzgnewwrhy",
  },
  {
    id: "12",
    name: "Gold Necklace",
    description: "18 karat pure gold. Weight: 7.6 grams.",
    price: 693000,
    category: "jewelry",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeic3xqlbjcx22doceugjwke3m4ckuxdckmabni2bwo34o6ecajel5m/",
  },
  {
    id: "13",
    name: "Interior Decoration",
    description: "Igun bronze work, suitable for homes and offices. Weight: 0.7kg.",
    price: 21000,
    category: "art",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeicg5cytin5jvzh23q7jtwn25uopgetwsk32ykcssdpr7zfqa3loey/",
  },
  {
    id: "14",
    name: "Palm oil",
    description: "Undiluted palm oil produced from Okomu. Weight: 4x6 liters.",
    price: 30000,
    category: "food",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeicqkclmtsxhzsazrqd4qtr3byuxpeshgwasknsfnzqrnys6xbo3uq/",
  },
  {
    id: "15",
    name: "Dion Collections",
    description: "Igun craft collections by Dion Osagie. Weight: 0.1kg.",
    price: 21000,
    category: "craft",
    image: "https://olive-adorable-cephalopod-171.mypinata.cloud/ipfs/bafybeidoiskmghzqt2vgpgioiyzq43psao6m6aea4i62w4nhqvftly2cre/",
  },
];

function isCategory(value: unknown): value is NonNullable<Product["category"]> {
  return value === "jewelry" || value === "fashion" || value === "art" || value === "craft" || value === "food";
}

function isProduct(value: unknown): value is Product {
  if (!value || typeof value !== "object") {
    return false;
  }

  const candidate = value as Partial<Product> & { id?: string | number };
  return (
    (typeof candidate.id === "string" || typeof candidate.id === "number") &&
    typeof candidate.name === "string" &&
    (typeof candidate.price === "number" || typeof candidate.price === "string") &&
    (candidate.stock === undefined || typeof candidate.stock === "number") &&
    (candidate.description === undefined || typeof candidate.description === "string") &&
    (candidate.image === undefined || typeof candidate.image === "string") &&
    (candidate.category === undefined || isCategory(candidate.category))
  );
}

function normalizeProduct(product: Product | (Partial<Product> & { id?: string | number })): Product {
  return {
    id: String(product.id ?? ""),
    name: product.name ?? "",
    price: product.price ?? 0,
    stock: product.stock,
    description: product.description,
    image: product.image,
    category: product.category,
  };
}

function parseProductsResponse(value: unknown): Product[] {
  let asArray: unknown = value;
  if (!Array.isArray(asArray) && typeof asArray === "object" && asArray !== null) {
    const w = asArray as Record<string, unknown>;
    asArray = w["products"] ?? w["results"] ?? w["items"];
  }
  if (!Array.isArray(asArray)) return [];
  return asArray.filter(isProduct).map(normalizeProduct);
}

async function fetchProducts(signal: AbortSignal): Promise<Product[]> {
  const endpoint = process.env.NEXT_PUBLIC_STORE_PRODUCTS_URL || "/api/store/products/";
  const response = await fetch(endpoint, { signal, cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  const payload: unknown = await response.json();
  return parseProductsResponse(payload);
}

export default function StoreProducts() {
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    setIsLoading(true);
    setError("");

    fetchProducts(controller.signal)
      .then((parsed) => {
        if (parsed.length > 0) {
          setProducts(parsed);
          return;
        }

        setProducts(PRODUCTS);
        setError("Store returned no products. Showing catalog fallback.");
      })
      .catch((fetchError) => {
        if ((fetchError as { name?: string }).name === "AbortError") {
          return;
        }

        setProducts(PRODUCTS);
        setError("Could not load products right now. Showing catalog fallback.");
      })
      .finally(() => {
        setIsLoading(false);
      });

    return () => {
      controller.abort();
    };
  }, [refreshKey]);

  const addToCart = (product: Product) => {
    setCart((current) => {
      const existing = current.find((item) => item.id === product.id);
      if (existing) {
        return current.map((item) =>
          item.id === product.id
            ? {
                ...item,
                quantity: item.quantity + 1,
              }
            : item,
        );
      }

      return [...current, { ...product, quantity: 1 }];
    });
  };

  const updateQuantity = (productId: string, quantity: number) => {
    if (quantity <= 0) {
      setCart((current) => current.filter((item) => item.id !== productId));
      return;
    }

    setCart((current) =>
      current.map((item) => (item.id === productId ? { ...item, quantity } : item)),
    );
  };

  const clearCart = () => {
    setCart([]);
  };

  const totalAmount = cart.reduce((sum, item) => sum + asPriceNumber(item.price) * item.quantity, 0);

  return (
    <section className="mt-10 rounded-2xl border border-ink/15 bg-white/70 p-5 shadow-sm">
      <h2 className="text-2xl font-semibold text-ink">EKIOBA Store</h2>
      <p className="mt-1 text-sm text-ink/70">Browse products, add items to cart, then pay with TON or Solana in Idia value.</p>
      {isLoading ? <p className="mt-3 text-sm text-ink/80">Loading products from store API...</p> : null}
      {error ? (
        <div className="mt-3 space-y-2">
          <p className="text-sm text-red-600">{error}</p>
          <button
            type="button"
            onClick={() => setRefreshKey((current) => current + 1)}
            className="rounded-xl border border-ink/20 bg-white px-3 py-2 text-sm font-medium text-ink"
          >
            Retry loading products
          </button>
        </div>
      ) : null}

      <div className="mt-5 grid gap-4 md:grid-cols-2">
        {products.map((product) => {
          const price = asPriceNumber(product.price);
          const description =
            product.description ?? `Premium ${product.name} from the Ekioba marketplace.`;

          return (
            <article key={product.id} className="overflow-hidden rounded-2xl border border-ink/10 bg-canvas/90">
              {product.image ? (
                <img src={product.image} alt={product.name} className="h-44 w-full object-cover" />
              ) : (
                <div className="h-44 w-full bg-gradient-to-br from-orange-100 via-amber-100 to-sky-100" />
              )}
              <div className="space-y-2 p-4">
                <h3 className="text-lg font-semibold text-ink">{product.name}</h3>
                <p className="text-sm text-ink/75">{description}</p>
                <div className="flex items-center justify-between pt-1">
                  <span className="text-base font-semibold text-ink">{asMoney(price)}</span>
                  <button
                    type="button"
                    onClick={() => addToCart(product)}
                    className="rounded-xl bg-ink px-4 py-2 text-sm font-medium text-canvas transition hover:opacity-90"
                  >
                    Add to cart
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      {!isLoading && !error && products.length === 0 ? <p className="mt-4 text-sm text-ink/80">No products available yet.</p> : null}

      <div className="mt-8 rounded-2xl border border-ink/15 bg-white/80 p-4">
        <h3 className="text-lg font-semibold text-ink">Cart</h3>
        {cart.length === 0 ? <p className="mt-2 text-sm text-ink/70">Your cart is empty.</p> : null}
        <ul className="mt-3 space-y-3">
          {cart.map((item) => (
            <li key={item.id} className="flex items-center justify-between gap-3 rounded-xl border border-ink/10 p-3">
              <div>
                <p className="text-sm font-medium text-ink">{item.name}</p>
                <p className="text-xs text-ink/70">{asMoney(asPriceNumber(item.price))} each</p>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => updateQuantity(item.id, item.quantity - 1)}
                  className="h-8 w-8 rounded-lg border border-ink/20 text-sm text-ink"
                >
                  -
                </button>
                <span className="min-w-6 text-center text-sm text-ink">{item.quantity}</span>
                <button
                  type="button"
                  onClick={() => updateQuantity(item.id, item.quantity + 1)}
                  className="h-8 w-8 rounded-lg border border-ink/20 text-sm text-ink"
                >
                  +
                </button>
              </div>
            </li>
          ))}
        </ul>

        <div className="mt-4 flex items-center justify-between border-t border-ink/10 pt-3">
          <p className="text-sm text-ink/70">Total (Idia)</p>
          <p className="text-lg font-semibold text-ink">{asMoney(totalAmount)}</p>
        </div>
      </div>

      <Checkout cart={cart} totalAmount={totalAmount} onPaid={clearCart} />
    </section>
  );
}
