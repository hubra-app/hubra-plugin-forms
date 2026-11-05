import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ActionIcon,
  Alert,
  Anchor,
  Button,
  Checkbox,
  Group,
  Menu,
  NumberInput,
  Paper,
  Radio,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Textarea,
} from '@mantine/core'
import { IconArrowLeft, IconChartBar, IconCircleCheck, IconCopy, IconDots, IconLock, IconLockOpen, IconPencil, IconTrash } from '@tabler/icons-react'
import { ConfirmModal, ErrorBanner, LoadingSpinner, PageHead, formatDateTime, useT, useToast } from '@hubra/plugin-sdk'
import { FieldError, QK, answer, copyForm, deleteForm, errorText, getForm, setStatus, withdraw, type Field, type FormDetail, type Value } from './api'
import { StateBadge, closesText, useAction } from './common'

/** Filling in a form; the board also opens, closes and edits it here. */
export function FormScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const id = Number(useParams().id)
  const form = useQuery({ queryKey: QK.form(id), queryFn: () => getForm(id) })

  if (form.error) return <ErrorBanner message={errorText(form.error)} onRetry={() => form.refetch()} />
  if (form.isLoading || !form.data) return <LoadingSpinner />
  const f = form.data

  return (
    <>
      <PageHead
        title={f.title}
        desc={closesText(f, t) ?? undefined}
        back={
          <Anchor component="button" size="sm" onClick={() => navigate('/app/forms')}>
            <Group gap={4}>
              <IconArrowLeft size={14} /> {t('forms.title')}
            </Group>
          </Anchor>
        }
        actions={
          <Group gap="xs">
            <StateBadge state={f.state} />
            {f.canSeeResults && (
              <Button variant="default" leftSection={<IconChartBar size={16} />} onClick={() => navigate(`/app/forms/${f.id}/results`)}>
                {f.manage ? t('forms.resultsCount', { count: f.responses ?? 0 }) : t('forms.results')}
              </Button>
            )}
            {f.manage && <BoardMenu form={f} />}
          </Group>
        }
      />
      <Stack gap="md" maw={720}>
        {f.description && <Text style={{ whiteSpace: 'pre-wrap' }}>{f.description}</Text>}
        {f.anonymous && (
          <Alert variant="light" color="violet" p="sm">
            {t('forms.anonymousNote')}
          </Alert>
        )}
        {f.state === 'draft' && (
          <Alert variant="light" color="gray" p="sm">
            {t('forms.draftNote')}
          </Alert>
        )}
        <Answering form={f} key={`${f.id}-${f.myAnsweredAt ?? ''}`} />
      </Stack>
    </>
  )
}

function BoardMenu({ form }: { form: FormDetail }) {
  const { t } = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { notify } = useToast()
  const { run } = useAction()
  const [opening, setOpening] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const refresh = (d: FormDetail) => {
    qc.setQueryData(QK.form(form.id), d)
    qc.invalidateQueries({ queryKey: QK.list })
  }
  return (
    <>
      {form.state !== 'open' ? (
        <Button leftSection={<IconLockOpen size={16} />} onClick={() => setOpening(true)}>
          {t('forms.open')}
        </Button>
      ) : (
        <Button variant="default" leftSection={<IconLock size={16} />} onClick={() => run(async () => refresh(await setStatus(form.id, 'closed')), t('forms.closedToast'))}>
          {t('forms.close')}
        </Button>
      )}
      <Menu position="bottom-end">
        <Menu.Target>
          <ActionIcon variant="default" size="lg" aria-label={t('forms.more')}>
            <IconDots size={18} />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item leftSection={<IconPencil size={14} />} onClick={() => navigate(`/app/forms/${form.id}/edit`)}>
            {t('forms.edit')}
          </Menu.Item>
          <Menu.Item
            leftSection={<IconCopy size={14} />}
            onClick={() =>
              run(async () => {
                const copy = await copyForm(form.id)
                qc.invalidateQueries({ queryKey: QK.list })
                navigate(`/app/forms/${copy.id}/edit`)
              })
            }
          >
            {t('forms.copy')}
          </Menu.Item>
          <Menu.Item color="red" leftSection={<IconTrash size={14} />} onClick={() => setDeleting(true)}>
            {t('forms.delete')}
          </Menu.Item>
        </Menu.Dropdown>
      </Menu>
      <ConfirmModal
        open={opening}
        title={t('forms.openTitle')}
        body={form.groupName ? t('forms.openBodyGroup', { group: form.groupName }) : t('forms.openBody')}
        confirmLabel={t('forms.openAndTell')}
        onClose={() => setOpening(false)}
        onConfirm={async () => {
          setOpening(false)
          await run(async () => {
            const d = await setStatus(form.id, 'open', true)
            refresh(d)
            notify('success', t('forms.openedToast', { count: d.announced ?? 0 }))
          })
        }}
      />
      <ConfirmModal
        open={deleting}
        title={t('forms.deleteTitle')}
        body={t('forms.deleteBody', { count: form.responses ?? 0 })}
        confirmLabel={t('forms.delete')}
        onClose={() => setDeleting(false)}
        onConfirm={async () => {
          setDeleting(false)
          if (await run(() => deleteForm(form.id))) {
            qc.invalidateQueries({ queryKey: QK.list })
            navigate('/app/forms')
          }
        }}
      />
    </>
  )
}

function Answering({ form }: { form: FormDetail }) {
  const { t } = useT()
  const qc = useQueryClient()
  const { notify } = useToast()
  const { busy, run } = useAction()
  const [values, setValues] = useState<Record<string, Value>>(form.myAnswers ?? {})
  const [editing, setEditing] = useState(!form.myAnswers)
  const [error, setError] = useState<{ id: number; message: string } | null>(null)
  useEffect(() => {
    if (error) document.getElementById(`field-${error.id}`)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [error])

  const done = (d: FormDetail) => {
    qc.setQueryData(QK.form(form.id), d)
    qc.invalidateQueries({ queryKey: QK.list })
  }
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const d = await answer(form.id, values)
      notify('success', form.myAnswers ? t('forms.changed') : t('forms.thanks'))
      done(d)
    } catch (err) {
      if (err instanceof FieldError) setError({ id: err.fieldId, message: err.message })
      else notify('error', errorText(err))
    }
  }

  const locked = !form.canAnswer || !editing
  return (
    <form onSubmit={submit}>
      {form.myAnswers && !editing && (
        <Paper withBorder radius="md" p="md" mb="md" style={{ borderColor: 'var(--mantine-color-green-filled)' }}>
          <Group justify="space-between" wrap="wrap" gap="sm">
            <Group gap="xs" wrap="nowrap">
              <IconCircleCheck size={20} color="var(--mantine-color-green-filled)" />
              <Text fw={600}>{t('forms.youAnswered', { when: form.myAnsweredAt ? formatDateTime(form.myAnsweredAt) : '' })}</Text>
            </Group>
            {form.canAnswer && (
              <Group gap="xs">
                <Button size="xs" variant="default" onClick={() => setEditing(true)}>
                  {t('forms.change')}
                </Button>
                <Button size="xs" variant="subtle" color="red" onClick={() => run(async () => done(await withdraw(form.id)), t('forms.withdrawn'))}>
                  {t('forms.withdraw')}
                </Button>
              </Group>
            )}
          </Group>
        </Paper>
      )}
      {!form.canAnswer && !form.myAnswers && form.state === 'closed' && (
        <Alert variant="light" color="gray" p="sm" mb="md">
          {t('forms.closedNote')}
        </Alert>
      )}
      <Stack gap="lg">
        {form.fields.map((f, i) => (
          <div key={f.id} id={`field-${f.id}`}>
            <FieldInput
              index={i + 1}
              field={f}
              value={values[String(f.id)]}
              disabled={locked}
              error={error?.id === f.id ? error.message : undefined}
              onChange={(v) => setValues((old) => ({ ...old, [String(f.id)]: v }))}
            />
          </div>
        ))}
      </Stack>
      {form.canAnswer && editing && (
        <Group mt="xl" gap="sm">
          <Button type="submit" loading={busy}>
            {form.myAnswers ? t('forms.saveChanges') : t('forms.submit')}
          </Button>
          {form.myAnswers && (
            <Button
              variant="default"
              onClick={() => {
                setValues(form.myAnswers ?? {})
                setEditing(false)
                setError(null)
              }}
            >
              {t('forms.cancel')}
            </Button>
          )}
        </Group>
      )}
    </form>
  )
}

function FieldInput({
  index,
  field,
  value,
  disabled,
  error,
  onChange,
}: {
  index: number
  field: Field & { id: number }
  value: Value | undefined
  disabled: boolean
  error?: string
  onChange: (v: Value) => void
}) {
  const { t } = useT()
  const label = `${index}. ${field.label}`
  const common = { label, description: field.help ?? undefined, withAsterisk: field.required, error, disabled }
  switch (field.kind) {
    case 'text':
      return <TextInput {...common} value={(value as string) ?? ''} onChange={(e) => onChange(e.currentTarget.value)} maxLength={300} />
    case 'textarea':
      return <Textarea {...common} autosize minRows={3} value={(value as string) ?? ''} onChange={(e) => onChange(e.currentTarget.value)} maxLength={5000} />
    case 'number':
      return (
        <NumberInput
          {...common}
          value={typeof value === 'number' ? value : value === undefined ? '' : String(value)}
          onChange={(v) => onChange(v === '' ? '' : v)}
          decimalSeparator="."
          thousandSeparator="'"
          maw={240}
        />
      )
    case 'date':
      return <TextInput {...common} type="date" value={(value as string) ?? ''} onChange={(e) => onChange(e.currentTarget.value)} maw={240} />
    case 'choice':
      return (
        <Radio.Group {...common} value={(value as string) ?? null} onChange={onChange}>
          <Stack gap={8} mt={6}>
            {field.options.map((o) => (
              <Radio key={o} value={o} label={o} disabled={disabled} />
            ))}
          </Stack>
        </Radio.Group>
      )
    case 'multi':
      return (
        <Checkbox.Group {...common} value={(value as string[]) ?? []} onChange={onChange}>
          <Stack gap={8} mt={6}>
            {field.options.map((o) => (
              <Checkbox key={o} value={o} label={o} disabled={disabled} />
            ))}
          </Stack>
        </Checkbox.Group>
      )
    case 'yesno':
      return (
        <div>
          <Text size="sm" fw={500}>
            {label}
            {field.required && <span style={{ color: 'var(--mantine-color-error)' }}> *</span>}
          </Text>
          {field.help && (
            <Text size="xs" c="dimmed">
              {field.help}
            </Text>
          )}
          <SegmentedControl
            mt={6}
            disabled={disabled}
            value={value === true ? 'yes' : value === false ? 'no' : ''}
            onChange={(v) => onChange(v === 'yes')}
            data={[
              { value: 'yes', label: t('forms.yes') },
              { value: 'no', label: t('forms.no') },
            ]}
          />
          {error && (
            <Text size="xs" c="red" mt={4}>
              {error}
            </Text>
          )}
        </div>
      )
  }
}
