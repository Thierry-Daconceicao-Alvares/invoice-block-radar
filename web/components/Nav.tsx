"use client";

import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/queue", label: "Blocked queue" },
  { href: "/radar", label: "Order radar" },
  { href: "/evidence", label: "Evidence" },
];

export default function Nav() {
  const path = usePathname();
  return (
    <nav className="nav" aria-label="Pages">
      {LINKS.map((link) => (
        <a key={link.href} href={link.href} aria-current={path === link.href ? "page" : undefined}>
          {link.label}
        </a>
      ))}
    </nav>
  );
}
