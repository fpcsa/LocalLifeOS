import type { components } from "@locallife/shared-types";

import { apiRequest, jsonBody, withQuery } from "./client";
import type {
  Account,
  AccountCreate,
  Budget,
  BudgetConsumption,
  BudgetCreate,
  CashFlowReport,
  CommittedBalanceReport,
  DataEnvelope,
  ListEnvelope,
  PlannedTransaction,
  SavingsGoal,
  SavingsGoalCreate,
  SpendingReport,
  Subscription,
  Transaction,
  TransactionCategory,
  TransactionCreate,
  TransferCreate,
} from "./types";

type Schemas = components["schemas"];

export interface TransactionFilters {
  page?: number;
  page_size?: number;
  q?: string;
  account_id?: string;
  category_id?: string;
  type?: Schemas["TransactionType"];
  currency?: string;
  start?: string;
  end?: string;
  order?: "asc" | "desc";
}

export async function listAccounts(): Promise<ListEnvelope<Account>> {
  return apiRequest<ListEnvelope<Account>>(withQuery("/finance/accounts", { page_size: 100 }));
}

export async function createAccount(payload: AccountCreate): Promise<Account> {
  return (
    await apiRequest<DataEnvelope<Account>>("/finance/accounts", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listTransactions(
  filters: TransactionFilters = {},
): Promise<ListEnvelope<Transaction>> {
  return apiRequest<ListEnvelope<Transaction>>(
    withQuery("/finance/transactions", { page_size: 100, ...filters }),
  );
}

export async function createTransaction(payload: TransactionCreate): Promise<Transaction> {
  return (
    await apiRequest<DataEnvelope<Transaction>>("/finance/transactions", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function createTransfer(payload: TransferCreate): Promise<Transaction> {
  return (
    await apiRequest<DataEnvelope<Transaction>>("/finance/transfers", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listPlannedTransactions(
  filters: TransactionFilters = {},
): Promise<PlannedTransaction[]> {
  return (
    await apiRequest<DataEnvelope<PlannedTransaction[]>>(
      withQuery("/finance/transactions/planned", { page_size: 100, ...filters }),
    )
  ).data;
}

export async function createPlannedTransaction(
  payload: Schemas["PlannedTransactionCreateRequest"],
): Promise<PlannedTransaction> {
  return (
    await apiRequest<DataEnvelope<PlannedTransaction>>("/finance/transactions/planned", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listCategories(): Promise<ListEnvelope<TransactionCategory>> {
  return apiRequest<ListEnvelope<TransactionCategory>>(
    withQuery("/finance/categories", { page_size: 100 }),
  );
}

export async function createCategory(
  payload: Schemas["TransactionCategoryCreateRequest"],
): Promise<TransactionCategory> {
  return (
    await apiRequest<DataEnvelope<TransactionCategory>>("/finance/categories", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function listBudgets(): Promise<ListEnvelope<Budget>> {
  return apiRequest<ListEnvelope<Budget>>(withQuery("/finance/budgets", { page_size: 100 }));
}

export async function createBudget(payload: BudgetCreate): Promise<Budget> {
  return (
    await apiRequest<DataEnvelope<Budget>>("/finance/budgets", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}

export async function getBudgetConsumption(budgetId: string): Promise<BudgetConsumption> {
  return (
    await apiRequest<DataEnvelope<BudgetConsumption>>(
      `/finance/budgets/${budgetId}/consumption`,
    )
  ).data;
}

export async function getCashFlowReport(startDate: string, months = 6): Promise<CashFlowReport> {
  return (
    await apiRequest<DataEnvelope<CashFlowReport>>(
      withQuery("/finance/reports/cash-flow", { start_date: startDate, months }),
    )
  ).data;
}

export async function getSpendingReport(
  startDate: string,
  endDate: string,
): Promise<SpendingReport> {
  return (
    await apiRequest<DataEnvelope<SpendingReport>>(
      withQuery("/finance/reports/spending-by-category", {
        start_date: startDate,
        end_date: endDate,
      }),
    )
  ).data;
}

export async function getCommittedBalance(
  asOf: string,
  endDate: string,
): Promise<CommittedBalanceReport> {
  return (
    await apiRequest<DataEnvelope<CommittedBalanceReport>>(
      withQuery("/finance/reports/committed-balance", { as_of: asOf, end_date: endDate }),
    )
  ).data;
}

export async function listSubscriptions(): Promise<ListEnvelope<Subscription>> {
  return apiRequest<ListEnvelope<Subscription>>(
    withQuery("/finance/subscriptions", { page_size: 100 }),
  );
}

export async function listSavingsGoals(): Promise<ListEnvelope<SavingsGoal>> {
  return apiRequest<ListEnvelope<SavingsGoal>>(
    withQuery("/finance/savings-goals", { page_size: 100 }),
  );
}

export async function createSavingsGoal(payload: SavingsGoalCreate): Promise<SavingsGoal> {
  return (
    await apiRequest<DataEnvelope<SavingsGoal>>("/finance/savings-goals", {
      method: "POST",
      ...jsonBody(payload),
    })
  ).data;
}
