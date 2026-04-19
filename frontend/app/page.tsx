import WalletConnectPanel from "./components/WalletConnectPanel";
import StoreProducts from "./components/StoreProducts";
import GenerativeUI from "./components/GenerativeUI";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center p-8 md:p-24 bg-gray-50 dark:bg-black text-gray-900 dark:text-white">
      {/* Header / Nav Area */}
      <div className="z-10 w-full max-w-5xl items-center justify-between font-mono text-sm lg:flex mb-10">
        <p className="fixed left-0 top-0 flex w-full justify-center border-b border-gray-300 bg-gradient-to-b from-zinc-200 pb-6 pt-8 backdrop-blur-2xl dark:border-neutral-800 dark:bg-zinc-800/30 dark:from-inherit lg:static lg:w-auto lg:rounded-xl lg:border lg:bg-gray-200 lg:p-4 lg:dark:bg-zinc-800/30">
          EKIOBA Marketplace
        </p>
        <div className="fixed bottom-0 left-0 flex h-48 w-full items-end justify-center bg-gradient-to-t from-white via-white dark:from-black dark:via-black lg:static lg:h-auto lg:w-auto lg:bg-none">
          <span className="pointer-events-none flex place-items-center gap-2 p-8 lg:pointer-events-auto lg:p-0">
            By Ekioba Team
          </span>
        </div>
      </div>

      {/* Hero Section */}
      <div className="relative flex flex-col place-items-center text-center mb-12">
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight mb-4">
          Welcome to Ekioba
        </h1>
        <p className="text-lg text-gray-600 dark:text-gray-400 max-w-2xl">
          The decentralized marketplace for everything. Connect your wallet to get started.
        </p>
      </div>

      {/* Generative UI Section */}
      <div className="w-full max-w-4xl mb-10">
        <GenerativeUI />
      </div>

      {/* Wallet Section */}
      <div className="w-full max-w-md mb-10">
        <WalletConnectPanel />
      </div>

      {/* Product Listing */}
      <div className="w-full max-w-5xl">
        <StoreProducts />
      </div>
    </main>
  );
}