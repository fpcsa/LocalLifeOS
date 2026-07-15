import type { components } from "@locallife/shared-types";

type Schemas = components["schemas"];

export type Account = Schemas["FinancialAccountResponse"];
export type AccountCreate = Schemas["FinancialAccountCreateRequest"];
export type Attachment = Schemas["AttachmentResponse"];
export type Budget = Schemas["BudgetResponse"];
export type BudgetConsumption = Schemas["BudgetConsumptionResponse"];
export type BudgetCreate = Schemas["BudgetCreateRequest"];
export type CalendarConflict = Schemas["CalendarConflictResponse"];
export type CalendarEvent = Schemas["CalendarEventResponse"];
export type CalendarEventCreate = Schemas["CalendarEventCreateRequest"];
export type CalendarMove = Schemas["CalendarMoveRequest"];
export type CalendarResize = Schemas["CalendarResizeRequest"];
export type CapacityReport = Schemas["CapacityReport"];
export type CashFlowReport = Schemas["CashFlowReportResponse"];
export type Commitment = Schemas["CommitmentResponse"];
export type CommitmentCreate = Schemas["CommitmentCreateRequest"];
export type CommitmentUpdate = Schemas["CommitmentUpdateRequest"];
export type CommitmentAssessment = Schemas["CommitmentAssessmentResponse"];
export type CommitmentImpact = Schemas["CommitmentImpactResponse"];
export type CommitmentLink = Schemas["CommitmentLinkResponse"];
export type CommitmentWarnings = Schemas["CommitmentWarningsResponse"];
export type Goal = Schemas["GoalResponse"];
export type GoalCreate = Schemas["GoalCreateRequest"];
export type Note = Schemas["NoteResponse"];
export type NoteCreate = Schemas["NoteCreateRequest"];
export type NoteUpdate = Schemas["NoteUpdateRequest"];
export type PaginationMeta = Schemas["PaginationMeta"];
export type PlannedTransaction = Schemas["PlannedTransactionResponse"];
export type Preferences = Schemas["PreferencesResponse"];
export type PreferencesUpdate = Schemas["PreferencesUpdate"];
export type Project = Schemas["ProjectResponse"];
export type ProjectCreate = Schemas["ProjectCreateRequest"];
export type SavingsGoal = Schemas["SavingsGoalResponse"];
export type SavingsGoalCreate = Schemas["SavingsGoalCreateRequest"];
export type SchedulingPreview = Schemas["SchedulingPreviewResponse"];
export type SchedulingApply = Schemas["SchedulingApplyResponse"];
export type Scenario = Schemas["ScenarioResponse"];
export type ScenarioChange = Schemas["ScenarioChangeResponse"];
export type ScenarioPreview = Schemas["ScenarioPreviewResponse"];
export type ScenarioCompare = Schemas["ScenarioCompareResponse"];
export type SpendingReport = Schemas["SpendingByCategoryReportResponse"];
export type CommittedBalanceReport = Schemas["CommittedBalanceReportResponse"];
export type Subscription = Schemas["SubscriptionResponse"];
export type Tag = Schemas["TagResponse"];
export type Task = Schemas["TaskResponse"];
export type TaskCreate = Schemas["TaskCreateRequest"];
export type TaskUpdate = Schemas["TaskUpdateRequest"];
export type TimelineItem = Schemas["UnifiedTimelineItem"];
export type Transaction = Schemas["TransactionResponse"];
export type TransactionCategory = Schemas["TransactionCategoryResponse"];
export type TransactionCreate = Schemas["TransactionCreateRequest"];
export type TransferCreate = Schemas["TransferCreateRequest"];
export type ImportBatch = Schemas["ImportBatchResponse"];
export type ImportPreview = Schemas["ImportPreviewResponse"];
export type ImportRow = Schemas["ImportRowResponse"];
export type CsvMapping = Schemas["CsvMappingRequest"];
export type CsvMappingProfile = Schemas["CsvMappingProfileResponse"];
export type AutomationRule = Schemas["AutomationRuleResponse"];
export type AutomationRuleCreate = Schemas["AutomationRuleCreateRequest"];
export type AutomationRuleUpdate = Schemas["AutomationRuleUpdateRequest"];
export type AutomationPreview = Schemas["AutomationPreviewResponse"];
export type AutomationExecution = Schemas["AutomationExecutionResponse"];
export type LocalNotification = Schemas["NotificationResponse"];
export type SchedulerStatus = Schemas["SchedulerStatusResponse"];

export interface DataEnvelope<T> {
  data: T;
}

export interface ListEnvelope<T> {
  data: T[];
  meta: PaginationMeta;
}

export interface PageParams {
  page?: number;
  page_size?: number;
  q?: string;
}
