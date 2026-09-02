Yes, your four points are much closer. I would organize the conversation with him exactly around these, but sharpen them so they sound like **research-design questions**, not a long literature summary.

Here is a 30-minute plan.

## 1. Start with a 2-minute pitch

Say:

> I am trying to study optimal monetary policy for uncertainty shocks in a production network. The shock is a second-moment shock to firm or sector productivity. My intended mechanism is that higher conditional volatility tightens credit or working-capital conditions, which lowers real production capacity and raises marginal costs and prices. Then, through input-output linkages, the shock propagates across sectors. I want to ask whether the divine coincidence logic in La’O and Tahbaz-Salehi survives once uncertainty shocks create heterogeneous financial wedges.

That is the clean version.

Then give the one-line mapping:

$$
\sigma_{i,t}\uparrow
\quad\Rightarrow\quad
\text{credit / working-capital wedge}\uparrow
\quad\Rightarrow\quad
y_{i,t}\downarrow,\ p_{i,t}\uparrow
\quad\Rightarrow\quad
\text{network propagation}
\quad\Rightarrow\quad
\text{optimal policy target?}
$$

This is already enough for him to understand the agenda.

## 2. Main question: divine coincidence and policy target

Your first question is the most important. I would phrase it like this:

> In La’O and Tahbaz-Salehi, optimal policy in a production network is shaped by sectoral wedges and network positions. I want to introduce uncertainty shocks that tighten working-capital or credit conditions. Do you think this should be viewed as a breakdown of divine coincidence? More concretely, should policy target aggregate inflation, network-weighted price dispersion, output gaps, or something like network-weighted financial wedges?

This is precise and open-ended.

The key conceptual issue is:

$$
\text{uncertainty shock}
\neq
\text{standard TFP level shock}.
$$

A productivity level shock changes feasible output directly. A volatility shock changes **risk, financing conditions, and expected unit costs**. So policy may face a different tradeoff: stabilizing prices may not stabilize the efficient allocation if financial wedges are heterogeneous across sectors.

That is your La’O–Tahbaz-Salehi extension: the relevant object may no longer be only the network-adjusted price index or markup wedge, but also a network-adjusted **uncertainty-finance wedge**.

## 3. Second question: financial channel versus information channel

Your second point is also good. I would ask him directly:

> Do you find the financial-friction channel the right way to make volatility shocks matter in a monetary production-network model? Kopytov et al. model supply-chain uncertainty through technology/network choice in a real model. Since I study monetary policy, I am considering a working-capital or credit-constraint channel, closer to Jermann–Quadrini and Alfaro–Bloom–Lin. Do you think this is the right abstraction, or should I also model an information channel?

My own recommendation: **do not put both channels in the first version**.

Use the financial channel as the benchmark. The reason is simple: if you include both financial friction and information friction, then when uncertainty raises prices or lowers output, nobody will know which mechanism is doing the work.

A clean first version is:

$$
\text{full-information rational expectations}
+
\text{uncertainty-dependent financial wedge}
+
\text{production network}
+
\text{optimal monetary policy}.
$$

Then later you can say:

> A natural extension is incomplete information about the network or firm productivity, which would add a distinct information channel.

This is easier to defend. It also distinguishes you from Kopytov et al.: they use uncertainty to shape technology/network choices in a real model; you use uncertainty to shape financial wedges and monetary-policy tradeoffs in a nominal model. Kopytov et al. study endogenous production networks under supply-chain uncertainty, while La’O and Tahbaz-Salehi study optimal monetary policy in a multisector economy where firms trade intermediate goods over a production network. ([Wiley Online Library][1])

For the financial channel, the best foundation is exactly what you identified: Jermann–Quadrini for financial shocks, Arellano–Bai–Kehoe / Alfaro–Bloom–Lin for uncertainty with financial frictions, and working-capital/cost-channel papers for monetary transmission. Alfaro, Bloom, and Lin explicitly study how uncertainty shocks affect firms’ real and financial activity, and the JPE page places their article in the finance-uncertainty literature. ([DOI][2])

## 4. Third question: how far to push optimal monetary policy

This is where I would be strategic.

Do **not** promise a full Ramsey problem immediately. Ask him whether the paper should first target a **policy-characterization result**.

Say:

> I am unsure how far to push the optimal-policy side. One route is to solve a full Ramsey problem. Another is to derive a target criterion: how the central bank should weight sectoral inflation or output gaps when uncertainty shocks create financial wedges. Which would you find more valuable?

For your contribution, I would think in layers:

**Minimum contribution**

> Show that uncertainty shocks in financially constrained sectors propagate through the production network and generate inflation-output tradeoffs.

**Stronger contribution**

> Show that divine coincidence fails because stabilizing aggregate inflation does not stabilize network-weighted financial distortions.

**Best contribution**

> Derive a sufficient-statistic policy target: optimal policy responds to sectoral uncertainty shocks according to their network centrality and financial tightness.

The best version sounds like:

$$
\text{optimal policy weight on sector } i
=
\text{network centrality}_i
\times
\text{financial-friction exposure}_i
\times
\text{uncertainty shock}_i.
$$

That is likely more publishable than just “uncertainty raises prices.”

So ask Born:

> Would a target-criterion result be enough, or should I aim for a full Ramsey characterization?

## 5. Fourth question: future collaboration with macro-finance coauthor

This is a good thing to ask near the end, after you get his comments on the main project.

Say:

> Separately, I may work with a macro-finance coauthor on production networks and credit cycles. Do you see promising questions where financial cycles interact with production-network propagation?

Then give two or three possible directions.

### Topic A: network credit cycle

Question:

$$
\text{Do credit booms concentrate in upstream sectors and amplify downstream production?}
$$

Mechanism:

$$
\text{credit expansion to upstream firms}
\Rightarrow
\text{lower input prices / higher input supply}
\Rightarrow
\text{downstream expansion}
\Rightarrow
\text{aggregate boom}.
$$

Literature anchor: Demir et al. study bank credit supply shocks using Spanish firm-to-firm and bank-loan data and build a GE production-network model with financial frictions. ([Benny AEA][3])

### Topic B: production-network amplification of monetary policy through financial frictions

Question:

$$
\text{Does monetary policy transmit more strongly through financially constrained network-central sectors?}
$$

This is close to your current project, but more empirical. There is already evidence that production networks matter for monetary-shock transmission; one paper finds network amplification is highly concentrated in a small set of sectors. ([科学直通车][4])

### Topic C: uncertainty shocks and supplier credit

Question:

$$
\text{When uncertainty rises, do firms cut trade credit to customers, causing a network credit crunch?}
$$

This could be very nice if your coauthor is macro-finance, because trade credit is naturally a network object.

### Topic D: monetary union / cross-border production networks

Given Born’s talk, ask:

> In a monetary union, do country-specific uncertainty or credit shocks propagate differently when firms are linked through cross-border input-output networks?

This connects directly to him and gives you a reason to talk after his presentation.

## What I would literally ask him

I would write these four questions on paper:

1. **Modeling channel:**
   “For a monetary production-network model of uncertainty shocks, does it make sense to discipline the volatility effect through working-capital/credit constraints rather than technology choice or information frictions?”

2. **Policy target:**
   “Once uncertainty creates heterogeneous financial wedges, what is the natural analogue of the La’O–Tahbaz-Salehi policy target? Inflation? Output gap? Network-weighted financial wedges?”

3. **Contribution:**
   “Would a target-criterion result be a meaningful contribution, or should the paper aim for a full Ramsey solution?”

4. **Next projects:**
   “What are promising macro-finance questions linking production networks to credit cycles, bank shocks, or monetary-policy transmission?”

This will make the meeting fruitful because you are asking him to help choose the **architecture** of the paper, not to solve your model line by line.

[1]: https://onlinelibrary.wiley.com/doi/10.3982/ECTA20629?utm_source=chatgpt.com "Endogenous Production Networks Under Supply Chain Uncertainty - Kopytov - 2024 - Econometrica - Wiley Online Library"
[2]: https://doi.org/10.1086/726230?utm_source=chatgpt.com "The Finance Uncertainty Multiplier | Journal of Political Economy: Vol 132, No 2"
[3]: https://benny.aeaweb.org/articles?id=10.1257%2Faer.20201088&utm_source=chatgpt.com "Production and Financial Networks in Interplay - American Economic Association"
[4]: https://www.sciencedirect.com/science/article/pii/S0304393221000179?utm_source=chatgpt.com "Monetary policy and production networks: an empirical investigation - ScienceDirect"
