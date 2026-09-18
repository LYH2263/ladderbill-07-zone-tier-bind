<script setup>
import { onMounted, ref } from 'vue'
import { getJSON, postJSON, putJSON } from '../api'

const bindings = ref([])
const plans = ref([])
const zones = ref([])
const error = ref('')
const notice = ref('')

const newBinding = ref({ zone_code: '', plan_id: null })
const newPlan = ref({ name: '', tiers: [{ up_to: null, price: 0.5 }] })

const load = async () => {
  const [b, p, z] = await Promise.all([
    getJSON('/api/zone-bindings'),
    getJSON('/api/tier-plans'),
    getJSON('/api/zones'),
  ])
  bindings.value = b.items.map((x) => ({ ...x, _plan_id: x.plan_id }))
  plans.value = p.items
  zones.value = z.items
  if (!newBinding.value.plan_id && p.items.length) newBinding.value.plan_id = p.items[0].id
}

const showError = (e) => {
  const d = e?.detail
  if (d?.error === 'zone_binding_conflict') {
    error.value = `片区 ${d.zone_code} 已绑定启用方案「${d.conflict_plan_name}」(方案#${d.conflict_plan_id})，请先停用该绑定或改绑。`
  } else {
    error.value = `操作失败：${e?.message ?? e}`
  }
}

const run = async (fn, okMsg) => {
  error.value = ''
  notice.value = ''
  try {
    await fn()
    notice.value = okMsg
    await load()
  } catch (e) {
    showError(e)
  }
}

const createBinding = () =>
  run(async () => {
    await postJSON('/api/zone-bindings', {
      zone_code: newBinding.value.zone_code.trim(),
      plan_id: newBinding.value.plan_id,
    })
    newBinding.value.zone_code = ''
  }, '绑定已创建')

const savePlan = (b) =>
  run(async () => {
    await putJSON(`/api/zone-bindings/${b.id}`, { plan_id: b._plan_id })
  }, `片区 ${b.zone_code} 已改绑`)

const toggle = (b) =>
  run(async () => {
    await putJSON(`/api/zone-bindings/${b.id}`, {
      status: b.status === 'enabled' ? 'disabled' : 'enabled',
    })
  }, b.status === 'enabled' ? `片区 ${b.zone_code} 绑定已停用` : `片区 ${b.zone_code} 绑定已启用`)

const addTier = () => newPlan.value.tiers.push({ up_to: null, price: 0.5 })
const dropTier = (i) => newPlan.value.tiers.splice(i, 1)

const createPlan = () =>
  run(async () => {
    const tiers = newPlan.value.tiers.map((t) => ({
      up_to: t.up_to === '' || t.up_to === null ? null : Number(t.up_to),
      price: Number(t.price),
    }))
    await postJSON('/api/tier-plans', { name: newPlan.value.name.trim(), tiers })
    newPlan.value = { name: '', tiers: [{ up_to: null, price: 0.5 }] }
  }, '方案已创建')

onMounted(load)
</script>

<template>
  <div class="page">
    <h1>片区档位绑定</h1>

    <p v-if="error" class="panel err">{{ error }}</p>
    <p v-if="notice" class="panel ok">{{ notice }}</p>

    <div class="panel">
      <h3>绑定关系</h3>
      <table>
        <thead>
          <tr><th>片区代码</th><th>绑定方案</th><th>状态</th><th>更新时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="b in bindings" :key="b.id">
            <td><strong>{{ b.zone_code }}</strong></td>
            <td>
              <select v-model.number="b._plan_id">
                <option v-for="p in plans" :key="p.id" :value="p.id">#{{ p.id }} {{ p.name }}</option>
              </select>
            </td>
            <td>
              <span class="tag" :class="b.status">{{ b.status === 'enabled' ? '启用' : '停用' }}</span>
            </td>
            <td class="muted">{{ b.updated_at }}</td>
            <td class="ops">
              <button v-if="b._plan_id !== b.plan_id" @click="savePlan(b)">保存改绑</button>
              <button class="ghost" @click="toggle(b)">{{ b.status === 'enabled' ? '停用' : '启用' }}</button>
            </td>
          </tr>
          <tr v-if="!bindings.length"><td colspan="5" class="muted">暂无绑定</td></tr>
        </tbody>
      </table>

      <h4>新增绑定</h4>
      <div class="form-row">
        <label>片区代码
          <input v-model="newBinding.zone_code" list="zone-codes" placeholder="如 Z03" />
          <datalist id="zone-codes">
            <option v-for="z in zones" :key="z" :value="z" />
          </datalist>
        </label>
        <label>档位方案
          <select v-model.number="newBinding.plan_id">
            <option v-for="p in plans" :key="p.id" :value="p.id">#{{ p.id }} {{ p.name }}</option>
          </select>
        </label>
        <button :disabled="!newBinding.zone_code.trim() || !newBinding.plan_id" @click="createBinding">绑定</button>
      </div>
      <p class="muted">同一片区同一时刻仅允许一套启用方案，重复绑定将被拒绝。</p>
    </div>

    <div class="panel">
      <h3>档位方案</h3>
      <div v-for="p in plans" :key="p.id" class="plan">
        <strong>#{{ p.id }} {{ p.name }}</strong>
        <table>
          <thead><tr><th>顺序</th><th>上限(kWh)</th><th>单价(元)</th></tr></thead>
          <tbody>
            <tr v-for="t in p.tiers" :key="t.id">
              <td>{{ t.sort_order }}</td>
              <td>{{ t.up_to ?? '以上' }}</td>
              <td>{{ t.price }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <h4>新建方案</h4>
      <div class="form-row">
        <label>方案名称 <input v-model="newPlan.name" placeholder="如 郊区居民方案" /></label>
      </div>
      <table class="tiers-edit">
        <thead><tr><th>上限(kWh，空为以上)</th><th>单价(元)</th><th></th></tr></thead>
        <tbody>
          <tr v-for="(t, i) in newPlan.tiers" :key="i">
            <td><input type="number" v-model="t.up_to" min="0" placeholder="以上" /></td>
            <td><input type="number" v-model="t.price" min="0" step="0.01" /></td>
            <td><button class="ghost" v-if="newPlan.tiers.length > 1" @click="dropTier(i)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <div class="form-row">
        <button class="ghost" @click="addTier">+ 加一档</button>
        <button :disabled="!newPlan.name.trim()" @click="createPlan">创建方案</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.form-row { display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; margin-top: 0.5rem; }
.form-row input, .form-row select { margin-left: 0.35rem; }
select { background: #0d1612; border: 1px solid var(--muted); color: var(--text); padding: 0.35rem 0.5rem; border-radius: 6px; }
.err { border-left: 4px solid #e06c75; color: #f0b6bc; }
.ok { border-left: 4px solid var(--accent); }
.tag { padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.8rem; background: color-mix(in srgb, var(--muted) 30%, transparent); }
.tag.enabled { background: color-mix(in srgb, var(--accent) 30%, transparent); color: var(--accent); }
.ops button { margin-right: 0.4rem; }
.ghost { background: transparent; border: 1px solid var(--muted); color: var(--text); }
.plan { margin-bottom: 0.75rem; }
.tiers-edit input { width: 8rem; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
