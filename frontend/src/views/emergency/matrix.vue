<template>
  <div class="matrix-view">
    <p class="matrix-tip">
      行是用人单位、列是演练主题，格子里的数字是演练次数；标「待办」的格子还有改进措施未落实。
      点有数字的格子可下钻查看明细，点「暂无」可直接补录。
    </p>

    <div v-if="loading" class="matrix-state">矩阵数据加载中…</div>
    <div v-else-if="loadError" class="matrix-state">
      <span class="error-text">{{ loadError }}</span>
      <button class="btn" type="button" @click="loadMatrix">重新加载</button>
    </div>

    <template v-else>
      <table class="data-table matrix-table">
        <thead>
          <tr>
            <th class="corner">用人单位 \ 演练主题</th>
            <th v-for="theme in themes" :key="theme">{{ theme }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="unit in units" :key="unit">
            <th class="unit-head">{{ unit }}</th>
            <td
              v-for="theme in themes"
              :key="theme"
              class="matrix-cell"
              :class="cellClass(unit, theme)"
              @click="onCellClick(unit, theme)"
            >
              <template v-if="cellOf(unit, theme)">
                <span class="cell-count">{{ cellOf(unit, theme)!.count }} 次</span>
                <span v-if="cellOf(unit, theme)!.todo" class="todo-badge">
                  待办 {{ cellOf(unit, theme)!.todo }}
                </span>
              </template>
              <span v-else class="cell-none">暂无</span>
            </td>
          </tr>
          <tr v-if="!units.length">
            <td :colspan="themes.length + 1" class="empty-state">暂无演练数据，可先在列表页登记演练记录</td>
          </tr>
        </tbody>
      </table>

      <section v-if="selected" class="drill-panel">
        <header class="drill-head">
          <strong>{{ selected.unit }} × {{ selected.theme }}</strong>
          <span class="drill-sub">共 {{ drillRows.length }} 次演练，口径与演练列表一致</span>
          <button class="link" type="button" @click="closeDrill">收起</button>
        </header>
        <div v-if="drillLoading" class="matrix-state">明细加载中…</div>
        <div v-else-if="drillError" class="matrix-state">
          <span class="error-text">{{ drillError }}</span>
          <button class="btn" type="button" @click="loadDrill">重新加载</button>
        </div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th v-for="column in drillColumns" :key="column">{{ column }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in drillRows" :key="String(row.id)">
              <td v-for="column in drillColumns" :key="column">
                <template v-if="column === '改进措施'">
                  {{ row[column] ?? '—' }}
                  <span v-if="measurePending(row)" class="todo-badge">待落实</span>
                </template>
                <template v-else>{{ row[column] ?? '—' }}</template>
              </td>
            </tr>
            <tr v-if="!drillRows.length">
              <td :colspan="drillColumns.length" class="empty-state">该组合下暂无演练记录</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <div v-if="createForm" class="modal-mask" @click.self="closeCreate">
      <form class="modal-card" @submit.prevent="submitCreate">
        <h3>补录演练记录</h3>
        <p class="modal-sub">{{ createForm.unit }} × {{ createForm.theme }} 目前还没有演练，补录一条即可点亮这个格子。</p>
        <label class="form-item">
          <span>参与单位</span>
          <input v-model="createForm.unit" required />
        </label>
        <label class="form-item">
          <span>演练主题</span>
          <input v-model="createForm.theme" required />
        </label>
        <label class="form-item">
          <span>演练类型</span>
          <select v-model="createForm.type">
            <option v-for="kind in drillKinds" :key="kind" :value="kind">{{ kind }}</option>
          </select>
        </label>
        <label class="form-item">
          <span>演练日期</span>
          <input v-model="createForm.date" type="date" required />
        </label>
        <label class="form-item">
          <span>演练编号</span>
          <input v-model="createForm.code" placeholder="留空则自动生成" />
        </label>
        <p v-if="createError" class="error-text">{{ createError }}</p>
        <footer class="modal-actions">
          <button class="btn primary" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认补录' }}
          </button>
          <button class="btn ghost" type="button" @click="closeCreate">取消</button>
        </footer>
      </form>
    </div>

    <p v-if="notice" class="notice-text">{{ notice }}</p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface MatrixCell {
  unit: string
  theme: string
  count: number
  todo: number
}

interface CreateForm {
  unit: string
  theme: string
  type: string
  date: string
  code: string
}

const ENDPOINT = '/api/emergency'
const SELECTED_KEY = 'emergency:matrix:selected'
const drillColumns = ['演练编号', '演练日期', '演练类型', '演练评估', '改进措施', '演练状态']
const drillKinds = ['综合演练', '专项演练', '桌面推演']

const units = ref<string[]>([])
const themes = ref<string[]>([])
const cells = ref<MatrixCell[]>([])
const loading = ref(false)
const loadError = ref('')
const notice = ref('')

const selected = ref<{ unit: string; theme: string } | null>(null)
const drillRows = ref<Row[]>([])
const drillLoading = ref(false)
const drillError = ref('')

const createForm = ref<CreateForm | null>(null)
const creating = ref(false)
const createError = ref('')

function cellOf(unit: string, theme: string): MatrixCell | undefined {
  return cells.value.find((cell) => cell.unit === unit && cell.theme === theme)
}

function cellClass(unit: string, theme: string) {
  const cell = cellOf(unit, theme)
  return {
    clickable: true,
    selected: selected.value?.unit === unit && selected.value?.theme === theme,
    todo: Boolean(cell?.todo),
    none: !cell,
  }
}

function measurePending(row: Row): boolean {
  return Boolean(String(row['改进措施'] ?? '').trim()) && row['status'] !== '已复盘'
}

function rememberSelected() {
  if (selected.value) {
    sessionStorage.setItem(SELECTED_KEY, JSON.stringify(selected.value))
  } else {
    sessionStorage.removeItem(SELECTED_KEY)
  }
}

function onCellClick(unit: string, theme: string) {
  if (cellOf(unit, theme)) {
    void selectCell(unit, theme)
  } else {
    openCreate(unit, theme)
  }
}

async function selectCell(unit: string, theme: string) {
  selected.value = { unit, theme }
  rememberSelected()
  await loadDrill()
}

function closeDrill() {
  selected.value = null
  drillRows.value = []
  rememberSelected()
}

function openCreate(unit: string, theme: string) {
  createError.value = ''
  createForm.value = {
    unit,
    theme,
    type: drillKinds[0],
    date: new Date().toISOString().slice(0, 10),
    code: '',
  }
}

function closeCreate() {
  createForm.value = null
  createError.value = ''
}

async function loadMatrix() {
  loading.value = true
  loadError.value = ''
  notice.value = ''
  try {
    const response = await request(`${ENDPOINT}/matrix`)
    if (!response.ok) {
      throw new Error(`矩阵数据读取失败（${response.status}）`)
    }
    const payload = (await response.json()) as { units: string[]; themes: string[]; cells: MatrixCell[] }
    units.value = payload.units ?? []
    themes.value = payload.themes ?? []
    cells.value = payload.cells ?? []
    restoreSelected()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '矩阵数据读取失败，请重试'
  } finally {
    loading.value = false
  }
}

function restoreSelected() {
  const raw = sessionStorage.getItem(SELECTED_KEY)
  if (!raw) {
    return
  }
  try {
    const saved = JSON.parse(raw) as { unit?: string; theme?: string }
    if (saved.unit && saved.theme && cellOf(saved.unit, saved.theme)) {
      void selectCell(saved.unit, saved.theme)
    } else {
      sessionStorage.removeItem(SELECTED_KEY)
    }
  } catch {
    sessionStorage.removeItem(SELECTED_KEY)
  }
}

async function loadDrill() {
  if (!selected.value) {
    return
  }
  drillLoading.value = true
  drillError.value = ''
  const query = new URLSearchParams({
    unit: selected.value.unit,
    theme: selected.value.theme,
    size: '100',
  }).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error(`演练明细读取失败（${response.status}）`)
    }
    const payload = await response.json()
    drillRows.value = payload.items ?? []
  } catch (error) {
    drillError.value = error instanceof Error ? error.message : '演练明细读取失败，请重试'
  } finally {
    drillLoading.value = false
  }
}

async function submitCreate() {
  if (!createForm.value || creating.value) {
    return
  }
  creating.value = true
  createError.value = ''
  const form = createForm.value
  const values: Record<string, string> = {
    参与单位: form.unit,
    演练主题: form.theme,
    演练类型: form.type,
    演练日期: form.date,
  }
  if (form.code.trim()) {
    values['演练编号'] = form.code.trim()
  }
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '补录未成功，请稍后重试')
    }
    closeCreate()
    notice.value = `已补录 ${payload.entry?.['演练编号'] ?? ''}（${form.unit} × ${form.theme}）`
    await loadMatrix()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '补录未成功，请稍后重试'
  } finally {
    creating.value = false
  }
}

onMounted(loadMatrix)
</script>

<style scoped>
.matrix-tip {
  color: var(--muted);
  font-size: 12px;
  margin: 0 0 10px;
}
.matrix-state {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 16px 4px;
  font-size: 13px;
  color: var(--muted);
}
.matrix-table th.corner {
  color: var(--muted);
  font-weight: normal;
  min-width: 140px;
}
.matrix-table .unit-head {
  text-align: left;
  white-space: nowrap;
}
.matrix-cell {
  text-align: center;
  min-width: 110px;
}
.matrix-cell.clickable {
  cursor: pointer;
}
.matrix-cell.selected {
  outline: 2px solid var(--brand);
  outline-offset: -2px;
}
.matrix-cell.todo {
  background: #fff7ed;
}
.matrix-cell.none {
  background: #fafbfc;
}
.cell-count {
  font-weight: 600;
}
.cell-none {
  color: var(--muted);
  font-size: 12px;
}
.matrix-cell.none:hover .cell-none {
  color: var(--brand);
}
.todo-badge {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 999px;
  background: #fef3c7;
  color: #b45309;
  font-size: 12px;
  white-space: nowrap;
}
.drill-panel {
  margin-top: 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: #fff;
  padding: 12px;
}
.drill-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 10px;
}
.drill-sub {
  color: var(--muted);
  font-size: 12px;
  flex: 1;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal-card {
  width: 360px;
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.modal-card h3 {
  margin: 0;
  font-size: 15px;
}
.modal-sub {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item select {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
}
.modal-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 4px;
}
.notice-text {
  color: #15803d;
  font-size: 12px;
  margin: 10px 0 0;
}
</style>
