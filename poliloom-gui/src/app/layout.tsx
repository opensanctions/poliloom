import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { SessionProvider } from "@/components/SessionProvider";
import { ArchivedPageProvider } from "@/contexts/ArchivedPageContext";
import { PreferencesProvider } from "@/contexts/PreferencesContext";
import { PoliticiansQueueProvider } from "@/contexts/PoliticiansQueueContext";
import { FetchInterceptor } from "@/components/FetchInterceptor";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PoliLoom - Data Confirmation",
  description: "Confirm politician data extracted from Wikipedia",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased grid grid-rows-[auto_1fr] h-screen`}
      >
        <SessionProvider>
          <FetchInterceptor />
          <PreferencesProvider>
            <PoliticiansQueueProvider>
              <ArchivedPageProvider>
                {children}
              </ArchivedPageProvider>
            </PoliticiansQueueProvider>
          </PreferencesProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
