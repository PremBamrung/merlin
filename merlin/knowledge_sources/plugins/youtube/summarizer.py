from datetime import datetime
import re
import threading

from merlin.core.logging import logger


class VideoSummarizer:
    """Handles video content summarization using LLM."""

    def __init__(self, model=None):
        """Initialize summarizer with prompt templates.

        Args:
            model: Pydantic AI model instance. If None, loaded lazily from
                merlin.rag.model.build_ingest_model (tests inject a TestModel).
        """
        self._model = model
        # Usage of the most recent summarize call: token counts + the resolved
        # model, read off the response by the plugin so the service layer can
        # persist a cost row. **Thread-local** because this summarizer is a
        # singleton shared across the ingest thread-pool workers — a plain
        # attribute would let one ingest's usage clobber another's (wrong cost
        # attributed to the wrong item). Each worker writes then reads back the
        # usage it produced on its own thread. None until a summary runs.
        self._usage = threading.local()

        TEMPLATE_SHORT = """Given the subtitles of a Youtube video, create a short summary that includes:

## Overview (2 sentences max)
- First sentence: Summary of what is discussed in the video
- Second sentence: Must answer the key questions raised in the video - mention specific causes, parties, entities, outcomes, or conclusions discussed (e.g., "The decline is attributed to **policy failures** and voter migration to the **PQ and Liberals**, with recovery unlikely before 2026")
- Use **markdown bold formatting** to highlight important keywords, themes, parties, entities, or concepts

## Main Key Points
- Format the points as a numbered list (1., 2., 3., ...), ordered by importance, not chronologically
- Begin every point with a **bold takeaway phrase** (about 3-8 words) that states the insight itself - not the topic or the entity. A reader skimming only the bold leads should grasp the gist of the video
- The leading bold phrase is mandatory and must come first in the point; any additional bold inside the point is optional - do NOT bold an entity or term at the start in place of the insight
- After the bold lead, add a short clause (1-2 lines max) with the specifics: name entities, cite numbers, state conclusions; never vaguely describe what the video "discusses" or "explores"
- Avoid introductory phrases ("The video shows that...", "According to...") and verbose explanations; be direct and concise
- Include only points that each carry a distinct, important insight; use up to 10 points, but only as many as the content genuinely warrants. Never pad with thin or repetitive points to reach a number - fewer strong points beat ten weak ones

Rules:
- Write the summary body in {lang}
- Keep the section headers ("## Overview", "## Main Key Points") in English even when the body is written in another language
- Begin the response directly with the "## Overview" header - do not write any introductory sentence, preamble, or sign-off; output only the summary itself
- If a video description is provided below, use it for supporting context (names, links, chapters, claims the creator makes), but treat the subtitles as the ground truth and ignore promotional or sponsor boilerplate in the description

Two examples of the expected output (note how each begins directly with "## Overview", keeps English headers, and numbers the key points):

### Example 1 (English) - "8 Myths About Espresso Everyone Still Believes" by Lance Hedrick

## Overview
**Lance Hedrick** dismantles eight espresso myths held by enthusiasts and reinforced by online communities. The core finding: popular rules like nine bars of pressure, always-fresh beans, and expensive grinders are largely misconceptions - better espresso comes from understanding variables and personal taste rather than fixed formulas.

## Main Key Points
1. **Nine bars of pressure is not required** - optimal pressure depends on the coffee and target outcome; lower pressure frequently performs better
2. **Crema is not a quality indicator** - it reflects roast level and CO2 off-gassing, not extraction quality; dark roasts produce more crema regardless of flavour
3. **Fresh beans can produce worse shots** - optimal rest time varies by roast; too-fresh beans yield harsh, unbalanced espresso
4. **Expensive grinders are not inherently better** - grinder choice should match flavour preference; budget grinders can outperform premium ones for certain profiles
5. **Higher extraction yield is not better flavour** - optimal range is typically **18-19%**; pushing higher often adds bitterness without sweetness
6. **Channeling is physically unavoidable** - perfectly even extraction is impossible; visual cues from naked portafilters mislead more than they guide
7. **Online espresso advice is mostly anecdotal** - personal experimentation is more reliable than community consensus

### Example 2 (French) - "Si vos discussions entre amis sont de moins en moins riches, c'est à cause de la 'catch up culture'" by LeHuffPost

## Overview
La vidéo examine la **"catch up culture"**, un phénomène où les amitiés se réduisent à des échanges superficiels de nouvelles sans expériences partagées. Ce déclin est attribué à la **priorité donnée à la vie de couple et de famille**, à l'**illusion de proximité entretenue par les réseaux sociaux**, et à l'absence croissante d'activités vécues ensemble.

## Main Key Points
1. **Les amitiés se figent dans le rattrapage d'actualités** - la "catch up culture" remplace le vécu commun par de simples mises à jour, sans progression
2. **Un ami qu'on voit rarement devient un quasi-étranger** - concept popularisé par **Mitchel Elman** dans *Bad Friend*
3. **Les réseaux sociaux donnent une fausse impression de proximité** - ils se substituent aux vraies interactions sans jamais les remplacer
4. **La vie de couple et de famille érode mécaniquement le temps d'amitié** - les responsabilités réduisent les occasions de se voir
5. **Les échanges se limitent aux bonnes nouvelles** - au détriment des conversations profondes ou difficiles
6. **Le remède est de partager des expériences en temps réel** - plutôt que d'échanger des mises à jour a posteriori

Now produce the summary for the actual video below. Write the body in {lang}. Use markdown formatting for emphasis.

Video titled "{title}" from the channel "{channel}"
{description_block}
Subtitles: {subtitles}

# Answer (begin directly with "## Overview"; use the English headers "## Overview" and "## Main Key Points"; number the key points; do not number the headers themselves): """

        TEMPLATE_LONG = """Given the subtitles of a Youtube video, create a comprehensive, in-depth summary that includes:

## Overview (3-5 sentences)
- First sentence: Summary of what is discussed in the video
- Second sentence: Must answer the key questions raised in the video - mention specific causes, parties, entities, outcomes, or conclusions discussed
- Additional sentences: Main purpose, theme, context, and overall significance or impact
- Use **markdown bold formatting** to highlight important keywords, themes, parties, entities, or concepts

## Main Topics
- Extract and list all key topics discussed in detail
- Include timestamps where each topic starts
- Organize topics hierarchically with sub-topics
- Explain the relationship between topics

## Key Points
- Format the points as a numbered list (1., 2., 3., ...), ordered by importance, not chronologically
- Begin every point with a **bold takeaway phrase** that states the insight itself - not the topic or the entity. A reader skimming only the bold leads should grasp the gist of the video. The leading bold is mandatory and comes first; do NOT bold an entity or term at the start in place of the insight
- After the bold lead, give supporting context, examples, and explanations (3-5 lines), with relevant timestamps where applicable
- Each point should provide deep insight, knowledge, or useful information gained from watching the video, and explain the reasoning behind key arguments
- Focus on actionable insights and key takeaways, not just an enumeration of topics discussed
- Provide up to 10-15 comprehensive points, but only as many as the content genuinely warrants; never pad with thin or repetitive points to reach a number

## Important Quotes
- Notable statements with timestamps
- Include speaker attribution if available
- Explain the context and significance of each quote
- Use **markdown bold formatting** for emphasis on key quotes

## Technical Details (if applicable)
- Comprehensive technical information
- Detailed definitions or explanations
- Code examples or technical concepts with context
- Step-by-step explanations where relevant
- Use **markdown bold formatting** to highlight technical terms and concepts

## Analysis and Insights
- Go beyond summarising: connect points the video does not link explicitly
- Identify the assumptions the argument depends on, and whether they hold
- Note tensions, counterarguments, or things left unaddressed
- Explain why this matters in a broader context
- Use **markdown bold formatting** to highlight key insights

## Takeaways
- 3-5 concrete, actionable conclusions a reader can apply or investigate further
- The "so what" for someone who will not watch the video - not a restatement of the key points

Rules:
- Write the summary body in {lang}
- Keep all section headers ("## Overview", "## Main Topics", "## Key Points", ...) in English even when the body is written in another language
- Begin the response directly with the "## Overview" header - do not write any introductory sentence, preamble, or sign-off; output only the summary itself
- If a video description is provided below, use it for supporting context (names, links, chapters, claims the creator makes), but treat the subtitles as the ground truth and ignore promotional or sponsor boilerplate in the description

Example of the expected output (French body, English headers, numbered key points; here "## Important Quotes" and "## Technical Details" are omitted because they were not applicable - include them when the content warrants):

### Example (French) - "Le sucre est-il vraiment addictif ? Ce que dit la science" by ScienceEtonnante

## Overview
**ScienceEtonnante** examine si le sucre est addictif au sens clinique du terme, en confrontant les études sur le rat aux données humaines. La conclusion est nuancée : **le sucre active bien les circuits de récompense dopaminergiques**, mais les critères d'une addiction comparable à l'alcool ou aux opioïdes ne sont pas remplis chez l'humain dans des conditions normales d'accès. L'épisode est particulièrement utile pour démêler ce que les études sur le rat prouvent réellement de ce qu'on leur fait dire dans la presse grand public.

## Main Topics
- **Les circuits dopaminergiques de la récompense** [02:15]
- **Les études sur le rat et leurs protocoles** [06:40]
- **Les critères cliniques d'addiction (DSM)** [11:20]
- **Le cadrage médiatique de la "sugar addiction"** [16:05]
- **Le rôle de l'environnement alimentaire** [20:30]

## Key Points
1. **Le sucre active la dopamine - mais comme tout aliment palatable, pas comme une drogue** [02:15]
   Les études d'imagerie montrent une libération de dopamine dans le noyau accumbens lors de la consommation de sucre. Cet effet est partagé par l'exercice, le sexe et la plupart des aliments caloriques - il ne suffit pas à qualifier d'addiction.
2. **Les études sur le rat en restriction ne sont pas transposables directement à l'humain** [06:40]
   Les rats rendus "dépendants" l'étaient dans des protocoles de restriction puis d'accès intermittent, une condition qui induit des comportements compulsifs pour presque n'importe quel aliment. En accès libre, ces comportements disparaissent presque totalement.
3. **Les critères DSM d'addiction ne sont pas remplis pour le sucre chez l'humain** [11:20]
   Tolérance, sevrage physique, perte de contrôle malgré les conséquences : en conditions normales, le sucre ne satisfait pas ces critères de façon robuste. Certains rapports de perte de contrôle relèvent de la restriction cognitive plutôt que d'une dépendance neurobiologique.
4. **La "sugar addiction" est en partie un phénomène culturel et médiatique** [16:05]
   Le cadrage addictif a émergé dans les années 2000-2010, amplifié par des études mal interprétées et des intérêts commerciaux (régimes, compléments "détox"). Ce cadrage peut paradoxalement aggraver les comportements alimentaires en renforçant la restriction puis la perte de contrôle.
5. **Le vrai problème est l'environnement alimentaire, pas la substance** [20:30]
   Les aliments ultra-transformés combinent sucre, sel, gras et texture pour maximiser la palatabilité et réduire les signaux de satiété. C'est la combinaison et l'accessibilité qui posent problème, pas le sucre isolément.

## Analysis and Insights
- La vidéo distingue bien études animales et humaines, mais sous-explore les **différences individuelles** : les personnes ayant des antécédents de TCA ou de restriction sévère montrent des patterns proches de l'addiction que le cadre "normal" ne capture pas.
- Le recadrage "environnement plutôt que substance" est solide, mais peut être instrumentalisé par l'industrie agro-alimentaire pour déresponsabiliser les produits ultra-transformés - une tension que la vidéo ne soulève pas.
- La question "est-ce addictif ?" est peut-être mal posée : **"quelles conditions rendent la consommation incontrôlable ?"** serait plus opérationnelle pour la prévention.

## Takeaways
- Éviter le mot "addiction" pour une surconsommation de sucre hors contexte clinique : le terme pathologise un comportement souvent mieux expliqué par l'environnement alimentaire.
- Si vous vous sentez "accro" au sucre, examinez d'abord vos schémas de restriction : la privation intermittente induit la compulsion, pas la neurobiologie du sucre.
- Méfiez-vous des études sur le rat citées sans le protocole (restriction vs accès libre) - c'est le signe d'une interprétation à vérifier.
- Agir sur l'environnement (accessibilité des aliments ultra-transformés) est plus efficace que de "résister au sucre" par la seule volonté.

Now produce the summary for the actual video below. Write the body in {lang}. Use markdown formatting for emphasis throughout.

Video titled "{title}" from the channel "{channel}"
{description_block}
Subtitles: {subtitles}

# Answer (begin directly with "## Overview"; use English markdown headers ("## Overview", "## Main Topics", "## Key Points", ...) for the sections, with the Key Points as a numbered list; do not number the headers themselves): """

        # Raw template strings; formatted with str.format(**vars) at call time.
        # The placeholders ({subtitles}, {lang}, {title}, {channel},
        # {description_block}) are the only braces in these templates.
        self.templates = {
            "short": TEMPLATE_SHORT,
            "long": TEMPLATE_LONG,
        }

    @property
    def last_usage(self) -> dict | None:
        return getattr(self._usage, "value", None)

    @last_usage.setter
    def last_usage(self, value: dict | None) -> None:
        self._usage.value = value

    # Cap the description fed into the prompt — descriptions can be enormous
    # (timestamps, affiliate links, sponsor blurbs); a few thousand chars is
    # plenty of grounding context without crowding out the transcript.
    _DESCRIPTION_CHAR_CAP = 4000

    def _build_description_block(self, description: str | None) -> str:
        """Render the optional description block; empty string when blank."""
        text = (description or "").strip()
        if not text:
            return ""
        if len(text) > self._DESCRIPTION_CHAR_CAP:
            text = text[: self._DESCRIPTION_CHAR_CAP] + "\n[description truncated]"
        return (
            "\nVideo description (supporting context — the subtitles are the "
            f"ground truth):\n{text}\n"
        )

    @property
    def model(self):
        if self._model is None:
            from merlin.rag.model import build_ingest_model

            self._model = build_ingest_model()
        return self._model

    def extract_topics_and_timestamps(
        self, summary_text: str, summary_length: str = "short"
    ) -> tuple[dict, dict]:
        """Extract topics and timestamps from the summary text."""
        topics = {}
        timestamps = {}

        # For short summaries, extract from "Main Key Points" section
        if summary_length == "short":
            if "## Main Key Points" in summary_text:
                key_points_section = summary_text.split("## Main Key Points")[1]
                key_point_lines = [
                    line.strip()
                    for line in key_points_section.split("\n")
                    if line.strip()
                ]

                for line in key_point_lines:
                    point = None
                    # Numbered list items ("1. ...") are the expected format
                    match = re.match(r"^\d+[.)]\s+(.*)", line)
                    if match:
                        point = match.group(1).strip()
                    elif "-" in line or "•" in line:
                        # Tolerate "-"/"•" bullets if the model falls back to them
                        bullet_char = "-" if "-" in line else "•"
                        point = line.split(bullet_char, 1)[1].strip()

                    # Look for timestamp in the point line
                    if point and "[" in point and "]" in point:
                        timestamp = point[point.find("[") + 1 : point.find("]")]
                        point = point.split("[")[0].strip()
                        topics[point] = timestamp
                        timestamps[timestamp] = point
        else:
            # For long summaries, extract from the "Main Topics" section.
            # Current long summaries use markdown headers ("## Main Topics");
            # the numbered branch ("2. Main Topics:") is a fallback for legacy
            # summaries produced by the old numbered templates.
            topics_section = None
            if "## Main Topics" in summary_text:
                topics_section = summary_text.split("## Main Topics")[1]
                # Cut at the next markdown section header, if present.
                for next_header in ("## Key Points", "## Important Quotes"):
                    if next_header in topics_section:
                        topics_section = topics_section.split(next_header)[0]
                        break
            elif "2. Main Topics:" in summary_text:
                if "3. Key Points:" in summary_text:
                    topics_section = summary_text.split("2. Main Topics:")[1].split(
                        "3. Key Points:"
                    )[0]
                else:
                    # Fallback if structure is slightly different
                    topics_section = summary_text.split("2. Main Topics:")[1]
                    if "4. Important Quotes:" in topics_section:
                        topics_section = topics_section.split("4. Important Quotes:")[0]

            if topics_section:
                topic_lines = [
                    line.strip() for line in topics_section.split("\n") if line.strip()
                ]

                for line in topic_lines:
                    if "-" in line:
                        topic = line.split("-")[1].strip()
                        # Look for timestamp in the topic line
                        if "[" in topic and "]" in topic:
                            timestamp = topic[topic.find("[") + 1 : topic.find("]")]
                            topic = topic.split("[")[0].strip()
                            topics[topic] = timestamp
                            timestamps[timestamp] = topic

        return topics, timestamps

    @staticmethod
    def _extract_usage(result) -> dict | None:
        """Pull token counts + the resolved model off a Pydantic AI run result.

        Pydantic AI's usage carries the token counts (input/output + cache-read
        sub-details) but **not** OpenRouter's per-call cost — so the service
        prices the call from the pricing map using the resolved model name (e.g.
        `deepseek/deepseek-v4-flash`, from the response, not our `@preset/…` id).
        `cost_usd` is left None here; `usage.record` computes it. Best-effort: any
        shape mismatch yields None.
        """
        try:
            u = result.usage
            if callable(u) and not hasattr(u, "input_tokens"):  # older pydantic-ai
                u = u()
            model = None
            for msg in result.all_messages():
                name = getattr(msg, "model_name", None)
                if name:
                    model = name
            return {
                "input_tokens": getattr(u, "input_tokens", None),
                "output_tokens": getattr(u, "output_tokens", None),
                "cache_read_tokens": getattr(u, "cache_read_tokens", None),
                "cost_usd": None,
                "model": model,
            }
        except Exception:
            return None

    def summarize(
        self,
        subtitles: str,
        title: str,
        channel: str,
        lang: str = "english",
        summary_length: str = "short",
        description: str | None = None,
    ) -> tuple[str, dict, dict]:
        """Generate a summary of the video content.

        Runs one tool-less Pydantic AI request and returns
        ``(summary, topics, timestamps)``. Token counts + the resolved model are
        stashed on `self.last_usage` for the plugin to persist a cost row.

        Args:
            subtitles: The video subtitles text
            title: The video title
            channel: The channel name
            lang: Target language for the summary
            summary_length: "short" or "long"
            description: Optional video description for grounding context
        """
        from pydantic_ai import Agent

        start_time = datetime.now()
        logger.info(f"Starting summarization for video: {title}")
        logger.debug(
            f"Summarization parameters - Language: {lang}, Length: {summary_length}"
        )

        normalized_length = summary_length.lower()
        if normalized_length not in self.templates:
            logger.warning(
                f"Unknown summary length '{summary_length}', defaulting to 'short'"
            )
            normalized_length = "short"

        prompt = self.templates[normalized_length].format(
            subtitles=subtitles,
            lang=lang,
            title=title,
            channel=channel,
            description_block=self._build_description_block(description),
        )

        self.last_usage = None
        try:
            result = Agent(self.model).run_sync(prompt)
            self.last_usage = self._extract_usage(result)
            summary = result.output

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Summarization completed in {duration:.2f}s")

            topics, timestamps = self.extract_topics_and_timestamps(
                summary, normalized_length
            )
            return summary, topics, timestamps
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Summarization failed after {duration:.2f}s: {str(e)}")
            raise
