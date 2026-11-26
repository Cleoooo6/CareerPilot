<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import TrendEvidenceDetails from '@/components/TrendEvidenceDetails.vue'
import {
  getIndustryTrends,
  getPersonalIndustryTrends,
} from '@/api/market'
import type {
  IndustryCatalogItem,
  IndustryTrendsData,
  PersonalIndustryTrendsData,
  TrendDirection,
} from '@/types/industryTrends'
import type { PulseIndustryFilter } from '@/types/industryPulse'

type Tab = 'overall' | 'personal'

const props = defineProps<{
  industry: PulseIndustryFilter
  months: number
}>()
const emit = defineEmits<{
  'update:industry': [value: PulseIndustryFilter]
  'update:months': [value: number]
  catalog: [value: IndustryCatalogItem[]]
}>()

const tab = ref<Tab>('overall')
const overall = ref<IndustryTrendsData | null>(null)
const personal = ref<PersonalIndustryTrendsData | null>(null)
const loading = ref(false)
const error = ref('')

const catalog = computed(
  () => overall.value?.industry_catalog ?? personal.value?.industry_catalog ?? [],
)
const warnings = computed(() =>
  tab.value === 'personal'
    ? personal.value?.warnings ?? []
    : overall.value?.warnings ?? [],
)
const insufficient = computed(() => overall.value?.insufficient_industries ?? [])

function directionLabel(direction: TrendDirection) {
  return {
    rising: '需求上升',
    stable: '需求平稳',
    cooling: '需求回落',
    unclear: '方向待确认',
    insufficient: '证据不足',
  }[direction]
}

function directionClass(direction: TrendDirection) {
  return {
    rising: 'is-up',
    stable: 'is-stable',
    cooling: 'is-down',
    unclear: 'is-uncertain',
    insufficient: 'is-muted',
  }[direction]
}

function confidenceLabel(confidence: string) {
  return { high: '高', medium: '中', low: '低' }[confidence] ?? confidence
}

function evidenceLabel(level: string) {
  return { strong: '证据充分', medium: '证据中等', insufficient: '证据不足' }[level] ?? level
}

function relevanceLabel(match: string) {
  return { high: '高相关', medium: '中等相关', low: '低相关' }[match] ?? match
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    if (tab.value === 'overall') {
      overall.value = await getIndustryTrends(props.industry, props.months)
    } else {
      personal.value = await getPersonalIndustryTrends(
        props.industry,
        props.months,
      )
    }
    emit('catalog', catalog.value)
  } catch {
    error.value = '行业趋势暂时无法读取，请稍后重试。'
  } finally {
    loading.value = false
  }
}

function switchTab(next: Tab) {
  if (tab.value === next) return
  tab.value = next
  if (
    (next === 'overall' && !overall.value) ||
    (next === 'personal' && !personal.value)
  ) {
    void load()
  }
}

const TREND_TABS: Tab[] = ['overall', 'personal']

function onTrendTabKeydown(event: KeyboardEvent, current: Tab) {
  const index = TREND_TABS.indexOf(current)
  let next = -1
  if (event.key === 'ArrowRight') next = (index + 1) % TREND_TABS.length
  if (event.key === 'ArrowLeft')
    next = (index - 1 + TREND_TABS.length) % TREND_TABS.length
  if (event.key === 'Home') next = 0
  if (event.key === 'End') next = TREND_TABS.length - 1
  if (next < 0) return
  event.preventDefault()
  const container = (event.currentTarget as HTMLElement | null)?.parentElement
  switchTab(TREND_TABS[next])
  void nextTick(() => {
    container
      ?.querySelectorAll<HTMLElement>('[role="tab"]')
      [next]?.focus()
  })
}

function changeIndustry(event: Event) {
  emit(
    'update:industry',
    (event.target as HTMLSelectElement).value as PulseIndustryFilter,
  )
}

function changeMonths(event: Event) {
  emit('update:months', Number((event.target as HTMLSelectElement).value))
}

watch(
  [() => props.industry, () => props.months],
  () => {
    overall.value = null
    personal.value = null
    void load()
  },
)
onMounted(() => void load())
</script>

<template>
  <section class="industry-trends card">
    <header class="industry-trends-head">
      <div>
        <p class="section-label">Industry Trends</p>
        <h2>行业趋势</h2>
        <p class="industry-trends-sub">
          整体趋势来自行业新闻与岗位样本；个性化趋势只使用已确认画像，不虚构匹配。
        </p>
      </div>
      <div class="trend-tabs" role="tablist" aria-label="行业趋势视图">
        <button
          type="button"
          role="tab"
          class="trend-tab"
          :class="{ 'is-active': tab === 'overall' }"
          :aria-selected="tab === 'overall'"
          :tabindex="tab === 'overall' ? 0 : -1"
          data-trend-tab="overall"
          @click="switchTab('overall')"
          @keydown="onTrendTabKeydown($event, 'overall')"
        >
          整体行业趋势
        </button>
        <button
          type="button"
          role="tab"
          class="trend-tab"
          :class="{ 'is-active': tab === 'personal' }"
          :aria-selected="tab === 'personal'"
          :tabindex="tab === 'personal' ? 0 : -1"
          data-trend-tab="personal"
          @click="switchTab('personal')"
          @keydown="onTrendTabKeydown($event, 'personal')"
        >
          与你相关
        </button>
      </div>
    </header>

    <div class="trend-filters">
      <label>
        行业
        <select :value="props.industry" @change="changeIndustry">
          <option value="all">全部行业</option>
          <option v-for="item in catalog" :key="item.id" :value="item.id">
            {{ item.label }}
          </option>
        </select>
      </label>
      <label>
        时间范围
        <select :value="props.months" @change="changeMonths">
          <option :value="6">近 6 个月</option>
          <option :value="12">近 12 个月</option>
          <option :value="24">近 24 个月</option>
        </select>
      </label>
      <span class="quiet-note">市场数据含合成演示时必须标注；新闻只作辅助证据。</span>
    </div>
    <p v-if="props.industry !== 'all'" class="trend-filter-note">
      已按所选行业过滤；其他行业的证据不足项已隐藏。
    </p>

    <div v-if="warnings.length" class="data-quality trend-warning" role="note">
      <span class="tag">数据说明</span>
      <span>{{ warnings.join(' ') }}</span>
    </div>

    <div v-if="loading" class="state-card">
      <h3>正在计算行业趋势…</h3>
      <p>只聚合已通过相关性判断的行业新闻与岗位样本。</p>
    </div>
    <div v-else-if="error" class="state-card">
      <h3>{{ error }}</h3>
      <button type="button" class="button secondary" @click="load">重新加载</button>
    </div>

    <template v-else-if="tab === 'overall'">
      <div
        v-if="overall?.items.length"
        id="market-verdict"
        class="trend-grid"
      >
        <article v-for="item in overall.items" :key="item.industry_id" class="trend-card">
          <div class="trend-card-head">
            <span class="tag">{{ item.label }}</span>
            <span class="badge trend-direction" :class="directionClass(item.direction)">
              {{ directionLabel(item.direction) }}
            </span>
          </div>
          <h3>{{ item.title }}</h3>
          <p>{{ item.summary }}</p>
          <div class="trend-metrics" title="置信度依据证据等级与数据性质；低表示样本或数据受限">
            <span>岗位 {{ item.job_count }}</span>
            <span>新闻 {{ item.news_count }}</span>
            <span>来源 {{ item.news_source_count }}</span>
            <span>置信度 {{ confidenceLabel(item.confidence) }}</span>
          </div>
          <div v-if="item.roles.length" class="trend-role-line">
            相关岗位：{{ item.roles.map((role) => role.name).join('、') }}
          </div>
          <div v-if="item.skills.length" class="trend-skill-chips">
            <span v-for="skill in item.skills.slice(0, 6)" :key="skill.skill" class="tag">
              {{ skill.skill }} {{ percent(skill.share) }}
            </span>
          </div>
          <TrendEvidenceDetails :evidence="item.evidence" :gaps="item.data_gaps" />
        </article>
      </div>
      <div v-else class="state-card">
        <h3>证据不足，暂无法形成可靠趋势</h3>
        <p>
          {{ insufficient[0]?.reason || '当前筛选没有同时满足岗位样本与新闻辅助证据的行业。' }}
        </p>
      </div>

      <div
        v-if="insufficient.length || props.industry !== 'all'"
        id="market-evidence"
        class="trend-insufficient"
      >
        <h3>
          证据不足的行业
          <span v-if="insufficient.length" class="quiet-note">（{{ insufficient.length }}）</span>
        </h3>
        <p v-if="insufficient.length" class="quiet-note">
          这些行业不会被强行填入趋势卡；可查看原因或扩大时间范围。
        </p>
        <p v-else class="quiet-note">所选行业证据充足，暂无证据不足项。</p>
        <div v-if="insufficient.length" class="trend-gap-grid">
          <div v-for="item in insufficient" :key="item.industry_id" class="trend-gap-item">
            <strong>{{ item.label }}</strong>
            <small>岗位 {{ item.job_count }} · 新闻 {{ item.news_count }}</small>
            <span>{{ item.reason }}</span>
          </div>
        </div>
      </div>
    </template>

    <template v-else>
      <div v-if="personal && !personal.profile_sufficient" class="state-card">
        <h3>职业画像资料不足</h3>
        <p>{{ personal.insufficient_reason }}</p>
        <p class="quiet-note">缺少：{{ personal.profile_missing.join('、') }}</p>
        <RouterLink class="button secondary" to="/profile">完善 Profile</RouterLink>
      </div>
      <template v-else>
        <div v-if="personal" class="trend-profile-banner">
          <span>目标岗位：{{ personal.target_role || '未填写' }}</span>
          <span>目标行业：{{ personal.target_industry_label || '未填写' }}</span>
          <span>地区：{{ personal.target_location || '未填写' }}</span>
          <span class="quiet-note">
            仅基于已确认画像；资料确认不等于客观能力验证。
          </span>
        </div>
        <div v-if="personal?.items.length" class="trend-grid personal">
          <article
            v-for="item in personal.items"
            :key="item.trend.industry_id"
            class="trend-card personal"
          >
            <div class="trend-card-head">
              <span class="tag">{{ item.trend.label }}</span>
              <span class="badge">{{ relevanceLabel(item.relevance_confidence) }}</span>
              <span class="badge trend-direction" :class="directionClass(item.trend.direction)">
                {{ directionLabel(item.trend.direction) }}
              </span>
            </div>
            <h3>{{ item.trend.title }}</h3>
            <p>{{ item.impact }}</p>
            <div class="trend-personal-block">
              <strong>为什么与你有关</strong>
              <ul>
                <li v-for="reason in item.why_relevant" :key="reason">{{ reason }}</li>
              </ul>
            </div>
            <div class="trend-personal-split">
              <div>
                <strong>已记录技能</strong>
                <p v-if="!item.matched_skills.length" class="quiet-note">
                  尚无记录，不等于不具备。
                </p>
                <div v-else class="trend-skill-chips">
                  <span v-for="skill in item.matched_skills" :key="skill" class="tag">
                    {{ skill }}
                  </span>
                </div>
              </div>
              <div>
                <strong>待补充证据</strong>
                <p v-if="!item.missing_skills.length" class="quiet-note">
                  当前岗位样本未显示额外技能缺口。
                </p>
                <div v-else class="trend-skill-chips">
                  <span v-for="skill in item.missing_skills" :key="skill" class="tag">
                    {{ skill }}
                  </span>
                </div>
              </div>
            </div>
            <div v-if="item.skill_gaps.length" class="trend-gap-notes">
              <p v-for="gap in item.skill_gaps.slice(0, 3)" :key="gap.name" class="quiet-note">
                {{ gap.name }}：{{ gap.evidence_note }}
              </p>
            </div>
            <div class="trend-personal-block">
              <strong>下一步</strong>
              <ul>
                <li v-for="action in item.next_actions" :key="action">{{ action }}</li>
              </ul>
            </div>
            <details class="trend-personal-more">
              <summary>机会、风险与系统解释</summary>
              <div class="trend-personal-block">
                <strong>机会与风险</strong>
                <ul>
                  <li v-for="opportunity in item.opportunities" :key="opportunity">
                    {{ opportunity }}
                  </li>
                  <li v-for="risk in item.risks" :key="risk" class="trend-risk">
                    {{ risk }}
                  </li>
                </ul>
              </div>
            </details>
            <div class="trend-roadmap-suggestion">
              <strong>Roadmap 调整建议（需要你确认）</strong>
              <p>{{ item.roadmap_suggestion.reason }}</p>
              <div v-if="item.roadmap_suggestion.suggested_skills.length" class="trend-skill-chips">
                <span
                  v-for="skill in item.roadmap_suggestion.suggested_skills"
                  :key="skill"
                  class="tag"
                >
                  {{ skill }}
                </span>
              </div>
              <RouterLink class="button secondary small" to="/roadmap">
                去 My Roadmap 确认
              </RouterLink>
            </div>
            <details class="trend-evidence">
              <summary>查看事实、推断与建议</summary>
              <div class="trend-evidence-body">
                <p class="section-label">已确认事实</p>
                <ul><li v-for="fact in item.facts" :key="fact">{{ fact }}</li></ul>
                <p class="section-label">系统推断</p>
                <ul><li v-for="line in item.inferences" :key="line">{{ line }}</li></ul>
                <p class="section-label">建议</p>
                <ul><li v-for="line in item.suggestions" :key="line">{{ line }}</li></ul>
              </div>
            </details>
            <TrendEvidenceDetails
              :evidence="item.trend.evidence"
              :gaps="item.trend.data_gaps"
            />
          </article>
        </div>
        <div v-else class="state-card">
          <h3>暂无可信的个性化行业趋势</h3>
          <p>{{ personal?.insufficient_reason || '请先补充目标方向或等待更多真实数据。' }}</p>
        </div>
      </template>
    </template>
  </section>
</template>