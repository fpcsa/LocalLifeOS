"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form-controls";
import { Modal } from "@/components/ui/modal";
import {
  createAccount,
  createBudget,
  createCategory,
  createSavingsGoal,
  createTransaction,
  createTransfer,
} from "@/lib/api/finance";
import { queryKeys } from "@/lib/api/query-keys";
import type { Account, TransactionCategory } from "@/lib/api/types";
import { fromDateTimeLocal, majorToMinor, toDateTimeLocal } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";

export type FinanceFormKind = "account" | "budget" | "category" | "savings" | "transaction";

interface AccountValues { name: string; type: Account["account_type"]; currency: string; opening: string; buffer: string }
interface TransactionValues { type: "income" | "expense" | "transfer"; accountId: string; destinationId: string; amount: string; currency: string; occurredAt: string; categoryId: string; payee: string; note: string }
interface BudgetValues { name: string; currency: string; period: "weekly" | "monthly" | "quarterly" | "yearly" | "custom"; start: string; end: string; categoryId: string; limit: string }
interface SavingsValues { name: string; accountId: string; currency: string; current: string; target: string; targetDate: string }

function localNow(timezone: string): string {
  return toDateTimeLocal(new Date().toISOString(), timezone);
}

function FormActions({ close, pending, label }: { close: () => void; pending: boolean; label: string }) {
  return <div className="flex justify-end gap-2"><Button onClick={close} type="button" variant="ghost">Cancel</Button><Button loading={pending} type="submit">{label}</Button></div>;
}

export function FinanceForms({ form, close, accounts, categories, timezone }: { form: FinanceFormKind | null; close: () => void; accounts: Account[]; categories: TransactionCategory[]; timezone: string }) {
  const queryClient = useQueryClient();
  const pushToast = useUiStore((state) => state.pushToast);
  const refresh = async () => queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
  const succeeded = async (title: string) => { await refresh(); pushToast({ title, tone: "success" }); close(); };
  const failed = (title: string) => (error: unknown) => pushToast({ title, description: error instanceof Error ? error.message : "Check the values and try again.", tone: "error" });

  const accountForm = useForm<AccountValues>({ defaultValues: { name: "", type: "checking", currency: "EUR", opening: "0", buffer: "0" } });
  const account = useMutation({ mutationFn: (values: AccountValues) => createAccount({ name: values.name, account_type: values.type, currency_code: values.currency.toUpperCase(), opening_balance_minor: majorToMinor(values.opening, values.currency), financial_buffer_minor: majorToMinor(values.buffer, values.currency) }), onSuccess: () => succeeded("Account created"), onError: failed("Couldn't create account") });

  const transactionForm = useForm<TransactionValues>({ defaultValues: { type: "expense", accountId: "", destinationId: "", amount: "", currency: "EUR", occurredAt: localNow(timezone), categoryId: "", payee: "", note: "" } });
  const transactionType = useWatch({ control: transactionForm.control, name: "type" });
  const transaction = useMutation({ mutationFn: async (values: TransactionValues) => { const common = { amount_minor: majorToMinor(values.amount, values.currency), currency_code: values.currency.toUpperCase(), occurred_at: fromDateTimeLocal(values.occurredAt, timezone)!, payee: values.payee || null, note: values.note || null }; return values.type === "transfer" ? createTransfer({ ...common, source_account_id: values.accountId, destination_account_id: values.destinationId }) : createTransaction({ ...common, account_id: values.accountId, transaction_type: values.type, category_id: values.categoryId || null }); }, onSuccess: () => succeeded(transactionType === "transfer" ? "Transfer recorded" : "Transaction recorded"), onError: failed("Couldn't record transaction") });

  const categoryForm = useForm<{ name: string; kind: "income" | "expense" }>({ defaultValues: { name: "", kind: "expense" } });
  const category = useMutation({ mutationFn: createCategory, onSuccess: () => succeeded("Category created"), onError: failed("Couldn't create category") });

  const budgetForm = useForm<BudgetValues>({ defaultValues: { name: "", currency: "EUR", period: "monthly", start: new Date().toISOString().slice(0, 10), end: "", categoryId: "", limit: "" } });
  const budget = useMutation({ mutationFn: (values: BudgetValues) => createBudget({ name: values.name, currency_code: values.currency.toUpperCase(), period: values.period, start_date: values.start, end_date: values.end || null, limits: values.categoryId && values.limit ? [{ category_id: values.categoryId, limit_minor: majorToMinor(values.limit, values.currency) }] : [] }), onSuccess: () => succeeded("Budget created"), onError: failed("Couldn't create budget") });

  const savingsForm = useForm<SavingsValues>({ defaultValues: { name: "", accountId: "", currency: "EUR", current: "0", target: "", targetDate: "" } });
  const savings = useMutation({ mutationFn: (values: SavingsValues) => createSavingsGoal({ name: values.name, account_id: values.accountId || null, currency_code: values.currency.toUpperCase(), current_minor: majorToMinor(values.current, values.currency), target_minor: majorToMinor(values.target, values.currency), target_date: values.targetDate || null }), onSuccess: () => succeeded("Savings goal created"), onError: failed("Couldn't create savings goal") });

  return (
    <>
      <Modal onClose={close} open={form === "account"} title="Create account"><form className="space-y-4" onSubmit={accountForm.handleSubmit((values) => account.mutate(values))}><Field error={accountForm.formState.errors.name?.message} id="account-name" label="Name" required><Input id="account-name" {...accountForm.register("name", { required: "Enter an account name." })} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field id="account-type" label="Type"><Select id="account-type" {...accountForm.register("type")}><option value="cash">Cash</option><option value="checking">Checking</option><option value="savings">Savings</option><option value="credit">Credit</option><option value="investment">Investment</option><option value="other">Other</option></Select></Field><Field id="account-currency" label="Currency"><Input id="account-currency" maxLength={3} {...accountForm.register("currency", { required: true })} /></Field></div><div className="grid gap-4 sm:grid-cols-2"><Field id="account-opening" label="Opening balance"><Input id="account-opening" inputMode="decimal" {...accountForm.register("opening")} /></Field><Field id="account-buffer" label="Safety buffer"><Input id="account-buffer" inputMode="decimal" {...accountForm.register("buffer")} /></Field></div><FormActions close={close} label="Create account" pending={account.isPending} /></form></Modal>
      <Modal onClose={close} open={form === "transaction"} title="Record transaction" wide><form className="space-y-4" onSubmit={transactionForm.handleSubmit((values) => transaction.mutate(values))}><div className="grid gap-4 sm:grid-cols-3"><Field id="transaction-type" label="Type"><Select id="transaction-type" {...transactionForm.register("type")}><option value="expense">Expense</option><option value="income">Income</option><option value="transfer">Transfer</option></Select></Field><Field id="transaction-amount" label="Amount" required><Input id="transaction-amount" inputMode="decimal" {...transactionForm.register("amount", { required: "Enter an amount." })} /></Field><Field id="transaction-currency" label="Currency"><Input id="transaction-currency" maxLength={3} {...transactionForm.register("currency", { required: true })} /></Field></div><div className="grid gap-4 sm:grid-cols-2"><Field id="transaction-account" label={transactionType === "transfer" ? "From account" : "Account"} required><Select id="transaction-account" {...transactionForm.register("accountId", { required: true })}><option value="">Choose account</option>{accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>{transactionType === "transfer" ? <Field id="transaction-destination" label="To account" required><Select id="transaction-destination" {...transactionForm.register("destinationId", { required: transactionType === "transfer" })}><option value="">Choose account</option>{accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field> : <Field id="transaction-category" label="Category"><Select id="transaction-category" {...transactionForm.register("categoryId")}><option value="">Uncategorised</option>{categories.filter((item) => item.kind === transactionType).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field>}</div><Field id="transaction-date" label="Occurred at"><Input id="transaction-date" type="datetime-local" {...transactionForm.register("occurredAt", { required: true })} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field id="transaction-payee" label="Payee"><Input id="transaction-payee" {...transactionForm.register("payee")} /></Field><Field id="transaction-note" label="Note"><Textarea id="transaction-note" {...transactionForm.register("note")} /></Field></div><FormActions close={close} label="Record" pending={transaction.isPending} /></form></Modal>
      <Modal onClose={close} open={form === "category"} title="Create category"><form className="space-y-4" onSubmit={categoryForm.handleSubmit((values) => category.mutate(values))}><Field error={categoryForm.formState.errors.name?.message} id="category-name" label="Name" required><Input id="category-name" {...categoryForm.register("name", { required: "Enter a category name." })} /></Field><Field id="category-kind" label="Kind"><Select id="category-kind" {...categoryForm.register("kind")}><option value="expense">Expense</option><option value="income">Income</option></Select></Field><FormActions close={close} label="Create category" pending={category.isPending} /></form></Modal>
      <Modal onClose={close} open={form === "budget"} title="Create budget" wide><form className="space-y-4" onSubmit={budgetForm.handleSubmit((values) => budget.mutate(values))}><div className="grid gap-4 sm:grid-cols-2"><Field id="budget-name" label="Name" required><Input id="budget-name" {...budgetForm.register("name", { required: true })} /></Field><Field id="budget-currency" label="Currency"><Input id="budget-currency" maxLength={3} {...budgetForm.register("currency", { required: true })} /></Field></div><div className="grid gap-4 sm:grid-cols-3"><Field id="budget-period" label="Period"><Select id="budget-period" {...budgetForm.register("period")}><option value="weekly">Weekly</option><option value="monthly">Monthly</option><option value="quarterly">Quarterly</option><option value="yearly">Yearly</option><option value="custom">Custom</option></Select></Field><Field id="budget-start" label="Starts"><Input id="budget-start" type="date" {...budgetForm.register("start", { required: true })} /></Field><Field id="budget-end" label="Ends"><Input id="budget-end" type="date" {...budgetForm.register("end")} /></Field></div><fieldset className="rounded-lg border border-border p-4"><legend className="px-2 text-sm font-medium">First category limit</legend><div className="grid gap-4 sm:grid-cols-2"><Field id="budget-category" label="Expense category"><Select id="budget-category" {...budgetForm.register("categoryId")}><option value="">No limit yet</option>{categories.filter((item) => item.kind === "expense").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field id="budget-limit" label="Limit"><Input id="budget-limit" inputMode="decimal" {...budgetForm.register("limit")} /></Field></div></fieldset><FormActions close={close} label="Create budget" pending={budget.isPending} /></form></Modal>
      <Modal onClose={close} open={form === "savings"} title="Create savings goal"><form className="space-y-4" onSubmit={savingsForm.handleSubmit((values) => savings.mutate(values))}><Field id="savings-name" label="Name" required><Input id="savings-name" {...savingsForm.register("name", { required: true })} /></Field><div className="grid gap-4 sm:grid-cols-2"><Field id="savings-account" label="Linked account"><Select id="savings-account" {...savingsForm.register("accountId")}><option value="">No account</option>{accounts.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</Select></Field><Field id="savings-currency" label="Currency"><Input id="savings-currency" maxLength={3} {...savingsForm.register("currency", { required: true })} /></Field></div><div className="grid gap-4 sm:grid-cols-2"><Field id="savings-current" label="Current amount"><Input id="savings-current" inputMode="decimal" {...savingsForm.register("current")} /></Field><Field id="savings-target" label="Target amount" required><Input id="savings-target" inputMode="decimal" {...savingsForm.register("target", { required: true })} /></Field></div><Field id="savings-date" label="Target date"><Input id="savings-date" type="date" {...savingsForm.register("targetDate")} /></Field><FormActions close={close} label="Create savings goal" pending={savings.isPending} /></form></Modal>
    </>
  );
}
