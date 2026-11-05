import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Badge, Button, Group, Paper, SimpleGrid, Stack, Text } from '@mantine/core'
import { IconCircleCheck, IconForms, IconPlus } from '@tabler/icons-react'
import { EmptyState, ErrorBanner, LoadingSpinner, PageHead, useT } from '@hubra/plugin-sdk'
import { QK, errorText, getOptions, listForms, type Form } from './api'
import { StateBadge, closesText } from './common'

/** Open forms to fill in first; the board also sees drafts and closed ones. */
export function FormsScreen() {
  const { t } = useT()
  const navigate = useNavigate()
  const options = useQuery({ queryKey: QK.options, queryFn: getOptions })
  const forms = useQuery({ queryKey: QK.list, queryFn: listForms })
  const manage = !!options.data?.can.manage

  if (forms.error) return <ErrorBanner message={errorText(forms.error)} onRetry={() => forms.refetch()} />
  if (forms.isLoading || options.isLoading) return <LoadingSpinner />
  const list = forms.data ?? []
  const todo = list.filter((f) => f.state === 'open' && !f.answered)
  const rest = list.filter((f) => !(f.state === 'open' && !f.answered))

  return (
    <>
      <PageHead
        title={t('forms.title')}
        desc={t('forms.desc')}
        actions={
          manage ? (
            <Button leftSection={<IconPlus size={16} />} onClick={() => navigate('/app/forms/new')}>
              {t('forms.newForm')}
            </Button>
          ) : undefined
        }
      />
      {!list.length ? (
        <EmptyState icon={<IconForms size={28} />} title={t('forms.none')} description={manage ? t('forms.noneHint') : undefined} />
      ) : (
        <Stack gap="lg">
          {todo.length > 0 && (
            <section>
              <Text fw={700} mb="xs">
                {t('forms.toFill')}
              </Text>
              <Grid forms={todo} manage={manage} />
            </section>
          )}
          {rest.length > 0 && (
            <section>
              {todo.length > 0 && (
                <Text fw={700} mb="xs">
                  {t('forms.others')}
                </Text>
              )}
              <Grid forms={rest} manage={manage} />
            </section>
          )}
        </Stack>
      )}
    </>
  )
}

function Grid({ forms, manage }: { forms: Form[]; manage: boolean }) {
  const { t } = useT()
  const navigate = useNavigate()
  return (
    <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="sm">
      {forms.map((f) => (
        <Paper key={f.id} withBorder radius="md" p="md" style={{ cursor: 'pointer' }} onClick={() => navigate(`/app/forms/${f.id}`)}>
          <Group justify="space-between" wrap="nowrap" align="flex-start" mb={6}>
            <Text fw={700} lineClamp={2}>
              {f.title}
            </Text>
            <StateBadge state={f.state} />
          </Group>
          {f.description && (
            <Text size="sm" c="dimmed" lineClamp={2} mb={6}>
              {f.description}
            </Text>
          )}
          <Group gap={8} wrap="wrap">
            {f.answered && (
              <Group gap={4} wrap="nowrap">
                <IconCircleCheck size={16} color="var(--mantine-color-green-filled)" />
                <Text size="sm" c="green">
                  {t('forms.answered')}
                </Text>
              </Group>
            )}
            {closesText(f, t) && (
              <Text size="sm" c="dimmed">
                {closesText(f, t)}
              </Text>
            )}
            {f.groupName && (
              <Badge size="sm" variant="outline" color="gray" style={{ textTransform: 'none' }}>
                {f.groupName}
              </Badge>
            )}
            {manage && f.responses !== undefined && (
              <Text size="sm" c="dimmed">
                {t('forms.responses', { count: f.responses })}
              </Text>
            )}
          </Group>
        </Paper>
      ))}
    </SimpleGrid>
  )
}
