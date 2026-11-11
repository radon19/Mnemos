"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "./ThemeToggle";
import { useSession } from "@/lib/session";
import { truncateAccount } from "@/lib/format";

const NAV: { href: string; label: string; note: string }[] = [
  { href: "/setup", label: "Setup", note: "wallet, contract, unlock" },
  { href: "/vault", label: "Vault", note: "encrypted notes by scope" },
  { href: "/grants", label: "Grants", note: "who may read, and for how long" },
  { href: "/activity", label: "Activity", note: "receipts for every read" },
  { href: "/earnings", label: "Earnings", note: "balance and withdrawals" },
  { href: "/redteam", label: "Red-team", note: "attempted memory extraction" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }): React.ReactNode {
  const pathname = usePathname();
  return (
    <ul>
      {NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              {...(onNavigate === undefined ? {} : { onClick: onNavigate })}
              aria-current={active ? "page" : undefined}
              className={`block border-l-2 py-2 pl-3 pr-2 transition-colors ${
                active
                  ? "border-ink text-ink"
                  : "border-transparent text-muted hover:border-rule hover:text-ink"
              }`}
            >
              <span className="field-label block">{item.label}</span>
              <span className="mt-0.5 hidden text-caption text-muted lg:block">{item.note}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function OwnerBlock(): React.ReactNode {
  const { status, account, demo, signIn, signOut } = useSession();
  if (status === "signed-in" && account !== null) {
    return (
      <div className="space-y-2">
        <p className="field-label">Owner</p>
        <p className="hash truncate text-caption text-ink" title={account}>
          {truncateAccount(account, 10, 6)}
        </p>
        {demo ? (
          <p className="field-label text-destructive">Local demo signer</p>
        ) : null}
        <button
          type="button"
          className="field-label underline decoration-rule underline-offset-4 hover:text-ink"
          onClick={() => {
            void signOut();
          }}
        >
          Sign out
        </button>
      </div>
    );
  }
  return (
    <div className="space-y-2">
      <p className="field-label">Owner</p>
      <p className="text-caption text-muted">Not signed in</p>
      <button
        type="button"
        className="field-label underline decoration-rule underline-offset-4 hover:text-ink"
        onClick={() => {
          void signIn();
        }}
      >
        Connect wallet
      </button>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }): React.ReactNode {
  const [menuOpen, setMenuOpen] = useState(false);
  const { account } = useSession();

  return (
    <div className="min-h-dvh bg-paper text-ink">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:border focus:border-ink focus:bg-paper focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <div className="flex">
        <aside className="sticky top-0 hidden h-dvh w-[208px] shrink-0 flex-col justify-between border-r border-rule px-4 py-6 md:flex">
          <div>
            <Link href="/" className="block">
              <span className="font-display text-[1.375rem] leading-none tracking-tight">
                Mnemos
              </span>
              <span className="field-label mt-1 block">Ledger of reads</span>
            </Link>
            <nav aria-label="Sections" className="mt-8">
              <NavLinks />
            </nav>
          </div>
          <div className="space-y-4">
            <ThemeToggle />
            <OwnerBlock />
          </div>
        </aside>

        <div className="min-w-0 flex-1">
          <header className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3 md:hidden">
            <Link href="/" className="font-display text-[1.25rem] leading-none">
              Mnemos
            </Link>
            <div className="flex items-center gap-3">
              <span className="hash text-caption text-muted">
                {account === null ? "signed out" : truncateAccount(account, 6, 4)}
              </span>
              <ThemeToggle />
              <button
                type="button"
                aria-expanded={menuOpen}
                aria-controls="mobile-nav"
                className="field-label border border-rule px-2 py-1"
                onClick={() => {
                  setMenuOpen(!menuOpen);
                }}
              >
                Menu
              </button>
            </div>
          </header>
          {menuOpen ? (
            <nav
              id="mobile-nav"
              aria-label="Sections"
              className="border-b border-rule bg-paper px-4 py-3 md:hidden"
            >
              <NavLinks
                onNavigate={() => {
                  setMenuOpen(false);
                }}
              />
              <div className="mt-4">
                <OwnerBlock />
              </div>
            </nav>
          ) : null}
          <main id="main" className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-8 sm:py-12">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
