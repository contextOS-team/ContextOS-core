import type { NextConfig } from "next";
import { withSentryConfig } from "@sentry/nextjs";

const nextConfig: NextConfig = {
  output: "standalone",
  serverExternalPackages: [],
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
