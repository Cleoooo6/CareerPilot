<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import IndustryTrendsPanel from '@/components/IndustryTrendsPanel.vue'
import PageSkeleton from '@/components/PageSkeleton.vue'
import { ApiError } from '@/api/client'
import {
  getMarketDistribution,
  getMarketOverview,
  getMarketRoles,
  getMarketSkills,
  getMarketTrends,
} from '@/api/market'
import {
  analyzeIndustryPulseArticle,
  getIndustryPulse,
  getPersonalIndustryPulse,
  refreshIndustryPulse,
} from '@/api/industryPulse'
import {
  type IndustryPulseArticle,
  type IndustryPulseData,
  type PulseIndustry,
  type PulseIndustryFilter,
  type PulseRegion,
} from '@/types/industryPulse'
import type {
  Distribution,
  MarketOverview,
  SkillDemand,
  TrendData,
} from '@/types/market'
import type { IndustryCatalogItem } from '@/types/industryTrends'
import { userFacingText } from '@/utils/userFacing'
import { allocatePercentages } from '@/utils/percentages'
import { formatPulseDate } from '@/utils/pulseTime'

type ViewId = 'trends' | 'pulse'
type PulseState = 'loading' | 'success' | 'empty' | 'error'
type PulseView = 'all' | 'personal'

const PULSE_VIEWS: { id: PulseView; label: string }[] = [
  { id: 'all', label: '全部动态' },
  { id: 'personal', label: '与你相关' },
]
const PULSE_LIMIT = 20

const VIEWS: { id: ViewId; en: string; cn: string }[] = [
  { id: 'trends', en: 'Trends', cn: '趋势总览' },
  { id: 'pulse', en: 'Industry Pulse', cn: '行业动态' },
]


const PULSE_REGIONS: { id: PulseRegion; label: string }[] = [
  { id: 'all', label: '全部地区' },
  { id: 'CN', label: '中国' },
  { id: 'INTL', label: '国际' },
]

const route = useRoute()
const router = useRouter()

const activeView = computed<ViewId>(() =>
  route.query.view === 'pulse' ? 'pulse' : 'trends',
)

const overview = ref<MarketOverview | null>(null)
const skills = ref<SkillDemand | null>(null)
const education = ref<Distribution | null>(null)
const experience = ref<Distribution | null>(null)
const locations = ref<Distribution | null>(null)
const trends = ref<TrendData | null>(null)
const roles = ref<string[]>([])
const role = ref('')
const trendIndustry = ref<PulseIndustryFilter>('all')
const trendMonths = ref(12)
const trendCatalog = ref<IndustryCatalogItem[]>([])
const refreshNote = ref('')
const loading = ref(true)
const error = ref('')

const pulseIndustry = ref<PulseIndustryFilter>('all')
const pulseRegion = ref<PulseRegion>('all')
const pulseView = ref<PulseView>('all')
const pulseOffset = ref(0)
const pulse = ref<IndustryPulseData | null>(null)
const pulseState = ref<PulseState>('loading')
const pulseError = ref('')
const pulseRefreshing = ref(false)
const pulseRefreshError = ref('')
const analysisArticleId = ref('')
const pulseHelpId = ref<PulseIndustryFilter | null>(null)
let pulseHelpTimer: number | null = null

const meta = computed(() => overview.value?.meta)
const hasRealData = computed(() =>
  (meta.value?.dataset_kinds ?? []).includes('real'),
)
const datasetLabel = computed(() =>
  hasRealData.value ? '真实数据' : '暂无真实数据',
)
const realSources = computed(() =>
  (meta.value?.sources ?? []).filter(
    (source) => source.dataset_kind !== 'synthetic',
  ),
)
const sampleNote = computed(() =>
  meta.value && !meta.value.sample_sufficient ? '样本量较少，仅作参考' : '',
)
const maxTrend = computed(() =>
  Math.max(...(trends.value?.points.map((point) => point.count) ?? [1]), 1),
)
const axisMid = computed(() => Math.round(maxTrend.value / 2))
const skillsExpanded = ref(false)
const allSkillItems = computed(() => skills.value?.items ?? [])
const skillItems = computed(() =>
  skillsExpanded.value ? allSkillItems.value : allSkillItems.value.slice(0, 8),
)
const pulseItems = computed(() => pulse.value?.items ?? [])
const pulseRun = computed(() => pulse.value?.latest_run ?? null)
const pulseTotal = computed(() => pulse.value?.total ?? 0)
const pulsePage = computed(() => Math.floor(pulseOffset.value / PULSE_LIMIT) + 1)
const pulsePageCount = computed(() =>
  Math.max(1, Math.ceil(pulseTotal.value / PULSE_LIMIT)),
)
const pulseCanPrev = computed(() => pulseOffset.value > 0)
const pulseCanNext = computed(
  () => pulseOffset.value + PULSE_LIMIT < pulseTotal.value,
)
const pulseProfileMissing = computed(() => pulse.value?.profile_missing ?? [])
const pulseFilters = computed(() => [
  {
    id: 'all' as PulseIndustryFilter,
    label: '全部行业',
    scope: '',
    majors: [] as string[],
    source_count: 0,
  },
  ...(pulse.value?.industries ?? [])
    .slice()
    .sort(
      (left, right) =>
        Number(left.source_count === 0) - Number(right.source_count === 0),
    )
    .map((item) => ({
      id: item.id as PulseIndustryFilter,
      label: item.label,
      scope: item.scope,
      majors: item.majors,
      source_count: item.source_count,
    })),
])
const aiEnabled = computed(() => pulse.value?.ai_enabled ?? false)
const canAnalyze = computed(
  () => aiEnabled.value && pulse.value?.llm_mode === 'real',
)
const activeCoverage = computed(() =>
  pulse.value?.industries.find((item) => item.id === pulseIndustry.value) ?? null,
)
const aiUnavailableReason = computed(
  () => pulse.value?.ai_unavailable_reason ?? '',
)
const activeIndustryLabel = computed(
  () =>
    pulseFilters.value.find((item) => item.id === pulseIndustry.value)?.label ??
    '全部',
)
const activePulseHelp = computed(
  () => pulseFilters.value.find((item) => item.id === pulseHelpId.value) ?? null,
)
const pulseFutureCount = computed(
  () =>
    pulseItems.value.filter(
      (item) =>
        item.published_at &&
        new Date(item.published_at).getTime() > Date.now(),
    ).length,
)

const pulseStatusText = computed(() => {
  if (pulseState.value === 'loading') return '正在读取行业动态…'
  if (pulseState.value === 'error') return '行业动态暂时无法读取'
  return ''
})

const trendIndustryLabel = computed(
  () =>
    trendCatalog.value.find((item) => item.id === trendIndustry.value)?.label ??
    '全部行业',
)
const marketScopeNote = computed(() => {
  const parts = [`统计范围：${trendIndustryLabel.value}`, `近 ${trendMonths.value} 个月`]
  if (role.value) parts.push(`职业方向：${role.value}`)
  return parts.join(' · ')
})
const dataCoverageNote = computed(() => {
  const start = meta.value?.period_start
  const end = meta.value?.period_end
  if (!start || !end) return ''
  const a = new Date(start)
  const b = new Date(end)
  if (Number.isNaN(a.getTime()) || Number.isNaN(b.getTime())) return ''
  const span = (b.getFullYear() - a.getFullYear()) * 12 + b.getMonth() - a.getMonth() + 1
  return span < trendMonths.value
    ? `岗位数据仅覆盖约 ${span} 个月，近 ${trendMonths.value} 个月筛选结果与当前覆盖期相同。`
    : ''
})
const educationPcts = computed(() => allocatePercentages(education.value?.items ?? []))
const experiencePcts = computed(() => allocatePercentages(experience.value?.items ?? []))
const locationPcts = computed(() => allocatePercentages(locations.value?.items ?? []))


function barWidth(count: number, items: { count: number }[]): number {
  const max = Math.max(...items.map((item) => item.count), 1)
  return Math.max(2, Math.round((count / max) * 100))
}

function percentLabel(count: number, total: number): string {
  return total > 0 ? `${Math.round((count / total) * 100)}%` : '0%'
}

function setView(view: ViewId) {
  if (activeView.value === view) return
  void router.replace({ query: { ...route.query, view } })
  if (view === 'pulse' && !pulse.value) void loadPulse()
}

function onViewKeydown(event: KeyboardEvent, view: ViewId) {
  const index = VIEWS.findIndex((item) => item.id === view)
  let next = -1
  if (event.key === 'ArrowRight') next = (index + 1) % VIEWS.length
  if (event.key === 'ArrowLeft') next = (index - 1 + VIEWS.length) % VIEWS.length
  if (event.key === 'Home') next = 0
  if (event.key === 'End') next = VIEWS.length - 1
  if (next < 0) return
  event.preventDefault()
  const container = (event.currentTarget as HTMLElement | null)?.parentElement
  setView(VIEWS[next].id)
  void nextTick(() => {
    container
      ?.querySelectorAll<HTMLElement>('[role="tab"]')
      [next]?.focus()
  })
}

async function loadPulse() {
  pulseState.value = 'loading'
  pulseError.value = ''
  try {
    const params = {
      industry: pulseIndustry.value,
      region: pulseRegion.value,
      limit: PULSE_LIMIT,
      offset: pulseOffset.value,
    }
    const data =
      pulseView.value === 'personal'
        ? await getPersonalIndustryPulse(params)
        : await getIndustryPulse(params)
    pulse.value = data
    pulseState.value = data.items.length ? 'success' : 'empty'
  } catch (value) {
    pulseError.value = message(value)
    pulseState.value = 'error'
  }
}

function onPulseViewKeydown(event: KeyboardEvent, view: PulseView) {
  const index = PULSE_VIEWS.findIndex((item) => item.id === view)
  let next = -1
  if (event.key === 'ArrowRight') next = (index + 1) % PULSE_VIEWS.length
  if (event.key === 'ArrowLeft')
    next = (index - 1 + PULSE_VIEWS.length) % PULSE_VIEWS.length
  if (event.key === 'Home') next = 0
  if (event.key === 'End') next = PULSE_VIEWS.length - 1
  if (next < 0) return
  event.preventDefault()
  const container = (event.currentTarget as HTMLElement | null)?.parentElement
  void switchPulseView(PULSE_VIEWS[next].id)
  void nextTick(() => {
    container
      ?.querySelectorAll<HTMLElement>('[role="tab"]')
      [next]?.focus()
  })
}

async function switchPulseView(view: PulseView) {
  if (pulseView.value === view) return
  closePulseHelp()
  pulseView.value = view
  pulseOffset.value = 0
  pulseRefreshError.value = ''
  await loadPulse()
}

async function changePulseIndustry(industry: PulseIndustryFilter) {
  closePulseHelp()
  pulseIndustry.value = industry
  pulseOffset.value = 0
  pulseRefreshError.value = ''
  await loadPulse()
}

async function changePulseRegion(region: PulseRegion) {
  closePulseHelp()
  pulseRegion.value = region
  pulseOffset.value = 0
  pulseRefreshError.value = ''
  await loadPulse()
}

async function changePulsePage(delta: number) {
  const next = Math.max(0, pulseOffset.value + delta * PULSE_LIMIT)
  if (next === pulseOffset.value) return
  pulseOffset.value = next
  await loadPulse()
}

async function refreshPulse() {

  if (pulseRefreshing.value) return
  pulseRefreshing.value = true
  pulseRefreshError.value = ''
  try {
    await refreshIndustryPulse()
    await loadPulse()
  } catch (value) {
    pulseRefreshError.value = message(value)
  } finally {
    pulseRefreshing.value = false
  }
}

async function analyzePulseArticle(article: IndustryPulseArticle) {
  if (!canAnalyze.value || analysisArticleId.value) return
  analysisArticleId.value = article.id
  try {
    const updated = await analyzeIndustryPulseArticle(article.id)
    if (pulse.value) {
      pulse.value.items = pulse.value.items.map((item) =>
        item.id === updated.id ? updated : item,
      )
    }
  } catch (value) {
    pulseRefreshError.value = message(value)
  } finally {
    analysisArticleId.value = ''
  }
}

function pulseStatusLabel(status: IndustryPulseArticle['analysis_status']) {
  if (status === 'analyzed') return 'AI 已分析'
  if (status === 'failed') return '分析失败'
  if (status === 'disabled') return 'AI 未启用'
  return '待分析'
}

function pulseStatusClass(status: IndustryPulseArticle['analysis_status']) {
  if (status === 'analyzed') return 'tag-suggestion'
  if (status === 'failed') return 'tag-danger'
  return 'tag'
}

function pulseFoldLabel(status: IndustryPulseArticle['analysis_status']): string {
  if (status === 'disabled') return '未启用'
  if (status === 'failed') return '分析失败'
  return '待分析'
}

function matchTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    target_industry: '目标行业',
    role: '目标岗位',
    skill: '已记录技能',
    region: '目标地区',
    cross_industry: '跨行业关联',
  }
  return labels[type] ?? type
}

function industryLabel(id: PulseIndustry | null): string {
  if (!id) return '未分类'
  return pulseFilters.value.find((item) => item.id === id)?.label ?? id
}

function clearPulseHelpTimer() {
  if (pulseHelpTimer !== null) {
    window.clearTimeout(pulseHelpTimer)
    pulseHelpTimer = null
  }
}

function openPulseHelp(id: PulseIndustryFilter) {
  clearPulseHelpTimer()
  pulseHelpId.value = id
}

function cancelPulseHelpClose() {
  clearPulseHelpTimer()
}

function closePulseHelpSoon() {
  clearPulseHelpTimer()
  pulseHelpTimer = window.setTimeout(() => {
    pulseHelpId.value = null
    pulseHelpTimer = null
  }, 300)
}

function closePulseHelp() {
  clearPulseHelpTimer()
  pulseHelpId.value = null
}



function handlePulseEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') closePulseHelp()
}

function handlePulseOutside(event: MouseEvent) {
  const target = event.target as Element | null
  if (target?.closest('.pulse-chip-wrap, .pulse-help-panel')) return
  closePulseHelp()
}

function scrollPulseTop() {
  document
    .querySelector('.pulse-view-tabs')
    ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function message(value: unknown): string {
  if (value instanceof ApiError) return value.message
  return '市场数据加载失败，请稍后重试'
}

function share(count: number, sample: number): number {
  return sample > 0 ? Math.max(2, Math.round((count / sample) * 100)) : 0
}

function trendHeight(count: number): number {
  return Math.max(8, Math.round((count / maxTrend.value) * 100))
}

function formatDate(value: string | null): string {
  if (!value) return '暂无'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit' })
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const industry = trendIndustry.value
    const months = trendMonths.value
    const [overviewData, skillData, edu, exp, loc, trendData, roleData] =
      await Promise.all([
        getMarketOverview(role.value || undefined, industry, months),
        getMarketSkills(role.value || undefined, 20, industry, months),
        getMarketDistribution('education', role.value || undefined, industry, months),
        getMarketDistribution('experience', role.value || undefined, industry, months),
        getMarketDistribution('location', role.value || undefined, industry, months),
        getMarketTrends(role.value || undefined, industry, months),
        getMarketRoles(industry, months),
      ])
    overview.value = overviewData
    skills.value = skillData
    education.value = edu
    experience.value = exp
    locations.value = loc
    trends.value = trendData
    roles.value = roleData.items
  } catch (value) {
    error.value = message(value)
  } finally {
    loading.value = false
  }
}

async function refreshMarket() {
  const before = JSON.stringify({
    overview: overview.value?.total_jobs,
    skills: skills.value?.items,
    education: education.value?.items,
    experience: experience.value?.items,
    locations: locations.value?.items,
    trends: trends.value?.points,
  })
  await load()
  const after = JSON.stringify({
    overview: overview.value?.total_jobs,
    skills: skills.value?.items,
    education: education.value?.items,
    experience: experience.value?.items,
    locations: locations.value?.items,
    trends: trends.value?.points,
  })
  refreshNote.value =
    before === after ? '已刷新 · 数据无变化' : '已刷新 · 数据已更新'
}

watch([trendIndustry, trendMonths], () => {
  refreshNote.value = ''
  void load()
})

onMounted(() => {
  void load()
  if (activeView.value === 'pulse') void loadPulse()
  document.addEventListener('keydown', handlePulseEscape)
  document.addEventListener('click', handlePulseOutside)
})

onBeforeUnmount(() => {
  clearPulseHelpTimer()
  document.removeEventListener('keydown', handlePulseEscape)
  document.removeEventListener('click', handlePulseOutside)
})
</script>

<template>
  <section class="page market-page">
    <header class="page-head market-head">
      <div class="page-head-copy">
        <h1>Market Radar <span class="page-title-cn">市场洞察</span></h1>
        <p class="page-lede">
          趋势看判断，行业动态看资讯；样本量与来源始终标注。
        </p>
      </div>
    </header>

    <div class="market-v2-tabs" role="tablist" aria-label="市场洞察视图">
      <button
        v-for="view in VIEWS"
        :key="view.id"
        type="button"
        class="market-v2-tab"
        :class="{ 'is-active': activeView === view.id }"
        role="tab"
        :aria-selected="activeView === view.id"
        :tabindex="activeView === view.id ? 0 : -1"
        :data-view-id="view.id"
        @click="setView(view.id)"
        @keydown="onViewKeydown($event, view.id)"
      >
        {{ view.en }} {{ view.cn }}
      </button>
    </div>

    <div v-if="activeView === 'trends'" class="market-v2-body">
      <IndustryTrendsPanel
        v-model:industry="trendIndustry"
        v-model:months="trendMonths"
        @catalog="trendCatalog = $event"
      />

      <PageSkeleton v-if="loading" variant="market" />

      <template v-else>
        <ErrorNotice
          v-if="error"
          :error="{ code: 'MARKET_ERROR', message: error }"
          retryable
          @dismiss="error = ''"
          @retry="load"
        />

        <template v-if="overview && meta">
          <div class="market-filter" style="display: flex; justify-content: flex-end; margin-bottom: 12px">
            <label class="field compact">
              <span>职业方向</span>
              <select v-model="role" @change="load">
                <option value="">全部方向</option>
                <option v-for="item in roles" :key="item" :value="item">{{ item }}</option>
              </select>
            </label>
          </div>

          <p class="market-scope-note">
            {{ marketScopeNote }}
            <span v-if="dataCoverageNote"> · {{ dataCoverageNote }}</span>
          </p>
          <nav class="market-section-nav" aria-label="页内导航">
            <a href="#market-verdict">趋势判断</a>
            <a href="#market-stats">统计细节</a>
            <a href="#market-evidence">证据与缺口</a>
          </nav>

          <div v-if="overview.total_jobs > 0 && hasRealData" class="market-meta">
            <span class="badge">{{ datasetLabel }}</span>
            <span>样本 {{ meta.sample_size }} 条</span>
            <span>统计周期 {{ formatDate(meta.period_start) }}–{{ formatDate(meta.period_end) }}</span>
            <span>更新 {{ formatDate(meta.updated_at) }}</span>
            <span
              class="badge"
              :class="{ 'badge-warning': !meta.sample_sufficient }"
              title="样本达标阈值为 5 条；低于阈值仅作参考"
            >
              {{ meta.sample_sufficient ? '样本达标' : '样本量较少' }}
            </span>
            <span v-if="refreshNote" class="quiet-note" role="status">
              {{ refreshNote }}
            </span>
            <button
              type="button"
              class="button secondary small"
              style="margin-left: auto"
              :disabled="loading"
              @click="refreshMarket"
            >
              刷新数据
            </button>
          </div>

          <div
            v-if="overview.total_jobs > 0 && hasRealData"
            class="market-number-row"
          >
            <div class="market-number card">
              <span>岗位样本</span>
              <strong class="stat-number">{{ overview.total_jobs }}</strong>
            </div>
            <div class="market-number card">
              <span>企业数</span>
              <strong class="stat-number">{{ overview.total_companies }}</strong>
            </div>
            <div class="market-number card">
              <span>职业方向</span>
              <strong class="stat-number">{{ overview.total_roles }}</strong>
            </div>
          </div>

          <div
            v-if="overview.total_jobs === 0 || !hasRealData"
            class="state-card"
            style="margin-top: 18px"
          >
            <h3>暂无真实市场数据</h3>
            <p>
              当前没有可验证的真实招聘样本；不会展示合成演示岗位或统计。
            </p>
          </div>

          <template v-else>
            <div id="market-stats" class="market-section-heading">
              <h3>统计细节</h3>
              <span class="quiet-note">
                样本 {{ meta.sample_size }} 条 · {{ datasetLabel }}
              </span>
            </div>
            <div class="market-panel-grid">
              <section class="market-panel card">
                <div class="market-panel-head">
                  <div>
                    <p class="section-label">技能需求</p>
                    <h3>高频技能</h3>
                  </div>
                  <span class="quiet-note">
                    共 {{ allSkillItems.length }} 项 · 样本 {{ meta.sample_size }}
                  </span>
                </div>
                <div v-if="!skillItems.length" class="note">暂无技能统计。</div>
                <p v-else class="note">
                  显示前 {{ skillItems.length }} 项 · 共 {{ allSkillItems.length }} 项
                </p>
                <div
                  v-for="item in skillItems"
                  :key="item.skill"
                  class="market-bar-row"
                >
                  <span class="market-bar-label">
                    <em>{{ item.rank }}</em>{{ item.skill }}
                  </span>
                  <div class="market-bar-track">
                    <div
                      class="market-bar"
                      :style="{ width: `${barWidth(item.count, allSkillItems)}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">
                    {{ item.count }} · {{ percentLabel(item.count, meta.sample_size) }}
                  </span>
                </div>
                <button
                  v-if="allSkillItems.length > 8"
                  type="button"
                  class="link-button"
                  style="margin-top: 8px"
                  @click="skillsExpanded = !skillsExpanded"
                >
                  {{ skillsExpanded ? '收起' : `展开全部 ${allSkillItems.length} 项` }}
                </button>
              </section>

              <section class="market-panel card">
                <div class="market-panel-head">
                  <div>
                    <p class="section-label">方向分布</p>
                    <h3>职业方向需求</h3>
                  </div>
                  <span class="quiet-note">按岗位数</span>
                </div>
                <div
                  v-for="item in overview.top_roles"
                  :key="item.name"
                  class="market-bar-row"
                >
                  <span class="market-bar-label">{{ item.name }}</span>
                  <div class="market-bar-track">
                    <div
                      class="market-bar"
                      :style="{ width: `${barWidth(item.count, overview.top_roles)}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">
                    {{ item.count }} · {{ percentLabel(item.count, meta.sample_size) }}
                  </span>
                </div>
              </section>
            </div>

            <div class="market-panel-grid three">
              <section class="market-panel card">
                <div class="market-panel-head">
                  <h3>学历要求</h3>
                </div>
                <div
                  v-for="item in education?.items"
                  :key="item.name"
                  class="market-bar-row"
                >
                  <span class="market-bar-label">{{ item.name }}</span>
                  <div class="market-bar-track">
                    <div
                      class="market-bar"
                      :style="{ width: `${barWidth(item.count, education?.items ?? [])}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">
                    {{ educationPcts[item.name] ?? 0 }}% · {{ item.count }}
                  </span>
                </div>
              </section>
              <section class="market-panel card">
                <div class="market-panel-head">
                  <h3>经验要求</h3>
                </div>
                <div
                  v-for="item in experience?.items"
                  :key="item.name"
                  class="market-bar-row"
                >
                  <span class="market-bar-label">{{ item.name }}</span>
                  <div class="market-bar-track">
                    <div
                      class="market-bar"
                      :style="{ width: `${barWidth(item.count, experience?.items ?? [])}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">
                    {{ experiencePcts[item.name] ?? 0 }}% · {{ item.count }}
                  </span>
                </div>
              </section>
              <section class="market-panel card">
                <div class="market-panel-head">
                  <h3>地区需求</h3>
                </div>
                <div
                  v-for="item in locations?.items"
                  :key="item.name"
                  class="market-bar-row"
                >
                  <span class="market-bar-label">{{ item.name }}</span>
                  <div class="market-bar-track">
                    <div
                      class="market-bar"
                      :style="{ width: `${barWidth(item.count, locations?.items ?? [])}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">
                    {{ locationPcts[item.name] ?? 0 }}% · {{ item.count }}
                  </span>
                </div>
              </section>
            </div>

            <p class="market-note">
              百分比采用最大余数法取整，合计 100%；条形长度按组内最大值缩放。
            </p>

            <section class="market-panel market-trend-panel card">
              <div class="market-panel-head">
                <div>
                  <p class="section-label">时间变化</p>
                  <h3>技能需求趋势</h3>
                </div>
                <span class="quiet-note">
                  {{ trendIndustryLabel }} · 近 {{ trendMonths }} 个月 · 单位：岗位数
                </span>
              </div>
              <div v-if="trends?.insufficient_data" class="empty-inline">
                <p>岗位数据覆盖不足 3 个月，暂不绘制趋势图。</p>
                <p class="quiet-note">
                  当前样本 {{ meta.sample_size }} 条；不会用等高柱或虚构月度制造趋势。
                </p>
              </div>
              <div
                v-else
                class="market-trend-wrap"
                role="img"
                :aria-label="`技能需求趋势：${trendIndustryLabel}，近 ${trendMonths} 个月岗位数`"
              >
                <div class="trend-y-axis">
                  <span>{{ maxTrend }}</span>
                  <span>{{ axisMid }}</span>
                  <span>0</span>
                </div>
                <div class="market-trend">
                  <div
                    v-for="point in trends?.points"
                    :key="point.period"
                    class="trend-point"
                  >
                    <strong>{{ point.count }}</strong>
                    <div class="trend-track">
                      <div
                        class="trend-bar"
                        :style="{ height: `${trendHeight(point.count)}%` }"
                      ></div>
                    </div>
                    <span>{{ point.period }}</span>
                  </div>
                </div>
              </div>
              <details v-if="!trends?.insufficient_data" class="chart-data">
                <summary>查看数据表</summary>
                <table class="chart-data-table">
                  <thead>
                    <tr>
                      <th>月份</th>
                      <th>岗位数</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="point in trends?.points" :key="point.period">
                      <td>{{ point.period }}</td>
                      <td>{{ point.count }}</td>
                    </tr>
                  </tbody>
                </table>
              </details>
              <p class="market-note">
                按岗位发布时间月度计数；柱高按组内最大值缩放。
              </p>
            </section>
          </template>

          <details class="market-source-panel card" style="padding: 20px 24px; margin-top: 18px">
            <summary class="profile-subsection-summary">
              <h3>数据来源与授权说明</h3>
              <span class="badge">{{ datasetLabel }}</span>
            </summary>
            <div
              v-for="source in realSources"
              :key="source.name"
              class="market-source"
            >
              <div class="market-source-head">
                <strong>{{ userFacingText(source.name) }}</strong>
                <span class="badge">
                  {{ source.dataset_kind === 'synthetic' ? '演示数据' : '真实数据' }}
                </span>
              </div>
              <p>
                {{
                  source.dataset_kind === 'synthetic'
                    ? '演示数据，仅用于体验，不代表真实招聘市场'
                    : source.license_note
                }}
              </p>
            </div>
            <p class="note">
              统计口径为导入岗位计数；薪资维度尚未接入真实数据，仅用于方向参考。
            </p>
          </details>

          <p v-if="sampleNote || dataCoverageNote" class="market-warning">
            {{ [sampleNote, dataCoverageNote].filter(Boolean).join(' · ') }}
          </p>
        </template>

        <p v-else class="note">当前没有可展示的市场统计。</p>
      </template>
    </div>

    <div v-else class="market-v2-body">
      <div class="trend-tabs pulse-view-tabs" role="tablist" aria-label="行业动态视图">
        <button
          v-for="view in PULSE_VIEWS"
          :key="view.id"
          type="button"
          role="tab"
          class="trend-tab"
          :class="{ 'is-active': pulseView === view.id }"
          :aria-selected="pulseView === view.id"
          :tabindex="pulseView === view.id ? 0 : -1"
          :data-pulse-view="view.id"
          @click="switchPulseView(view.id)"
          @keydown="onPulseViewKeydown($event, view.id)"
        >
          {{ view.label }}
        </button>
      </div>

      <div class="pulse-toolbar">
        <div class="pulse-filter-group pulse-filter-industry">
          <span class="pulse-filter-label">行业筛选</span>
          <div class="pulse-filters" role="group" aria-label="行业筛选">
            <div
              v-for="item in pulseFilters"
              :key="item.id"
              class="pulse-chip-wrap"
              @mouseleave="closePulseHelpSoon"
              @focusout="closePulseHelpSoon"
            >
              <button
                type="button"
                class="chip"
                :class="{
                  'is-active': pulseIndustry === item.id,
                  'is-unavailable': item.id !== 'all' && item.source_count === 0,
                }"
                @click="changePulseIndustry(item.id)"
              >
                {{ item.label }}
              </button>
              <span
                v-if="item.id !== 'all' && item.source_count === 0"
                class="pulse-no-source"
              >
                暂无来源
              </span>
              <button
                v-if="item.scope"
                type="button"
                class="pulse-help"
                :aria-label="`查看${item.label}说明`"
                :aria-expanded="pulseHelpId === item.id"
                title="查看行业说明"
                @mouseenter="openPulseHelp(item.id)"
                @focusin="openPulseHelp(item.id)"
                @click.stop="openPulseHelp(item.id)"
              >
                ?
              </button>
            </div>
          </div>
        </div>
        <div class="pulse-filter-group pulse-filter-region">
          <span class="pulse-filter-label">地区筛选</span>
          <div class="pulse-filters" role="group" aria-label="地区筛选">
            <button
              v-for="item in PULSE_REGIONS"
              :key="item.id"
              type="button"
              class="chip"
              :class="{ 'is-active': pulseRegion === item.id }"
              @click="changePulseRegion(item.id)"
            >
              {{ item.label }}
            </button>
          </div>
        </div>
        <button
          type="button"
          class="button secondary small pulse-refresh"
          :disabled="pulseRefreshing"
          @click="refreshPulse"
        >
          {{ pulseRefreshing ? '采集中…' : '手动更新' }}
        </button>
      </div>

      <div
        v-if="activePulseHelp"
        class="pulse-help-panel"
        role="region"
        aria-live="polite"
        @mouseenter="cancelPulseHelpClose"
        @mouseleave="closePulseHelpSoon"
      >
        <button
          type="button"
          class="pulse-help-close"
          aria-label="关闭行业说明"
          @click="closePulseHelp"
        >
          ×
        </button>
        <strong>{{ activePulseHelp.label }}</strong>
        <p>{{ activePulseHelp.scope }}</p>
        <p class="pulse-help-sub">相关专业方向（示例）</p>
        <ul>
          <li v-for="major in activePulseHelp.majors" :key="major">{{ major }}</li>
        </ul>
        <p class="pulse-help-note">{{ pulse?.industry_majors_note }}</p>
      </div>

      <div class="pulse-source-note">
        公开 RSS 来源；发布时间统一按北京时间（Asia/Shanghai）显示。仅展示 RSS
        提供的标题、摘要（来源允许时）、发布时间与原文链接，保留来源署名。
        部分来源仅提供元数据，因此不展示正文摘要。AI 分析默认关闭，AI
        内容会明确标注为推断。
      </div>

      <div
        v-if="pulse && pulseState !== 'loading' && pulseState !== 'error'"
        class="pulse-count"
      >
        共 {{ pulseTotal }} 条 · 第 {{ pulsePage }} / {{ pulsePageCount }} 页
        <span v-if="pulseView === 'personal'"> · 仅展示与你画像有可解释关联的新闻</span>
      </div>

      <div
        v-if="pulseView === 'personal' && pulse?.profile_sufficient && pulseState !== 'loading'"
        class="pulse-personal-banner"
      >
        <span>目标岗位：{{ pulse.personal_target_role || '未填写' }}</span>
        <span>目标行业：{{ pulse.personal_target_industry || '未填写' }}</span>
        <span>地区：{{ pulse.personal_target_location || '未填写' }}</span>
        <span class="quiet-note">仅使用已确认画像；资料记录不等于能力验证。</span>
      </div>

      <p
        v-if="pulseState !== 'loading' && pulseFutureCount"
        class="pulse-time-warning"
      >
        当前页有 {{ pulseFutureCount }} 条发布时间晚于当前时间，可能因来源未标注时区；已标记“待核实”，不以未来时间展示。
      </p>

      <p
        v-if="pulseState !== 'loading' && activeCoverage && activeCoverage.source_count === 0"
        class="market-warning"
      >
        {{ activeCoverage.label }}暂无已启用的可靠来源；当前不填充示例新闻。
      </p>

      <div v-if="pulseRun && pulseState !== 'loading'" class="pulse-run">
        最近更新 {{ formatPulseDate(pulseRun.finished_at || pulseRun.started_at) }}
        <template v-if="pulseRefreshing">
          · 采集中…（完成后刷新统计）
        </template>
        <template v-else>
          · 最近一次采集：解析 {{ pulseRun.articles_fetched }} 条，去重后入库
          {{ pulseRun.articles_inserted }} 条
          <template v-if="pulseRun.stats_legacy">
            · 历史运行未区分重复与上限跳过
          </template>
          <template v-else>
            · 重复 {{ pulseRun.articles_duplicates }} 条
            <span v-if="pulseRun.articles_skipped_limit">
              · 上限跳过 {{ pulseRun.articles_skipped_limit }} 条
            </span>
          </template>
        </template>
        · 来源成功 {{ pulseRun.sources_ok }}/{{ pulseRun.sources_total }}
        <span v-if="pulseRun.sources_failed">· 失败 {{ pulseRun.sources_failed }}</span>
        <span v-if="pulseRun.sources_skipped">· 未处理 {{ pulseRun.sources_skipped }}</span>
      </div>

      <p v-if="pulseRefreshError" class="error-inline">{{ pulseRefreshError }}</p>

      <div
        v-if="pulseState === 'loading'"
        class="pulse-list pulse-loading"
        aria-busy="true"
      >
        <p class="pulse-loading-note">正在加载动态…</p>
        <div
          v-for="index in 3"
          :key="index"
          class="skeleton skeleton-block pulse-skeleton"
        ></div>
      </div>

      <div v-else-if="pulseState === 'error'" class="error-inline">
        <span>{{ pulseError || '行业动态暂时无法读取，趋势总览不受影响。' }}</span>
        <button
          type="button"
          class="button secondary small"
          @click="loadPulse"
        >
          重新加载
        </button>
      </div>

      <div v-else-if="pulseView === 'personal' && pulse && pulse.profile_sufficient === false" class="state-card">
        <h3>先完善职业画像</h3>
        <p>{{ pulse.personalization_reason }}</p>
        <p class="quiet-note">缺少：{{ pulseProfileMissing.join('、') }}</p>
        <RouterLink class="button secondary" to="/profile">完善 Profile</RouterLink>
      </div>

      <div v-else-if="!pulseItems.length" class="state-card">
        <h3>
          {{
            pulseView === 'personal'
              ? '暂无与你相关的行业动态'
              : activeCoverage && activeCoverage.article_count === 0
                ? '暂无高相关行业动态'
                : '暂时没有行业动态'
          }}
        </h3>
        <p v-if="pulseView === 'personal'">
          {{ pulse?.personalization_reason || '当前筛选下没有与画像形成可解释关联的新闻；未用其他新闻凑数。' }}
        </p>
        <p v-else-if="activeCoverage && activeCoverage.article_count === 0">
          {{ activeCoverage.label }}当前没有通过产业相关性判断的新闻；未分类与宏观信号不会计入该行业。
        </p>
        <p v-else>
          {{ activeIndustryLabel }}筛选下没有已采集文章。可以手动更新，或切换到其他行业。
        </p>
        <button type="button" class="button secondary" @click="loadPulse">
          重新加载
        </button>
      </div>

      <div v-else class="pulse-list">
        <article
          v-for="item in pulseItems"
          :key="item.id"
          class="pulse-card card pulse-row"
        >
          <div class="pulse-row-main">
            <div class="pulse-meta">
              <span v-if="!item.industry_labels.length" class="tag tag-muted">
                未分类
              </span>
              <span v-for="label in item.industry_labels" :key="label" class="tag">
                {{ label }}
              </span>
              <span class="tag tag-muted">
                {{ item.region === 'CN' ? '中国' : '国际' }}
              </span>
              <span class="tag tag-muted pulse-source-pill">
                {{ item.source_name }}
              </span>
              <span class="tag" :class="pulseStatusClass(item.analysis_status)">
                {{ pulseStatusLabel(item.analysis_status) }}
              </span>
            </div>
            <h3>{{ item.title }}</h3>
            <p v-if="item.content_policy === 'feed_excerpt'" class="pulse-summary">
              {{ item.summary || 'RSS 未提供摘要。' }}
            </p>
            <div
              v-if="pulseView === 'personal' && item.match_reasons?.length"
              class="pulse-match"
            >
              <div class="pulse-match-head">
                <strong>为什么与你相关</strong>
                <span v-if="item.match_types?.length" class="pulse-match-types">
                  <span
                    v-for="type in item.match_types"
                    :key="type"
                    class="pulse-match-type"
                  >
                    {{ matchTypeLabel(type) }}
                  </span>
                </span>
              </div>
              <ul>
                <li v-for="reason in item.match_reasons" :key="reason">
                  {{ reason }}
                </li>
              </ul>
              <p v-if="item.industries.length > 1" class="pulse-match-primary">
                主标签：{{ industryLabel(item.primary_industry) }}（共
                {{ item.industries.length }} 个行业标签）
              </p>
              <p class="quiet-note">
                匹配依据为确定性规则，按目标行业/岗位/技能/地区逐项说明，不生成综合分数。
              </p>
            </div>

            <div v-if="item.analysis_status === 'analyzed'" class="pulse-sections">
              <div class="pulse-section">
                <strong>AI 摘要 · 推断</strong>
                <p>{{ item.ai_summary }}</p>
              </div>
              <div class="pulse-section">
                <strong>职业影响 · 推断</strong>
                <p>{{ item.career_impact }}</p>
              </div>
            </div>
            <details
              v-else-if="item.analysis_status === 'pending' || item.analysis_status === 'failed'"
              class="pulse-ai-fold"
            >
              <summary>AI 分析（{{ pulseFoldLabel(item.analysis_status) }}）</summary>
              <p class="quiet-note">
                {{ aiUnavailableReason || '当前没有可展示的 AI 分析。' }}
              </p>
              <button
                v-if="canAnalyze && item.content_policy === 'feed_excerpt'"
                type="button"
                class="button secondary small"
                :disabled="analysisArticleId === item.id"
                @click="analyzePulseArticle(item)"
              >
                {{ analysisArticleId === item.id ? '分析中…' : '分析本文' }}
              </button>
            </details>
          </div>

          <div class="pulse-row-side">
            <span class="pulse-time">{{ formatPulseDate(item.published_at) }}</span>
            <a
              :href="item.url"
              class="link-button"
              target="_blank"
              rel="noreferrer"
              title="将在新标签页打开外部来源，可能离开本站"
            >
              查看原文 ↗
            </a>
          </div>
        </article>
      </div>

      <div
        v-if="pulseState === 'success' && pulseTotal > PULSE_LIMIT"
        class="pulse-pagination"
      >
        <button
          type="button"
          class="button secondary small"
          :disabled="!pulseCanPrev"
          @click="changePulsePage(-1)"
        >
          上一页
        </button>
        <span>第 {{ pulsePage }} / {{ pulsePageCount }} 页 · 共 {{ pulseTotal }} 条</span>
        <button
          type="button"
          class="button secondary small"
          :disabled="!pulseCanNext"
          @click="changePulsePage(1)"
        >
          下一页
        </button>
        <button
          type="button"
          class="button secondary small"
          @click="scrollPulseTop"
        >
          回到顶部
        </button>
      </div>
    </div>
  </section>
</template>