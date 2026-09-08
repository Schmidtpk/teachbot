# Introduction to Discrete Choice Modelling — Lecture Notes

These notes cover the core ideas of an introductory class on discrete choice modelling: what a discrete choice is, the random utility framework, binary logit and probit, the multinomial and conditional logit, the IIA property, estimation by maximum likelihood, interpretation of results, and a brief look at extensions (nested logit, mixed logit, probit). The standard textbook reference is Train (2009), *Discrete Choice Methods with Simulation* (freely available online).

---

## 1. What is a discrete choice?

Many economic decisions are not "how much" but "which one":

- Which **mode of transport** to take to work (car, bus, train, bike).
- Whether to **participate in the labour force** (yes / no).
- Which **brand** of a product to buy.
- Which **university** or **degree programme** to enrol in.
- Whether a firm **enters** a market.

The dependent variable is **categorical**: it takes one of a finite set of mutually exclusive, collectively exhaustive alternatives. The alternatives usually have no natural numerical ordering (car = 1, bus = 2 is just a label). Discrete choice models describe the **probability** that a decision maker chooses each alternative as a function of observed characteristics of the alternatives and of the decision maker.

Key vocabulary:

- **Decision maker** $n = 1, \dots, N$ (person, household, firm).
- **Choice set** $J$: the set of alternatives available to the decision maker; alternatives $j = 1, \dots, J$.
- **Attributes of alternatives** $x_{nj}$ (e.g. travel time and cost of each mode) — these vary across alternatives.
- **Characteristics of the decision maker** $s_n$ (e.g. income, age) — these do not vary across alternatives.
- **Revealed preference (RP) data**: actual choices observed in the market. **Stated preference (SP) data**: hypothetical choices from a survey or choice experiment.

## 2. Why not ordinary least squares?

For a binary outcome $y_n \in \{0, 1\}$ one could run the **linear probability model** (LPM)
$$ y_n = x_n' \beta + u_n, \qquad E[y_n \mid x_n] = P(y_n = 1 \mid x_n) = x_n' \beta. $$

It is easy to estimate and the coefficients are directly marginal effects on the probability, but it has well-known problems:

1. **Predictions outside $[0,1]$**: $x_n'\beta$ is unbounded, so fitted probabilities can be negative or above one.
2. **Constant marginal effects**: a one-unit change in $x$ always shifts the probability by $\beta$, even when the probability is already close to 0 or 1.
3. **Heteroskedasticity**: $\text{Var}(u_n \mid x_n) = x_n'\beta (1 - x_n'\beta)$ depends on $x_n$ by construction.

The LPM remains a useful first approximation (and is fine for average marginal effects in many applications), but discrete choice models address all three issues by modelling the probability through a **nonlinear link** derived from utility maximisation.

## 3. The random utility model (RUM)

Discrete choice models are built on the assumption that decision makers **choose the alternative with the highest utility**. Utility is not fully observed by the analyst, so it is split into an observed and an unobserved part:

$$ U_{nj} = V_{nj} + \varepsilon_{nj}, \qquad j = 1, \dots, J. $$

- $V_{nj}$ is the **representative (systematic) utility**, a function of observed attributes and characteristics, typically linear: $V_{nj} = x_{nj}'\beta$.
- $\varepsilon_{nj}$ is the **random component**: everything that affects utility but is not observed by the analyst (unobserved attributes, taste variation, measurement error). It is random *from the analyst's point of view*; the decision maker knows their own utility.

Decision maker $n$ chooses alternative $i$ if $U_{ni} > U_{nj}$ for all $j \neq i$. Hence the **choice probability** is

$$ P_{ni} = P(U_{ni} > U_{nj} \ \forall j \neq i) = P(\varepsilon_{nj} - \varepsilon_{ni} < V_{ni} - V_{nj} \ \forall j \neq i). $$

Different assumptions about the distribution of $\varepsilon$ give different models (logit, probit, nested logit, ...).

### 3.1 Only differences in utility matter

Because the choice depends on which utility is *largest*, adding a constant to all utilities changes nothing. Consequences:

- **Alternative-specific constants (ASCs)**: with $J$ alternatives, only $J - 1$ constants are identified; one is normalised to zero (the *base* or *reference alternative*).
- **Characteristics of the decision maker** (income, age, ...) do not vary across alternatives, so they can only enter through **alternative-specific coefficients**: e.g. "income × (alternative = car)". Again, the coefficient for one alternative must be normalised to zero.
- **Attributes of alternatives** (cost, time) do vary across alternatives and can enter with a **generic coefficient** (the same $\beta$ for all alternatives) or with alternative-specific coefficients.

### 3.2 The scale of utility is arbitrary

Multiplying all utilities by a positive constant also leaves the choice unchanged. Therefore the variance of $\varepsilon$ must be **normalised** (e.g. to $\pi^2/6$ per alternative in logit, or to 1 in probit). Estimated coefficients are therefore always "coefficient divided by the scale of the error", which matters when comparing coefficients across models or data sets. **Ratios of coefficients** (see Section 7) are unaffected by the scale.

## 4. Binary choice: logit and probit

With two alternatives ($y_n = 1$ if alternative 1 is chosen), write the utility difference as a **latent variable**
$$ y_n^* = U_{n1} - U_{n0} = x_n'\beta + \varepsilon_n, \qquad y_n = \mathbf{1}\{ y_n^* > 0 \}. $$
Then
$$ P(y_n = 1 \mid x_n) = P(\varepsilon_n > -x_n'\beta) = F(x_n'\beta), $$
where $F$ is the CDF of $-\varepsilon_n$ (for symmetric distributions, of $\varepsilon_n$).

- **Logit**: $\varepsilon$ logistic, $F(z) = \Lambda(z) = \dfrac{e^{z}}{1 + e^{z}} = \dfrac{1}{1 + e^{-z}}$.
- **Probit**: $\varepsilon$ standard normal, $F(z) = \Phi(z)$.

Both are S-shaped ("sigmoid") functions mapping the real line into $(0, 1)$. The logistic distribution has slightly fatter tails; in practice the two models give very similar fitted probabilities. A rule of thumb: logit coefficients are roughly $1.6$–$1.7$ times the probit coefficients (because the error variances differ: $\pi^2/3$ vs. 1). Logit is more popular because of its closed form and easy odds interpretation; probit is natural when the errors are thought to be normal or in multivariate settings.

### 4.1 Marginal effects

The coefficients $\beta$ are *not* marginal effects on the probability. For a continuous regressor $x_k$,
$$ \frac{\partial P(y = 1 \mid x)}{\partial x_k} = f(x'\beta)\, \beta_k, $$
where $f = F'$ is the density (logit: $\Lambda(z)(1-\Lambda(z))$; probit: $\phi(z)$). The marginal effect therefore

- has the **sign** of $\beta_k$,
- is **largest** when $P = 0.5$ (the steepest point of the S-curve) and shrinks towards 0 when $P$ is near 0 or 1,
- **depends on $x$**, so it must be summarised: the **average marginal effect (AME)** averages $f(x_n'\beta)\beta_k$ over the sample, while the **marginal effect at the mean (MEM)** evaluates at $\bar{x}$. AMEs are usually preferred.

For a **dummy** regressor, report the discrete change $F(x'\beta \mid d = 1) - F(x'\beta \mid d = 0)$.

### 4.2 Odds ratios (logit)

In the logit model the log-odds are linear in $x$:
$$ \ln \frac{P}{1 - P} = x'\beta . $$
So $\beta_k$ is the change in the **log-odds** per unit of $x_k$, and $e^{\beta_k}$ is the **odds ratio**: the factor by which the odds $P/(1-P)$ are multiplied when $x_k$ increases by one unit. Example: $\beta_k = 0.8$ means the odds of choosing alternative 1 rise by a factor $e^{0.8} \approx 2.2$ per unit of $x_k$. Note that an odds ratio of 2.2 does **not** mean the probability doubles.

## 5. The multinomial logit (MNL) model

With $J \ge 2$ alternatives, assume the $\varepsilon_{nj}$ are **independent and identically distributed (iid) type I extreme value** (Gumbel). Then (McFadden, 1974) the choice probability has the closed form

$$ P_{ni} = \frac{e^{V_{ni}}}{\sum_{j=1}^{J} e^{V_{nj}}} . $$

This is the workhorse discrete choice model. Properties:

- Probabilities are strictly between 0 and 1 and sum to one across alternatives.
- $P_{ni}$ is an S-shaped function of $V_{ni}$: improving an alternative that is already very likely (or very unlikely) to be chosen changes its probability little.
- With $J = 2$ it reduces to the binary logit.

**Terminology.** In the econometrics literature the name *multinomial logit* is often reserved for the case where the regressors are **characteristics of the decision maker** (with alternative-specific coefficients $\beta_j$, one set normalised to zero), while **conditional logit** refers to regressors that are **attributes of the alternatives** with generic coefficients. Both are the same random utility model; a general specification can mix both types (sometimes called the *mixed* or *general* multinomial logit — not to be confused with mixed logit in Section 8).

With individual characteristics $s_n$ and alternative-specific coefficients the model reads
$$ P_{ni} = \frac{e^{s_n'\beta_i}}{\sum_{j} e^{s_n'\beta_j}}, \qquad \beta_1 = 0, $$
and $\beta_i$ is interpreted **relative to the base alternative**: $\ln (P_{ni}/P_{n1}) = s_n'\beta_i$.

### 5.1 Independence of irrelevant alternatives (IIA)

The ratio of any two MNL probabilities does not depend on any other alternative:
$$ \frac{P_{ni}}{P_{nk}} = \frac{e^{V_{ni}}}{e^{V_{nk}}} = e^{V_{ni} - V_{nk}} . $$
This is the **IIA** property. It follows directly from the iid assumption on $\varepsilon$: alternatives have no unobserved attributes in common.

**The red bus / blue bus problem.** Suppose commuters choose between car and a blue bus with $P_{\text{car}} = P_{\text{blue}} = 1/2$. Now a red bus is introduced that is identical to the blue bus except for its colour. Intuitively, bus riders split between the two buses and the car share stays at $1/2$: $(1/2, 1/4, 1/4)$. The MNL, however, must keep the ratio $P_{\text{car}}/P_{\text{blue}} = 1$, and by symmetry $P_{\text{blue}} = P_{\text{red}}$, so it predicts $(1/3, 1/3, 1/3)$. The model *overpredicts* the share of the new alternative because it ignores that the two buses share unobserved attributes (their $\varepsilon$'s are correlated).

**Substitution patterns.** Under IIA, when one alternative improves, it draws share from all other alternatives **proportionally** to their current shares. This is often unrealistic (a cheaper train draws more from the bus than from the bike).

**When is IIA acceptable?** When the alternatives are genuinely dissimilar in their unobserved parts, or when the analyst is only interested in the aggregate effect of variables and the specification of $V$ is rich enough (many ASCs and interactions) that little correlation is left in $\varepsilon$. IIA can be tested with the **Hausman–McFadden test** (compare estimates with the full choice set to those obtained after dropping an alternative; under IIA both are consistent and should be close). Models relaxing IIA are discussed in Section 8.

## 6. Estimation by maximum likelihood

Let $y_{nj} = 1$ if $n$ chose $j$ and 0 otherwise. Because each decision maker chooses exactly one alternative, the probability of the observed choice is $\prod_j P_{nj}^{y_{nj}}$, and under independent sampling the **log-likelihood** is

$$ \ln L(\beta) = \sum_{n=1}^{N} \sum_{j=1}^{J} y_{nj} \ln P_{nj}(\beta). $$

- For logit and probit the log-likelihood is **globally concave** in $\beta$ (for the linear-in-parameters specification), so numerical maximisation (Newton–Raphson, BFGS) finds the unique maximum quickly.
- The **first-order conditions** for the MNL are
  $$ \sum_n \sum_j (y_{nj} - P_{nj})\, x_{nj} = 0, $$
  i.e. at the ML estimate the average predicted share of each alternative equals its observed share whenever ASCs are included (the model fits the sample shares exactly).
- The ML estimator is consistent, asymptotically normal and efficient under correct specification. Standard errors come from the inverse Hessian (or a robust "sandwich" estimator).
- **Identification requirements**: one ASC and, for individual characteristics, one coefficient vector normalised to zero; the error scale normalised; no perfect prediction (if some $x$ perfectly separates the choices the ML estimate does not exist).

## 7. Interpreting and reporting results

1. **Signs and significance** of $\beta$: a negative cost coefficient means higher cost lowers utility and hence choice probability. $t$-tests and Wald/likelihood-ratio tests work as usual.
2. **Marginal effects** (Section 4.1). In the MNL, the marginal effect of an attribute of alternative $j$ on the probability of alternative $i$ is
   $$ \frac{\partial P_{ni}}{\partial x_{nj}} = \beta\, P_{ni} (\mathbf{1}\{i=j\} - P_{nj}), $$
   so an improvement of $j$ raises $P_{nj}$ and lowers all other probabilities. For decision-maker characteristics the sign of the marginal effect need **not** equal the sign of $\beta_i$ (because $\beta_i$ is relative to the base alternative).
3. **Elasticities**: the own-elasticity of $P_{ni}$ with respect to $x_{ni}$ is $\beta\, x_{ni} (1 - P_{ni})$; the cross-elasticity with respect to $x_{nj}$ is $-\beta\, x_{nj} P_{nj}$, which is the same for all $i \neq j$ — another face of IIA.
4. **Ratios of coefficients** are scale-free and have a natural interpretation. With a time coefficient $\beta_T$ and a cost coefficient $\beta_C$ (both negative), the **value of time** (willingness to pay to save one unit of travel time) is
   $$ \text{VOT} = \frac{\beta_T}{\beta_C} \quad \text{(in money per unit time)} . $$
   More generally $\beta_k / \beta_C$ is the **willingness to pay** for one unit of attribute $k$.
5. **Predicted probabilities** for a scenario: compute $V_{nj}$ under the scenario, plug into the MNL formula, and average over decision makers to obtain predicted **market shares**. Comparing shares before and after a policy change (a fare increase, a new alternative) is the main use of the model in practice — keeping the IIA caveat in mind for new alternatives.

### Goodness of fit

- **McFadden's pseudo-$R^2$**: $\rho^2 = 1 - \dfrac{\ln L(\hat\beta)}{\ln L_0}$, where $\ln L_0$ is the log-likelihood with only constants (or with all coefficients zero). It is *not* comparable to the OLS $R^2$; values of 0.2–0.4 already indicate a good fit.
- **Likelihood-ratio test** of nested models: $LR = 2(\ln L_{\text{full}} - \ln L_{\text{restricted}}) \sim \chi^2_{q}$ with $q$ restrictions.
- **Hit rate** (share of observations whose predicted most-likely alternative equals the actual choice) is intuitive but crude.
- **AIC/BIC** for comparing non-nested specifications.

## 8. Beyond the multinomial logit

All of these keep the random utility framework but relax the iid extreme value assumption.

- **Nested logit.** Alternatives are grouped into *nests* (e.g. {car} and {bus, train}); $\varepsilon$ is correlated within a nest but independent across nests. IIA holds within a nest, not across nests. The choice probability factors as $P_{ni} = P(\text{nest}) \times P(i \mid \text{nest})$, with a nest-level "inclusive value" (log-sum) term $\ln \sum_{j \in \text{nest}} e^{V_{nj}/\lambda}$ carrying information about the nest's attractiveness. The parameter $\lambda \in (0,1]$ measures independence within the nest ($\lambda = 1$ gives back the MNL). This solves the red bus / blue bus problem by putting both buses in one nest.
- **Mixed (random-parameters) logit.** Coefficients vary randomly across decision makers, $\beta_n \sim g(\beta \mid \theta)$. The choice probability is the MNL probability integrated over the taste distribution,
  $$ P_{ni} = \int \frac{e^{x_{ni}'\beta}}{\sum_j e^{x_{nj}'\beta}}\, g(\beta \mid \theta)\, d\beta , $$
  which has no closed form and is estimated by **simulated maximum likelihood** (draw $\beta$'s, average the logit probabilities). It allows arbitrary substitution patterns (no IIA), unobserved taste heterogeneity, and correlation across repeated choices of the same person (panel data).
- **Multinomial probit.** $\varepsilon \sim N(0, \Omega)$ with a general covariance matrix; very flexible, but the probabilities are multi-dimensional normal integrals requiring simulation (GHK simulator) and identification of $\Omega$ is delicate.
- **Ordered models** (ordered logit/probit) apply when the categories have a natural ordering (e.g. survey ratings "poor / fair / good"); these use a single latent index with cut-points rather than a utility per alternative.

## 9. A small worked example

A commuter chooses between **car** (alternative 1) and **bus** (alternative 2). Representative utility depends on travel time in minutes with generic coefficient $\beta_T = -0.05$, and the bus has an ASC $\alpha_{\text{bus}} = -0.5$ relative to the car ($\alpha_{\text{car}} = 0$):

$$ V_{\text{car}} = -0.05 \cdot 30 = -1.5, \qquad V_{\text{bus}} = -0.5 - 0.05 \cdot 40 = -2.5 . $$

Logit probabilities:
$$ P_{\text{car}} = \frac{e^{-1.5}}{e^{-1.5} + e^{-2.5}} = \frac{1}{1 + e^{-1}} \approx 0.73, \qquad P_{\text{bus}} \approx 0.27 . $$

Only the *difference* $V_{\text{car}} - V_{\text{bus}} = 1$ matters. If a bus lane cuts bus travel time to 30 minutes, $V_{\text{bus}} = -2.0$, the difference falls to $0.5$ and $P_{\text{car}} = 1/(1 + e^{-0.5}) \approx 0.62$. The marginal effect of bus time on $P_{\text{bus}}$ at the original values is $\beta_T P_{\text{bus}}(1 - P_{\text{bus}}) = -0.05 \cdot 0.27 \cdot 0.73 \approx -0.010$ per minute.

If a cost variable with coefficient $\beta_C = -0.10$ per euro were also included, the value of time would be $\beta_T / \beta_C = 0.5$ euro per minute, i.e. 30 euro per hour.

## 10. Software

- **R**: `mlogit` (MNL, nested, mixed logit), `apollo` (very general, industry standard for transport), `nnet::multinom` (MNL with individual characteristics), `glm(family = binomial)` for binary logit/probit.
- **Stata**: `logit`, `probit`, `mlogit`, `clogit`, `cmclogit`, `nlogit`, `mixlogit`, `margins` for marginal effects.
- **Python**: `statsmodels` (`Logit`, `Probit`, `MNLogit`), `biogeme`, `xlogit`, `pylogit`.

Data for MNL/conditional logit are usually arranged in **long format**: one row per (decision maker, alternative) with a choice indicator and the alternative's attributes.

## 11. Summary

1. Discrete choice models explain **which** alternative is chosen via **choice probabilities**.
2. They derive from **random utility maximisation**: $U_{nj} = V_{nj} + \varepsilon_{nj}$; only utility differences matter and the scale is normalised.
3. **Logit/probit** handle binary choice; coefficients are interpreted via **marginal effects** or (logit) **odds ratios**, not directly.
4. The **multinomial logit** gives closed-form probabilities but imposes **IIA** and proportional substitution — beware of the red bus / blue bus problem.
5. Estimation is by **maximum likelihood**; fit is judged by pseudo-$R^2$, LR tests and prediction.
6. **Ratios of coefficients** (value of time, willingness to pay) and **predicted shares** under scenarios are the economically meaningful outputs.
7. **Nested logit, mixed logit and probit** relax IIA at the cost of more complex estimation.

### References

- Train, K. (2009). *Discrete Choice Methods with Simulation*, 2nd ed., Cambridge University Press.
- McFadden, D. (1974). Conditional logit analysis of qualitative choice behavior. In P. Zarembka (ed.), *Frontiers in Econometrics*, Academic Press.
- Ben-Akiva, M. and Lerman, S. (1985). *Discrete Choice Analysis: Theory and Application to Travel Demand*, MIT Press.
- Cameron, A. C. and Trivedi, P. K. (2005). *Microeconometrics: Methods and Applications*, Cambridge University Press, ch. 14–15.
- Wooldridge, J. M. (2010). *Econometric Analysis of Cross Section and Panel Data*, 2nd ed., MIT Press, ch. 15–16.
