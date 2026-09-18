<script setup>
import { computed, onMounted, ref } from 'vue'
import { getJSON, patchJSON } from '../api'

const items = ref([])
const zones = ref([])
const zoneFilter = ref('')
const editing = ref({})
const error = ref('')

const load = async () => {
  const [a, z] = await Promise.all([getJSON('/api/accounts'), getJSON('/api/zones')])
  items.value = a.items
  zones.value = z.items
}

const filtered = computed(() => {
  if (!zoneFilter.value) return items.value
  if (zoneFilter.value === '__none__') return items.value.filter((a) => !a.zone_code)
  return items.value.filter((a) => a.zone_code === zoneFilter.value)
})

const saveZone = async (a) => {
  error.value = ''
  const zone = (editing.value[a.id] ?? a.zone_code ?? '').trim()
  try {
    await patchJSON(`/api/accounts/${a.id}`, { zone_code: zone || null })
    delete editing.value[a.id]
    await load()
  } catch (e) {
    error.value = `保存失败：${e.message}`
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h1>户号列表</h1>
    <div class="panel filter-row">
      <label>片区筛选
        <select v-model="zoneFilter">
          <option value="">全部</option>
          <option v-for="z in zones" :key="z" :value="z">{{ z }}</option>
          <option value="__none__">未设置片区</option>
        </select>
      </label>
      <span class="muted">{{ filtered.length }} / {{ items.length }} 户</span>
    </div>
    <p v-if="error" class="panel err">{{ error }}</p>
    <table>
      <thead><tr><th>名称</th><th>表号</th><th>片区</th><th>备注</th><th></th></tr></thead>
      <tbody>
        <tr v-for="a in filtered" :key="a.id">
          <td>{{ a.name }}</td>
          <td>{{ a.meter_no }}</td>
          <td>
            <span v-if="editing[a.id] === undefined">
              {{ a.zone_code || '—' }}
              <a href="javascript:;" class="edit" @click="editing[a.id] = a.zone_code ?? ''">编辑</a>
            </span>
            <span v-else>
              <input v-model="editing[a.id]" list="zone-codes" placeholder="片区代码" @keyup.enter="saveZone(a)" />
              <datalist id="zone-codes">
                <option v-for="z in zones" :key="z" :value="z" />
              </datalist>
              <a href="javascript:;" class="edit" @click="saveZone(a)">保存</a>
              <a href="javascript:;" class="edit" @click="delete editing[a.id]">取消</a>
            </span>
          </td>
          <td class="muted">{{ a.note }}</td>
          <td><router-link :to="`/accounts/${a.id}`">详情</router-link></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.filter-row { display: flex; gap: 1rem; align-items: center; }
select, input { background: #0d1612; border: 1px solid var(--muted); color: var(--text); padding: 0.35rem 0.5rem; border-radius: 6px; }
input { width: 7rem; }
.edit { margin-left: 0.5rem; font-size: 0.85rem; }
.err { border-left: 4px solid #e06c75; color: #f0b6bc; }
</style>
