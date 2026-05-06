import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: [],
  compress: true,
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  experimental: {
    optimizePackageImports: [
      "@xyflow/react",
      "posthog-js",
      "react-markdown",
      "remark-gfm",
      "radix-ui",
    ],
  },
  images: {
    formats: ["image/avif", "image/webp"],
    minimumCacheTTL: 60 * 60 * 24 * 7,
  },
};

export default withSentryConfig(nextConfig, {
  // Sentry organization and project (set via env vars in production)
  org: process.env.SENTRY_ORG || "",
  project: process.env.SENTRY_PROJECT || "",

  // Suppress Sentry build output noise
  silent: true,

  // Widen client file upload for better stack traces
  widenClientFileUpload: true,

  // Disable source map upload in local dev (enable in CI)
  sourcemaps: {
    disable: true,
  },
});
