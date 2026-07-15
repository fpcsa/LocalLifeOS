"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeftRight, Landmark, Plus, Tags } from "lucide-react";
import { useState } from "react";
import { CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Panel, PanelHeader } from "@/components/ui/panel";
import { Progress } from "@/components/ui/progress";
import { EmptyState, ErrorState, SkeletonList } from "@/components/ui/states";
import { getPreferences } from "@/lib/api/connected";
import {
  getBudgetConsumption,
  getCashFlowReport,
  getCommittedBalance,
  getSpendingReport,
  listAccounts,
  listBudgets,
  listCategories,
  listSavingsGoals,
  listSubscriptions,
  listTransactions,
} from "@/lib/api/finance";
import { queryKeys } from "@/lib/api/query-keys";
import { currentMonthDates } from "@/lib/date-range";
import { currencyDigits, formatDate, formatDateTime, formatMoney } from "@/lib/format";

import { FinanceForms, type FinanceFormKind } from "./finance-forms";

function monthRange(): { reportStart: string; startDate: string; endDate: string } {
  const now = new Date();
  return {
    reportStart: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() - 5, 1)).toISOString().slice(0, 10),
    ...currentMonthDates("UTC", now),
  };
}

function ChartFrame({ label, children }: { label: string; children: React.ReactNode }) {
  return <div aria-label={label} className="h-64 w-full" role="img">{children}</div>;
}

export function FinanceWorkspace() {
  const [form, setForm] = useState<FinanceFormKind | null>(null);
  const range = monthRange();
  const preferences = useQuery({ queryKey: queryKeys.system.preferences, queryFn: getPreferences });
  const accounts = useQuery({ queryKey: queryKeys.finance.accounts, queryFn: listAccounts });
  const transactions = useQuery({ queryKey: queryKeys.finance.transactions({ page_size: 100 }), queryFn: () => listTransactions({ page_size: 100, order: "desc" }) });
  const categories = useQuery({ queryKey: queryKeys.finance.categories, queryFn: listCategories });
  const budgets = useQuery({ queryKey: queryKeys.finance.budgets, queryFn: listBudgets });
  const cashFlow = useQuery({ queryKey: queryKeys.finance.cashFlow({ start: range.reportStart, months: 6 }), queryFn: () => getCashFlowReport(range.reportStart, 6) });
  const spending = useQuery({ queryKey: queryKeys.finance.spending(range), queryFn: () => getSpendingReport(range.startDate, range.endDate) });
  const committed = useQuery({ queryKey: queryKeys.finance.committed(range.endDate), queryFn: () => getCommittedBalance(new Date().toISOString().slice(0, 10), range.endDate) });
  const subscriptions = useQuery({ queryKey: queryKeys.finance.subscriptions, queryFn: listSubscriptions });
  const savings = useQuery({ queryKey: queryKeys.finance.savingsGoals, queryFn: listSavingsGoals });
  const budgetConsumption = useQueries({ queries: (budgets.data?.data || []).map((budget) => ({ queryKey: queryKeys.finance.budgetConsumption(budget.id), queryFn: () => getBudgetConsumption(budget.id) })) });
  const required = [accounts, transactions, categories, budgets, cashFlow, spending, committed, subscriptions, savings];
  const loading = required.some((query) => query.isLoading);
  const failed = required.some((query) => query.isError);
  if (loading) return <SkeletonList rows={10} />;
  if (failed) return <ErrorState description="One or more local finance summaries could not be calculated." retry={() => required.forEach((query) => void query.refetch())} />;

  const primaryCash = cashFlow.data?.groups[0];
  const primarySpending = spending.data?.groups[0];
  const digits = primaryCash ? currencyDigits(primaryCash.currency) : 2;
  const cashData = (primaryCash?.months || []).map((month) => ({ month: month.month, income: month.actual_income_minor + month.planned_income_minor, expense: month.actual_expense_minor + month.planned_expense_minor, balance: month.projected_ending_balance_minor }));
  const spendingData = (primarySpending?.categories || []).filter((item) => item.actual_minor || item.planned_minor).map((item) => ({ name: item.category_name, value: item.actual_minor + item.planned_minor }));
  const timezone = preferences.data?.timezone || "UTC";
  const accountById = new Map((accounts.data?.data || []).map((account) => [account.id, account]));
  const categoryById = new Map((categories.data?.data || []).map((category) => [category.id, category]));
  return (
    <div className="space-y-6">
      <PageHeader title="Finance" description="Local ledger balances, budgets, cash flow, subscriptions, and savings—stored in exact minor units." actions={<><Button onClick={() => setForm("account")} type="button" variant="secondary"><Landmark aria-hidden="true" className="h-4 w-4" />Account</Button><Button onClick={() => setForm("transaction")} type="button"><Plus aria-hidden="true" className="h-4 w-4" />Transaction</Button></>} />
      <nav aria-label="Finance sections" className="flex gap-2 overflow-x-auto pb-1">{["Accounts", "Transactions", "Budgets", "Reports", "Subscriptions", "Savings"].map((item) => <a className="inline-flex min-h-10 shrink-0 items-center rounded-md bg-accent px-3 text-sm font-medium hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" href={`#${item.toLowerCase()}`} key={item}>{item}</a>)}</nav>
      <section className="space-y-3" id="accounts"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Accounts</h2></div>{!accounts.data?.data.length ? <Panel><EmptyState title="No accounts" description="Create an account before recording transactions." action={<Button onClick={() => setForm("account")} type="button">Create account</Button>} /></Panel> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">{accounts.data.data.map((account) => <Panel className="p-4" key={account.id}><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-medium">{account.name}</p><p className="mt-1 text-xs capitalize text-muted-foreground">{account.account_type}</p></div>{account.below_financial_buffer ? <Badge tone="danger">Below buffer</Badge> : <Badge tone="success">Available</Badge>}</div><p className="mt-5 text-2xl font-semibold tabular-nums">{formatMoney(account.balance_minor, account.currency_code)}</p><p className="mt-1 text-xs text-muted-foreground">Buffer {formatMoney(account.financial_buffer_minor, account.currency_code)}</p></Panel>)}</div>}</section>
      <section id="transactions"><Panel><PanelHeader title="Transactions" description="Income, expenses, and balanced account transfers." action={<div className="flex gap-2"><Button onClick={() => setForm("category")} size="sm" type="button" variant="ghost"><Tags aria-hidden="true" className="h-4 w-4" />Category</Button><Button onClick={() => setForm("transaction")} size="sm" type="button" variant="secondary"><ArrowLeftRight aria-hidden="true" className="h-4 w-4" />Record</Button></div>} />{!transactions.data?.data.length ? <EmptyState title="No transactions" description="Record income, an expense, or a transfer to begin the ledger." /> : <div className="overflow-x-auto"><table className="w-full min-w-[44rem] text-left text-sm"><thead className="bg-muted text-xs text-muted-foreground"><tr><th className="px-4 py-3 font-medium">Date</th><th className="px-4 py-3 font-medium">Payee</th><th className="px-4 py-3 font-medium">Account</th><th className="px-4 py-3 font-medium">Category</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 text-right font-medium">Amount</th></tr></thead><tbody className="divide-y divide-border">{transactions.data.data.map((item) => <tr key={item.id}><td className="px-4 py-3 text-muted-foreground">{formatDateTime(item.occurred_at, timezone)}</td><td className="px-4 py-3 font-medium">{item.payee || item.note || "—"}</td><td className="px-4 py-3">{accountById.get(item.account_id)?.name || "Account"}</td><td className="px-4 py-3">{item.category_id ? categoryById.get(item.category_id)?.name || "Category" : "—"}</td><td className="px-4 py-3"><Badge tone={item.transaction_type === "income" ? "success" : "neutral"}>{item.transaction_type}</Badge></td><td className="px-4 py-3 text-right font-medium tabular-nums">{formatMoney(item.amount_minor, item.currency_code)}</td></tr>)}</tbody></table></div>}</Panel></section>
      <section className="space-y-3" id="budgets"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Budgets</h2><Button onClick={() => setForm("budget")} size="sm" type="button" variant="secondary">Create budget</Button></div>{!budgets.data?.data.length ? <Panel><EmptyState title="No budgets" description="Set category limits for a week, month, quarter, year, or custom range." /></Panel> : <div className="grid gap-4 xl:grid-cols-2">{budgets.data.data.map((budget, index) => { const consumption = budgetConsumption[index]?.data; const used = consumption?.total_limit_minor ? ((consumption.total_actual_minor + consumption.total_planned_minor) / consumption.total_limit_minor) * 100 : 0; return <Panel className="p-4" key={budget.id}><div className="flex items-start justify-between gap-3"><div><p className="font-medium">{budget.name}</p><p className="mt-1 text-xs capitalize text-muted-foreground">{budget.period} · from {formatDate(budget.start_date, timezone)}</p></div><Badge tone={used > 100 ? "danger" : used > 80 ? "warning" : "neutral"}>{used.toFixed(0)}%</Badge></div><div className="mt-4"><Progress label={`${budget.name} consumption`} value={used} /></div><div className="mt-4 grid grid-cols-3 gap-2 text-xs"><div><p className="text-muted-foreground">Limit</p><p className="mt-1 font-medium">{formatMoney(consumption?.total_limit_minor || 0, budget.currency_code)}</p></div><div><p className="text-muted-foreground">Actual</p><p className="mt-1 font-medium">{formatMoney(consumption?.total_actual_minor || 0, budget.currency_code)}</p></div><div><p className="text-muted-foreground">Planned</p><p className="mt-1 font-medium">{formatMoney(consumption?.total_planned_minor || 0, budget.currency_code)}</p></div></div></Panel>; })}</div>}</section>
      <section className="space-y-4" id="reports"><h2 className="text-lg font-semibold">Reports</h2><div className="grid gap-5 xl:grid-cols-2"><Panel><PanelHeader title="Six-month cash flow" description={primaryCash ? `Income, expenses, and projected balance in ${primaryCash.currency}.` : "No currency data yet."} />{primaryCash ? <div className="space-y-4 p-4"><ChartFrame label={`Cash flow chart in ${primaryCash.currency}`}><ResponsiveContainer height="100%" width="100%"><LineChart data={cashData} margin={{ left: 12, right: 12 }}><CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} tickFormatter={(value) => `${(Number(value) / 10 ** digits).toFixed(0)}`} /><Tooltip formatter={(value) => formatMoney(Number(value), primaryCash.currency)} /><Legend /><Line dataKey="income" name="Income" stroke="hsl(var(--success))" strokeWidth={2} /><Line dataKey="expense" name="Expense" stroke="hsl(var(--destructive))" strokeWidth={2} /><Line dataKey="balance" name="Balance" stroke="hsl(var(--foreground))" strokeWidth={2} /></LineChart></ResponsiveContainer></ChartFrame><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted-foreground"><th className="py-2">Month</th><th className="py-2 text-right">Income</th><th className="py-2 text-right">Expense</th><th className="py-2 text-right">Balance</th></tr></thead><tbody>{cashData.map((item) => <tr className="border-t border-border" key={item.month}><td className="py-2">{item.month}</td><td className="py-2 text-right">{formatMoney(item.income, primaryCash.currency)}</td><td className="py-2 text-right">{formatMoney(item.expense, primaryCash.currency)}</td><td className="py-2 text-right">{formatMoney(item.balance, primaryCash.currency)}</td></tr>)}</tbody></table></div></div> : <EmptyState title="No cash-flow data" description="Add an account and transactions to calculate the report." />}</Panel><Panel><PanelHeader title="Spending by category" description={primarySpending ? `Actual plus planned spending in ${primarySpending.currency}.` : "No expense data this month."} />{primarySpending && spendingData.length ? <div className="space-y-4 p-4"><ChartFrame label={`Spending by category in ${primarySpending.currency}`}><ResponsiveContainer height="100%" width="100%"><PieChart><Pie data={spendingData} dataKey="value" nameKey="name" innerRadius={48} outerRadius={88}>{spendingData.map((item, index) => <Cell fill={index % 2 ? "hsl(var(--muted-foreground))" : "hsl(var(--primary))"} key={item.name} />)}</Pie><Tooltip formatter={(value) => formatMoney(Number(value), primarySpending.currency)} /></PieChart></ResponsiveContainer></ChartFrame><ul className="space-y-2">{spendingData.map((item) => <li className="flex justify-between gap-4 text-sm" key={item.name}><span>{item.name}</span><span className="font-medium tabular-nums">{formatMoney(item.value, primarySpending.currency)}</span></li>)}</ul></div> : <EmptyState title="No category spending" description="Categorised expenses and planned transactions appear here." />}</Panel></div><Panel><PanelHeader title="Committed balances" description={`Ledger balance after known commitments through ${range.endDate}.`} />{!committed.data?.groups.length ? <EmptyState title="No committed balance" description="Create an account to calculate effective availability." /> : <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">{committed.data.groups.map((group) => <div className="rounded-lg bg-muted p-4" key={group.currency}><div className="flex items-center justify-between"><p className="font-semibold">{group.currency}</p>{group.buffer_violation ? <Badge tone="danger">Buffer risk</Badge> : <Badge tone="success">Within buffer</Badge>}</div><p className="mt-4 text-2xl font-semibold">{formatMoney(group.effectively_available_minor, group.currency)}</p><p className="mt-1 text-xs text-muted-foreground">Effective availability after {formatMoney(group.committed_total_minor, group.currency)} committed</p></div>)}</div>}</Panel></section>
      <section id="subscriptions"><Panel><PanelHeader title="Subscriptions & price changes" description="Recurring services with locally detected price history." />{!subscriptions.data?.data.length ? <EmptyState title="No subscriptions" description="Subscription records created through the API will appear here." /> : <ul className="divide-y divide-border">{subscriptions.data.data.map((item) => { const latest = item.price_changes.at(-1); return <li className="flex flex-wrap items-center justify-between gap-3 p-4" key={item.id}><div><p className="text-sm font-medium">{item.name}</p><p className="mt-1 text-xs text-muted-foreground">{item.billing_rrule} · {item.status}</p></div><div className="text-right"><p className="text-sm font-semibold">{formatMoney(item.amount_minor, item.currency_code)}</p>{latest ? <p className="mt-1 flex items-center gap-1 text-xs text-warning"><AlertTriangle aria-hidden="true" className="h-3 w-3" />Changed by {formatMoney(latest.delta_minor, item.currency_code)}</p> : <p className="mt-1 text-xs text-muted-foreground">No price changes</p>}</div></li>; })}</ul>}</Panel></section>
      <section className="space-y-3" id="savings"><div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Savings goals</h2><Button onClick={() => setForm("savings")} size="sm" type="button" variant="secondary">Create goal</Button></div>{!savings.data?.data.length ? <Panel><EmptyState title="No savings goals" description="Set a target amount and optionally link the account holding it." /></Panel> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{savings.data.data.map((goal) => <Panel className="p-4" key={goal.id}><div className="flex items-start justify-between gap-2"><p className="font-medium">{goal.name}</p><Badge>{goal.status}</Badge></div><p className="mt-4 text-xl font-semibold">{formatMoney(goal.current_minor, goal.currency_code)}</p><p className="mt-1 text-xs text-muted-foreground">of {formatMoney(goal.target_minor, goal.currency_code)} · {goal.target_date ? formatDate(goal.target_date, timezone) : "no target date"}</p><div className="mt-4"><Progress label={`${goal.name} savings progress`} value={goal.progress_basis_points / 100} /></div></Panel>)}</div>}</section>
      <FinanceForms accounts={accounts.data?.data || []} categories={categories.data?.data || []} close={() => setForm(null)} form={form} />
    </div>
  );
}
