import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { listAccounts, listCategories } from "@/lib/api/finance";
import {
  listAutomationExecutions,
  listAutomationRules,
  listLocalNotifications,
  previewAutomationRule,
} from "@/lib/api/imports-automation";
import { listTags } from "@/lib/api/productivity";

import { AutomationWorkspace } from "./automation-workspace";

vi.mock("@/lib/api/finance", () => ({ listAccounts: vi.fn(), listCategories: vi.fn() }));
vi.mock("@/lib/api/productivity", () => ({ listTags: vi.fn() }));
vi.mock("@/lib/api/imports-automation", () => ({
  createAutomationRule: vi.fn(),
  deleteAutomationRule: vi.fn(),
  getSchedulerStatus: vi.fn().mockResolvedValue({ running: false, scheduled_rule_ids: [], next_wakeup_at: null }),
  listAutomationExecutions: vi.fn(),
  listAutomationRules: vi.fn(),
  listLocalNotifications: vi.fn(),
  previewAutomationRule: vi.fn(),
  updateAutomationRule: vi.fn(),
}));

function Wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe("AutomationWorkspace", () => {
  beforeEach(() => {
    vi.mocked(listAutomationRules).mockResolvedValue([{
      id: "rule-1",
      workspace_id: "workspace-1",
      name: "Large transaction notice",
      description: null,
      enabled: true,
      trigger: { type: "transaction_created", conditions: [{ field: "amount_minor", operator: "greater_than_or_equal", value: 1000 }], schedule: null, lookahead_minutes: null },
      action: { type: "create_notification", title: "Review this transaction", body: null, priority: "medium", days_from_trigger: 0 },
      last_run_at: null,
      next_run_at: null,
      execution_count: 0,
      revision: 1,
      created_at: "2026-07-15T10:00:00Z",
      updated_at: "2026-07-15T10:00:00Z",
    }]);
    vi.mocked(listAutomationExecutions).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listLocalNotifications).mockResolvedValue([]);
    vi.mocked(listAccounts).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listCategories).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(listTags).mockResolvedValue({ data: [], meta: { page: 1, page_size: 100, total_items: 0, total_pages: 0 } });
    vi.mocked(previewAutomationRule).mockResolvedValue({ rule_id: "rule-1", matched: true, condition_results: ["amount matched"], action: { type: "create_notification", description: "Create notification “Review this transaction”", payload: {} }, writes_performed: false });
  });

  it("tests a saved rule without executing its action", async () => {
    render(<AutomationWorkspace />, { wrapper: Wrapper });
    fireEvent.click(await screen.findByRole("button", { name: /Large transaction notice/ }));
    fireEvent.click(screen.getByRole("button", { name: "Run safe test" }));

    await waitFor(() => expect(previewAutomationRule).toHaveBeenCalledWith("rule-1", expect.objectContaining({ source_key: "manual-ui-preview" })));
    expect(await screen.findByText("Create notification “Review this transaction”")).toBeInTheDocument();
  });
});
