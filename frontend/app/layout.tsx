import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import BlockchainProviders from "./components/BlockchainProviders";
import CopilotProvider from "./components/CopilotProvider";
import "@solana/wallet-adapter-react-ui/styles.css";
import "@copilotkit/react-ui/styles.css";
import "./globals.css";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "EKIOBA Multi-Service Platform",
  description: "Unified ecosystem for store, academy, hotels, tourism, cargo, and crypto forecasting.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="manifest" href="/manifest.json" />
        <meta name="theme-color" content="#020617" />
      </head>
      <body className={spaceGrotesk.className}>
        <CopilotProvider>
          <BlockchainProviders>
            {children}
          </BlockchainProviders>
        </CopilotProvider>
      </body>
    </html>
  );
}
