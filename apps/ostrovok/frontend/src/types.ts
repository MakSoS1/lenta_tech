export interface Intent {
  origin: string | null;
  destinations: string[];
  departure_date: string | null;
  return_by?: string | null;
  nights: number;
  adults: number;
  children_ages: number[];
  children_count: number;
  pet_kg: number | null;
  pet_requested?: boolean;
  budget_rub: number | null;
  max_travel_hours: number | null;
  transport: string;
  meal: string;
  refundable: boolean;
  warm: boolean;
  rooms: number;
  hotel_preference: string;
  lock_transport: boolean;
  [key: string]: unknown;
}
export interface Offer {
  offer_id: string;
  kind: "transport" | "hotel" | "transfer";
  title: string;
  total_minor: number;
  currency: string;
  details: Record<string, unknown>;
  source: { kind: string; name: string; url: string; observed_at: string };
  expires_at: string;
}
export interface Plan {
  plan_id: string;
  destination: { id: string; name: string; country: string };
  title: string;
  total_minor: number;
  currency: string;
  components: Offer[];
  timeline: { at: string; label: string; detail: string }[];
  validation: {
    passed: boolean;
    issues: {
      rule_id: string;
      status: string;
      severity: string;
      message: string;
    }[];
  };
  reasons: string[];
  tradeoffs: string[];
  useful_hours: number;
  weather: Record<string, unknown> | null;
}
export interface Quote {
  quote_id: string;
  plan_id: string;
  plan_version: number;
  total_minor: number;
  currency: string;
  expires_at: string;
  requires_confirmation: boolean;
}
export interface Order {
  order_id: string;
  trip_id: string;
  quote_id: string;
  total_minor: number;
  currency: string;
  status: string;
  created_at: string;
  plan: Plan;
}
export interface TripState {
  trip_id: string;
  version: number;
  status: string;
  intent: Intent;
  reference_now: string;
  origin_timezone: string;
  plans: Plan[];
  selected_plan_id: string | null;
  questions: { key: string; label: string; suggestions: string[] }[];
  assumptions: string[];
  messages: { role: string; text: string }[];
  delta: null | {
    changed_fields: string[];
    preserved_offer_ids: string[];
    invalidated_offer_ids: string[];
    price_delta_minor: number | null;
    summary: string[];
  };
  quote: Quote | null;
  order: Order | null;
  action_trace: { tool: string; status: string; detail: string }[];
  llm: {
    mode: string;
    model: string | null;
    used: boolean;
    reason: string | null;
  };
  warnings: string[];
  locked_component_ids: string[];
}
export interface Capabilities {
  llm: {
    mode: string;
    primary_model: string;
    fallback_model: string;
    free_only: boolean;
  };
  catalog: {
    origins: { id: string; name: string }[];
    destinations: { id: string; name: string }[];
    date_from: string;
    date_to: string;
    min_nights: number;
    max_nights: number;
  };
  data_sources: Record<string, unknown>[];
}
export interface HistoryItem {
  trip_id: string;
  version: number;
  status: string;
  title: string;
  updated_at: string;
}
