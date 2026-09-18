<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
import TierLadder from '../components/TierLadder.vue'
import SegmentTable from '../components/SegmentTable.vue'

const kwh = ref(220)
const peak = ref(false)
const accountId = ref('')
const accounts = ref([])
const result = ref(null)
const loadError = ref('')

onMounted(async () => {
  try {
    accounts.value = (await getJSON('/api/accounts')).items
  } catch (e) { loadError.value = e.message }
})

const run = async () => {
  loadError.value = ''
  result.value = await postJSON('/api/bill', {
    kwh: kwh.value,
    peak: peak.value,
    account_id: accountId.value === '' ? null : Number(accountId.value),
    persist: true,
  })
}
</script>
<template>
  <div class="page work">
    <h1>测算工作台</h1>
    <div class="panel form-row">
      <label>户号
        <select v-model="accountId">
          <option value="">（不指定·全局档表）</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">
            #{{ a.id }} {{ a.name }}{{ a.zone_code ? ` · ${a.zone_code}` : '' }}
          </option>
        </select>
      </label>
      <label>电量(kWh) <input type="number" v-model.number="kwh" min="0" step="1" /></label>
      <label><input type="checkbox" v-model="peak" /> 尖峰系数</label>
      <button @click="run">计算并入库</button>
    </div>
    <p v-if="loadError" class="err">{{ loadError }}</p>

    <div v-if="result" class="panel">
      <div class="resolution-bar">
        <span class="chip" :class="result.resolution.fallback ? 'warn' : 'ok'">
          {{ result.resolution.fallback ? '回退全局档表' : '片区方案' }}
        </span>
        <span>片区代码：<strong>{{ result.resolution.zone_code ?? '—' }}</strong></span>
        <span>方案标识：<strong>{{ result.resolution.scheme_code ?? 'GLOBAL' }}</strong></span>
        <span v-if="result.resolution.fallback" class="muted">
          回退原因：{{ ({
            no_account: '未指定户号', no_zone: '该户未分配片区',
            no_binding: '片区无绑定', scheme_disabled: '绑定方案已停用',
          })[result.resolution.fallback_reason] }}
        </span>
      </div>
      <details class="path-details">
        <summary>解析路径</summary>
        <code>{{ result.resolution.resolved_path.join('  →  ') }}</code>
      </details>
      <p>合计 ¥{{ result.total }} <span class="muted">记录#{{ result.run_id }}</span></p>
      <TierLadder :segments="result.segments" />
      <SegmentTable :rows="result.segments" />
    </div>
  </div>
</template>
<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: end; }
input[type=number] { width: 6rem; margin-left: 0.35rem; }
select { padding: 0.35rem 0.5rem; }
.resolution-bar { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center;
  padding: 0.5rem 0.75rem; border-radius: 8px; margin-bottom: 0.6rem;
  background: #0d1612; border: 1px solid color-mix(in srgb, var(--muted) 35%, transparent); }
.chip { padding: 0.15rem 0.6rem; border-radius: 999px; font-size: 0.8rem; font-weight: 600; }
.chip.ok { background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); }
.chip.warn { background: color-mix(in srgb, #e6a817 22%, transparent); color: #e6a817; }
.path-details { margin-bottom: 0.6rem; }
.path-details code { color: var(--muted); font-size: 0.82rem; }
.err { color: #e5484d; }
</style>
