/** Types for liaison command-center --json (hand-maintained v0). */

export interface CommandCenterSummary {
  total_tasks: number;
  open_tasks: number;
  closed_tasks: number;
  blockers: number;
  filtered_open: number;
  flywheel_open?: number;
  workload_id?: string | null;
  intake_ready?: boolean;
  ready_to_build?: boolean;
  ready_to_build_strict?: boolean;
  ready_to_build_soft?: boolean;
  executor_launch_ready?: boolean;
  intake_blockers?: number;
  has_project_plan?: boolean;
  executor_session_stale?: boolean;
  executor_session_stale_count?: number;
  debrief_age_days?: number | null;
  debrief_stale?: boolean;
  debrief_stale_days?: number;
}

export interface ProjectPlanGate {
  summary?: string;
  commands?: string[];
  blocked?: boolean;
  intake_note?: string;
}

export interface ProjectPlan {
  project: string;
  path: string;
  generated_at?: string;
  has_registry_plan?: boolean;
  has_on_disk_plan?: boolean;
  on_disk_path?: string | null;
  tier?: string;
  intent?: string;
  maturity_target?: string;
  workflow?: string;
  workflow_source?: string;
  pattern?: string | null;
  validation_profile?: string;
  external_guide?: string;
  research_gate?: ProjectPlanGate;
  engineering_gate?: ProjectPlanGate;
  backlog?: string[];
  intake?: {
    intake_ready?: boolean;
    ready_to_build?: boolean;
    recommended_lane?: string;
  };
  reporter_auto_advance?: boolean;
  liaison_cmd_write?: string;
}

export interface ProjectIntakeCheck {
  id: string;
  severity: string;
  pass: boolean;
  label: string;
  detail: string;
  liaison_cmd?: string | null;
  path?: string | null;
}

export interface ProjectIntakeBlocker {
  id: string;
  severity: string;
  label: string;
  detail: string;
  liaison_cmd?: string | null;
  path?: string | null;
}

export interface ProjectIntake {
  project: string;
  path: string;
  generated_at: string;
  intake_ready: boolean;
  ready_to_build: boolean;
  ready_to_build_strict?: boolean;
  ready_to_build_soft?: boolean;
  recommended_lane: string;
  checks: ProjectIntakeCheck[];
  blockers: ProjectIntakeBlocker[];
  summary?: {
    critical_fail?: number;
    warn_fail?: number;
    intake_blockers?: number;
  };
}

export interface ReporterStepStatus {
  init: boolean;
  snapshot: boolean;
  attach: boolean;
  approve: boolean;
  validate: boolean;
  close: boolean;
}

export interface ReporterStepState {
  current_step_id: string;
  completed_steps: string[];
  allowed_next: string[];
  updated_at?: string;
  task_id?: string;
}

export interface OperatorSession {
  project_key?: string;
  task_id?: string | null;
  pattern_id?: string | null;
  updated_at?: string;
}

export interface TerminalSession {
  id: string;
  agent_name: string;
  launch: string;
  pid?: number | null;
  started_at?: string;
  pane_title?: string;
  alive?: boolean;
  project_key?: string;
  repo_path?: string;
  task_id?: string;
  pattern_id?: string;
  engine?: string;
  status?: "running" | "ended";
  exit_code?: number | null;
  outcome?: string | null;
  ended_at?: string | null;
  log_excerpt?: string;
}

export interface WorkstationEngineSlot {
  engine: string;
  used: number;
  max: number;
  free: number;
  requires_gpu?: boolean;
}

export interface WorkstationUsage {
  running_ventures: number;
  max_active_ventures: number;
  ventures_free: number;
  engine_slots: WorkstationEngineSlot[];
  profile_defaults?: Record<string, unknown>;
}

export interface VentureQueueItem {
  id: string;
  project_key: string;
  task_id: string;
  pattern_id?: string;
  agent: string;
  engine?: string;
  priority?: number;
  status: string;
  created_at?: string;
}

export interface VentureQueueSummary {
  pending_count: number;
  running_count: number;
  total_items: number;
  max_active_ventures: number;
}

export interface ProjectMatrixRow {
  option: string;
  label: string;
  score: number;
  confidence: number;
  impact: string;
  effort: string;
  contributors: string;
  phase: string;
  lifecycle: string;
}

export interface AgentRow {
  name: string;
  display: string;
  status: string;
  registry_status: string;
  tasks: number;
  launch: string;
  role?: string;
  recommended?: boolean;
  output_contract?: string;
  handoff_guide?: string;
  hub_docs?: string;
  launch_note?: string;
  resume?: RolodexResume;
}

export interface ProjectAgentPattern {
  id: string;
  label: string;
  agents: string[];
  when: string;
  steps: string[];
}

export interface KanbanTask {
  task_id: string;
  description?: string;
  current_phase?: string;
  repo?: string;
  closed?: boolean;
  gate_status?: string;
  path?: string;
  reporter_steps?: ReporterStepStatus;
  last_executor_outcome?: string | null;
  bound_agent?: string | null;
}

export interface KanbanBuckets {
  todo: KanbanTask[];
  in_progress: KanbanTask[];
  review: KanbanTask[];
  done: KanbanTask[];
}

export interface HandoffChain {
  name: string;
  agents: string[];
  when: string;
}

export interface MetricsRow {
  id: string;
  label: string;
  detail: string;
  path?: string | null;
  liaison_cmd?: string;
}

export interface RolodexAction {
  label: string;
  liaison_cmd: string;
}

export interface RolodexNextStep {
  label: string;
  liaison_cmd?: string;
}

export interface RolodexResume {
  headline?: string;
  summary?: string;
  capabilities?: string[];
  best_for?: string;
  when_to_use?: string;
  outputs?: string;
  limits?: string;
}

export interface RolodexEntry {
  id: string;
  title: string;
  subtitle?: string;
  summary?: string;
  what?: string;
  when_to_use?: string;
  resume?: RolodexResume;
  next_steps?: RolodexNextStep[];
  launch?: string;
  path?: string;
  recommended?: boolean;
  actions?: RolodexAction[];
  meta?: Record<string, unknown>;
}

export interface RolodexCatalog {
  skills: RolodexEntry[];
  subagents: RolodexEntry[];
  projects: RolodexEntry[];
  commands: RolodexEntry[];
  tools: RolodexEntry[];
}

export interface PanelBriefSection {
  title: string;
  body: string;
  bullets?: string[];
}

export interface OverviewBrief {
  project: PanelBriefSection;
  work: PanelBriefSection;
  hub: PanelBriefSection;
  patterns: PanelBriefSection;
  ops: PanelBriefSection;
  playbook?: { id: string; label: string; detail: string }[];
}

export interface WorkstreamBrief {
  title: string;
  body: string;
  reporter_how_to?: string;
  sections?: PanelBriefSection[];
}

export interface ProductionCheckItem {
  id: string;
  label: string;
  done: boolean;
  detail?: string;
}

export interface HubWorkflowPattern {
  id: string;
  label: string;
  when: string;
  agents: string[];
  steps: string[];
  fit_score: number;
  fit_reason: string;
  recommended: boolean;
  liaison_cmd: string;
}

export interface ProjectDetail {
  key: string;
  label: string;
  path?: string;
  intent: string;
  maturity_target?: string;
  workflow?: string;
  pattern?: string | null;
  validation_profile?: string;
  tier?: string;
  agents: string[];
  specialists: string[];
  agent_chain: string;
  skills: string[];
  production_checklist: ProductionCheckItem[];
  research_summary?: string;
  research_commands: string[];
  backlog: string[];
  recommended_patterns: HubWorkflowPattern[];
  all_patterns: HubWorkflowPattern[];
  liaison_cmds: Record<string, string>;
}

export interface ProjectPortfolioDetail {
  project_key: string;
  intake_ready: boolean;
  ready_to_build: boolean;
  has_plan: boolean;
  plan_workflow?: string | null;
  corpus_trace_count: number;
  build_steps_recorded: number;
  intake_blockers?: number;
}

export interface ProjectPortfolioRow {
  key: string;
  label: string;
  score: number;
  phase: string;
  lifecycle: string;
  intent_short: string;
  agent_chain: string;
  pattern?: string | null;
  ready?: boolean;
}

export interface RolodexCategoryIntro {
  title: string;
  body: string;
}

export interface OverviewAction {
  id: string;
  label: string;
  detail: string;
  how_to?: string;
  liaison_cmd?: string;
  kind?: string;
  path?: string | null;
}

export interface OpsSignoffStep {
  id: string;
  label: string;
  done: boolean;
  liaison_cmd?: string;
  detail?: string;
  how_to?: string;
}

export interface OpsSignoff {
  pending_handoffs: HandoffRow[];
  pending_handoff_count: number;
  global_scope?: boolean;
  gate_failures: number;
  flywheel_open: number;
  debrief_age: string;
  debrief_age_days?: number | null;
  debrief_stale?: boolean;
  debrief_stale_days?: number;
  debrief_count: number;
  flywheel_phases?: WorkflowPhase[];
  flywheel_copy_cmds?: string[];
  checklist: OpsSignoffStep[];
  copy_hints: RolodexAction[];
  ready_for_signoff: boolean;
  summary?: string;
  playbook?: string[];
}

export interface ProjectRegistryEntry {
  key: string;
  path: string;
  label: string;
  default_profile: string;
  phase: string;
  lifecycle: string;
  score: number;
  has_registry_plan: boolean;
  has_on_disk_plan: boolean;
  plan_tier?: string | null;
  has_brief: boolean;
  has_phase: boolean;
  liaison_cmd_intake: string;
  liaison_cmd_plan: string;
  liaison_cmd_focus: string;
}

export interface BuildCorpusSummary {
  project?: string;
  build_steps_recorded?: number;
  exported_recipes?: number;
  open_tasks_with_build_trace?: number;
  recommended_pattern?: string | null;
  workflow?: string;
  liaison_record?: string;
  liaison_export?: string;
}

export interface HandoffRow {
  task_id: string;
  repo: string;
  artifact: string;
  status: string;
  phase: string;
  path?: string;
  project_key?: string;
}

export interface WorkflowPhase {
  id: string;
  label: string;
  objective?: string;
  artifacts?: string[];
  suggested_liaison_commands?: string[];
  missing_artifacts?: string[];
}

export interface WorkflowNextAction {
  action: string;
  liaison_cmd: string;
  hint: string;
  task_id?: string;
}

export interface TerminalBridgeInfo {
  mode: string;
  spawn_allowed: boolean;
  tmux_available?: boolean;
  wezterm_available?: boolean;
}

export interface DebriefRow {
  repo: string;
  file: string;
  age: string;
  path?: string;
}

export interface FocusState {
  project: string;
  path: string;
  phase: string;
  project_phase?: string;
  lifecycle: string;
  validation: string;
  recommended_agents: string[];
  exit_criteria: string[];
  default_profile?: string;
}

export interface EngineeringMetrics {
  gate_failures: number;
  pending_handoffs: number;
  promoted_learnings: number;
  reporter_tasks: number;
  executor_tasks: number;
  last_debrief_age?: string;
  debrief_age_days?: number | null;
  debrief_stale?: boolean;
  debrief_stale_days?: number;
  repos_with_profile?: number;
}

export interface CommandCenterState {
  generated_at: string;
  env: string;
  platform: string;
  user: string;
  refresh_sec: number;
  selected_project: string | null;
  active_task_id?: string | null;
  pattern_id?: string | null;
  operator_session?: OperatorSession | null;
  terminal_sessions?: TerminalSession[];
  workstation_profile?: Record<string, unknown>;
  workstation_usage?: WorkstationUsage;
  venture_queue?: VentureQueueItem[];
  venture_queue_summary?: VentureQueueSummary;
  summary: CommandCenterSummary;
  focus: FocusState | null;
  project_matrix: ProjectMatrixRow[];
  kanban: KanbanBuckets;
  agent_rows: AgentRow[];
  handoff_chains: HandoffChain[];
  handoffs: HandoffRow[];
  debriefs: DebriefRow[];
  metrics_rows: MetricsRow[];
  engineering_metrics: EngineeringMetrics;
  hub_skills_catalog?: Record<string, unknown[]>;
  project_agent_patterns?: ProjectAgentPattern[];
  project_intake?: ProjectIntake | null;
  project_plan?: ProjectPlan | null;
  build_corpus_summary?: BuildCorpusSummary | null;
  rolodex?: RolodexCatalog;
  ops_signoff?: OpsSignoff;
  overview_actions?: OverviewAction[];
  overview_brief?: OverviewBrief;
  workstream_brief?: WorkstreamBrief;
  project_detail?: ProjectDetail | null;
  project_portfolio?: ProjectPortfolioRow[];
  projects_portfolio_detail?: ProjectPortfolioDetail[];
  hub_workflows?: HubWorkflowPattern[];
  rolodex_category_intros?: Record<string, RolodexCategoryIntro>;
  projects_registry?: ProjectRegistryEntry[];
  workflow_phases?: WorkflowPhase[];
  next_workflow_step?: WorkflowPhase | null;
  suggested_workflow_commands?: string[];
  reporter_step_state?: ReporterStepState | null;
  workflow_next_action?: WorkflowNextAction | null;
  active_task_phase?: string | null;
  terminal_bridge?: TerminalBridgeInfo;
  sqlite_loaded?: boolean;
}
