"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
export default function BottomNav() {
  const path = usePathname();
  return <nav className="bottom-nav" aria-label="Main navigation">{[["/home", "Home"], ["/discover", "Discover"], ["/search", "Search"], ["/favorites", "Saved"], ["/my-taste", "My Taste"]].map(([href, label]) => <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>{label}</Link>)}</nav>;
}
