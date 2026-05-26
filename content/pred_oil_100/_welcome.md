**Superforecasting challenge — WTI crude oil close on June 26, 2026**

Below is a structured reasoning trace and an opening probability estimate for the question:

> **Will the front-month WTI crude oil futures contract (`CL=F`) close below \$100.00 per barrel on June 26, 2026?**

---

## Reasoning Trace

**Step 1 — Anchor on the current price**

As of May 26, 2026, CL=F trades around **\$92–96 / bbl**, with WTI briefly printing below \$90 last week on US–Iran deal optimism. The question therefore asks whether a price already \$4–8 *below* the threshold will *stay* below it through one more month of trading.

**Step 2 — Volatility-based sanity check**

The WTI 1-month at-the-money implied volatility is roughly **86 % annualised**. The implied 1-month σ on a current price near \$93 is

$$
\sigma_{1M} \approx 93 \cdot \frac{0.86}{\sqrt{12}} \approx 23 \text{ dollars}.
$$

The \$100 threshold sits about **+0.3 σ** above current. Under a no-drift lognormal model, the probability of finishing below \$100 at horizon is therefore on the order of

$$
P(S_T < 100) \approx \Phi(0.3) \approx 0.62.
$$

This is the pure option-market-implied baseline before any directional view.

**Step 3 — Drift / fundamental view**

*Pushing probability of YES (close < \$100) up:*

- Current spot is already comfortably below the threshold.
- The futures curve is in mild contango — the August contract (CLQ26, which will be the front-month on June 26) trades a hair below the July contract, implying market expectation of continued softening.
- US–Iran negotiations are visibly progressing; a deal announcement before June 26 would likely cut another \$10–20 off the price.
- OPEC+ has been *unwinding* cuts in 2026; the June 7 meeting may continue that path.
- 10–11 mb/d of shut-in production sits ready to return — overhang risk is asymmetric to the downside.

*Pushing probability of YES down:*

- EIA's May 2026 STEO still pencils Brent at **\$109.73** for Q2 (≈ \$104–105 WTI), well above the threshold. EIA is using a "Hormuz stays mostly shut" assumption that the market has begun pricing against.
- A **collapse** of US–Iran talks — or fresh escalation in the Gulf — could spike prices \$10–20 in a single session. Tail risk is meaningful.
- Implied vol of 86 % means the \$8 cushion is *thin* relative to one-month uncertainty.
- The June 7 OPEC+ meeting could surprise with a fresh cut.

**Step 4 — Reconcile the volatility-implied baseline with the directional view**

The options-implied baseline (~0.62) already prices in much of the high-vol regime. The directional case is mildly **bullish for YES** — the macro narrative, news flow and futures curve all lean toward continued softening — but the geopolitical asymmetry caps how far above the volatility baseline we should go.

Net adjustment: **+0.06** for clear downside trend and shut-in overhang, **−0.03** for unresolved Hormuz tail risk and EIA's institutional view. Combined drift adjustment: **+0.03**.

**Step 5 — Synthesis**

- Volatility-implied baseline: ~0.62
- Net directional adjustment: +0.03
- Headline-risk haircut for the 26-day window containing OPEC+ meeting and a possible diplomatic announcement: −0.01

---

## Initial Probability Estimate

$$\hat{p} = 0.64$$

*64% probability that WTI front-month (`CL=F`) settles below \$100.00 per barrel on June 26, 2026.*

This is above coin-flip because the spot is already below the threshold and the directional pressure is bearish, but well short of certainty because (a) one-month volatility is extremely high, (b) the Hormuz situation could re-escalate, and (c) institutional forecasters with full models still expect prices to be *above* \$100 over this window.

---

## Your Turn

This estimate is a starting point, not a verdict. Can you find information, analogues, or arguments that should push this probability up or down? Share your reasoning and I will evaluate it and update the forecast if warranted.
