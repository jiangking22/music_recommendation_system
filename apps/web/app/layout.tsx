import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Music Recommendation Foundation",
  description: "Phase 1 fixture-backed music recommendation client",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
