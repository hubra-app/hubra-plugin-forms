import { useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { ActionIcon, Anchor, Button, Group, Paper, Select, SimpleGrid, Stack, Switch, TagsInput, Text, TextInput, Textarea, Tooltip } from '@mantine/core'
import { IconArrowDown, IconArrowLeft, IconArrowUp, IconCopy, IconPlus, IconTrash } from '@tabler/icons-react'
import { ErrorBanner, Field as Labelled, LoadingSpinner, PageHead, useT } from '@hubra/plugin-sdk'
import { KINDS, QK, errorText, fromLocalInput, getForm, getOptions, saveForm, toLocalInput, type Field, type Kind } from './api'
import { useAction } from './common'

type Draft = Field & { key: string }
let next = 0
const blank = (kind: Kind = 'text'): Draft => ({ key: `n${next++}`, kind, label: '', help: null, required: false, options: [] })

/** Build a new form or change one: its settings and its fields. */
export function BuilderScreen() {
  const id = Number(useParams().id) || undefined
  const form = useQuery({ queryKey: QK.form(id ?? 0), queryFn: () => getForm(id!), enabled: !!id })
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  if (form.error) return <ErrorBanner message={errorText(form.error)} onRetry={() => form.refetch()} />
  if ((id && !form.data) || options.isLoading) return <LoadingSpinner />
  return <Builder key={id ?? 'new'} id={id} initial={form.data} groups={options.data?.groups ?? []} />
}

function Builder({
  id,
  initial,
  groups,
}: {
  id?: number
  initial?: Awaited<ReturnType<typeof getForm>>
  groups: { id: number; name: string }[]
}) {
  const { t } = useT()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { busy, run } = useAction()
  const [title, setTitle] = useState(initial?.title ?? '')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [closesAt, setClosesAt] = useState(toLocalInput(initial?.closesAt ?? null))
  const [groupId, setGroupId] = useState<string | null>(initial?.groupId ? String(initial.groupId) : null)
  const [anonymous, setAnonymous] = useState(initial?.anonymous ?? false)
  const [resultsPublic, setResultsPublic] = useState(initial?.resultsPublic ?? false)
  const [remind, setRemind] = useState(initial?.remind ?? false)
  const [fields, setFields] = useState<Draft[]>(
    initial ? initial.fields.map((f) => ({ ...f, key: `f${f.id}` })) : [blank('text')],
  )
  const answered = (initial?.responses ?? 0) > 0

  const update = (key: string, patch: Partial<Draft>) => setFields((fs) => fs.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  const move = (i: number, d: number) =>
    setFields((fs) => {
      const out = [...fs]
      const [x] = out.splice(i, 1)
      out.splice(i + d, 0, x)
      return out
    })

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    let savedId = id
    const ok = await run(async () => {
      const saved = await saveForm(
        {
          title,
          description: description || null,
          closesAt: fromLocalInput(closesAt),
          groupId: groupId ? Number(groupId) : null,
          anonymous,
          resultsPublic,
          remind: remind && !!closesAt,
          fields: fields.map(({ key: _key, ...f }) => f),
        },
        id,
      )
      savedId = saved.id
      qc.setQueryData(QK.form(saved.id), saved)
      qc.invalidateQueries({ queryKey: QK.list })
    }, t('forms.saved'))
    if (ok) navigate(`/app/forms/${savedId}`)
  }

  const kindData = KINDS.map((k) => ({ value: k, label: t(`forms.kind.${k}`) }))

  return (
    <form onSubmit={submit}>
      <PageHead
        title={id ? t('forms.edit') : t('forms.newForm')}
        back={
          <Anchor component="button" type="button" size="sm" onClick={() => navigate(id ? `/app/forms/${id}` : '/app/forms')}>
            <Group gap={4}>
              <IconArrowLeft size={14} /> {id ? initial?.title : t('forms.title')}
            </Group>
          </Anchor>
        }
        actions={
          <Button type="submit" loading={busy} disabled={!title.trim() || !fields.length}>
            {t('forms.save')}
          </Button>
        }
      />
      <Stack gap="lg" maw={820}>
        <Paper withBorder radius="md" p="md">
          <Stack gap="sm">
            <Labelled label={t('forms.formTitle')}>
              <TextInput value={title} onChange={(e) => setTitle(e.currentTarget.value)} placeholder={t('forms.titleExample')} required data-autofocus />
            </Labelled>
            <Labelled label={t('forms.intro')} hint={t('forms.introHint')}>
              <Textarea autosize minRows={2} value={description} onChange={(e) => setDescription(e.currentTarget.value)} />
            </Labelled>
            <SimpleGrid cols={{ base: 1, sm: 2 }} spacing="sm">
              <Labelled label={t('forms.closesAt')} hint={t('forms.closesAtHint')}>
                <TextInput type="datetime-local" required value={closesAt} onChange={(e) => setClosesAt(e.currentTarget.value)} />
              </Labelled>
              <Labelled label={t('forms.who')}>
                <Select
                  aria-label={t('forms.who')}
                  value={groupId}
                  onChange={setGroupId}
                  placeholder={t('forms.everyone')}
                  clearable
                  searchable
                  data={groups.map((g) => ({ value: String(g.id), label: g.name }))}
                />
              </Labelled>
            </SimpleGrid>
            <Switch
              checked={anonymous}
              // Answers given anonymously stay anonymous.
              disabled={!!initial?.anonymous && (initial?.responses ?? 0) > 0}
              onChange={(e) => setAnonymous(e.currentTarget.checked)}
              label={t('forms.anonymous')}
              description={t(initial?.anonymous && (initial?.responses ?? 0) > 0 ? 'forms.anonymousLocked' : 'forms.anonymousHint')}
            />
            <Switch
              checked={resultsPublic}
              // Members answered on the promise that only the board sees the results.
              disabled={!initial?.resultsPublic && (initial?.responses ?? 0) > 0}
              onChange={(e) => setResultsPublic(e.currentTarget.checked)}
              label={t('forms.resultsPublic')}
              description={t(!initial?.resultsPublic && (initial?.responses ?? 0) > 0 ? 'forms.resultsPublicLocked' : 'forms.resultsPublicHint')}
            />
            <Switch
              checked={remind && !!closesAt}
              disabled={!closesAt}
              onChange={(e) => setRemind(e.currentTarget.checked)}
              label={t('forms.remind')}
              description={t('forms.remindHint')}
            />
          </Stack>
        </Paper>

        <Text fw={700}>{t('forms.fields')}</Text>
        {fields.map((f, i) => (
          <Paper key={f.key} withBorder radius="md" p="md">
            <Group justify="space-between" mb="xs" wrap="nowrap">
              <Text size="sm" c="dimmed" fw={600}>
                {t('forms.question', { n: i + 1 })}
              </Text>
              <Group gap={2} wrap="nowrap">
                <ActionIcon variant="subtle" color="gray" disabled={i === 0} onClick={() => move(i, -1)} aria-label={t('forms.up')}>
                  <IconArrowUp size={16} />
                </ActionIcon>
                <ActionIcon variant="subtle" color="gray" disabled={i === fields.length - 1} onClick={() => move(i, 1)} aria-label={t('forms.down')}>
                  <IconArrowDown size={16} />
                </ActionIcon>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  onClick={() => setFields((fs) => [...fs.slice(0, i + 1), { ...f, id: undefined, key: `n${next++}` }, ...fs.slice(i + 1)])}
                  aria-label={t('forms.duplicate')}
                >
                  <IconCopy size={16} />
                </ActionIcon>
                <ActionIcon variant="subtle" color="red" disabled={fields.length === 1} onClick={() => setFields((fs) => fs.filter((x) => x.key !== f.key))} aria-label={t('forms.remove')}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            </Group>
            <Stack gap="sm">
              <Group grow align="flex-start" wrap="wrap" gap="sm">
                <TextInput
                  style={{ flex: '2 1 260px' }}
                  aria-label={t('forms.label')}
                  placeholder={t('forms.labelPlaceholder')}
                  value={f.label}
                  onChange={(e) => update(f.key, { label: e.currentTarget.value })}
                  required
                />
                <Tooltip label={t('forms.kindLocked')} disabled={!(answered && f.id)}>
                  <div style={{ flex: '1 1 180px' }}>
                    <Select
                      aria-label={t('forms.kindLabel')}
                      data={kindData}
                      value={f.kind}
                      allowDeselect={false}
                      disabled={answered && !!f.id}
                      onChange={(v) => v && update(f.key, { kind: v as Kind })}
                    />
                  </div>
                </Tooltip>
              </Group>
              {(f.kind === 'choice' || f.kind === 'multi') && (
                <TagsInput
                  label={t('forms.choices')}
                  description={t('forms.choicesHint')}
                  value={f.options}
                  onChange={(v) => update(f.key, { options: v })}
                  clearable
                  splitChars={[',', ';']}
                />
              )}
              <Group justify="space-between" wrap="wrap" gap="sm">
                <TextInput
                  style={{ flex: '1 1 260px' }}
                  size="xs"
                  aria-label={t('forms.help')}
                  placeholder={t('forms.helpPlaceholder')}
                  value={f.help ?? ''}
                  onChange={(e) => update(f.key, { help: e.currentTarget.value || null })}
                />
                <Switch size="sm" checked={f.required} onChange={(e) => update(f.key, { required: e.currentTarget.checked })} label={t('forms.required')} />
              </Group>
            </Stack>
          </Paper>
        ))}
        <Group>
          <Button variant="light" leftSection={<IconPlus size={16} />} onClick={() => setFields((fs) => [...fs, blank(fs[fs.length - 1]?.kind === 'yesno' ? 'yesno' : 'text')])}>
            {t('forms.addField')}
          </Button>
        </Group>
      </Stack>
    </form>
  )
}
