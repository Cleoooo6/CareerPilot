<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import ErrorNotice from '@/components/ErrorNotice.vue'
import { ApiError } from '@/api/client'
import {
  getMarketDistribution,
  getMarketOverview,
  getMarketRoles,
  getMarketSkills,
  getMarketTrends,
} from '@/api/market'
import type {
  Distribution,
  MarketOverview,
  SkillDemand,
  TrendData,
} from '@/types/market'
import { userFacingText } from '@/utils/userFacing'

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

        <h2>看清市场需要什么</h2>
        <p class="page-lede">
          用岗位数据理解技能需求、学历经验与方向变化。
        </p>
      </div>
      <div class="market-filter">
        <label class="field compact">
          <span>职业方向</span>
          <select v-model="role" @change="load">
            <option value="">全部方向</option>
            <option v-for="item in roles" :key="item" :value="item">{{ item }}</option>
          </select>
        </label>
      </div>
    </header>

    <ErrorNotice
      v-if="error"
      :error="{ code: 'MARKET_ERROR', message: error }"
      @dismiss="error = ''"
    />

    <div v-if="loading" class="loading-state">正在整理市场数据…</div>

    <template v-else-if="overview && meta">
      <div class="market-meta">
        <span class="badge">{{ datasetLabel }}</span>
        <span>样本 {{ meta.sample_size }} 条</span>
        <span>统计周期 {{ formatDate(meta.period_start) }}–{{ formatDate(meta.period_end) }}</span>
        <span>更新 {{ formatDate(meta.updated_at) }}</span>
        <span class="badge" :class="{ 'badge-warning': !meta.sample_sufficient }">
          {{ meta.sample_sufficient ? '样本达标' : '样本量较少' }}
        </span>
      </div>
      <p v-if="datasetNote || sampleNote" class="market-warning">
        {{ [datasetNote, sampleNote].filter(Boolean).join(' · ') }}
      </p>

      <div class="market-cards">
        <article class="market-card is-primary">
          <span>岗位样本</span>
          <strong>{{ overview.total_jobs }}</strong>
        </article>
        <article class="market-card">
          <span>企业数</span>
          <strong>{{ overview.total_companies }}</strong>
        </article>
        <article class="market-card">
          <span>职业方向</span>
          <strong>{{ overview.total_roles }}</strong>
        </article>
        <article class="market-card">
          <span>城市数</span>
          <strong>{{ overview.total_locations }}</strong>
        </article>
      </div>

      <div v-if="overview.total_jobs === 0" class="empty-state">
        <h3>当前方向暂无市场数据</h3>
        <p>换一个职业方向看看，或稍后再试。</p>
      </div>

      <template v-else>
        <div class="market-panel-grid">
          <section class="market-panel">
            <div class="market-panel-head">
              <div>
                <p class="section-label">技能需求</p>
                <h3>高频技能</h3>
              </div>
              <span class="quiet-note">样本 {{ meta.sample_size }}</span>
            </div>
            <div v-if="!skills?.items.length" class="note">暂无技能统计。</div>
            <div
              v-for="item in skills?.items"
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
          </section>

          <section class="market-panel">
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
          <section class="market-panel">
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
          <section class="market-panel">
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
          <section class="market-panel">
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

        <section class="market-panel market-trend-panel">
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
          <div v-else class="market-trend">
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
        </section>

        <section class="market-panel market-source-panel">
          <div class="market-panel-head">
            <div>
              <p class="section-label">数据说明</p>
              <h3>数据来源与授权说明</h3>
            </div>
            <span class="badge">{{ datasetLabel }}</span>
          </div>
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
            统计口径为导入岗位计数，仅用于方向参考。
          </p>
        </section>
      </template>
    </template>
  </section>
</template>