import { registerPlugin } from '@hubra/plugin-sdk'
import { IconForms } from '@tabler/icons-react'
import { BuilderScreen } from './BuilderScreen'
import { FormScreen } from './FormScreen'
import { FormsScreen } from './FormsScreen'
import { ResultsScreen } from './ResultsScreen'
import translations from './translations.json'

registerPlugin({
  id: 'forms',
  routes: [
    { path: 'forms', module: 'forms', component: FormsScreen },
    { path: 'forms/new', module: 'forms', perm: 'forms.forms.update', component: BuilderScreen },
    { path: 'forms/:id/edit', module: 'forms', perm: 'forms.forms.update', component: BuilderScreen },
    { path: 'forms/:id/results', module: 'forms', component: ResultsScreen },
    { path: 'forms/:id', module: 'forms', component: FormScreen },
  ],
  // The nav entry in hubra_forms/__init__.py names this icon.
  icons: { forms: IconForms },
  translations,
})
