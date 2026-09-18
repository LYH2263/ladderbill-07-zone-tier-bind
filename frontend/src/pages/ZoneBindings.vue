<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { delJSON, getJSON, postJSON, putJSON } from '../api'

const schemes = ref([])
const bindings = ref([])
const loadError = ref('')
const banner = reactive({ text: '', kind: '' })
const showBanner = (text, kind = 'ok') => { banner.text = text; banner.kind = kind }

const enabledSchemes = computed(() => schemes.value.filter(s => s.enabled))
const schemeById = (id) => schemes.value.find(s => s.id === id)

async function loadAll() {
  loadError.value = ''
  try {
    const [s, b] = await Promise.all([getJSON('/api/tier-schemes'), getJSON('/api/zone-bindings')])
    schemes.value = s.items
    bindings.value = b.items
  } catch (e) { loadError.value = e.message }
}
onMounted(loadAll)

// ---------- 方案编辑 ----------
const schemeForm = ref(null)
const schemeFormError = ref('')
const blankTier = () => ({ up_to: '', price: '' })
const newSchemeForm = () => ({
  id: null, code: '', name: '', enabled: true,
  tiers: [blankTier(), blankTier(), blankTier()],
})

function startCreateScheme() { schemeFormError.value = ''; schemeForm.value = newSchemeForm() }
function startEditScheme(s) {
  schemeFormError.value = ''
  schemeForm.value = {
    id: s.id, code: s.code, name: s.name, enabled: s.enabled,
    tiers: s.tiers.map(t => ({ up_to: t.up_to ?? '', price: String(t.price) })),
  }
}
function cancelScheme() { schemeForm.value = null }
function addTierRow() { schemeForm.value.tiers.push(blankTier()) }
function removeTierRow(i) { schemeForm.value.tiers.splice(i, 1) }

function payloadTiers(tiers) {
  const rows = tiers.filter(t => String(t.price).trim() !== '')
  return rows.map((t, i) => ({
    up_to: i === rows.length - 1 && String(t.up_to).trim() === '' ? null : Number(t.up_to),
    price: Number(t.price),
  }))
}

async function saveScheme() {
  const f = schemeForm.value
  schemeFormError.value = ''
  const tiers = payloadTiers(f.tiers)
  try {
    if (f.id) {
      await putJSON(`/api/tier-schemes/${f.id}`, { name: f.name, enabled: f.enabled, tiers })
      showBanner(`方案 ${f.code} 已更新`)
    } else {
      await postJSON('/api/tier-schemes', { code: f.code.trim(), name: f.name, enabled: f.enabled, tiers })
      showBanner(`方案 ${f.code.trim()} 已创建`)
    }
    schemeForm.value = null
    await loadAll()
  } catch (e) {
    schemeFormError.value = e.status === 422
      ? '校验失败：档表上限须严格递增，仅末档上限可留空，单价须大于 0'
      : e.message
  }
}

async function toggleEnabled(s) {
  try {
    await putJSON(`/api/tier-schemes/${s.id}`, { enabled: !s.enabled })
    await loadAll()
  } catch (e) { showBanner(e.message, 'err') }
}

// ---------- 绑定编辑 ----------
const bindingForm = ref(null)
const bindingFormError = ref('')
function startCreateBinding() {
  bindingFormError.value = ''
  bindingForm.value = { zone_code: '', scheme_id: enabledSchemes.value[0]?.id ?? null, note: '', existing: false }
}
function startRebind(b) {
  bindingFormError.value = ''
  bindingForm.value = { zone_code: b.zone_code, scheme_id: b.scheme_id, note: b.note ?? '', existing: true }
}
function cancelBinding() { bindingForm.value = null }

async function saveBinding() {
  const f = bindingForm.value
  bindingFormError.value = ''
  const body = { scheme_id: Number(f.scheme_id), note: f.note || null }
  try {
    if (f.existing) {
      await putJSON(`/api/zone-bindings/${encodeURIComponent(f.zone_code)}`, body)
      showBanner(`片区 ${f.zone_code} 已改绑`)
    } else {
      await postJSON('/api/zone-bindings', { zone_code: f.zone_code.trim(), ...body })
      showBanner(`片区 ${f.zone_code.trim()} 已绑定`)
    }
    bindingForm.value = null
    await loadAll()
  } catch (e) {
    if (e.status === 409) {
      const d = e.data?.detail || {}
      bindingFormError.value = `绑定冲突：片区 ${d.zone_code} 已绑定方案 #${d.conflict_scheme_id}（${d.conflict_scheme_code ?? '—'}）。如需更换请用该行的“改绑”。`
    } else if (e.status === 400) {
      bindingFormError.value = e.message
    } else if (e.status === 422) {
      bindingFormError.value = '请填写片区代码并选择启用方案'
    } else {
      bindingFormError.value = e.message
    }
  }
}

async function unbind(b) {
  if (!window.confirm(`解除片区 ${b.zone_code} 的绑定？该片区测算将回退全局档表。`)) return
  try {
    await delJSON(`/api/zone-bindings/${encodeURIComponent(b.zone_code)}`)
    showBanner(`片区 ${b.zone_code} 已解绑，将回退全局档表`)
    await loadAll()
  } catch (e) { showBanner(e.message, 'err') }
}
</script>

<template>
  <div class="page">
    <h1>片区档位绑定</h1>
    <p v-if="loadError" class="banner err">{{ loadError }}</p>
    <p v-if="banner.text" class="banner" :class="banner.kind">{{ banner.text }}</p>

    <!-- 绑定关系 -->
    <section class="panel">
      <div class="section-head">
        <h3>片区 → 启用方案</h3>
        <button @click="startCreateBinding">新增绑定</button>
      </div>
      <form v-if="bindingForm" class="subform" @submit.prevent="saveBinding">
        <label>片区代码
          <input v-model="bindingForm.zone_code" :disabled="bindingForm.existing" placeholder="如 Z-C" />
        </label>
        <label>档位方案
          <select v-model="bindingForm.scheme_id">
            <option v-for="s in schemes" :key="s.id" :value="s.id" :disabled="!s.enabled">
              {{ s.code }} · {{ s.name }}{{ s.enabled ? '' : '（已停用）' }}
            </option>
          </select>
        </label>
        <label class="grow">备注 <input v-model="bindingForm.note" /></label>
        <div class="form-actions">
          <button type="submit">{{ bindingForm.existing ? '保存改绑' : '绑定' }}</button>
          <button type="button" class="ghost" @click="cancelBinding">取消</button>
        </div>
        <p v-if="bindingFormError" class="banner err form-note">{{ bindingFormError }}</p>
      </form>
      <table>
        <thead><tr><th>片区代码</th><th>方案标识</th><th>方案名称</th><th>状态</th><th>备注</th><th></th></tr></thead>
        <tbody>
          <tr v-for="b in bindings" :key="b.id">
            <td><strong>{{ b.zone_code }}</strong></td>
            <td>{{ b.scheme_code }}</td>
            <td>{{ b.scheme_name }}</td>
            <td>
              <span :class="b.scheme_enabled ? 'tag ok' : 'tag warn'">
                {{ b.scheme_enabled ? '启用' : '方案已停用→回退' }}
              </span>
            </td>
            <td class="muted">{{ b.note }}</td>
            <td class="row-actions">
              <a href="#" @click.prevent="startRebind(b)">改绑</a>
              <a href="#" class="danger" @click.prevent="unbind(b)">解绑</a>
            </td>
          </tr>
          <tr v-if="!bindings.length"><td colspan="6" class="muted">暂无绑定，片区将统一回退全局档表</td></tr>
        </tbody>
      </table>
    </section>

    <!-- 档位方案 -->
    <section class="panel">
      <div class="section-head">
        <h3>完整档位方案</h3>
        <button @click="startCreateScheme">新建方案</button>
      </div>
      <form v-if="schemeForm" class="subform" @submit.prevent="saveScheme">
        <div class="form-grid">
          <label>方案标识
            <input v-model="schemeForm.code" :disabled="!!schemeForm.id" placeholder="SCH-XX" />
          </label>
          <label>名称 <input v-model="schemeForm.name" /></label>
          <label class="check"><input type="checkbox" v-model="schemeForm.enabled" /> 启用</label>
        </div>
        <table class="tier-edit">
          <thead><tr><th>顺序</th><th>上限(kWh，末档留空)</th><th>单价(元)</th><th></th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in schemeForm.tiers" :key="i">
              <td>{{ i + 1 }}</td>
              <td><input v-model="t.up_to" type="number" min="0" placeholder="末档留空" /></td>
              <td><input v-model="t.price" type="number" min="0" step="0.01" /></td>
              <td><button type="button" class="ghost" @click="removeTierRow(i)">删</button></td>
            </tr>
          </tbody>
        </table>
        <div class="form-actions">
          <button type="button" class="ghost" @click="addTierRow">+ 加一档</button>
          <button type="submit">保存方案</button>
          <button type="button" class="ghost" @click="cancelScheme">取消</button>
        </div>
        <p v-if="schemeFormError" class="banner err form-note">{{ schemeFormError }}</p>
      </form>

      <div v-for="s in schemes" :key="s.id" class="scheme-card">
        <div class="scheme-head">
          <div>
            <strong>{{ s.code }}</strong> · {{ s.name }}
            <span :class="s.enabled ? 'tag ok' : 'tag warn'">{{ s.enabled ? '启用' : '停用' }}</span>
          </div>
          <div class="row-actions">
            <a href="#" @click.prevent="startEditScheme(s)">编辑档表</a>
            <a href="#" @click.prevent="toggleEnabled(s)">{{ s.enabled ? '停用' : '启用' }}</a>
          </div>
        </div>
        <table class="compact">
          <thead><tr><th>档</th><th>上限</th><th>单价</th></tr></thead>
          <tbody>
            <tr v-for="(t, i) in s.tiers" :key="i">
              <td>{{ i + 1 }}</td><td>{{ t.up_to ?? '以上' }}</td><td>¥{{ t.price }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.section-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; }
.section-head h3 { margin: 0; }
.subform { background: #0d1612; border: 1px solid color-mix(in srgb, var(--accent) 30%, transparent);
  border-radius: 10px; padding: 0.85rem 1rem; margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: end; }
.subform label { display: flex; flex-direction: column; gap: 0.3rem; font-size: 0.85rem; }
.subform label.grow { flex: 1; min-width: 12rem; }
.subform select, .subform input { min-width: 9rem; }
.subform input[type=checkbox] { min-width: 0; }
.form-grid { display: flex; gap: 0.75rem; flex-wrap: wrap; width: 100%; }
.form-grid .check { justify-content: center; }
.form-actions { display: flex; gap: 0.5rem; align-items: center; }
.form-note { width: 100%; margin: 0.4rem 0 0; }
.tier-edit { margin: 0.6rem 0; }
.tier-edit input { min-width: 0; width: 100%; }
button.ghost { background: transparent; color: var(--text); border: 1px solid var(--muted); }
.banner { background: color-mix(in srgb, var(--accent) 15%, transparent); border: 1px solid var(--accent);
  border-radius: 8px; padding: 0.5rem 0.75rem; }
.banner.err { background: color-mix(in srgb, #e5484d 18%, transparent); border-color: #e5484d; }
.tag { padding: 0.1rem 0.45rem; border-radius: 999px; font-size: 0.75rem; }
.tag.ok { background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); }
.tag.warn { background: color-mix(in srgb, #e6a817 22%, transparent); color: #e6a817; }
.row-actions { display: flex; gap: 0.75rem; white-space: nowrap; }
.row-actions .danger { color: #e5484d; }
.scheme-card { border: 1px solid color-mix(in srgb, var(--muted) 30%, transparent); border-radius: 10px;
  padding: 0.75rem 1rem; margin-bottom: 0.75rem; }
.scheme-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem; }
table.compact { width: auto; }
table.compact th, table.compact td { padding: 0.2rem 1.2rem 0.2rem 0; }
</style>
