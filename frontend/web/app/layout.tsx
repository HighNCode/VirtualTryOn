import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import { EmbeddedNavigationBootstrap } from "./_components/EmbeddedNavigation";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"]
});

export const metadata: Metadata = {
  title: "Optimo VTS AI",
  description:
    "Optimo VTS AI onboarding page for virtual try-on and conversion optimization."
};

const shopifyApiKey =
  process.env.NEXT_PUBLIC_SHOPIFY_API_KEY?.trim() ||
  process.env.SHOPIFY_API_KEY?.trim() ||
  "";

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <meta name="shopify-api-key" content={shopifyApiKey} />
        {/* eslint-disable-next-line @next/next/no-sync-scripts */}
        <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js" data-api-key={shopifyApiKey} />
      </head>
      <body className={manrope.className}>
        <EmbeddedNavigationBootstrap />
        {children}
      </body>
    </html>
  );
}
