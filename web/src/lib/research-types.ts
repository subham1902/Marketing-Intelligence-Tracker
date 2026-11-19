// TypeScript mirror of the research Pydantic schemas (api/schemas.py).

export const FINDING_CATEGORIES = [
  "expansion",
  "product_launch",
  "partnership",
  "funding",
  "policy",
  "tender",
  "hiring",
  "technology",
  "market_entry",
  "other",
] as const;
export type FindingCategory = (typeof FINDING_CATEGORIES)[number];

export const SOURCE_PREFERENCES = [
  "official_company",
  "government",
  "tenders",
  "regulatory",
  "news",
  "industry",
] as const;
export type SourcePreference = (typeof SOURCE_PREFERENCES)[number];

export type TimeWindow = "1m" | "3m" | "6m" | "12m";
export type ResearchStatus = "queued" | "running" | "completed" | "partial" | "failed";

export interface ResearchCreate {
  objective: string;
  industry?: string | null;
  geography?: string;
  time_window?: TimeWindow;
  companies?: string[];
  source_preferences?: SourcePreference[];
}

export interface ResearchRunSummary {
  id: string;
  objective: string;
  industry: string | null;
  geography: string | null;
  time_window: string | null;
  date_from: string | null;
  date_to: string | null;
  companies: string[];
  source_preferences: string[];
  status: ResearchStatus;
  provider: string;
  is_demo: boolean;
  provider_request_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  source_count: number;
  finding_count: number;
}

export interface ResearchReport {
  executive_summary: string | null;
  industry_overview: string | null;
  market_trends: string[];
  company_developments: string[];
  product_launches: string[];
  manufacturing_expansion: string[];
  partnerships_and_investment: string[];
  policy_and_regulatory: string[];
  tenders_and_procurement: string[];
  commercial_opportunities: string[];
  risks: string[];
}

export interface ResearchRun extends ResearchRunSummary {
  result: ResearchReport | null;
}

export interface ResearchSource {
  id: string;
  research_run_id: string;
  url: string;
  domain: string | null;
  title: string | null;
  source_type: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  snippet: string | null;
  link_status?: string | null;
}

export interface ResearchFinding {
  id: string;
  research_run_id: string;
  title: string;
  category: FindingCategory;
  entity: string | null;
  industry: string | null;
  summary: string | null;
  significance: number | null;
  confidence: number | null;
  kind: "verified_fact" | "analysis";
  event_date: string | null;
  source_ids: string[];
  flags: string[];
  created_at: string | null;
}

export interface FeedFinding extends ResearchFinding {
  run_objective: string | null;
  is_demo: boolean;
  provider: string | null;
}

export interface FindingQuery {
  category?: FindingCategory;
  kind?: "verified_fact" | "analysis";
  include_demo?: boolean;
  limit?: number;
  offset?: number;
}

export interface ResearchConfig {
  provider: string;
  live_available: boolean;
  mode: string;
}

export const CATEGORY_LABEL: Record<FindingCategory, string> = {
  expansion: "Expansion",
  product_launch: "Product launch",
  partnership: "Partnership",
  funding: "Funding",
  policy: "Policy",
  tender: "Tender",
  hiring: "Hiring",
  technology: "Technology",
  market_entry: "Market entry",
  other: "Other",
};

export const PREFERENCE_LABEL: Record<SourcePreference, string> = {
  official_company: "Company announcements",
  government: "Government",
  tenders: "Tenders & procurement",
  regulatory: "Regulatory filings",
  news: "Business news",
  industry: "Industry bodies",
};

export const WINDOW_LABEL: Record<TimeWindow, string> = {
  "1m": "Last month",
  "3m": "Last 3 months",
  "6m": "Last 6 months",
  "12m": "Last 12 months",
};
