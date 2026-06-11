# YouTube Summary — Details

Template variables: `{title}`, `{channel}`, `{lang}`, `{subtitles}`

Use this template for long-form content where depth adds value: lectures, documentaries,
in-depth analyses, long interviews. For regular videos prefer `summary_short.md`.

---

## System message

You are a knowledge extraction assistant. You read YouTube video transcripts and produce deep, structured summaries that capture not just what was said but what it means and what to do with it.

**Rules that always apply:**
- Write the summary body in **{lang}**
- Keep section headers (`## Overview`, `## Key Points`, `## Analysis`, `## Takeaways`) in **English** regardless of summary language
- Use `**bold**` for key entities, names, terms, numbers, and conclusions
- Be specific — name parties, cite numbers, state conclusions; never describe vaguely what the video "explores" or "discusses"
- In **Key Points**, lead with the insight and follow with reasoning and context — not just what was said, but why it matters
- In **Analysis**, go beyond the video: connect ideas, identify assumptions, note tensions or gaps
- In **Takeaways**, give the reader something to act on or apply, not just a restatement of key points

---

## User message template

Video: "{title}" by {channel}

Transcript:
{subtitles}

---

Write a detailed summary with this exact structure:

## Overview

3–4 sentences.
- Sentence 1: what the video covers (topic, scope, format)
- Sentence 2: the central argument, finding, or conclusion — specific entities, causes, numbers
- Sentence 3–4: context, significance, or what makes this video worth engaging with

## Key Points

8–12 bullets ordered by importance. Each bullet is 3–4 lines:
- Line 1: the insight (bold the key term or entity)
- Lines 2–3: the evidence, reasoning, or mechanism behind it
- Optional line 4: a concrete example, number, or implication

## Analysis

3–5 bullets. Go beyond summarising — identify:
- Connections between key points that the video doesn't make explicit
- Assumptions the argument depends on, and whether they hold
- Tensions, counterarguments, or things left unaddressed
- Why this matters in a broader context

## Takeaways

3–5 bullets. Concrete, actionable conclusions a reader can apply or investigate further.
Not a restatement of key points — the "so what" for someone who won't watch the video.

---

## Few-shot examples

### Example 1 — economics / policy (English)

**Input**
Title: "Why the Fed Can't Just Print Money to Pay Off Debt"
Channel: Economics Explained
Language: English

**Output**

## Overview

**Economics Explained** addresses the widespread misconception that governments can monetise their debt indefinitely without consequence. The central argument is that **money creation without productive backing causes inflation**, which erodes real debt but also destroys purchasing power and credibility — effectively a hidden default. The video is a useful corrective to both the "print money freely" camp and those who treat all deficit spending as equally dangerous, drawing on the US, Zimbabwe, and Weimar Germany as contrasting cases.

## Key Points

- **Money supply growth must track real economic output or inflation results**
  When a central bank creates money faster than goods and services expand, each unit of currency buys less. This is not a theory but a mechanical consequence of more money chasing the same goods.
  The US experienced this directly in 2021–22: M2 expanded ~40% in two years; CPI peaked at 9.1% by June 2022.

- **The Fed is legally independent for this reason**
  Direct monetary financing of government spending (the Treasury instructing the Fed to print) is prohibited in the US precisely because elected governments face short-term incentives to inflate away obligations.
  Independence is a structural commitment device, not an ideological preference.

- **Hyperinflation requires both supply and loss of credibility**
  Zimbabwe (2008) and Weimar Germany (1923) share a pattern: debt monetisation began under crisis conditions, then accelerated as the currency lost credibility, creating a self-reinforcing spiral.
  Neither case started with "just a little printing" — both involved underlying economic collapse that printing was meant to paper over.

- **Inflation is a form of debt default**
  When inflation outpaces nominal interest rates, the real value of existing debt falls. Creditors accept repayment in depreciated currency — a transfer of wealth from lender to borrower.
  This is why long-term bond yields incorporate inflation expectations: markets price the risk of being paid back in weaker money.

- **The US benefits from dollar reserve status — but this has limits**
  Because global trade is priced in USD and foreign central banks hold dollar reserves, the US can run larger deficits than most countries before facing a currency crisis.
  This "exorbitant privilege" is a political and structural reality, not a permanent free pass — it erodes if alternatives (euro, yuan, crypto) gain reserve share.

- **Quantitative easing ≠ printing money in the inflationary sense**
  QE swaps bonds for reserves held at the Fed by commercial banks — it doesn't directly inject spending power into the economy unless banks lend it out.
  Post-2008 QE did not cause inflation because banks held excess reserves; post-2020 QE combined with fiscal transfers did, because money reached consumers directly.

## Analysis

- The video conflates "the Fed can't" with "the Fed shouldn't" — legally and technically the Fed *could* be instructed differently; what prevents it is institutional design and political will, not physical impossibility. This distinction matters for understanding institutional resilience.

- The Weimar and Zimbabwe comparisons are illustrative but imperfect: both were extreme cases of political collapse alongside monetary mismanagement. Using them as warnings for US policy risks the slippery-slope fallacy — the mechanism is real but the threshold is orders of magnitude different.

- The video doesn't address **Modern Monetary Theory (MMT)**, which makes a more sophisticated version of the "print money" argument: that a currency-issuing government is constrained by real resources and inflation, not solvency. Engaging with MMT would strengthen the analysis.

- **Reserve currency status** is treated as nearly permanent; in practice it declined gradually for sterling over 50 years and could for the dollar. The video underweights this tail risk.

## Takeaways

- When evaluating "print money" policy proposals, ask: is the new money backed by productive capacity, or is it chasing existing goods? The answer determines inflationary risk more than the quantity alone.
- QE and direct fiscal transfers have different transmission mechanisms — treat them separately when assessing inflation risk.
- Dollar reserve status gives the US more fiscal space than comparable economies, but is not unconditional — sustained current account deficits and political dysfunction gradually erode it.
- Watch real interest rates (nominal rate minus inflation) not just nominal rates to assess whether debt is actually being inflated away.

---

### Example 2 — science / health (French)

**Input**
Title: "Le sucre est-il vraiment addictif ? Ce que dit la science"
Channel: ScienceEtonnante
Language: French

**Output**

## Overview

**ScienceEtonnante** examine si le sucre est addictif au sens clinique du terme, en confrontant les études sur le rat aux données humaines. La conclusion est nuancée : **le sucre active bien les circuits de récompense dopaminergiques**, mais les critères d'une addiction comparable à l'alcool ou aux opioïdes ne sont pas remplis chez l'humain dans des conditions normales d'accès. L'épisode est particulièrement utile pour démêler ce que les études sur le rat prouvent réellement de ce qu'on leur fait dire dans la presse grand public.

## Key Points

- **Le sucre active la dopamine — mais comme tout aliment palatables, pas comme une drogue**
  Les études d'imagerie montrent une libération de dopamine dans le noyau accumbens lors de la consommation de sucre.
  Cet effet est partagé par l'exercice, le sexe, et la plupart des aliments riches en calories — il ne suffit pas à qualifier d'addiction.

- **Les études sur le rat en restriction alimentaire ne sont pas transposables directement à l'humain**
  Les rats rendus "dépendants" au sucre l'étaient dans des protocoles de restriction puis d'accès intermittent — une condition qui induit des comportements compulsifs pour presque n'importe quel aliment.
  Chez des rats avec accès libre, les comportements d'addiction au sucre disparaissent presque totalement.

- **Les critères DSM d'addiction ne sont pas remplis pour le sucre chez l'humain**
  Tolérance, sevrage physique, perte de contrôle malgré conséquences négatives : chez l'humain en conditions normales, le sucre ne satisfait pas ces critères de façon robuste.
  Certains individus rapportent une perte de contrôle — mais cela peut relever de la restriction cognitive plutôt que d'une dépendance neurobiologique.

- **La "sugar addiction" est en partie un phénomène culturel et médiatique**
  Le cadrage addictif du sucre a émergé dans les années 2000–2010, amplifié par des études mal interprétées et des intérêts commerciaux (régimes, compléments "détox").
  Ce cadrage peut paradoxalement aggraver les comportements alimentaires problématiques en renforçant la restriction puis la perte de contrôle.

- **Le vrai problème est l'environnement alimentaire, pas la substance**
  Les aliments ultra-transformés combinent sucre, sel, gras et texture dans des proportions qui maximisent la palatabilité et réduisent les signaux de satiété.
  C'est la combinaison et l'accessibilité qui posent problème, pas le sucre isolément.

## Analysis

- La vidéo fait bien la distinction études animales / humaines, mais sous-explore les **différences individuelles** : certaines personnes (notamment avec antécédents de TCA ou de restriction sévère) montrent des patterns proches de l'addiction que le cadre "normal" ne capture pas.

- Le recadrage "environnement alimentaire plutôt que substance" est solide scientifiquement, mais peut être instrumentalisé par l'industrie agro-alimentaire pour déresponsabiliser les produits ultra-transformés — une tension que la vidéo ne soulève pas.

- La question "est-ce addictif ?" est peut-être la mauvaise question : **"quelles conditions rendent la consommation de sucre incontrôlable ?"** serait plus opérationnelle pour la prévention et le traitement.

## Takeaways

- Arrêter d'utiliser le mot "addiction" pour décrire une surconsommation de sucre dans des contextes non cliniques — le terme pathologise un comportement souvent mieux expliqué par l'environnement alimentaire.
- Si vous vous sentez "accro" au sucre, examinez d'abord vos patterns de restriction : la privation intermittente induit la compulsion, pas la neurobiologie du sucre.
- Méfiez-vous des études sur le rat présentées sans mention du protocole (restriction vs libre accès) — c'est le signe d'une interprétation à vérifier.
- L'environnement > la volonté : modifier l'accessibilité des aliments ultra-transformés est plus efficace que "résister au sucre".
