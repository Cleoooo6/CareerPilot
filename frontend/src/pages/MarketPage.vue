<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
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
  PULSE_EXAMPLES,
  PULSE_INDUSTRIES,
  type PulseIndustry,
  type PulseItem,
} from '@/data/industryPulse'
import type {
  Distribution,
  MarketOverview,
  SkillDemand,
  TrendData,
} from '@/types/market'
import { userFacingText } from '@/utils/userFacing'

type ViewId = 'trends' | 'pulse'
type PulseState = 'normal' | 'loading' | 'empty' | 'error'

const VIEWS: { id: ViewId; en: string; cn: string }[] = [
  { id: 'trends', en: 'Trends', cn: '趋势总览' },
  { id: 'pulse', en: 'Industry Pulse', cn: '行业动态' },
]

const PULSE_FILTERS: { id: 'all' | PulseIndustry; label: string }[] = [
  { id: 'all', label: '全部' },
  ...PULSE_INDUSTRIES,
]

const PULSE_STATES: { id: PulseState; label: string }[] = [
  { id: 'normal', label: '正常' },
  { id: 'loading', label: '加载' },
  { id: 'empty', label: '空' },
  { id: 'error', label: '错误' },
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
const loading = ref(true)
const error = ref('')

const pulseIndustry = ref<'all' | PulseIndustry>('all')
const pulseState = ref<PulseState>('normal')

const meta = computed(() => overview.value?.meta)
const datasetLabel = computed(() => {
  const kinds = meta.value?.dataset_kinds ?? []
  if (kinds.includes('real') && kinds.includes('synthetic')) return '真实 + 演示'
  if (kinds.includes('real')) return '真实数据'
  if (kinds.includes('synthetic')) return '演示数据'
  return '无数据'
})
const datasetNote = computed(() => {
  const kinds = meta.value?.dataset_kinds ?? []
  return kinds.includes('synthetic')
    ? '演示数据，仅用于体验，不代表真实招聘市场'
    : ''
})
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
const pulseItems = computed<PulseItem[]>(() => {
  if (pulseState.value !== 'normal') return []
  return pulseIndustry.value === 'all'
    ? PULSE_EXAMPLES
    : PULSE_EXAMPLES.filter((item) => item.industry === pulseIndustry.value)
})
const activeIndustryLabel = computed(
  () =>
    PULSE_FILTERS.find((item) => item.id === pulseIndustry.value)?.label ??
    '全部',
)

function setView(view: ViewId) {
  if (activeView.value === view) return
  void router.replace({ query: { ...route.query, view } })
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
    const [overviewData, skillData, edu, exp, loc, trendData, roleData] =
      await Promise.all([
        getMarketOverview(role.value || undefined),
        getMarketSkills(role.value || undefined),
        getMarketDistribution('education', role.value || undefined),
        getMarketDistribution('experience', role.value || undefined),
        getMarketDistribution('location', role.value || undefined),
        getMarketTrends(role.value || undefined),
        getMarketRoles(),
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

onMounted(load)
</script>

<template>
  <section class="page market-page">
    <header class="page-head market-head">
      <div class="page-head-copy">
        <h2>Market Radar <span class="page-title-cn">市场洞察</span></h2>
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
        @click="setView(view.id)"
      >
        {{ view.en }} {{ view.cn }}
      </button>
    </div>

    <div v-if="activeView === 'trends'" class="market-v2-body">
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

          <div class="market-meta">
            <span class="badge">{{ datasetLabel }}</span>
            <span>样本 {{ meta.sample_size }} 条</span>
            <span>统计周期 {{ formatDate(meta.period_start) }}–{{ formatDate(meta.period_end) }}</span>
            <span>更新 {{ formatDate(meta.updated_at) }}</span>
            <span
              class="badge"
              :class="{ 'badge-warning': !meta.sample_sufficient }"
            >
              {{ meta.sample_sufficient ? '样本达标' : '样本量较少' }}
            </span>
            <button
              type="button"
              class="button secondary small"
              style="margin-left: auto"
              :disabled="loading"
              @click="load"
            >
              刷新数据
            </button>
          </div>

          <div class="market-number-row">
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

          <div v-if="overview.total_jobs === 0" class="state-card" style="margin-top: 18px">
            <h3>当前方向暂无市场数据</h3>
            <p>换一个职业方向看看，或稍后再试。</p>
          </div>

          <template v-else>
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
                      :style="{ width: `${share(item.count, meta.sample_size)}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">{{ item.count }}</span>
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
                      class="market-bar is-soft"
                      :style="{ width: `${share(item.count, meta.sample_size)}%` }"
                    ></div>
                  </div>
                  <span class="market-bar-value">{{ item.count }}</span>
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
                  class="market-dist-row"
                >
                  <span>{{ item.name }}</span>
                  <strong>{{ Math.round(item.share * 100) }}%</strong>
                  <small>{{ item.count }}</small>
                </div>
              </section>
              <section class="market-panel card">
                <div class="market-panel-head">
                  <h3>经验要求</h3>
                </div>
                <div
                  v-for="item in experience?.items"
                  :key="item.name"
                  class="market-dist-row"
                >
                  <span>{{ item.name }}</span>
                  <strong>{{ Math.round(item.share * 100) }}%</strong>
                  <small>{{ item.count }}</small>
                </div>
              </section>
              <section class="market-panel card">
                <div class="market-panel-head">
                  <h3>地区需求</h3>
                </div>
                <div
                  v-for="item in locations?.items"
                  :key="item.name"
                  class="market-dist-row"
                >
                  <span>{{ item.name }}</span>
                  <strong>{{ Math.round(item.share * 100) }}%</strong>
                  <small>{{ item.count }}</small>
                </div>
              </section>
            </div>

            <section class="market-panel market-trend-panel card">
              <div class="market-panel-head">
                <div>
                  <p class="section-label">时间变化</p>
                  <h3>技能需求趋势</h3>
                </div>
                <span class="quiet-note">按岗位发布时间月度</span>
              </div>
              <div v-if="trends?.insufficient_data" class="empty-inline">
                数据周期不足，暂不展示趋势
              </div>
              <div v-else class="market-trend-wrap">
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
            </section>
          </template>

          <details class="market-source-panel card" style="padding: 20px 24px; margin-top: 18px">
            <summary class="profile-subsection-summary">
              <h3>数据来源与授权说明</h3>
              <span class="badge">{{ datasetLabel }}</span>
            </summary>
            <div
              v-for="source in meta.sources"
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

          <p v-if="datasetNote || sampleNote" class="market-warning">
            {{ [datasetNote, sampleNote].filter(Boolean).join(' · ') }}
          </p>
        </template>

        <p v-else class="note">当前没有可展示的市场统计。</p>
      </template>
    </div>

    <div v-else class="market-v2-body">
      <div class="pulse-filters" role="group" aria-label="行业筛选">
        <button
          v-for="item in PULSE_FILTERS"
          :key="item.id"
          type="button"
          class="chip"
          :class="{ 'is-active': pulseIndustry === item.id }"
          @click="pulseIndustry = item.id"
        >
          {{ item.label }}
        </button>
      </div>

      <div class="pulse-example-note">
        行业动态为新增功能，尚未接入真实数据；以下内容均为「示例」，仅展示版式与四态，不代表真实资讯。
      </div>

      <div class="pulse-state-switch" style="margin: 12px 0">
        <span>状态预览（设计验收）</span>
        <button
          v-for="state in PULSE_STATES"
          :key="state.id"
          type="button"
          class="chip"
          :class="{ 'is-active': pulseState === state.id }"
          @click="pulseState = state.id"
        >
          {{ state.label }}
        </button>
      </div>

      <div v-if="pulseState === 'loading'" class="pulse-list">
        <div
          v-for="index in 2"
          :key="index"
          class="skeleton skeleton-block"
          style="height: 200px"
        ></div>
      </div>

      <div v-else-if="pulseState === 'error'" class="error-inline">
        <span>行业动态没加载出来。网络不太顺畅，趋势总览不受影响。</span>
        <button
          type="button"
          class="button secondary small"
          @click="pulseState = 'normal'"
        >
          重新加载
        </button>
      </div>

      <div
        v-else-if="pulseState === 'empty' || !pulseItems.length"
        class="state-card"
      >
        <h3>{{ pulseState === 'empty' ? '空状态预览' : '暂时没有行业动态' }}</h3>
        <p v-if="pulseState === 'empty'">
          这是空状态预览：{{ activeIndustryLabel }} 筛选下的空态展示，不代表该行业实际没有动态；切回正常状态即可查看示例数据。
        </p>
        <p v-else>
          {{ activeIndustryLabel }}这个行业最近没有新动态，换个行业看看。
        </p>
        <button
          type="button"
          class="button secondary"
          @click="pulseIndustry = 'all'; pulseState = 'normal'"
        >
          查看全部行业
        </button>
      </div>

      <div v-else class="pulse-list">
        <article
          v-for="item in pulseItems"
          :key="item.id"
          class="pulse-card card"
        >
          <div class="pulse-card-head">
            <div>
              <div class="pulse-meta">
                <span class="tag">{{ item.industryLabel }}</span>
                <span class="tag tag-muted">{{ item.topic }}</span>
                <span class="tag tag-inference">示例</span>
              </div>
              <h3>{{ item.title }}</h3>
              <div class="pulse-meta">
                <span>来源：{{ item.source }}</span>
                <span>{{ item.publishedAt }}</span>
              </div>
            </div>
          </div>
          <p class="pulse-summary">{{ item.summary }}</p>
          <div class="pulse-sections">
            <div class="pulse-section">
              <strong>AI 解读</strong>
              <p>{{ item.aiRead }}</p>
            </div>
            <div class="pulse-section">
              <strong>职业影响</strong>
              <p>{{ item.careerImpact }}</p>
            </div>
          </div>
          <div class="pulse-foot">
            <span class="quiet-note">示例内容，不代表真实资讯</span>
            <a
              :href="item.url"
              class="link-button"
              target="_blank"
              rel="noreferrer"
            >
              原文链接（示例）↗
            </a>
          </div>
        </article>
      </div>

      <p class="market-warning" style="margin-top: 16px">
        示例内容仅用于展示版式结构，不代表真实资讯。
      </p>
    </div>
  </section>
</template>