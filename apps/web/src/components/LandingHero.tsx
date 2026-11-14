import Link from "next/link";
import { StatCards, type StatCard } from "./StatCards";
import { StatusMark } from "./StatusMark";
import { BrandMark } from "./BrandMark";
import { nearNetwork } from "@/lib/config";

/** The reference's raised white sheet, globe and figure row, in Mnemos' world. */
export function LandingHero({ cards, ready, failed }: {
  cards: StatCard[];
  ready: boolean;
  failed: boolean;
}): React.ReactNode {
  return (
    <section className="landing-stage" aria-labelledby="landing-title">
      <div className="landing-orbit landing-orbit-one" aria-hidden="true" />
      <div className="landing-orbit landing-orbit-two" aria-hidden="true" />
      <div className="landing-seal" aria-hidden="true"><BrandMark /></div>
      <div className="landing-sheet">
        <div className="landing-globe" aria-hidden="true" />
        <div className="landing-copy">
          <span className="landing-network">
            <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="7.25" /><ellipse cx="10" cy="10" rx="3.25" ry="7.25" /><path d="M3 10h14M4.5 5.5h11M4.5 14.5h11" /></svg>
            Built on NEAR <span className="landing-network-dot" /> {nearNetwork}
          </span>
          <h1 id="landing-title" className="landing-title">
            <span>Your expertise.</span><br />Their AI. Your terms.
          </h1>
          <p className="landing-description">
            Let AI agents pay for answers from your private knowledge. Choose what
            they can access, set a price, and close access whenever you want.
          </p>
          <div className="landing-actions">
            <Link href="/exchange" className="landing-primary">
              Try the live demo
              <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 10h12m-5-5 5 5-5 5" /></svg>
            </Link>
            <Link href="/docs" className="landing-secondary">See how it works</Link>
          </div>
        </div>
        <div className="landing-stat-row" aria-label="Live deployment figures">
          <StatCards cards={cards} />
        </div>
        <div className="landing-proof">
          <StatusMark kind={ready ? "verified" : "pending"}
            label={ready ? "Live figures from NEAR" : failed ? "Live figures unavailable" : "Reading the deployment"} />
          <span>Testnet activity · encrypted notes · hash-only receipts</span>
        </div>
      </div>
    </section>
  );
}
