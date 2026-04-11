from typing import TypedDict, Annotated
import operator


# --------------------------------------------------------------------------- #
#  Sub-models (plain dicts — keep it simple, Pydantic can be added later)
# --------------------------------------------------------------------------- #

class ResearchItem(TypedDict):
    fact: str
    source_url: str
    reliability_score: float   # 0.0 – 1.0
    relevance_score: float     # 0.0 – 1.0


class SEOAnalysis(TypedDict):
    primary_keyword: str
    secondary_keywords: list[str]
    competitor_urls: list[str]
    content_gaps: list[str]
    suggested_title: str
    suggested_slug: str
    suggested_meta_description: str
    target_word_count: int
    heading_structure: list[str]   # ["H1: ...", "H2: ...", ...]


class ContentStrategy(TypedDict):
    content_angle: str
    unique_value_proposition: str
    key_messages: list[str]        # 3-5 items
    target_emotions: list[str]
    call_to_action: str
    article_outline: list[str]


class ClaimVerification(TypedDict):
    claim: str
    status: str                    # Verified | Partially Verified | Unverified | Contradicted
    confidence_score: float        # 0.0 – 1.0
    source_reference: str
    suggested_correction: str


class ImageAsset(TypedDict):
    prompt: str
    url: str                       # local path or remote URL after generation
    platform: str                  # featured | twitter_card | linkedin_banner | youtube_thumbnail


class HumanFeedback(TypedDict):
    approved_platforms: list[str]  # which platform outputs are approved
    revision_notes: dict[str, str] # platform -> feedback text
    action: str                    # approve | revise | reject


class PublishResult(TypedDict):
    platform: str
    status: str                    # published | failed | scheduled
    url: str
    error: str


class ErrorLog(TypedDict):
    agent: str
    error: str
    timestamp: str


# --------------------------------------------------------------------------- #
#  Central shared state
# --------------------------------------------------------------------------- #

class ContentState(TypedDict):
    # ── User inputs ──────────────────────────────────────────────────────── #
    topic: str
    audience: str
    platforms: list[str]
    tone: str                      # professional | casual | technical | inspirational
    word_count_target: int
    custom_keywords: list[str]
    brand_guidelines: str

    # ── Phase 1: Research ────────────────────────────────────────────────── #
    research: Annotated[list[ResearchItem], operator.add]
    seo_analysis: SEOAnalysis

    # ── Phase 2: Creation ────────────────────────────────────────────────── #
    strategy: ContentStrategy
    article: str
    meta_description: str
    twitter_thread: list[str]
    linkedin_post: str
    youtube_script: str

    # ── Phase 3: Quality ─────────────────────────────────────────────────── #
    fact_check_report: list[ClaimVerification]
    seo_optimized_article: str
    seo_scorecard: dict
    image_prompts: list[str]
    generated_images: list[ImageAsset]

    # ── Human review ─────────────────────────────────────────────────────── #
    human_feedback: HumanFeedback

    # ── Phase 4: Publishing ──────────────────────────────────────────────── #
    publishing_results: Annotated[list[PublishResult], operator.add]

    # ── Pipeline meta ────────────────────────────────────────────────────── #
    status: str                    # e.g. "researching" | "writing" | "review" | "done"
    errors: Annotated[list[ErrorLog], operator.add]