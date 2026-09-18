<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getJSON, postJSON } from '../api'
import SegmentTable from '../components/SegmentTable.vue'
const route = useRoute()
const data = ref(null)
const bill = ref(null)
const peak = ref(false)
const load = async () => {
  data.value = await getJSON(`/api/accounts/${route.params.id}`)
  const r = data.value.readings[0]
  if (r) bill.value = await postJSON('/api/bill', { account_id: +route.params.id, kwh: r.kwh, peak: !!r.peak, persist: false })
}
onMounted(load)
watch(() => route.params.id, load)
const account = computed(() => data.value?.account)
</script>
<template>
  <div class="page" v-if="account">
    <h1>{{ account.name }}</h1>
    <p class="muted">表号 {{ account.meter_no }} · {{ account.note }}</p>
    <div class="panel">
      <h3>最近抄表试算</h3>
      <label><input type="checkbox" v-model="peak" @change="bill = null" /> 尖峰</label>
      <button @click="load">刷新</button>
      <p v-if="bill" class="resolution-line">
        <span :class="bill.resolution?.fallback ? 'tag warn' : 'tag ok'">
          {{ bill.resolution?.fallback ? '回退全局档表' : '片区方案' }}
        </span>
        片区 {{ bill.resolution?.zone_code ?? '—' }} ·
        方案 {{ bill.resolution?.scheme_code ?? 'GLOBAL' }}
      </p>
      <p v-if="bill">合计 <strong class="hero-num" style="font-size:1.5rem">¥{{ bill.total }}</strong></p>
      <SegmentTable :rows="bill?.segments || []" />
    </div>
  </div>
</template>
<style scoped>
.resolution-line { font-size: 0.85rem; }
.tag { padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; margin-right: 0.35rem; }
.tag.ok { background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); }
.tag.warn { background: color-mix(in srgb, #e6a817 22%, transparent); color: #e6a817; }
</style>
