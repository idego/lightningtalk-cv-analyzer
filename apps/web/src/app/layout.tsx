import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Bricolage_Grotesque, JetBrains_Mono } from "next/font/google";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeBootstrap } from "@/components/theme/theme-bootstrap";
import "./globals.css";

const fontSans = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-theme-sans",
  display: "swap",
});

const fontMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-theme-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CV Analyzer",
  description: "Idego CV location consistency analyzer admin panel",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const cookieStore = await cookies();
  const themeCookie = cookieStore.get("theme")?.value;
  const dark = themeCookie === "dark";

  return (
    <html
      lang="en"
      className={`${fontSans.variable} ${fontMono.variable} h-full antialiased ${dark ? "dark" : ""}`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col">
        <ThemeBootstrap />
        <TooltipProvider>{children}</TooltipProvider>
      </body>
    </html>
  );
}
