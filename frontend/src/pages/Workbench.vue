<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON } from '../api'
import TierLadder from '../components/TierLadder.vue'
import SegmentTable from '../components/SegmentTable.vue'

const kwh = ref(220)
const peak = ref(false)
const accountId = ref(null)
const accounts = ref([])
const result = ref(null)
const error = ref('')

const run = async () => {
  error.value = ''
  try {
    result.value = await postJSON('/api/bill', {
      kwh: kwh.value,
      peak: peak.value,
      account_id: accountId.value,
      persist: true,
    })
  } catch (e) {
    error.value = `测算失败：${e.message}`
  }
}

onMounted(async () => {
  accounts.value = (await getJSON('/api/accounts')).items
})
</script>

<template>
  <div class="page work">
    <h1>测算工作台</h1>
    <div class="panel form-row">
      <label>户号
        <select v-model="accountId">
          <option :value="null">不选（全局档表）</option>
          <option v-for="a in accounts" :key="a.id" :value="a.id">
            {{ a.name }}（{{ a.zone_code || '无片区' }}）
          </option>
        </select>
      </label>
      <label>电量(kWh) <input type="number" v-model.number="kwh" min="0" step="1" /></label>
      <label><input type="checkbox" v-model="peak" /> 尖峰系数</label>
      <button @click="run">计算并入库</button>
    </div>
    <p v-if="error" class="panel err">{{ error }}</p>
    <div v-if="result" class="panel">
      <p>合计 ¥{{ result.total }} <span class="muted">记录#{{ result.run_id }}</span></p>
      <p class="reso">
        本次解析：
        <template v-if="result.resolution.fallback">
          <span class="tag fallback">回退全局档表</span>
          <span v-if="result.resolution.zone_code" class="muted">
            片区 {{ result.resolution.zone_code }} 无启用绑定
          </span>
          <span v-else class="muted">未指定户号</span>
        </template>
        <template v-else>
          <span class="tag">片区 {{ result.resolution.zone_code }}</span>
          方案 #{{ result.resolution.plan_id }}「{{ result.resolution.plan_name }}」
        </template>
        <span class="muted">（路径：{{ result.resolution.source }}）</span>
      </p>
      <TierLadder :segments="result.segments" />
      <SegmentTable :rows="result.segments" />
    </div>
  </div>
</template>

<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 1rem; align-items: end; }
input[type=number] { width: 6rem; margin-left: 0.35rem; }
select { background: #0d1612; border: 1px solid var(--muted); color: var(--text); padding: 0.35rem 0.5rem; border-radius: 6px; margin-left: 0.35rem; }
.reso { display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap; }
.tag { padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.8rem; background: color-mix(in srgb, var(--accent) 30%, transparent); color: var(--accent); }
.tag.fallback { background: color-mix(in srgb, #e0a75e 30%, transparent); color: #e0a75e; }
.err { border-left: 4px solid #e06c75; color: #f0b6bc; }
</style>
