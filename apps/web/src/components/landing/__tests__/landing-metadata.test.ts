import { describe, expect, it } from "vitest";
import { metadata } from "@/app/(landing)/layout";
import { alt as ogImageAlt } from "@/app/(landing)/opengraph-image";
import { LANDING_SEO } from "../landing-copy";

describe("landing metadata", () => {
  it("uses the approved launch SEO strings", () => {
    expect(metadata.title).toEqual({ absolute: LANDING_SEO.title });
    expect(metadata.description).toBe(LANDING_SEO.description);
    expect(metadata.openGraph).toMatchObject({
      title: LANDING_SEO.title,
      description: LANDING_SEO.description,
      siteName: "ContextOS",
      type: "website",
    });
    expect(metadata.twitter).toMatchObject({
      card: "summary_large_image",
      title: LANDING_SEO.title,
      description: LANDING_SEO.description,
    });
    expect(ogImageAlt).toBe(LANDING_SEO.title);
  });

  it("does not expose meta keywords", () => {
    expect(Object.prototype.hasOwnProperty.call(metadata, "keywords")).toBe(
      false
    );
  });
});
