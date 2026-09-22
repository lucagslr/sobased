/** Bookkeeping: categories, transactions, receipts, budget, advances, exports. */
import { api } from './client'
import type { components } from './schema'
import type { Paginated } from './tasks'

type Schemas = components['schemas']

export type Category = Schemas['Category']
export type Transaction = Schemas['Transaction']
export type TransactionKind = Schemas['TransactionKindEnum']
export type PaymentStatus = Schemas['PaymentStatusEnum']
export type DisplayStatus = Schemas['DisplayStatusEnum']
export type RecurringExpense = Schemas['RecurringExpense']
export type Frequency = Schemas['FrequencyEnum']
export type BudgetLine = Schemas['BudgetLine']
export type FinanceSummary = Schemas['FinanceSummary']
export type Budget = Schemas['Budget']
export type BudgetEntry = Schemas['BudgetEntry']
export type Advance = Schemas['Advance']

export interface TransactionPayload {
  project?: number
  kind?: TransactionKind
  amount?: string
  date?: string
  category?: number
  label?: string
  vendor?: string
  contact?: number | null
  event?: number | null
  payment_status?: PaymentStatus
  paid_by_username?: string | null
  paid_by_contact?: number | null
  to_reimburse?: boolean
  reimbursed_on?: string | null
}

export interface TransactionFilters {
  project?: number
  include_descendants?: boolean
  workspace?: number
  kind?: TransactionKind
  category?: number
  date_after?: string
  date_before?: string
  payment_status?: PaymentStatus
  needs_receipt?: boolean
  to_reimburse?: boolean
  paid_by?: string
  search?: string
  ordering?: string
  page?: number
  page_size?: number
}

export interface RecurringExpensePayload {
  project?: number
  label?: string
  amount?: string
  category?: number
  vendor?: string
  frequency?: Frequency
  day?: number
  month?: number
  start_date?: string
  end_date?: string | null
  is_active?: boolean
}

export function financeQuery(filters: object): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  }
  const text = params.toString()
  return text ? `?${text}` : ''
}

/** The receipt travels with the form: multipart when a file is attached. */
function transactionBody(payload: TransactionPayload, receipt?: File | null) {
  if (!receipt) return { body: payload }
  const form = new FormData()
  for (const [key, value] of Object.entries(payload)) {
    if (value !== undefined && value !== null) form.append(key, String(value))
  }
  form.append('receipt', receipt)
  return { formData: form }
}

export const financeApi = {
  categories: (workspace: number) => api<Category[]>(`/api/categories/?workspace=${workspace}`),
  createCategory: (workspace: number, name: string) =>
    api<Category>('/api/categories/', { method: 'POST', body: { workspace, name } }),
  renameCategory: (id: number, name: string) =>
    api<Category>(`/api/categories/${id}/`, { method: 'PATCH', body: { name } }),
  removeCategory: (id: number, replaceWith?: number) =>
    api(`/api/categories/${id}/${replaceWith ? `?replace_with=${replaceWith}` : ''}`, {
      method: 'DELETE',
    }),

  transactions: (filters: TransactionFilters = {}) =>
    api<Paginated<Transaction>>(
      `/api/transactions/${financeQuery({ page_size: 100, ...filters })}`,
    ),
  transaction: (id: number) => api<Transaction>(`/api/transactions/${id}/`),
  createTransaction: (payload: TransactionPayload, receipt?: File | null) =>
    api<Transaction>('/api/transactions/', {
      method: 'POST',
      ...transactionBody(payload, receipt),
    }),
  updateTransaction: (id: number, payload: TransactionPayload, receipt?: File | null) =>
    api<Transaction>(`/api/transactions/${id}/`, {
      method: 'PATCH',
      ...transactionBody(payload, receipt),
    }),
  removeTransaction: (id: number) => api(`/api/transactions/${id}/`, { method: 'DELETE' }),
  removeReceipt: (id: number) =>
    api<Transaction>(`/api/transactions/${id}/receipt/`, { method: 'DELETE' }),
  markPaid: (id: number) =>
    api<Transaction>(`/api/transactions/${id}/mark-paid/`, { method: 'POST' }),
  markReimbursed: (id: number, reimbursedOn?: string) =>
    api<Transaction>(`/api/transactions/${id}/mark-reimbursed/`, {
      method: 'POST',
      body: reimbursedOn ? { reimbursed_on: reimbursedOn } : {},
    }),

  summary: (filters: TransactionFilters = {}) =>
    api<FinanceSummary>(`/api/finance/summary/${financeQuery(filters)}`),
  budget: (project: number) => api<Budget>(`/api/finance/budget/?project=${project}`),
  budgetLines: (project: number) => api<BudgetLine[]>(`/api/budget-lines/?project=${project}`),
  setBudgetLine: (project: number, category: number, kind: TransactionKind, amount: string) =>
    api<BudgetLine>('/api/budget-lines/', {
      method: 'POST',
      body: { project, category, kind, amount },
    }),
  removeBudgetLine: (id: number) => api(`/api/budget-lines/${id}/`, { method: 'DELETE' }),

  advances: (filters: { workspace?: number; project?: number } = {}) =>
    api<Advance[]>(`/api/finance/advances/${financeQuery(filters)}`),
  settleAdvances: (transactions: number[]) =>
    api<{ updated: number }>('/api/finance/advances/', {
      method: 'POST',
      body: { transactions },
    }),

  recurringExpenses: (filters: { project?: number; workspace?: number } = {}) =>
    api<RecurringExpense[]>(`/api/recurring-expenses/${financeQuery(filters)}`),
  createRecurringExpense: (payload: RecurringExpensePayload & { project: number }) =>
    api<RecurringExpense>('/api/recurring-expenses/', { method: 'POST', body: payload }),
  updateRecurringExpense: (id: number, payload: RecurringExpensePayload) =>
    api<RecurringExpense>(`/api/recurring-expenses/${id}/`, { method: 'PATCH', body: payload }),
  removeRecurringExpense: (id: number) =>
    api(`/api/recurring-expenses/${id}/`, { method: 'DELETE' }),

  /** Download URLs (same origin: the session cookie travels with them). */
  exportUrl: (kind: 'xlsx' | 'pdf' | 'receipts', filters: TransactionFilters = {}) => {
    const file = kind === 'receipts' ? 'export-receipts.zip' : `export.${kind}`
    return `/api/finance/${file}${financeQuery(filters)}`
  },
}
