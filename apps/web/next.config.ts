import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  poweredByHeader: false,
  reactStrictMode: true,
  transpilePackages: ["@locallife/shared-types", "@locallife/ui"],
};

export default nextConfig;
