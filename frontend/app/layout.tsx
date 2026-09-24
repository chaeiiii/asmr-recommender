import type { Metadata } from "next";
import "./globals.css";
import SessionGate from "../components/SessionGate";

export const metadata: Metadata = {
  title: "ASMR Recommender",
  description: "Find ASMR based on what you enjoy listening to.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><SessionGate>{children}</SessionGate></body>
    </html>
  );
}
