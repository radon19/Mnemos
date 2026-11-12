"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { ThemeToggle } from "./ThemeToggle";
import { useSession } from "@/lib/session";
import { truncateAccount } from "@/lib/format";

const NAV: { href: string; label: string }[] = [
  { href: "/setup", label: "Setup" },
  { href: "/vault", label: "Vault" },
  { href: "/grants", label: "Grants" },
  { href: "/activity", label: "Activity" },
  { href: "/earnings", label: "Earnings" },
  { href: "/redteam", label: "Red-team" },
];

function NavLinks({ onNavigate }: { onNavigate?: () => void }): React.ReactNode {
  const pathname = usePathname();
  return (
    <ul className="flex flex-wrap items-center gap-1">
      {NAV.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              {...(onNavigate === undefined ? {} : { onClick: onNavigate })}
              aria-current={active ? "page" : undefined}
              className={`inline-flex min-h-11 items-center rounded-full px-3.5 py-1.5 text-caption transition-colors md:min-h-9 ${
                active
                  ? "bg-sunken text-ink"
                  : "text-muted hover:bg-sunken hover:text-ink"
              }`}
            >
              {item.label}
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
      <div className="flex items-center gap-3">
        <span className="hidden max-w-[10rem] items-center sm:flex">
          <span className="sr-only">{account}</span>
          <span aria-hidden="true" className="hash truncate text-caption text-muted">
            {truncateAccount(account, 8, 5)}
          </span>
        </span>
        {demo ? (
          <span className="hidden rounded-full bg-accent-soft px-2.5 py-1 text-micro text-accent-ink md:inline">
            Demo signer
          </span>
        ) : null}
        <button
          type="button"
          className="rounded-full border border-rule px-3 py-1.5 text-caption text-muted transition-colors hover:border-ink hover:text-ink"
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
    <button
      type="button"
      className="min-h-11 rounded-full border border-rule px-4 py-2 text-caption text-ink transition-colors hover:border-ink"
      onClick={() => {
        void signIn();
      }}
    >
      Connect wallet
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }): React.ReactNode {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-ink focus:px-4 focus:py-2 focus:text-canvas"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 px-3 pt-3 sm:px-5 sm:pt-4">
        <div className="mx-auto flex max-w-[1180px] items-center gap-3 rounded-full border border-rule bg-surface px-3 py-2 shadow-[var(--shadow-card)] sm:px-4">
          <Link href="/" className="flex min-h-11 items-center gap-2.5 pr-1">
            <span className="mark" aria-hidden="true" />
            <span className="font-display text-[1.0625rem] font-semibold tracking-tight">
              Mnemos
            </span>
          </Link>

          <nav aria-label="Sections" className="hidden md:block">
            <NavLinks />
          </nav>

          <div className="ml-auto flex items-center gap-2">
            <div className="hidden lg:block">
              <OwnerBlock />
            </div>
            <ThemeToggle />
            <Link
              href="/setup"
              className="hidden min-h-11 rounded-full bg-ink px-4 py-2 text-caption text-canvas transition-opacity hover:opacity-90 lg:inline-flex"
            >
              Open the ledger
            </Link>
            <button
              type="button"
              aria-expanded={menuOpen}
              aria-controls="mobile-nav"
              className="min-h-11 rounded-full border border-rule px-3 py-1.5 text-caption text-ink lg:hidden"
              onClick={() => {
                setMenuOpen(!menuOpen);
              }}
            >
              Menu
            </button>
          </div>
        </div>

        {/* The panel stays mounted when it is closed: unmounting it would
            remove the link from the document during the click and cancel the
            navigation. */}
        <div
          id="mobile-nav"
          hidden={!menuOpen}
          className="mx-auto mt-2 max-w-[1180px] rounded-[var(--radius-card)] border border-rule bg-surface p-4 shadow-[var(--shadow-card)] lg:hidden"
        >
          <nav aria-label="Sections">
            <NavLinks
              onNavigate={() => {
                setMenuOpen(false);
              }}
            />
          </nav>
          <div className="mt-4 border-t border-rule pt-4">
            <OwnerBlock />
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </main>

      <footer className="mx-auto w-full max-w-[1180px] px-4 pb-10 sm:px-6">
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-6 text-caption text-muted">
          <p>
            Mnemos — user-owned AI memory with metered, revocable access on NEAR.
          </p>
          <p className="numeric">MIT licensed · built during the hackathon window</p>
        </div>
      </footer>
    </div>
  );
}
