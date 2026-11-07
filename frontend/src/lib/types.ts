export type RecordStatus = "complete" | "partial" | "unsupported_language";
export type NicheOrigin = "seed_taxonomy" | "emergent_cluster" | "custom_user";
export type PersonaType = "content_creator" | "business";
export type FitStatus = "strong_fit" | "conditional_fit" | "weak_fit" | "disqualified";

export interface TranscriptSegment {
  start_seconds: number;
  end_seconds: number;
  text: string;
}

export interface OnScreenTextItem {
  text: string;
  frame_index: number;
  timestamp_seconds: number;
}

export interface VisualFrame {
  index: number;
  timestamp_seconds: number;
  description: string;
  asset_path: string;
}

export interface VisualAction {
  description: string;
  frame_indices: number[];
  start_seconds: number;
  end_seconds: number;
}

export interface NumericExpressionItem {
  source: string;
  text: string;
  compact_digits: string;
  start_seconds: number;
  match_hint_only: boolean;
}

export interface OrganVideoRecordV1_2 {
  schema_version: string;
  analysis_version: string;
  id: string;
  status: RecordStatus;
  video: {
    platform: string;
    id: string;
    url: string;
    creator_id: string;
    published_at: string;
    duration_seconds: number;
  };
  collection: {
    run_id: string;
    collected_at: string;
    discovery_queries: string[];
  };
  language: {
    code: string;
    confidence: number;
    source: string;
    supported: boolean;
    allowed: string[];
  };
  elements: {
    post_description: string;
    hashtags: string[];
    transcript: {
      status: string;
      source: string;
      model: string;
      language: string;
      text: string;
      segments: TranscriptSegment[];
    };
    sound: {
      id: string;
      title: string;
      author: string;
      is_original: boolean;
    };
    on_screen_text: {
      status: string;
      source: string;
      items: OnScreenTextItem[];
    };
    numeric_expressions: NumericExpressionItem[];
  };
  description: {
    text: string;
    sources: string[];
    method: string;
  };
  visual: {
    status: string;
    model: string;
    summary: string;
    frames: VisualFrame[];
    actions: VisualAction[];
    coverage: string;
    audio_delivery: string;
    action_localization: string;
  };
  observation: {
    observed_at: string;
    views: number;
    likes: number;
    shares: number;
    comments: number;
    saves: number;
    like_rate: number;
    share_rate: number;
  };
  features: {
    topic: string;
    hook_type: string;
    format: string;
    call_to_action: string;
    opening_text: string;
    evidence_sources: string[];
  };
  classifier: {
    name: string;
    model: string;
    status: string;
    taxonomy_version: string;
    input_truncated: boolean;
    min_confidence: number;
  };
  limitations: string[];
}

export interface TrendDominantFeatures {
  topic: string;
  hook_type: string;
  format: string;
  call_to_action: string;
  common_hashtags: string[];
  sound_motif: string;
}

export interface TrendBenchmarkMetrics {
  record_count: number;
  usable_record_count: number;
  complete_count: number;
  partial_count: number;
  unsupported_language_count: number;
  total_views: number;
  avg_views: number;
  avg_like_rate: number;
  avg_share_rate: number;
  avg_save_rate: number;
  avg_comment_rate: number;
}

export interface NicheCluster {
  niche_id: string;
  name: string;
  origin: NicheOrigin;
  description: string;
  taxonomy_source: string;
  confidence: number;
  cohesion_score: number;
  keywords: string[];
  matched_trend_ids: string[];
  commercial_categories: string[];
}

export interface LayaTypedDecisionTrace {
  model_id: string;
  backbone: string;
  execution_mode: string;
  estimated_input_tokens: number;
  max_context_tokens: number;
  input_truncated: boolean;
  english_compatible: boolean;
  temperature: number;
  choice_probabilities: Record<string, number>;
  top_choice_id: string;
  top_choice_confidence: number;
  virality_rubric_score: number;
  virality_rubric_label: string;
  commercial_rubric_score: number;
  commercial_rubric_label: string;
  production_effort_label: "low" | "medium" | "high";
  brand_safe_probability: number;
  clear_cta_probability: number;
  emergent_niche_triggered: boolean;
  compact_state_preview: string;
  notes: string[];
}

export interface PersonaProfile {
  type: PersonaType;
  display_name: string;
  target_domain: string;
  domain_keywords: string[];
  target_audience: string;
  allowed_languages: string[];
  creator_params: {
    preferred_formats: string[];
    max_production_effort: "low" | "medium" | "high";
    growth_goal: "virality" | "engagement" | "community";
    original_audio_preference: "any" | "trending_sound" | "original_only";
  };
  business_params: {
    brand_safety_strictness: "standard" | "strict";
    campaign_objective: "awareness" | "lead_gen" | "direct_conversion";
    commercial_fit_required: boolean;
  };
}

export interface EvidenceReference {
  record_id: string;
  platform: string;
  record_status: string;
  signal_type: string;
  excerpt: string;
  timestamp_range?: string | null;
}

export interface SuitabilityVerdict {
  trend_id: string;
  niche_id: string;
  persona_type: string;
  fit_status: FitStatus;
  overall_score: number;
  dimension_scores: {
    domain_relevance: number;
    persona_alignment: number;
    engagement_momentum: number;
    execution_or_brand_safety: number;
    cta_and_conversion_fit: number;
    data_completeness: number;
  };
  headline: string;
  rationale: string;
  strengths: string[];
  risks_and_limitations: string[];
  recommended_angles: string[];
  evidence_refs: EvidenceReference[];
}

export interface ValidatedTrendView {
  trend_id: string;
  title: string;
  summary: string;
  discovered_at: string;
  shared_elements: string[];
  dominant_features: TrendDominantFeatures;
  benchmark_metrics: TrendBenchmarkMetrics;
  matched_niche: NicheCluster;
  laya_trace: LayaTypedDecisionTrace;
  suitability_verdict: SuitabilityVerdict;
  ingestion_warnings: string[];
  records: OrganVideoRecordV1_2[];
}

export interface OptimizationHandoffBundle {
  handoff_version: string;
  handoff_id: string;
  confirmed_at: string;
  source_branch: string;
  target_branch: string;
  persona: PersonaProfile;
  niche: NicheCluster;
  selected_trend: {
    trend_id: string;
    title: string;
    summary: string;
    shared_elements: string[];
    dominant_features: TrendDominantFeatures;
    benchmark_metrics: TrendBenchmarkMetrics;
    supporting_records: OrganVideoRecordV1_2[];
  };
  suitability_verdict: SuitabilityVerdict;
  laya_decision_trace: LayaTypedDecisionTrace;
  optimization_seed_hints: {
    recommended_hook_type: string;
    recommended_format: string;
    recommended_cta: string;
    seed_hashtags: string[];
    opening_hook_templates: string[];
    target_duration_seconds_range: [number, number];
    budget_allocation_posture: "aggressive_scale" | "controlled_test" | "micro_experiment";
    suggested_initial_population_size: number;
  };
  user_notes: string;
  delivery?: {
    persisted_path: string;
    webhook_configured: boolean;
    webhook_url?: string | null;
    webhook_forwarded: boolean;
    webhook_status_code?: number | null;
    webhook_message: string;
  } | null;
}

export interface LayaEngineRuntime {
  model_id: string;
  huggingface_url: string;
  architecture: string;
  configured_backend: string;
  hf_token_present: boolean;
  local_agent_loaded: boolean;
  temperature: number;
  seed_niche_threshold: number;
  seed_niche_count: number;
  last_load_note?: string | null;
}

export interface ValidationWorkspaceResponse {
  active_persona: PersonaProfile;
  persona_presets: Record<PersonaType, PersonaProfile>;
  laya_engine: LayaEngineRuntime;
  niches: NicheCluster[];
  trends: ValidatedTrendView[];
  handoffs: OptimizationHandoffBundle[];
}
