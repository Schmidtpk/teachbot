# Assignment Questions — Predictions: Economics, Empirics and Evaluations 2026

43 questions · Submission deadline: June 4, 2026

---

## Question 1

**Question:** Will Curaçao score at least one goal against Germany in the World Cup?

**Resolution:** True if Curaçao's score in the FIFA World Cup group stage game against Germany on June 14th 2026 is at least 1. If the game is aborted or if it is moved to another day, the score is 0.

**Background:** The prediction should not consider a potential game between Germany and Curaçao after the group stage.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-|y-p|`

---

## Question 2

**Question:** By how many jobs will US Nonfarm Payroll Employment change during May 2026?

**Resolution:** The actual value for evaluation is the released value for the change in US Total Nonfarm Payroll Employment during May 2026, published in the US Bureau of Labor Statistics' Employment Situation Summary on Friday, June 5 2026, 14:30 Berlin time (8:30am ET).

**Background:** Timely forecasts of the change in Nonfarm Payroll Employment can be found at tradingeconomics.com, forexfactory.com, and estimize.com. For the unconditional mean, historical level data is at fred.stlouisfed.org/series/PAYEMS (note: that is the level, not the change).

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `(-1)*(y-p)^2`

---

## Question 3

**Question:** Will the ECB increase its deposit facility rate at the monetary policy meeting on June 11, 2026?

**Resolution:** The event is true if the European Central Bank increases the deposit facility rate in its official monetary policy decision published on June 11, 2026. The event is false if the deposit facility rate is kept unchanged or reduced.

**Background:** Relevant information includes inflation data, ECB statements, market expectations, and euro area macroeconomic conditions.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 4

**Question:** How many page views will the English Wikipedia page for Heidelberg receive in June 2026?

**Resolution:** The total number of page views during June 2026 of the English Wikipedia page "Heidelberg" (https://en.wikipedia.org/wiki/Heidelberg), according to the Wikipedia Pageviews Analysis tool (with the settings "All platforms" and "User" selected).

**Background:** Recent daily page view data shows that the English Heidelberg page generally receives around 700–900 daily views, with occasional spikes above 1,000 views.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `50000-|y-p|`

---

## Question 5

**Question:** What will Germany's June 2026 flash inflation rate (HICP) be?

**Resolution:** The flash estimate of the Harmonised Index of Consumer Prices (HICP) for June 2026, as published by Destatis in its official press release at the end of June 2026. The headline inflation rate in percentage, year on year. Published before July 15, 2026.

**Background:** The HICP is the standard EU measure of inflation. Destatis issues a flash estimate at the end of each month. Inflation is affected by energy prices, food prices, supply-chain conditions, and ECB monetary policy.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `-(p-y)^2`

---

## Question 6

**Question:** What will be the Nasdaq-100 closing value on 23 June 2026, as listed on Nasdaq's NDX historical data page?

**Resolution:** The close price is the final value of the index at the end of the trading day. Regular closing time of the Nasdaq-100 (NDX) is 4pm ET.

**Background:** Historical data about the Nasdaq 100 is available on Nasdaq.com (NDX - Historical Data).

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100000-|y-p|`

---

## Question 7

**Question:** What will the maximum temperature in Heidelberg be on June 12, 2026?

**Resolution:** The official daily maximum temperature (in °C) recorded at the Heidelberg weather station on June 12, 2026. Resolution source: https://www.wetterkontor.de/de/wetter/deutschland/rueckblick.asp?id=111, checked on June 13, 2026.

**Background:** There are three major numerical weather models — GFS (American), ECMWF (European), and ICON (German). Most smartphone weather apps rely on one of them. For predictions more than 5 days ahead, these models can diverge considerably.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 8

**Question:** How many goals will Germany score in the group-stage at the 2026 FIFA World Cup?

**Resolution:** The total number of goals officially credited to Germany in its three FIFA World Cup 2026 group-stage matches, excluding penalty shootouts. Own goals by opponents count if officially recorded as goals for Germany. If Germany does not play all three group-stage matches, only officially completed matches count.

**Background:** Germany will play Curaçao, Côte d'Ivoire, and Ecuador in the group stage. Germany beat Ecuador 3–0 in the 2006 World Cup and 4–2 in a 2013 friendly. Against Côte d'Ivoire, Germany drew 2–2 in a 2009 friendly. Germany and Curaçao have not played each other before.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 9

**Question:** How many UEFA (European) countries will advance to the Knock-Out Stage of the FIFA World Cup 2026?

**Resolution:** The number of UEFA countries that qualify for the Round of 32 (Knock-Out Stage) at the FIFA World Cup 2026. Resolution date: June 28, 2026.

**Background:** 16 UEFA countries participate in the group stage (out of 48 total participants), distributed across 12 groups of 4 teams each. A total of 32 teams will advance to the Knock-Out Stage.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-6.25*|y-p|`

---

## Question 10

**Question:** Will any student ask a question during the first 20 minutes of the lecture on June 17, 2026?

**Resolution:** True if at least one student verbally asks a question related to the course content. If the lecture is cancelled, the event is false.

**Background:** In previous sessions, questions occurred in about most of lectures. The first 20 minutes usually have fewer questions than later in the lecture.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 11

**Question:** Will Pete Hegseth be the United States Secretary of Defense on July 15, 2026?

**Resolution:** The event resolves as true if Pete Hegseth officially holds the office of United States Secretary of Defense at 23:59 EDT on July 15, 2026. Resolution will be determined using official announcements from the U.S. Department of Defense and/or the White House.

**Background:** War with Iran & high gas prices in the US.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 12

**Question:** Will the total number of goals scored in the UEFA Champions League final 2026 between Paris Saint-Germain and Arsenal be an odd number?

**Resolution:** The event is true if the sum of all goals scored by both teams during regular time and extra time in the Champions League final is an odd number (1, 3, 5, 7, …). Only goals officially recorded by UEFA in the final match report count. If the match is cancelled or forfeited, the total is zero (even → false).

**Background:** In the 2025 UEFA Champions League final, PSG vs Inter Milan, the sum of all goals was 5. PSG also plays in the 2026 final.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-|y-p|`

---

## Question 13

**Question:** What will the 7-day average price of electricity per MWh be on July 1, 2026, on the EPEX power exchange?

**Resolution:** The 7-day average price in EUR/MWh on July 1, 2026. Shown at: https://www.dashboard-konjunktur.de/konjunktur/Energie/1750061370434

**Background:** The trend, including historical data, can be viewed at the same URL.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 14

**Question:** Will Heidelberg University fall out of the global top 80 in the QS World University Rankings 2027?

**Resolution:** True if Heidelberg University is ranked lower than 80th place in the official QS World University Rankings 2027 release. Otherwise false.

**Background:** Heidelberg University has gradually declined from rankings around 50th place in the early 2010s and dropped into the 80s following recent QS methodology changes. The 2026 ranking showed a recovery to 80th place.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 15

**Question:** What will be the EUR/SGD exchange rate at market close on July 11, 2026?

**Resolution:** ECB Closing Rate, units of SGD per 1 Euro.

**Background:** The rate has historically traded roughly in the 1.40–1.55 range, with SGD being a relatively strong and low-volatility currency. EUR/SGD is sensitive to global growth expectations and US-China trade tensions.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `-(y-p)^2`

---

## Question 16

**Question:** What will be the temperature in Heidelberg at 12:00 on June 20, 2026?

**Resolution:** The air temperature in degrees Celsius measured in Heidelberg, Germany, at 12:00 local time on June 20, 2026, according to the official Deutscher Wetterdienst (DWD) weather report.

**Background:** Average daytime temperatures in Heidelberg in June are typically between 20°C and 28°C, but weather conditions can vary substantially due to rain and heat waves.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 17

**Question:** Will Crude Oil Jun 26 (CL=F) fall below $100 at time it closes?

**Resolution:** True if price < $100, false otherwise, on June 26 as the future expires. No rollover.

**Background:** The future price has been wobbling around $100 since Trump initiated military operation in Iran. As Trump truces, price has temporarily fallen but rose again after small-scale conflicts.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 18

**Question:** What will the May 2026 headline CPI YoY print be?

**Resolution:** The official year-over-year percentage change in the U.S. headline Consumer Price Index (CPI) for May 2026, as published by the Bureau of Labor Statistics (BLS) on June 10, 2026, at 8:30 AM ET.

**Background:** April 2026 CPI showed re-acceleration, driven by grocery prices and energy passthrough. WTI crude oil is trading near $100–110/bbl. Core CPI has been accelerating (recent MoM +0.376%), and 5Y breakeven inflation rose sharply to 2.69%. Strong base effects and persistent energy/food pressures suggest limited cooling in May.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-100*|y-p|`

---

## Question 19

**Question:** Will Italy defeat Brazil in the women's Volleyball Nations League match on 7 June 2026?

**Resolution:** y=1 if the official Volleyball World result for the Brazil vs Italy Women's VNL 2026 match (Pool 2 — Week 1 — Women #33) shows Italy as the winner. y=0 if Brazil wins. If cancelled/no result by July 15, 2026, then y=0.

**Background:** Italy is the defending champion and ranked #1 in the world on the FIVB ranking, on a 36-match winning streak. Brazil is ranked #2 and will be hosting the match.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 20

**Question:** Will Real Madrid CF appoint José Mourinho as head coach before July 15, 2026?

**Resolution:** The event resolves as true if Real Madrid officially announces José Mourinho as head coach on its official website or official social media channels before July 15, 2026.

**Background:** José Mourinho previously managed Real Madrid from 2010 to 2013. Real Madrid is signing a new manager after a season without trophies.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 21

**Question:** How many Flammkuchen will be on the fresh bakery shelf at Rewe Fahrtgasse 18 on June 13, 2026, at 8:00 PM?

**Resolution:** Location: Rewe supermarket at Fahrtgasse 18, 69117 Heidelberg. Time: June 13, 2026 (Saturday), 20:00. Target: Fresh bakery section, baked Flammkuchen (not frozen or ready-to-bake). Count: Total number of complete pieces available for purchase, excluding damaged items. If completely sold out, the count is 0. Verified in person with a photo as evidence.

**Background:** This product is very popular and tends to sell out quickly. Evening stock rarely exceeds 3 pieces and stockouts are common. June 13 is a Saturday (busiest shopping day in Germany). By 8:00 PM, after a full day of traffic, the bakery section is typically depleted. Restocking at this hour is highly unlikely.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 22

**Question:** How many articles will the English Wikipedia contain on July 10, 2026?

**Resolution:** The total number of articles in the English Wikipedia as recorded in the Internet Archive of https://en.wikipedia.org/wiki/Special:Statistics at 12:00 CEST on July 10, 2026.

**Background:** As of May 13, 2026, English Wikipedia contains almost exactly 7,182,000 articles. According to Wikipedia, the encyclopedia grows at approximately 15,000 new articles per month (as of July 2024).

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `10000-|y-p|`

---

## Question 23

**Question:** How many days will the Lufthansa crew strike between June 5th and July 15th?

**Resolution:** The number of days that the Lufthansa crew (either cabin or cockpit crew) will strike between June 5th and July 15th. Only strikes at Lufthansa and Lufthansa Cargo count — not other Lufthansa Group airlines or Lufthansa CityAirlines.

**Background:** As of May 13, after several strikes in recent months, the crew unions have not announced any new strikes.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 24

**Question:** Will NVIDIA remain the company with the highest market capitalization among the Magnificent Seven on July 1, 2026?

**Resolution:** True if NVIDIA has the highest market capitalization among Apple, Microsoft, NVIDIA, Amazon, Meta, Alphabet, and Tesla at the close of U.S. stock markets on July 1, 2026. Values taken from Yahoo Finance or CompaniesMarketCap.

**Background:** NVIDIA recently became the world's most valuable company due to strong investor expectations surrounding AI and semiconductor demand. Competition from Microsoft and Apple could challenge this position.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 25

**Question:** Will the European Central Bank reduce its deposit facility rate at least once at the June 2026 Governing Council monetary policy meeting?

**Resolution:** True (y=1) if the ECB officially announces a reduction of the deposit facility rate at the Governing Council meeting scheduled for June 10–11, 2026. False (y=0) if the rate is unchanged, increased, or no official rate decision is announced.

**Background:** Eurozone inflation has recently declined, while economic growth remains weak. Financial markets currently expect possible monetary easing during 2026.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 26

**Question:** Will turnout for the Maine 2nd Congressional District Republican primary on July 9th exceed 80,000?

**Resolution:** True if at least 80,001 primary voters cast a ballot across all candidates. False if turnout is 80,000 or below.

**Background:** In previous midterm election cycles, mean turnout was 89,886 and median turnout was 83,382. There are Senate races in Maine in 2026, which may inflate turnout numbers.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 27

**Question:** Will the ECB reference exchange rate for EUR 1 in USD be above 1.20 on 10 June 2026?

**Resolution:** True if the daily ECB euro foreign exchange reference rate for EUR/USD, as published for June 10, 2026, is strictly greater than 1.2000. Retrieved from the ECB's official page at 14:00 UTC on June 11, 2026. If June 10 is a bank holiday, the next available daily rate is used.

**Background:** In recent months, the euro has traded mainly between 1.15 and 1.19. As of mid-May 2026, it sits near the upper end of this band at around 1.17. The key question is whether it can break above 1.20.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 28

**Question:** Will the Boston Red Sox win 10 or more games from June 4 through the end of June?

**Resolution:** True if the Boston Red Sox win at least 10 games from June 4 through the end of June.

**Background:** 17 scheduled games for this period, 9 home games. Winning percentage as of May 14, 2026 is .415 (17–24).

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 29

**Question:** Will Jannik Sinner win the Wimbledon 2026 men's single title?

**Resolution:** True if Jannik Sinner is officially recorded as the winner of the Wimbledon 2026 men's singles championship (final on July 12). False otherwise.

**Background:** Together with Carlos Alcaraz, Sinner is among the top favorites. Sinner is the defending Wimbledon champion (won 2025 against Alcaraz), but Alcaraz won the last 10 out of 17 games against Sinner. Alcaraz currently has a hand injury. Betting odds and ATP rankings may also help.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 30

**Question:** Will the word "sustainable" appear in the ECB "Monetary policy statement (with Q&A)" for the June 2026 monetary policy meeting?

**Resolution:** True if the exact word "sustainable" appears at least once in the official English-language ECB document "Monetary policy statement (with Q&A)" published for the June 2026 meeting (June 10–11, 2026). The entire published text counts, including headings, prepared statements, and Q&A.

**Background:** The word "sustainable" appeared twice in the December 2025 statement, once in the February 2026 statement, zero times in the March 2026 statement, and twice in the April 2026 statement.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 31

**Question:** Will the average Google Trends search interest for "Claude" in Germany reach at least 31.25% of the average Google Trends search interest for "ChatGPT" between June 5 and June 30, 2026?

**Resolution:** True if, for Germany, the average Google Trends value C for "Claude" satisfies C/G ≥ 0.3125, where G is the average for "ChatGPT", over the period June 5–30, 2026. Settings: Germany, web search, all categories.

**Background:** Recent ratios: 05.04–05.05.2026: 20/67 = 0.2985; 05.03–05.04.2026: 20/70 = 0.2597; 05.02–05.03.2026: 12/79 = 0.1518.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 32

**Question:** Will the Canadian government decide on who will win the contract for replacing their submarine fleet before July 15th?

**Resolution:** True if the Canadian government accepts the existing bid from ThyssenKrupp Marine Systems or Hanwha Ocean for replacing the Victoria class submarine by July 15th.

**Background:** The Canadian government is looking to purchase 12 new submarines. Only ThyssenKrupp Marine Systems and Hanwha Ocean have bids currently being considered. Both bids were finalized at the end of April and are currently under review.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 33

**Question:** According to ICE Futures Europe: Will the official settlement price of Brent crude oil futures for August 2026 exceed 95 USD per barrel on June 8, 2026?

**Resolution:** True if the daily official ICE settlement price of the August 2026 Brent crude oil futures contract is strictly greater than 95.00 USD per barrel on June 8, 2026 UTC. Report available at June 9, 2026 on https://www.ice.com/report/10 (Select Contract B-Brent Crude Future).

**Background:** Brent crude oil is a key global benchmark strongly influenced by geopolitical developments. The settlement price is the official end-of-day price determined by the Intercontinental Exchange (ICE).

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 34

**Question:** How many goals will the German National Team score in the World Cup until the resolution date?

**Resolution:** The number of regular goals scored by the German national team from June 14 through the potential first semifinal on July 14. Opponents' own goals are included; German own goals are not. A potential final, third-place match, or second semifinal is not included.

**Background:** Germany will play a minimum of three and up to seven matches in this timeframe. The three confirmed fixtures are against Curaçao, Côte d'Ivoire, and Ecuador.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|`

---

## Question 35

**Question:** Will Germany reach the 2026 FIFA World Cup quarterfinals?

**Resolution:** Resolves as 1 if Germany reaches the quarterfinals of the 2026 FIFA World Cup before July 15, 2026, and 0 otherwise. Official FIFA records will be used.

**Background:** Germany is historically a strong national team, but recent tournament performances have been mixed.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 36

**Question:** How many goals will be scored in the 2026 World Cup match of the Democratic Republic of the Congo versus Uzbekistan?

**Resolution:** The number of goals scored during the World Cup match between Uzbekistan and the Democratic Republic of the Congo on June 28th at 1:30 AM CET.

**Background:** Uzbekistan has averaged 2 goals/game and conceded 0.6 goals/game in their last 8 matches. DRC has averaged 1.2 goals/game and conceded 0.4 goals/game.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `10-|y-p|`

---

## Question 37

**Question:** How many sockeye salmon will be caught commercially in Bristol Bay, Alaska, from June 8 to July 10, 2026?

**Resolution:** The cumulative number of sockeye salmon caught commercially in Bristol Bay, Alaska, from June 8–July 10, 2026, as reported by the Alaska Department of Fish and Game (ADF&G). Note: y and p are measured in millions of salmon (e.g., p=1 means a prediction of 1,000,000 salmon).

**Background:** Bristol Bay produces 57% of global sockeye salmon supply, valued at over $2.2 billion annually. Dependence on 9 major river systems and rising ocean temperatures creates significant variability in salmon harvest.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-(|p-y|)^2`

---

## Question 38

**Question:** Will at least one direct train from Frankfurt(Main) Hbf to Heidelberg Hbf on June 15, 2026 arrive more than 10 minutes late?

**Resolution:** True if at least one train from Frankfurt(Main) Hbf to Heidelberg Hbf arrives at least 10 minutes late on June 15, 2026. Cancelled trains count as arriving more than 10 minutes late. Connecting journeys are excluded.

**Background:** There are approximately 20 direct trains from Frankfurt(Main) Hbf to Heidelberg Hbf on a typical day. The probability of at least one delay is higher than the probability of a single specific train being delayed.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 39

**Question:** How many total vehicular traffic fatalities will occur in the city of Austin, Texas on June 13th?

**Resolution:** The number of reports of traffic fatalities (involving pedestrians, bicyclists, motorists, motorcyclists, and e-scooter riders) within the city limits of Austin, Texas on June 13th. Data: https://data.austintexas.gov/Transportation-and-Mobility/Austin-Crash-Report-Data-Crash-Victim-Demographic-/xecs-rpy9/about_data

**Background:** See the Austin crash report data linked above for historical base rates.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `1000-|y-p|`

---

## Question 40

**Question:** Will at least one named tropical cyclone form in the Atlantic Ocean before July 15, 2026?

**Resolution:** True if at least one tropical or subtropical cyclone in the Atlantic basin receives an official name at any time before July 15, 2026 (00:00 UTC on July 15), according to the National Hurricane Center (NHC) Atlantic storm database.

**Background:** The Atlantic hurricane season officially starts on June 1 each year. The timing of the first named storm varies considerably. Atmospheric conditions, sea surface temperatures, and wind shear all influence whether a cyclone develops early in the season.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 41

**Question:** What is the Real GDP growth rate (Provisional Estimate) of India for FY 25-26, accurate to 1 decimal place?

**Resolution:** Based on the figure published by the Government of India Ministry of Statistics and Programme Implementation (https://www.mospi.gov.in/). Under: What's new > Press Releases. Figures are scheduled to be published on June 7th.

**Background:** For any financial year, the Government of India publishes: "1st Advance Estimate" in Jan, "2nd Advance Estimate" in Feb, "Provisional Estimate" in June, and "Revised Estimates" in January of the following year. Past figures and advance estimates can be found on the same website.

**Target type:** real-valued | **Prediction type:** point prediction (for real) | **Score:** `100-|y-p|*20`

---

## Question 42

**Question:** Will the European Central Bank lower its deposit facility rate at its monetary policy meeting on June 11, 2026?

**Resolution:** True if the ECB announces on June 11, 2026 that it lowers the deposit facility rate compared with the rate in effect immediately before that meeting. False if the rate is left unchanged, increased, or no cut is announced.

**Background:** The deposit facility rate is one of the ECB's key policy rates — the rate banks receive when depositing funds overnight with the ECB.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`

---

## Question 43

**Question:** Will the total "User" agent pageviews for the English Wikipedia article "2026_FIFA_World_Cup" be strictly greater than 42,500,000 during June 11 – July 12, 2026?

**Resolution:** Resolution via Wikimedia Pageviews Analysis API (pageviews.wmcloud.org) for article "2026_FIFA_World_Cup" on en.wikipedia.org. Date range: June 1 to July 12, 2026, inclusive. Agent: "User" only. Platform: "All Access". Resolves Yes if sum ≥ 42,500,001; No if sum ≤ 42,500,000. Data retrieved July 14, 2026 at 12:00 UTC.

**Background:** The 2022 FIFA World Cup generated about 33.89 million Wikipedia pageviews during the core period (Nov 20 – Dec 18) across 64 games. The 2026 tournament expands to 104 matches, projecting roughly 55 million views. The forecasting window (June 11 – July 12) captures 82% of the 39-day core period, yielding an expected ~45 million views.

**Target type:** event | **Prediction type:** probability (for event) | **Score:** `1-(y-p)^2`
