import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "LocalLife OS",
    short_name: "LocalLife",
    description: "Plan time, money, and commitments privately on this device.",
    start_url: "/",
    display: "standalone",
    background_color: "#f7f7f8",
    theme_color: "#202023",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml" }],
  };
}
