/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  // Allow loading images from the IPFS gateway used in StoreProducts.tsx
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "olive-adorable-cephalopod-171.mypinata.cloud",
      },
    ],
  },
};

module.exports = nextConfig;