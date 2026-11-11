import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  transpilePackages: ["@mnemos/crypto"],
  // The container image runs the standalone server, which bundles only the
  // modules the app actually uses.
  output: "standalone",
};

export default nextConfig;
