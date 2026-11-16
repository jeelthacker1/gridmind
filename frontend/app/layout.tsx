import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "GRIDMIND | Energy intelligence",
  description: "Industrial energy intelligence and microgrid digital twin",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
