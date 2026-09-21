import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib";

export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: `${SITE_URL}/`, lastModified: new Date("2026-09-21"), changeFrequency: "monthly", priority: 1 }];
}
