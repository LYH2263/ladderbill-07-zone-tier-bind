<script setup>
import { computed, onMounted, ref } from 'vue'
import { getJSON, putJSON } from '../api'

const items = ref([])
const zones = ref([])
const zoneFilter = ref('__all__')
const savingId = ref(null)
const rowError = ref('')

async function load() {
  const r = await getJSON('/api/accounts')
  items.value = r.items
  zones.value = r.zones
}
onMounted(load)

const zoneOptions = computed(() => zones.value.map(z => z.zone_code).filter(c => c))
const filtered = computed(() => {
  if (zoneFilter.value === '__all__') return items.value
  if (zoneFilter.value === '__none__') return items.value.filter(a => !a.zone_code)
  return items.value.filter(a => a.zone_code === zoneFilter.value)
})

async function saveZone(a, ev) {
  const val = ev.target.value.trim()
  rowError.value = ''
  savingId.value = a.id
  try {
    const r = await putJSON(`/api/accounts/${a.id}/zone`, { zone_code: val || null })
    a.zone_code = r.account.zone_code
    const fresh = await getJSON('/api/accounts')
    zones.value = fresh.zones
  } catch (e) {
    rowError.value = `户号 ${a.name} 片区保存失败：${e.message}`
  } finally {
    savingId.value = null
  }
}
</script>
<template>
  <div class="page">
    <h1>户号列表</h1>
    <div class="panel filter-bar">
      <label>按片区筛选
        <select v-model="zoneFilter">
          <option value="__all__">全部片区</option>
          <option v-for="z in zones.filter(x => x.zone_code)" :key="z.zone_code" :value="z.zone_code">
            {{ z.zone_code }}（{{ z.account_count }} 户）
          </option>
          <option value="__none__">未分配片区</option>
        </select>
      </label>
      <router-link to="/zones">维护片区绑定 →</router-link>
      <span v-if="rowError" class="err">{{ rowError }}</span>
    </div>
    <table>
      <thead><tr><th>名称</th><th>表号</th><th>片区</th><th>备注</th><th></th></tr></thead>
      <tbody>
        <tr v-for="a in filtered" :key="a.id">
          <td>{{ a.name }}</td>
          <td>{{ a.meter_no }}</td>
          <td>
            <input
              class="zone-input"
              list="zone-options"
              :value="a.zone_code ?? ''"
              :disabled="savingId === a.id"
              placeholder="未分配"
              @change="saveZone(a, $event)"
            />
          </td>
          <td class="muted">{{ a.note }}</td>
          <td><router-link :to="`/accounts/${a.id}`">详情</router-link></td>
        </tr>
        <tr v-if="!filtered.length"><td colspan="5" class="muted">无符合户号</td></tr>
      </tbody>
    </table>
    <datalist id="zone-options">
      <option v-for="c in zoneOptions" :key="c" :value="c" />
    </datalist>
  </div>
</template>
<style scoped>
.filter-bar { display: flex; align-items: center; gap: 1.25rem; flex-wrap: wrap; }
.filter-bar label { display: flex; align-items: center; gap: 0.5rem; }
.zone-input { width: 7rem; }
.err { color: #e5484d; font-size: 0.85rem; }
</style>
