import { apiFetch, apiFetchRaw } from '@hubra/plugin-sdk'

export type Kind = 'text' | 'textarea' | 'number' | 'date' | 'choice' | 'multi' | 'yesno'
export const KINDS: Kind[] = ['text', 'textarea', 'number', 'date', 'choice', 'multi', 'yesno']
export type State = 'draft' | 'open' | 'closed'
export type Value = string | number | boolean | string[]

export interface Options {
  memberId: number
  can: { manage: boolean }
  groups?: { id: number; name: string }[]
}

export interface Field {
  id?: number
  kind: Kind
  label: string
  help: string | null
  required: boolean
  options: string[]
}

export interface Form {
  id: number
  title: string
  description: string | null
  state: State
  closesAt: string | null
  groupId: number | null
  groupName: string | null
  anonymous: boolean
  resultsPublic: boolean
  remind: boolean
  answered: boolean
  openedAt: string | null
  answersDeleteAt: string | null
  createdAt: string | null
  responses?: number
}

export interface FormDetail extends Form {
  fields: (Field & { id: number })[]
  myAnswers: Record<string, Value> | null
  myAnsweredAt: string | null
  canAnswer: boolean
  canSeeResults: boolean
  manage: boolean
  announced?: number
}

export interface SummaryItem {
  fieldId: number
  label: string
  kind: Kind
  answered: number
  counts?: { option: string; count: number }[]
  sum?: number | null
  average?: number | null
  min?: number | null
  max?: number | null
  values?: string[]
}

export interface Results {
  responses: number
  fields: (Field & { id: number })[]
  summary: SummaryItem[]
  rows?: { id: number; name: string | null; memberId: number | null; at: string | null; answers: Record<string, string> }[]
  missing?: string[]
}

export class FieldError extends Error {
  fieldId: number
  constructor(message: string, fieldId: number) {
    super(message)
    this.fieldId = fieldId
  }
}

export const QK = {
  all: ['forms'] as const,
  options: ['forms', 'options'] as const,
  list: ['forms', 'list'] as const,
  form: (id: number) => ['forms', 'form', id] as const,
  results: (id: number) => ['forms', 'results', id] as const,
}

const BASE = '/app/forms'
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const getOptions = () => apiFetch<Options>(`${BASE}/options`)
export const listForms = () => apiFetch<Form[]>(`${BASE}/forms`)
export const getForm = (id: number) => apiFetch<FormDetail>(`${BASE}/forms/${id}`)
export const saveForm = (body: Record<string, unknown>, id?: number) =>
  apiFetch<FormDetail>(id ? `${BASE}/forms/${id}` : `${BASE}/forms`, json(id ? 'PUT' : 'POST', body))
export const setStatus = (id: number, status: State, announce = false) =>
  apiFetch<FormDetail>(`${BASE}/forms/${id}/status`, json('POST', { status, announce }))
export const copyForm = (id: number) => apiFetch<FormDetail>(`${BASE}/forms/${id}/copy`, json('POST', {}))
export const deleteForm = (id: number) => apiFetch<void>(`${BASE}/forms/${id}`, { method: 'DELETE' })
export const withdraw = (id: number) => apiFetch<FormDetail>(`${BASE}/forms/${id}/response`, { method: 'DELETE' })
export const getResults = (id: number) => apiFetch<Results>(`${BASE}/forms/${id}/results`)

/** Sends the caller's answers; a refused field comes back as a FieldError. */
export async function answer(id: number, answers: Record<string, Value>): Promise<FormDetail> {
  const res = await apiFetchRaw(`${BASE}/forms/${id}/response`, json('PUT', { answers }))
  const body = await res.json().catch(() => ({}))
  if (res.ok) return body as FormDetail
  if (body.fieldId) throw new FieldError(body.message, body.fieldId)
  throw new Error(body.message || `HTTP ${res.status}`)
}

export async function downloadCsv(id: number, title: string) {
  const res = await apiFetchRaw(`${BASE}/forms/${id}/results.csv`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `${title.replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'form'}.csv`
  a.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function errorText(err: unknown) {
  return err instanceof Error ? err.message : String(err)
}

/** "2027-01-05T18:00:00+00:00" → "2027-01-05T19:00" in the browser's time (for inputs). */
export function toLocalInput(value: string | null) {
  if (!value) return ''
  const d = new Date(value)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

/** Local input value → an ISO time with the browser's offset. */
export function fromLocalInput(value: string) {
  return value ? new Date(value).toISOString() : null
}
