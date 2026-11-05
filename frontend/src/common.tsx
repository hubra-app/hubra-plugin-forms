import { useState } from 'react'
import { Badge } from '@mantine/core'
import { formatDateTime, useT, useToast } from '@hubra/plugin-sdk'
import { errorText, type Form, type State } from './api'

/** Runs an action with a busy flag and a toast for errors. */
export function useAction() {
  const { notify } = useToast()
  const [busy, setBusy] = useState(false)
  const run = async (fn: () => Promise<unknown>, ok?: string) => {
    setBusy(true)
    try {
      await fn()
      if (ok) notify('success', ok)
      return true
    } catch (err) {
      notify('error', errorText(err))
      return false
    } finally {
      setBusy(false)
    }
  }
  return { busy, run }
}

const COLORS: Record<State, string> = { draft: 'gray', open: 'green', closed: 'red' }

export function StateBadge({ state }: { state: State }) {
  const { t } = useT()
  return (
    <Badge size="sm" variant="light" color={COLORS[state]} style={{ textTransform: 'none', flexShrink: 0 }}>
      {t(`forms.state.${state}`)}
    </Badge>
  )
}

/** "Open until 12.1.2027, 18:00" or nothing. */
export function closesText(form: Form, t: (k: string, o?: Record<string, unknown>) => string) {
  if (!form.closesAt) return null
  const when = formatDateTime(form.closesAt)
  return form.state === 'closed' ? t('forms.closedOn', { when }) : t('forms.until', { when })
}
