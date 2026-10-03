// TypeScript mirror of backend/app/contracts and backend/app/domain.
// Keep in sync with the backend; the README "Contract decisions" section is the source of truth.

// ---------- Profile ----------

export type Source = 'stated' | 'edited' | 'assumption'

/** `value: null` means the user said "I don't know". Unknown is never zero. */
export interface ProfileValue<T> {
  value: T | null
  source: Source
  confirmed: boolean
}

export type ExpenseCategory =
  | 'final_expenses'
  | 'education'
  | 'debt_payoff'
  | 'mortgage_payoff'
  | 'other'

export interface OneTimeExpense {
  id: string
  label: string
  category: ExpenseCategory
  /** Whole USD dollars. */
  amount: number
}

export interface AssumptionFlags {
  mortgage_payment_in_annual_support: boolean | null
  education_in_annual_support: boolean | null
}

/** A field that is `null` has not been asked yet. */
export interface Profile {
  dependents_count: ProfileValue<number> | null
  youngest_dependent_age: ProfileValue<number> | null
  annual_support_need: ProfileValue<number> | null
  annual_survivor_contribution: ProfileValue<number> | null
  support_years: ProfileValue<number> | null
  one_time_expenses: ProfileValue<OneTimeExpense[]> | null
  available_assets: ProfileValue<number> | null
  personal_coverage: ProfileValue<number> | null
  employer_coverage: ProfileValue<number> | null
  budget_monthly: ProfileValue<number> | null
  assumption_flags: AssumptionFlags
}

export type ProfileFieldName = Exclude<keyof Profile, 'assumption_flags'>

// ---------- Questions ----------

export type InputType = 'integer' | 'currency' | 'expenses' | 'confirm'

export interface NextQuestion {
  /** A ProfileFieldName, or "review" for the confirmation step. */
  field: ProfileFieldName | 'review'
  text: string
  input_type: InputType
  min: number | null
  max: number | null
  allow_unknown: boolean
  review_fields: ProfileFieldName[]
}

// ---------- Assessment ----------

export type AssessmentStatus = 'incomplete' | 'partial' | 'complete'

export type LineItemCode =
  | 'ongoing_support'
  | 'one_time_expenses'
  | 'available_assets'
  | 'personal_coverage'
  | 'employer_coverage'
  | 'additional_gap'

export interface LineItem {
  code: LineItemCode
  label: string
  /** Signed amount actually applied; rows 1-5 sum to row 6. */
  amount: number
  /** For offsets: what the user entered (may exceed what was applied). */
  entered_amount: number | null
  display_order: number
}

export interface AssessmentPreview {
  status: AssessmentStatus
  calculation_version: string
  currency: string
  missing_fields: string[]
  unresolved_fields: string[]
  annual_shortfall: number | null
  support_years: number | null
  line_items: LineItem[]
  additional_coverage_gap: number | null
  assumptions: string[]
  warnings: string[]
  explanation: string | null
  disclaimer: string
  limitations: string[]
}

export interface AssessmentResponse extends AssessmentPreview {
  id: string
  profile_revision: number
  is_current: boolean
  stale_reason: string | null
  created_at: string
}

// ---------- Sessions / profile / messages ----------

export interface SessionCreatedResponse {
  session_id: string
  revision: number
  access_token: string
  expires_at: string
}

export interface TokenResponse {
  access_token: string
  expires_at: string
}

export interface ProfileResponse {
  session_id: string
  revision: number
  profile: Profile
  next_question: NextQuestion | null
  assessment: AssessmentPreview
}

export interface SessionResponse extends ProfileResponse {
  turn_count: number
  turn_limit: number
  expires_at: string
}

export interface MessageOut {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

export interface MessagesResponse {
  session_id: string
  messages: MessageOut[]
}

export interface MessageResponse extends ProfileResponse {
  /** Never contains amounts; render numbers from `assessment`. */
  assistant_message: string
  warnings: string[]
}

// ---------- Requests ----------

/** Include a key to set it; send `null` for "I don't know". Omitted keys are unchanged. */
export type ProfileUpdates = Partial<{
  [K in ProfileFieldName]: NonNullable<Profile[K]>['value']
}> & {
  assumption_flags?: Partial<AssumptionFlags>
}

export interface ProfilePatchRequest {
  expected_revision: number
  client_request_id: string
  updates?: ProfileUpdates
  confirm?: ProfileFieldName[]
}

export interface MessageRequest {
  text: string
  client_request_id: string
  expected_revision: number
}

export interface ScenarioOverrides {
  annual_support_need?: number
  annual_survivor_contribution?: number
  support_years?: number
  available_assets?: number
  personal_coverage?: number
  employer_coverage?: number
  exclude_employer_coverage?: boolean
}

export interface ScenarioRequest {
  base_revision: number
  scenarios: { name: string; overrides: ScenarioOverrides }[]
}

export interface ScenarioResponse {
  base_revision: number
  base: AssessmentPreview
  scenarios: { name: string; overrides: Record<string, unknown>; result: AssessmentPreview }[]
  /** Min/max gap across base and scenarios. Not a probability range. */
  range: { low: number; high: number } | null
}

// ---------- Content ----------

export interface CoverageTypesResponse {
  content_version: string
  review_status: string
  coverage_types: { id: string; title: string; summary: string; points: string[] }[]
  resources: { title: string; summary: string; url: string; source_owner: string }[]
  disclaimer: string
}

// ---------- Errors ----------

export type ErrorCode =
  | 'validation_error'
  | 'unauthorized'
  | 'session_expired'
  | 'not_found'
  | 'stale_revision'
  | 'duplicate_request'
  | 'payload_too_large'
  | 'turn_limit_exceeded'
  | 'internal_error'

export interface ErrorBody {
  code: ErrorCode | string
  message: string
  request_id: string | null
  current_revision?: number | null
  details?: Record<string, unknown>[] | null
}
