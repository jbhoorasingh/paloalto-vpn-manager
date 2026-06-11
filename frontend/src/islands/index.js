import { createApp } from 'vue'

// Registry of available island components
const components = {
  'wizard': () => import('../components/wizard/VpnWizard.vue'),
  'requests-table': () => import('../components/dashboard/RequestsTable.vue'),
  'stats-panel': () => import('../components/dashboard/StatsPanel.vue'),
  'flows-editor': () => import('../components/flows/FlowsEditor.vue'),
  'flow-diagram': () => import('../components/shared/FlowDiagram.vue'),
  'topology-diagram': () => import('../components/shared/TopologyDiagram.vue'),
  'approval-queue': () => import('../components/approvals/ApprovalQueue.vue'),
  'workflow-diagram': () => import('../components/shared/WorkflowDiagram.vue'),
}

// Auto-mount all islands found in the DOM
export async function mountIslands() {
  const elements = document.querySelectorAll('[data-vue-component]')

  for (const el of elements) {
    const name = el.dataset.vueComponent
    const loader = components[name]
    if (!loader) {
      console.warn(`Unknown Vue island component: ${name}`)
      continue
    }

    try {
      const { default: Component } = await loader()
      const props = JSON.parse(el.dataset.vueProps || '{}')
      const app = createApp(Component, props)
      app.mount(el)
    } catch (err) {
      console.error(`Failed to mount island "${name}":`, err)
    }
  }
}
