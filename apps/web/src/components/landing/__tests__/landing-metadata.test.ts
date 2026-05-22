import { describe, expect, it } from "vitest";
import { metadata } from "@/app/(landing)/layout";
import { LANDING_SEO } from "../landing-copy";

describe("landing metadata", () => {
  it("uses the approved launch SEO strings", () => {
    expect(metadata.title).toBe(LANDING_SEO.title);
    expect(metadata.description).toBe(LANDING_SEO.description);
  });

  it("does not expose meta keywords", () => {
    expect(Object.prototype.hasOwnProperty.call(metadata, "keywords")).toBe(
      false
    );
  });
});
