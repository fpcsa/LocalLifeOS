# Finance engine

## Scope and guarantees

The finance engine is deterministic, local-only, and workspace-scoped. It stores money as integer
minor units paired with a validated ISO 4217 currency code. It never uses binary floating-point
money, downloads exchange rates, or silently combines currencies. Reports either filter one
currency or return a separate group for every currency represented by their inputs.

All editable records use optimistic revisions. Meaningful changes emit a timeline event in the
same database transaction. Report responses include their date inputs, currency filter,
assumptions, included/excluded source records, and calculation timestamp so a result can be
explained and reproduced from local data.

## Ledger and transfers

An account balance is derived from its opening balance and active posted transactions; no mutable
cached balance is stored. Income adds to its account and expense subtracts from it. A transfer is
one transaction with source and destination account IDs and two explicit effects: a negative
source effect and an equal positive destination effect. Both accounts must be different and use
the transfer currency. This representation keeps transfer creation atomic and cash-flow reports
can exclude the single neutral record without matching two rows later.

Importers may provide a workspace-scoped `import_fingerprint`. Duplicate actual or planned
fingerprints are rejected, providing an idempotency boundary without depending on a bank API.

## Actual, planned, recurring, and subscription records

Posted `transactions` are ledger facts. `planned_transactions` are projections with a lifecycle of
`planned`, `fulfilled`, or `cancelled`; they do not change account balances. Fulfilling a plan
atomically creates its posted transaction and records that transaction on the plan, preventing a
second fulfillment.

`recurring_transaction_rules` store canonical iCalendar RRULE values and can be active, paused, or
ended. Generation expands a bounded, timezone-aware half-open range and creates planned records.
Each generated row has a stable key made from the rule ID and UTC occurrence. The database unique
constraint and service lookup make repeat generation idempotent. Paused and ended rules do not
generate; ended rules cannot be resumed.

Subscriptions store their own billing RRULE and active/paused/cancelled state. Changing the amount
creates an immutable price-change row containing the old and new minor-unit values. A subscription
may be linked to one recurring rule; projections de-duplicate that relationship.

## Budgets and goals

A budget has a weekly, monthly, quarterly, yearly, or explicit custom range and normalized category
limits. Limits accept expense categories only. Consumption reports show actual and planned amounts
separately, remaining values after each, and actual consumption in basis points. Negative remaining
values intentionally represent an exceeded limit.

Savings goals track a target, current amount, optional target date, currency, and optional
same-currency account. Progress is derived as integer basis points and capped at 10,000; a
contribution that reaches the target completes the goal. General goals use explicit basis-point
progress and automatically complete when updated to 10,000.

## Projection rules

Cash-flow reports use posted transactions in the requested horizon, open plans, ungenerated active
recurrences, and active subscriptions. Generated plans replace their matching recurrence or
subscription occurrence, preventing double counting. Transfers are excluded as cash-flow neutral.
The opening balance includes posted history before the first report day. Monthly buckets and date
boundaries use the workspace IANA timezone.

Committed-balance reports start with ledger balance through `as_of`, then subtract committed open
plans, committed active recurring expenses, active subscription occurrences, and active commitment
costs through `end_date`. The result is the effectively available balance. It is compared with the
sum of account financial buffers for the currency; falling below that minimum sets
`buffer_violation=true`.

Spending and budget reports count only expenses. Planned and actual values remain distinct. Every
report uses half-open internal UTC ranges derived from inclusive API dates.

## Local API workflow

A complete demo can be created through `/api/v1` without direct database edits:

1. Create accounts through `/finance/accounts`; seeded categories are available from
   `/finance/categories`.
2. Post income/expenses through `/finance/transactions` and transfers through
   `/finance/transfers`.
3. Add open plans, recurrence rules, budgets, subscriptions, savings goals, and general goals.
4. Generate recurrence occurrences with `/finance/recurring/{id}/generate` when materialized plans
   are wanted.
5. Read ledger, budget-consumption, cash-flow, spending, and committed-balance responses.

No endpoint requires an API key, remote provider, remote database, exchange-rate service, or
external runtime request.
