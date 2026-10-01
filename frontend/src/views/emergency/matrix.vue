<template>
  <div class="matrix-view">
    <div v-if="errorMessage" class="error-bar">
      <span>{{ errorMessage }}</span>
      <button class="btn" type="button" @click="reload">重新加载</button>
    </div>

    <p v-if="loading" class="empty-state">概览矩阵加载中…</p>

    <template v-else-if="matrix">
      <table class="data-table matrix-table">
        <thead>
          <tr>
            <th class="matrix-corner">用人单位 ＼ 演练主题</th>
            <th v-for="theme in matrix.themes" :key="theme">{{ theme }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="unit in matrix.units" :key="unit">
            <th class="matrix-rowhead">{{ unit }}</th>
            <td
              v-for="theme in matrix.themes"
              :key="theme"
              class="matrix-cell"
              :class="cellClass(unit, theme)"
              @click="onCellClick(unit, theme)"
            >
              <template v-if="cellOf(unit, theme)">
                <span class="cell-count">{{ cellOf(unit, theme)?.count }} 次</span>
                <span v-if="cellOf(unit, theme)?.todo" class="cell-todo">
                  待办 {{ cellOf(unit, theme)?.todo }}
                </span>
              </template>
              <span v-else class="cell-empty">暂无</span>
            </td>
          </tr>
        </tbody>
      </table>

      <section v-if="selectedCell" class="drill-panel">
        <header>
          <h3>{{ selectedCell.unit }} · {{ selectedCell.theme }}</h3>
          <div class="panel-actions">
            <button class="btn primary" type="button" @click="openCreate(selectedCell)">补录该组合演练</button>
            <button class="btn ghost" type="button" @click="emit('select', null)">收起</button>
          </div>
        </header>
        <table v-if="selectedEntries.length" class="data-table">
          <thead>
            <tr>
              <th v-for="column in detailColumns" :key="column">{{ column }}</th>
              <th>改进落实</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in selectedEntries" :key="String(entry.id)">
              <td v-for="column in detailColumns" :key="column">{{ entry[column] || '—' }}</td>
              <td>
                <span v-if="entry.改进待落实" class="todo-flag">待办：改进措施未落实</span>
                <span v-else class="done-flag">已闭环</span>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-state">该单位在此主题下暂无演练记录，可直接补录。</p>
      </section>

      <footer class="page-foot">
        <span>共 {{ matrix.total }} 条应急演练记录，与演练列表同一份数据口径</span>
      </footer>

      <div v-if="createForm" class="modal-mask" @click.self="cancelCreate">
        <form class="modal-card" @submit.prevent="submitCreate">
          <h3>补录演练记录</h3>
          <p class="modal-tip">{{ createForm.values.参与单位 }} · {{ createForm.values.演练主题 }}</p>
          <label>
            <span>演练编号</span>
            <input v-model="createForm.values.演练编号" placeholder="留空自动生成" />
          </label>
          <label>
            <span>演练类型（必填）</span>
            <input v-model="createForm.values.演练类型" placeholder="如：实战演练、桌面推演" />
          </label>
          <label>
            <span>演练日期</span>
            <input v-model="createForm.values.演练日期" type="date" />
          </label>
          <label>
            <span>演练评估</span>
            <input v-model="createForm.values.演练评估" placeholder="可后补" />
          </label>
          <label>
            <span>改进措施</span>
            <input v-model="createForm.values.改进措施" placeholder="可后补" />
          </label>
          <p v-if="createError" class="error-text">{{ createError }}</p>
          <footer>
            <button class="btn" type="button" @click="cancelCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="creating">
              {{ creating ? '提交中…' : '确认补录' }}
            </button>
          </footer>
        </form>
      </div>
    </template>

    <p v-else-if="!errorMessage" class="empty-state">暂无应急演练数据，可先在演练列表登记演练记录</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

interface MatrixEntry {
  id: number
  改进待落实: boolean
  [field: string]: string | number | boolean | null
}

interface MatrixCell {
  unit: string
  theme: string
  count: number
  todo: number
  entries: MatrixEntry[]
}

interface MatrixPayload {
  units: string[]
  themes: string[]
  cells: MatrixCell[]
  total: number
}

interface CellKey {
  unit: string
  theme: string
}

const props = defineProps<{ selectedCell: CellKey | null }>()
const emit = defineEmits<{ select: [cell: CellKey | null] }>()

const ENDPOINT = '/api/emergency'
const detailColumns = ["演练编号", "演练类型", "演练日期", "演练评估", "改进措施", "演练状态"]

const matrix = ref<MatrixPayload | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const createForm = ref<{ values: Record<string, string> } | null>(null)
const creating = ref(false)
const createError = ref('')

const cellMap = computed(() => {
  const map = new Map<string, MatrixCell>()
  for (const cell of matrix.value?.cells ?? []) {
    map.set(`${cell.unit}||${cell.theme}`, cell)
  }
  return map
})

function cellOf(unit: string, theme: string) {
  return cellMap.value.get(`${unit}||${theme}`)
}

const selectedEntries = computed<MatrixEntry[]>(() => {
  if (!props.selectedCell) {
    return []
  }
  return cellOf(props.selectedCell.unit, props.selectedCell.theme)?.entries ?? []
})

function cellClass(unit: string, theme: string) {
  const cell = cellOf(unit, theme)
  return {
    selected: props.selectedCell?.unit === unit && props.selectedCell?.theme === theme,
    'has-todo': Boolean(cell?.todo),
  }
}

function onCellClick(unit: string, theme: string) {
  const already = props.selectedCell?.unit === unit && props.selectedCell?.theme === theme
  if (already) {
    emit('select', null)
    return
  }
  emit('select', { unit, theme })
  const cell = cellOf(unit, theme)
  if (!cell) {
    // 空格直接补录：选中该格的同时弹出补录表单
    openCreate({ unit, theme })
  }
}

function openCreate(cell: CellKey) {
  createError.value = ''
  createForm.value = {
    values: {
      演练编号: '',
      演练主题: cell.theme,
      演练类型: '',
      参与单位: cell.unit,
      演练日期: '',
      演练评估: '',
      改进措施: '',
    },
  }
}

function cancelCreate() {
  createForm.value = null
  createError.value = ''
}

async function submitCreate() {
  if (!createForm.value || creating.value) {
    return
  }
  createError.value = ''
  if (!createForm.value.values.演练类型.trim()) {
    createError.value = '请填写演练类型'
    return
  }
  creating.value = true
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: createForm.value.values }),
    })
    const payload = (await response.json()) as { ok: boolean; message?: string }
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? '补录未生效，请稍后重试')
    }
    cancelCreate()
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '补录失败，请稍后重试'
  } finally {
    creating.value = false
  }
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/matrix`)
    if (!response.ok) {
      throw new Error(`概览矩阵读取失败（${response.status}）`)
    }
    matrix.value = (await response.json()) as MatrixPayload
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '概览矩阵读取失败，请重新加载'
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>
