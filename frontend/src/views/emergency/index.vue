<template>
  <section class="page" data-module="emergency">
    <header class="page-head">
      <div>
        <h2>应急演练管理</h2>
        <p class="page-desc">维护演练记录，围绕演练编号、演练主题、演练类型、参与单位做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记演练记录</button>
        <button class="btn" type="button" @click="exportRows">导出应急演练清单</button>
      </div>
    </header>

    <div class="view-switch">
      <button type="button" :class="{ active: view === 'list' }" @click="setView('list')">演练列表</button>
      <button type="button" :class="{ active: view === 'matrix' }" @click="setView('matrix')">概览矩阵</button>
    </div>

    <template v-if="view === 'list'">
      <div class="stat-row">
        <article v-for="item in stats" :key="item.label" class="stat-card">
          <span class="stat-label">{{ item.label }}</span>
          <strong class="stat-value">{{ item.value }}</strong>
        </article>
      </div>

      <form class="filter-bar" @submit.prevent="reload">
        <label v-for="field in filterFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="filters[field]" :placeholder="`按${field}检索`" />
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="runAction(action, row)"
              >
                {{ action }}
              </button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">暂无应急演练数据，可先登记演练记录</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 条应急演练记录</span>
        <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      </footer>
    </template>

    <EmergencyMatrix v-else :selected-cell="selectedCell" @select="onSelectCell" />
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'
import EmergencyMatrix from './matrix.vue'

type Row = Record<string, string | number | null>
type ViewMode = 'list' | 'matrix'

interface CellKey {
  unit: string
  theme: string
}

const ENDPOINT = '/api/emergency'
const columns = ["演练编号", "演练主题", "演练类型", "参与单位", "演练日期", "演练评估", "改进措施", "演练状态"]
const actions = ["组织演练", "完成演练", "复盘总结"]
const statuses = ["待组织", "已组织", "已完成", "已复盘"]
const stats = [{"label": "待组织演练", "value": 0}, {"label": "已完成演练", "value": 0}, {"label": "已复盘演练", "value": 0}]

// 视图与选中格子的停留状态：localStorage 兜底，URL query 可分享，两者保持一致
const STORAGE_KEY = 'emergency:overview-state'

const route = useRoute()
const router = useRouter()

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const view = ref<ViewMode>('list')
const selectedCell = ref<CellKey | null>(null)

function restoreState() {
  let saved: { view?: ViewMode; cell?: CellKey | null } = {}
  try {
    saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as typeof saved
  } catch {
    saved = {}
  }
  const queryView = route.query.view
  if (queryView === 'matrix' || queryView === 'list') {
    view.value = queryView
  } else if (saved.view === 'matrix' || saved.view === 'list') {
    view.value = saved.view
  }
  const unit = typeof route.query.unit === 'string' ? route.query.unit : ''
  const theme = typeof route.query.theme === 'string' ? route.query.theme : ''
  if (unit && theme) {
    selectedCell.value = { unit, theme }
    view.value = 'matrix'
  } else if (saved.cell && typeof saved.cell.unit === 'string' && typeof saved.cell.theme === 'string') {
    selectedCell.value = saved.cell
  }
}

function persistState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ view: view.value, cell: selectedCell.value }))
  const query: Record<string, string> = {}
  if (view.value === 'matrix') {
    query.view = 'matrix'
    if (selectedCell.value) {
      query.unit = selectedCell.value.unit
      query.theme = selectedCell.value.theme
    }
  }
  void router.replace({ query })
}

function setView(next: ViewMode) {
  view.value = next
}

function onSelectCell(cell: CellKey | null) {
  selectedCell.value = cell
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '演练记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ action }),
    })
    if (!response.ok) {
      throw new Error('应急演练动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '应急演练操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('演练记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '应急演练列表读取失败'
  }
}

restoreState()
watch([view, selectedCell], persistState, { immediate: true })
// 切回列表时重新拉一次，保证与矩阵里补录的数据口径一致
watch(view, (current) => {
  if (current === 'list') {
    void reload()
  }
}, { immediate: true })
</script>
