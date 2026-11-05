import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Anchor, Box, Button, Group, Paper, SimpleGrid, Stack, Table, Text } from '@mantine/core'
import { IconArrowLeft, IconDownload } from '@tabler/icons-react'
import { EmptyState, ErrorBanner, LoadingSpinner, PageHead, Seg, formatDateTime, useT } from '@hubra/plugin-sdk'
import { QK, downloadCsv, errorText, getForm, getResults, type SummaryItem } from './api'
import { useAction } from './common'

/** The summary per question; for the board also every answer and who is missing. */
export function ResultsScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const id = Number(useParams().id)
  const form = useQuery({ queryKey: QK.form(id), queryFn: () => getForm(id) })
  const results = useQuery({ queryKey: QK.results(id), queryFn: () => getResults(id) })
  const [view, setView] = useState('summary')
  const { busy, run } = useAction()

  const err = form.error || results.error
  if (err) return <ErrorBanner message={errorText(err)} onRetry={() => results.refetch()} />
  if (!form.data || !results.data) return <LoadingSpinner />
  const f = form.data
  const r = results.data
  const board = !!r.rows

  return (
    <>
      <PageHead
        title={f.title}
        desc={t('forms.responses', { count: r.responses })}
        back={
          <Anchor component="button" size="sm" onClick={() => navigate(`/app/forms/${f.id}`)}>
            <Group gap={4}>
              <IconArrowLeft size={14} /> {t('forms.toForm')}
            </Group>
          </Anchor>
        }
        actions={
          board ? (
            <Button variant="default" leftSection={<IconDownload size={16} />} loading={busy} onClick={() => run(() => downloadCsv(f.id, f.title))}>
              {t('forms.csv')}
            </Button>
          ) : undefined
        }
      />
      {board && (
        <Group mb="md">
          <Seg
            value={view}
            onChange={setView}
            options={[
              { value: 'summary', label: t('forms.summary') },
              { value: 'table', label: t('forms.table') },
            ]}
          />
        </Group>
      )}
      {!r.responses ? (
        <EmptyState title={t('forms.noAnswers')} description={f.state === 'draft' ? t('forms.draftNote') : undefined} />
      ) : view === 'summary' ? (
        <Stack gap="md" maw={820}>
          {r.missing && r.missing.length > 0 && (
            <Paper withBorder radius="md" p="md">
              <Text fw={600} size="sm" mb={4}>
                {t('forms.missing', { count: r.missing.length })}
              </Text>
              <Text size="sm" c="dimmed">
                {r.missing.join(', ')}
              </Text>
            </Paper>
          )}
          {r.summary.map((s, i) => (
            <SummaryCard key={s.fieldId} index={i + 1} item={s} total={r.responses} />
          ))}
        </Stack>
      ) : (
        <Paper withBorder radius="md" style={{ overflowX: 'auto' }}>
          <Table striped verticalSpacing="xs" horizontalSpacing="md" miw={Math.max(600, 160 * (r.fields.length + 1))}>
            <Table.Thead>
              <Table.Tr>
                {!f.anonymous && <Table.Th>{t('forms.name')}</Table.Th>}
                {r.fields.map((fd) => (
                  <Table.Th key={fd.id}>{fd.label}</Table.Th>
                ))}
                <Table.Th>{t('forms.at')}</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {r.rows!.map((row) => (
                <Table.Tr key={row.id}>
                  {!f.anonymous && (
                    <Table.Td style={{ whiteSpace: 'nowrap' }}>
                      <Text size="sm" fw={600}>
                        {row.name}
                      </Text>
                    </Table.Td>
                  )}
                  {r.fields.map((fd) => (
                    <Table.Td key={fd.id}>
                      <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>
                        {row.answers[String(fd.id)]}
                      </Text>
                    </Table.Td>
                  ))}
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>
                    <Text size="xs" c="dimmed">
                      {row.at ? formatDateTime(row.at) : ''}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </>
  )
}

function SummaryCard({ index, item, total }: { index: number; item: SummaryItem; total: number }) {
  const { t } = useT()
  const counts = item.counts ?? []
  const most = Math.max(1, ...counts.map((c) => c.count))
  return (
    <Paper withBorder radius="md" p="md">
      <Group justify="space-between" wrap="nowrap" align="flex-start" mb="sm">
        <Text fw={700}>
          {index}. {item.label}
        </Text>
        <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
          {t('forms.answeredOf', { n: item.answered, total })}
        </Text>
      </Group>
      {counts.length > 0 && (
        <Stack gap={8}>
          {counts.map((c) => (
            <div key={c.option}>
              <Group justify="space-between" gap="xs" wrap="nowrap" mb={2}>
                <Text size="sm" truncate>
                  {item.kind === 'yesno' ? t(`forms.${c.option}`) : c.option}
                </Text>
                <Text size="sm" fw={600} style={{ whiteSpace: 'nowrap' }}>
                  {c.count}
                  <Text span size="xs" c="dimmed">
                    {' '}
                    · {total ? Math.round((c.count / total) * 100) : 0}%
                  </Text>
                </Text>
              </Group>
              <Box style={{ height: 8, borderRadius: 4, background: 'var(--mantine-color-default-hover)' }}>
                <Box style={{ height: 8, borderRadius: 4, width: `${(c.count / most) * 100}%`, background: 'var(--mantine-color-violet-filled)' }} />
              </Box>
            </div>
          ))}
        </Stack>
      )}
      {item.kind === 'number' && (
        <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
          {(['average', 'sum', 'min', 'max'] as const).map((k) => (
            <div key={k}>
              <Text size="xs" c="dimmed">
                {t(`forms.stat.${k}`)}
              </Text>
              <Text fw={700}>{item[k] ?? '–'}</Text>
            </div>
          ))}
        </SimpleGrid>
      )}
      {item.values && (
        <Stack gap={4}>
          {item.values.length ? (
            item.values.slice(-30).map((v, i) => (
              <Text key={i} size="sm" style={{ whiteSpace: 'pre-wrap', borderLeft: '2px solid var(--mantine-color-default-border)', paddingLeft: 8 }}>
                {v}
              </Text>
            ))
          ) : (
            <Text size="sm" c="dimmed">
              –
            </Text>
          )}
          {item.values.length > 30 && (
            <Text size="xs" c="dimmed">
              {t('forms.moreInTable', { count: item.values.length - 30 })}
            </Text>
          )}
        </Stack>
      )}
    </Paper>
  )
}
