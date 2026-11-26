<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import PageSkeleton from '@/components/PageSkeleton.vue'
import ProfileEditor from '@/components/ProfileEditor.vue'
import ToastNotice from '@/components/ToastNotice.vue'
import {
  analyzeProfile,
  confirmResume,
  deleteProfile,
  discardResume,
  getProfile,
  listAnalyses,
  listProfileRevisions,
  saveProfile,
  uploadResume,
} from '@/api/profile'
import { getMarketOverview } from '@/api/market'
import { getCurrentRoadmap, getSkillGap } from '@/api/roadmap'
import { ApiError } from '@/api/client'
import {
  BASIS_LABELS,
  CHANGE_SOURCE_LABELS,
  CONFIDENCE_LABELS,
  PROFILE_SECTIONS,
  emptyProfileData,
  type AnalysisClaim,
  type ProfileAnalysisOut,
  type ProfileData,
  type ProfileOut,
  type ProfileRevisionOut,
  type ProfileSection,
  type ResumeParseOut,
  type SkillItem,
} from '@/types/profile'
import type { MarketOverview } from '@/types/market'
import type { Roadmap, RoadmapStage, SkillGap } from '@/types/roadmap'
import { profileCompletion, topCountTitle } from '@/utils/dashboardView'
import {
  evidenceLabel,
  formatProfileDate,
  gapCoverage,
  latestAnalysis,
  proficiencyLabel,
  unknownInformation,
} from '@/utils/profileView'
import { progressPercent } from '@/utils/roadmapView'
import { userFacingText } from '@/utils/userFacing'

const TABS = [
  { id: 'overview', en: 'Overview', cn: '总览' },
  { id: 'skills', en: 'Skills & Interests', cn: '能力与兴趣' },
  { id: 'market', en: 'Market Match', cn: '市场匹配' },
  { id: 'growth', en: 'Growth Record', cn: '成长记录' },
  { id: 'manage', en: 'Manage Profile', cn: '资料管理' },
] as const

type TabId = (typeof TABS)[number]['id']
const TAB_IDS = TABS.map((tab) => tab.id)

const route = useRoute()
const router = useRouter()

const profile = ref<ProfileOut | null>(null)
const draft = ref<ProfileData>(emptyProfileData())
const analyses = ref<ProfileAnalysisOut[]>([])
const selectedAnalysisId = ref('')
const revisions = ref<ProfileRevisionOut[]>([])
const loading = ref(true)
const saving = ref(false)
const analyzing = ref(false)
const uploading = ref(false)
const error = ref('')
const toast = ref('')

const marketOverview = ref<MarketOverview | null>(null)
const marketLoading = ref(false)
const marketError = ref('')
const roadmap = ref<Roadmap | null>(null)
const roadmapGap = ref<SkillGap | null>(null)
const gapLoading = ref(false)

const selectedFile = ref<File | null>(null)
const resume = ref<ResumeParseOut | null>(null)
const resumeDraft = ref<ProfileData>(emptyProfileData())
const selectedSections = ref<ProfileSection[]>(
  PROFILE_SECTIONS.map(([value]) => value),
)

const activeTab = computed<TabId>(() => {
  const value = String(route.query.tab ?? '')
  return TAB_IDS.includes(value as TabId) ? (value as TabId) : 'overview'
})
const hasProfile = computed(() => Boolean(profile.value))
const analysis = computed(() => latestAnalysis(analyses.value))
const targetRole = computed(
  () => profile.value?.data.goals.target_role.trim() ?? '',
)
const completion = computed(() =>
  profileCompletion(profile.value?.data ?? null),
)
const initial = computed(() =>
  (profile.value?.data.basic.name.trim() || 'P').slice(0, 1).toUpperCase(),
)
const identityLine = computed(() => {
  const data = profile.value?.data
  if (!data) return '建立画像后，这里会显示你的身份、目标与完善度。'
  return (
    [
      data.basic.name,
      data.basic.education_level,
      data.basic.major,
      data.basic.graduation_year ? `${data.basic.graduation_year} 届` : '',
      data.basic.location,
    ]
      .filter(Boolean)
      .join(' · ') || '资料待补充'
  )
})
const basicFacts = computed(() => {
  const data = profile.value?.data
  if (!data) return []
  return [
    { label: '姓名', value: data.basic.name || '待补充' },
    { label: '目标方向', value: data.goals.target_role || '待补充' },
    {
      label: '学校 / 专业',
      value:
        [data.basic.education_level, data.basic.major]
          .filter(Boolean)
          .join(' · ') || '待补充',
    },
    {
      label: '毕业时间',
      value: data.basic.graduation_year
        ? `${data.basic.graduation_year} 年`
        : '待补充',
    },
    { label: '所在地', value: data.basic.location || '待补充' },
    { label: '目标行业', value: data.goals.target_industry || '待补充' },
    { label: '求职状态', value: data.goals.job_status || '待补充' },
    { label: '期望方向', value: data.goals.desired_direction || '待补充' },
  ]
})
const skills = computed(() => profile.value?.data.skills ?? [])
const analysisText = computed(() => analysis.value?.analysis.overview ?? '')
const analysisShort = computed(() =>
  friendly(firstSentence(analysisText.value)),
)
const nextActions = computed(
  () => analysis.value?.analysis.next_actions.slice(0, 3) ?? [],
)
const strengths = computed(() => analysis.value?.analysis.strengths ?? [])
const gaps = computed(() => analysis.value?.analysis.gaps ?? [])
const directions = computed(() => analysis.value?.analysis.directions ?? [])
const unknownItems = computed(() => {
  if (!profile.value) return []
  return [
    ...new Set(
      [
        ...unknownInformation(profile.value.data),
        ...(analysis.value?.analysis.missing_information ?? []),
      ]
        .map((item) => item.trim())
        .filter(Boolean),
    ),
  ]
})
const recentRevisions = computed(() => revisions.value.slice(0, 3))

const marketMeta = computed(() => marketOverview.value?.meta ?? null)
const marketDatasetLabel = computed(() => {
  const kinds = marketMeta.value?.dataset_kinds ?? []
  if (kinds.includes('real') && kinds.includes('synthetic')) return '真实 + 演示'
  if (kinds.includes('real')) return '真实数据'
  if (kinds.includes('synthetic')) return '演示数据'
  return '无数据'
})
const marketSources = computed(
  () =>
    marketMeta.value?.sources
      .map((source) => userFacingText(source.name))
      .join('、') ?? '',
)
const coverage = computed(() => gapCoverage(roadmapGap.value))
const coveragePercent = computed(() =>
  coverage.value.total
    ? Math.round((coverage.value.matched / coverage.value.total) * 100)
    : 0,
)
const nextActionsTitle = computed(() =>
  topCountTitle('建议', nextActions.value.length, 3),
)
const routeSummary = computed(() =>
  roadmap.value
    ? `当前路线 v${roadmap.value.version} · ${roadmap.value.task_completed}/${roadmap.value.task_total} 任务`
    : '',
)
const roleCards = computed(() => marketOverview.value?.top_roles.slice(0, 4) ?? [])
const gapTop = computed(
  () => roadmapGap.value?.to_improve.slice(0, 3) ?? [],
)
const conflicts = computed(() => {
  const gap = roadmapGap.value
  if (!gap) return []
  const owned = new Map(
    skills.value.map((skill) => [normalizeName(skill.name), skill.name]),
  )
  return gap.not_recorded
    .filter((item) => owned.has(normalizeName(item.name)))
    .map((item) => ({
      skill: owned.get(normalizeName(item.name)) ?? item.name,
      gap: item,
    }))
})
const growthStages = computed(() => roadmap.value?.stages ?? [])
const selectedAnalysis = computed(
  () =>
    analyses.value.find((item) => item.id === selectedAnalysisId.value) ??
    analyses.value[0] ??
    null,
)

function normalizeName(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, '')
}

function firstSentence(text: string): string {
  const trimmed = text.trim()
  if (!trimmed) return ''
  const match = trimmed.match(/^[^。！？!?；;]+[。！？!?；;]?/)
  return match ? match[0] : trimmed
}

function cloneData(data: ProfileData): ProfileData {
  return JSON.parse(JSON.stringify(data)) as ProfileData
}

function errorMessage(value: unknown): string {
  if (value instanceof ApiError) return value.message
  return '操作失败，请稍后重试'
}

function timeLabel(): string {
  return new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  })
}

function setTab(tab: TabId) {
  if (activeTab.value !== tab) {
    void router.replace({ query: { ...route.query, tab } })
  }
  void nextTick(() => {
    document
      .querySelector('.profile-v2-tabs')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function onTabKeydown(event: KeyboardEvent, tab: TabId) {
  const index = TAB_IDS.indexOf(tab)
  let next = -1
  if (event.key === 'ArrowRight') next = (index + 1) % TAB_IDS.length
  if (event.key === 'ArrowLeft')
    next = (index - 1 + TAB_IDS.length) % TAB_IDS.length
  if (event.key === 'Home') next = 0
  if (event.key === 'End') next = TAB_IDS.length - 1
  if (next < 0) return
  event.preventDefault()
  const container = (event.currentTarget as HTMLElement | null)?.parentElement
  setTab(TAB_IDS[next])
  void nextTick(() => {
    container
      ?.querySelectorAll<HTMLElement>('[role="tab"]')
      [next]?.focus()
  })
}

function basisTagClass(basis: AnalysisClaim['basis']): string {
  if (basis === 'inference') return 'tag-inference'
  if (basis === 'suggestion') return 'tag-suggestion'
  return 'tag-fact'
}

function basisLabel(basis: AnalysisClaim['basis']): string {
  if (basis === 'fact') return '已确认事实'
  if (basis === 'inference') return 'AI 推断 · 待确认'
  return 'AI 建议'
}

function skillTagClass(skill: SkillItem): string {
  if (skill.source === 'ai') return 'tag-inference'
  if (skill.verification === 'confirmed' || skill.evidence.trim()) {
    return 'tag-evidence'
  }
  return 'tag'
}

function skillTagLabel(skill: SkillItem): string {
  if (skill.source === 'ai') return 'AI 推断 · 待确认'
  if (skill.verification === 'confirmed' || skill.evidence.trim()) {
    return '有记录'
  }
  return '待确认'
}

function skillLevelWidth(skill: SkillItem): number {
  const text = skill.proficiency.trim()
  if (/精通|专家/.test(text)) return 95
  if (/熟练|良好/.test(text)) return 78
  if (/熟悉|掌握/.test(text)) return 62
  if (/了解|入门/.test(text)) return 40
  return 30
}

function stageProgress(stage: RoadmapStage): number {
  const completed = stage.tasks.filter(
    (task) => task.status === 'completed',
  ).length
  return progressPercent(stage.tasks.length, completed)
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function fileSize(value: number): string {
  return `${Math.max(0.1, value / 1024).toFixed(1)} KB`
}

function analysisHistoryLabel(item: ProfileAnalysisOut): string {
  return item.llm_mode === 'mock' ? '演示分析' : 'AI 分析'
}

function friendly(value: string): string {
  return userFacingText(value).replace(/^【演示分析】\s*/, '')
}

async function loadAnalysisHistory() {
  const result = await listAnalyses()
  analyses.value = result.items
  if (!selectedAnalysisId.value && result.items.length) {
    selectedAnalysisId.value = result.items[0].id
  }
}

async function loadRevisions() {
  const result = await listProfileRevisions()
  revisions.value = result.items
}

async function loadMarket(role: string) {
  marketError.value = ''
  if (!role.trim()) {
    marketOverview.value = null
    return
  }
  marketLoading.value = true
  try {
    marketOverview.value = await getMarketOverview(role)
  } catch (value) {
    marketOverview.value = null
    marketError.value = errorMessage(value)
  } finally {
    marketLoading.value = false
  }
}

async function loadRoadmap() {
  gapLoading.value = true
  try {
    const [roadmapResult, gapResult] = await Promise.allSettled([
      getCurrentRoadmap(),
      getSkillGap(),
    ])
    roadmap.value =
      roadmapResult.status === 'fulfilled' ? roadmapResult.value.roadmap : null
    roadmapGap.value = gapResult.status === 'fulfilled' ? gapResult.value : null
  } finally {
    gapLoading.value = false
  }
}

async function loadPage() {
  loading.value = true
  error.value = ''
  try {
    const [profileResult, analysisResult, revisionResult] = await Promise.all([
      getProfile(),
      listAnalyses(),
      listProfileRevisions(),
    ])
    profile.value = profileResult.profile
    draft.value = profile.value
      ? cloneData(profile.value.data)
      : emptyProfileData()
    analyses.value = analysisResult.items
    revisions.value = revisionResult.items
    if (!selectedAnalysisId.value && analyses.value.length) {
      selectedAnalysisId.value = analyses.value[0].id
    }
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
  if (profile.value) {
    await Promise.all([loadMarket(targetRole.value), loadRoadmap()])
  }
}

async function refreshPortraitData() {
  await Promise.all([
    loadAnalysisHistory(),
    loadRevisions(),
    loadMarket(targetRole.value),
    loadRoadmap(),
  ])
}

async function save() {
  error.value = ''
  saving.value = true
  try {
    profile.value = await saveProfile(draft.value)
    draft.value = cloneData(profile.value.data)
    toast.value = `职业画像已保存 · ${timeLabel()}`
    await refreshPortraitData()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    saving.value = false
  }
}

async function removeProfile() {
  if (!hasProfile.value) return
  if (typeof window !== 'undefined' && !window.confirm('确认删除已保存的职业画像？')) {
    return
  }
  error.value = ''
  saving.value = true
  try {
    await deleteProfile()
    profile.value = null
    draft.value = emptyProfileData()
    analyses.value = []
    selectedAnalysisId.value = ''
    revisions.value = []
    marketOverview.value = null
    roadmap.value = null
    roadmapGap.value = null
    toast.value = `职业画像已删除 · ${timeLabel()}`
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    saving.value = false
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] ?? null
}

async function upload() {
  if (!selectedFile.value) return
  error.value = ''
  uploading.value = true
  try {
    const result = await uploadResume(selectedFile.value)
    resume.value = result
    resumeDraft.value = cloneData(result.parsed_data)
    selectedSections.value = PROFILE_SECTIONS.map(([value]) => value)
    toast.value = `简历已解析，请审核后导入 · ${timeLabel()}`
  } catch (value) {
    error.value = errorMessage(value)
    resume.value = null
  } finally {
    uploading.value = false
  }
}

async function confirmImport() {
  if (!resume.value || !selectedSections.value.length) {
    error.value = '请选择至少一个要导入的区块'
    return
  }
  error.value = ''
  uploading.value = true
  try {
    profile.value = await confirmResume(
      resume.value.id,
      resumeDraft.value,
      selectedSections.value,
    )
    draft.value = cloneData(profile.value.data)
    resume.value = { ...resume.value, status: 'confirmed' }
    toast.value = `已确认并写入职业画像 · ${timeLabel()}`
    setTab('manage')
    await refreshPortraitData()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    uploading.value = false
  }
}

async function discard() {
  if (!resume.value) return
  error.value = ''
  uploading.value = true
  try {
    resume.value = await discardResume(resume.value.id)
    toast.value = `已放弃本次解析，正式画像未改变 · ${timeLabel()}`
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    uploading.value = false
  }
}

function toggleSection(section: ProfileSection) {
  if (selectedSections.value.includes(section)) {
    selectedSections.value = selectedSections.value.filter(
      (item) => item !== section,
    )
  } else {
    selectedSections.value = [...selectedSections.value, section]
  }
}

async function analyze() {
  error.value = ''
  analyzing.value = true
  try {
    const result = await analyzeProfile()
    analyses.value = [result, ...analyses.value]
    selectedAnalysisId.value = result.id
    toast.value = `AI 职业分析已完成 · ${timeLabel()}`
    await Promise.all([loadMarket(targetRole.value), loadRoadmap()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    analyzing.value = false
  }
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <section class="page profile-page">
    <header class="page-head profile-v2-head">
      <template v-if="loading">
        <div class="profile-v2-identity">
          <div class="skeleton skeleton-avatar"></div>
          <div style="display: flex; flex-direction: column; gap: 8px">
            <div class="skeleton skeleton-line lg" style="width: 220px"></div>
            <div class="skeleton skeleton-line sm" style="width: 320px"></div>
          </div>
        </div>
        <div class="skeleton skeleton-line md" style="width: 140px; height: 28px"></div>
      </template>
      <template v-else>
        <div class="profile-v2-identity">
          <span class="profile-avatar">{{ initial }}</span>
          <div>
            <h1>Profile <span class="page-title-cn">职业画像</span></h1>
            <p class="page-lede">{{ identityLine }}</p>
          </div>
        </div>
        <div class="profile-completion">
          <strong class="stat-number">{{ completion }}%</strong>
          <span class="quiet-note">画像完善度<br />按已确认资料计算</span>
        </div>
      </template>
    </header>

    <div class="legend-row">
      <span class="tag tag-fact">已确认事实</span>
      <span class="tag tag-evidence">客观能力证据</span>
      <span class="tag tag-inference">AI 推断 · 待确认</span>
      <span class="tag tag-suggestion">AI 建议</span>
      <span class="quiet-note">标签说明信息来源与可信度</span>
    </div>

    <PageSkeleton v-if="loading" variant="profile" />

    <template v-else>
      <ErrorNotice
        v-if="error"
        :error="{ code: 'PROFILE_ERROR', message: error }"
        retryable
        @dismiss="error = ''"
        @retry="loadPage"
      />

      <template v-if="!profile">
        <div class="state-card">
          <h3>建立你的第一份职业画像</h3>
          <p>从基本信息、技能和一段经历开始，之后逐步补充证据。</p>
        </div>
        <section class="card profile-v2-card" style="margin-top: 18px">
          <div class="profile-v2-card-head">
            <div>
              <h3>补充资料</h3>
              <p>保存即确认，并记录第一个资料版本。</p>
            </div>
            <button
              type="button"
              class="button primary"
              :disabled="saving"
              @click="save"
            >
              {{ saving ? '正在保存' : '保存画像' }}
            </button>
          </div>
          <ProfileEditor v-model="draft" collapsible />
        </section>
      </template>

      <template v-else>
        <div class="profile-v2-tabs" role="tablist" aria-label="职业画像标签">
          <button
            v-for="tab in TABS"
            :key="tab.id"
            type="button"
            class="profile-v2-tab"
            :class="{ 'is-active': activeTab === tab.id }"
            role="tab"
            :aria-selected="activeTab === tab.id"
            :tabindex="activeTab === tab.id ? 0 : -1"
            :data-tab-id="tab.id"
            @click="setTab(tab.id)"
            @keydown="onTabKeydown($event, tab.id)"
          >
            <strong>{{ tab.en }}</strong>
            <span>{{ tab.cn }}</span>
          </button>
        </div>

        <div v-if="activeTab === 'overview'" class="profile-v2-body">
          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>基本信息</h3>
                <p>由你填写，只记录事实。</p>
              </div>
              <span class="tag tag-fact">已确认事实</span>
            </div>
            <dl class="profile-fact-grid">
              <div v-for="fact in basicFacts" :key="fact.label" class="profile-fact">
                <dt>{{ fact.label }}</dt>
                <dd>{{ fact.value }}</dd>
              </div>
            </dl>
            <div class="profile-overview-counts">
              <span>教育经历 {{ profile.data.education.length }} 段</span>
              <span>项目 {{ profile.data.projects.length }} 个</span>
              <span>工作 / 实习 {{ profile.data.experiences.length }} 段</span>
              <span>技能 {{ profile.data.skills.length }} 项</span>
            </div>
            <details class="profile-count-help">
              <summary>计数口径</summary>
              <p>
                这些计数与「资料管理」来自同一份画像资料；如两处不一致，请以资料管理中的明细为准。
              </p>
            </details>
            <button
              type="button"
              class="button primary"
              style="margin-top: 18px"
              @click="setTab('manage')"
            >
              编辑基本信息
            </button>
          </section>

          <div class="profile-overview-grid">
            <section class="card profile-v2-card">
              <div class="profile-v2-card-head">
                <div>
                  <h3>AI 对你的判断</h3>
                  <p>基于已确认画像，推断与建议分开标注。</p>
                </div>
                <span v-if="analysis" class="tag tag-inference">AI 推断 · 待确认</span>
              </div>
              <template v-if="analysis">
                <p>{{ analysisShort }}</p>
                <details class="profile-ai-fold">
                  <summary>展开完整分析</summary>
                  <p>{{ friendly(analysisText) }}</p>
                </details>
              </template>
              <p v-else class="note">
                还没有 AI 分析；生成后会在这里给出判断，不会自动写入正式画像。
              </p>
              <button
                v-if="!analysis"
                type="button"
                class="button secondary small"
                :disabled="analyzing || !hasProfile"
                @click="analyze"
              >
                {{ analyzing ? '正在分析' : '生成分析' }}
              </button>
            </section>

            <section class="card profile-v2-card">
              <div class="profile-v2-card-head">
                <div>
                  <h3>{{ nextActionsTitle }}</h3>
                  <p>来自最近一次分析。</p>
                </div>
                <span v-if="nextActions.length" class="tag tag-suggestion">AI 建议</span>
              </div>
              <ol v-if="nextActions.length" class="profile-mini-list">
                <li v-for="(item, index) in nextActions" :key="index">
                  {{ friendly(item) }}
                </li>
              </ol>
              <p v-else class="note">还没有建议；完成分析后会出现在这里。</p>
            </section>
          </div>

          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>最近动态</h3>
                <p>画像与资料版本的变化会记在这里。</p>
              </div>
              <span class="tag tag-muted">资料 v{{ revisions[0]?.version ?? 1 }}</span>
            </div>
            <div v-if="recentRevisions.length">
              <div
                v-for="revision in recentRevisions"
                :key="revision.id"
                class="profile-growth-row"
              >
                <span
                  class="tag"
                  :class="revision.change_source === 'resume' ? 'tag-evidence' : 'tag-fact'"
                >
                  {{ revision.change_source === 'resume' ? '有记录' : '事实' }}
                </span>
                <span>
                  {{ CHANGE_SOURCE_LABELS[revision.change_source] ?? revision.change_source }}
                  · v{{ revision.version }}
                </span>
                <time>{{ formatProfileDate(revision.created_at) }}</time>
              </div>
            </div>
            <p v-else class="note">尚无版本记录；保存画像后开始记录。</p>
          </section>
        </div>

        <div v-else-if="activeTab === 'skills'" class="profile-v2-body">
          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>能力与兴趣</h3>
                <p>熟练度为自评；标签表示来源与确认状态。</p>
              </div>
              <span class="tag tag-muted">{{ skills.length }} 项技能</span>
            </div>
            <div v-if="skills.length">
              <div v-for="skill in skills" :key="skill.id" class="skill-row">
                <div>
                  <div class="skill-row-name">
                    {{ friendly(skill.name || '未命名技能') }}
                  </div>
                  <div class="skill-row-evidence">
                    {{ friendly(evidenceLabel(skill)) }} ·
                    {{ skill.category || '未分类' }}
                  </div>
                </div>
                <div>
                  <div class="skill-level">
                    <span :style="{ width: `${skillLevelWidth(skill)}%` }"></span>
                  </div>
                  <span class="quiet-note">
                    自评 · {{ proficiencyLabel(skill.proficiency) }}
                  </span>
                </div>
                <span class="tag" :class="skillTagClass(skill)">
                  {{ skillTagLabel(skill) }}
                </span>
              </div>
            </div>
            <div v-else class="state-card">
              <h3>还没有技能记录</h3>
              <p>在资料管理中补充技能与证据，市场匹配会随之更新。</p>
              <button
                type="button"
                class="button primary"
                @click="setTab('manage')"
              >
                去补充技能
              </button>
            </div>
          </section>

          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>可探索方向</h3>
                <p>AI 基于画像给出的方向，默认不写入正式画像。</p>
              </div>
              <span class="tag tag-inference">AI 推断 · 待确认</span>
            </div>
            <ul v-if="directions.length" class="claim-list">
              <li v-for="(item, index) in directions" :key="index">
                <span class="tag" :class="basisTagClass(item.basis)">
                  {{ basisLabel(item.basis) }}
                </span>
                {{ friendly(item.statement) }}
              </li>
            </ul>
            <p v-else class="note">
              还没有方向建议；生成分析后会出现在这里。
            </p>
          </section>

          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>AI 能力分析</h3>
                <p>长文默认收起，只显示结论。</p>
              </div>
              <button type="button" class="link-button" @click="setTab('manage')">
                查看分析历史
              </button>
            </div>
            <template v-if="analysis">
              <p>{{ analysisShort }}</p>
              <details class="profile-ai-fold">
                <summary>展开优势与待提升</summary>
                <div class="profile-claim-grid">
                  <div>
                    <h4>已有优势</h4>
                    <ul v-if="strengths.length" class="claim-list">
                      <li v-for="(item, index) in strengths" :key="index">
                        <span class="tag" :class="basisTagClass(item.basis)">
                          {{ basisLabel(item.basis) }}
                        </span>
                        {{ friendly(item.statement) }}
                      </li>
                    </ul>
                    <p v-else class="note">尚无足够证据形成优势判断。</p>
                  </div>
                  <div>
                    <h4>待提升</h4>
                    <ul v-if="gaps.length" class="claim-list">
                      <li v-for="(item, index) in gaps" :key="index">
                        <span class="tag" :class="basisTagClass(item.basis)">
                          {{ basisLabel(item.basis) }}
                        </span>
                        {{ friendly(item.statement) }}
                      </li>
                    </ul>
                    <p v-else class="note">暂无分析结论。</p>
                  </div>
                </div>
              </details>
            </template>
            <p v-else class="note">还没有分析结论。</p>
          </section>
        </div>

        <div v-else-if="activeTab === 'market'" class="profile-v2-body">
          <section class="card profile-v2-card" data-testid="profile-market-match">
            <div class="profile-v2-card-head">
              <div>
                <h3>市场匹配</h3>
                <p>只做摘要与链接，不重复计算完整差距。</p>
              </div>
              <span class="tag">{{ marketDatasetLabel }}</span>
            </div>

            <p v-if="!targetRole" class="note">
              先设置目标岗位，才能按方向查看市场要求。
            </p>
            <p v-else-if="marketLoading" class="note state-loading" role="status">
              正在读取市场数据…
            </p>
            <p v-else-if="gapLoading" class="note state-loading" role="status">
              正在读取目标岗位技能差距…
            </p>
            <p v-else-if="marketError" class="note warning-text">
              暂时无法读取市场数据，画像本身不受影响。
            </p>

            <template v-else-if="marketOverview && marketMeta">
              <div class="market-match-meta">
                <span>目标 {{ targetRole }}</span>
                <span>样本 {{ marketMeta.sample_size }} 条</span>
                <span data-testid="profile-gap-coverage">
                  目标岗位需求技能已记录 {{ coverage.matched }} / {{ coverage.total }}
                </span>
                <span
                  class="tag"
                  :class="marketMeta.sample_sufficient ? 'tag-evidence' : 'tag-inference'"
                >
                  {{ marketMeta.sample_sufficient ? '样本达标' : '样本量较少' }}
                </span>
              </div>
              <div class="profile-match-score">
                <div class="profile-match-score-copy">
                  <strong>{{ coverage.matched }} / {{ coverage.total }}</strong>
                  <span>目标岗位需求技能已记录</span>
                </div>
                <div
                  class="profile-match-track"
                  role="progressbar"
                  :aria-valuenow="coveragePercent"
                  aria-valuemin="0"
                  aria-valuemax="100"
                >
                  <span :style="{ width: `${coveragePercent}%` }"></span>
                </div>
              </div>
              <p class="note">
                来源 {{ marketSources || '未记录' }} · 统计口径为导入岗位计数，仅用于方向参考。
              </p>

              <div v-if="conflicts.length" class="conflict-card">
                <h4>冲突确认：画像与差距接口不一致</h4>
                <p class="note">
                  同一技能在两处结果不同。请核对来源后再决定，前端不会隐藏或改数。
                </p>
                <div class="conflict-grid">
                  <div v-for="item in conflicts" :key="item.skill" class="conflict-side">
                    <strong>画像技能列表</strong>{{ item.skill }}（已记录）
                    <hr style="border: 0; border-top: 1px solid var(--border); margin: 8px 0" />
                    <strong>差距接口</strong>{{ item.gap.name }}（未记录，需求占比
                    {{ Math.round(item.gap.market_share * 100) }}%）
                  </div>
                </div>
                <button
                  type="button"
                  class="button secondary small"
                  @click="setTab('manage')"
                >
                  去资料管理核对
                </button>
              </div>

              <div class="market-role-grid">
                <article
                  v-for="roleItem in roleCards"
                  :key="roleItem.name"
                  class="card profile-v2-card"
                >
                  <h4>{{ roleItem.name }}</h4>
                  <p class="note">
                    {{ roleItem.count }} 条岗位 · 占样本
                    {{ Math.round(roleItem.share * 100) }}%
                  </p>
                  <RouterLink to="/roadmap" class="link-button">
                    查看差距
                  </RouterLink>
                </article>
              </div>

              <div v-if="gapTop.length" class="profile-gap-summary">
                <h4>优先补齐</h4>
                <div
                  v-for="item in gapTop"
                  :key="item.name"
                  class="profile-growth-row"
                >
                  <span>{{ item.name }}</span>
                  <span class="quiet-note">
                    {{ Math.round(item.market_share * 100) }}% 需求
                  </span>
                </div>
                <RouterLink to="/roadmap" class="link-button">
                  去成长路线查看完整差距
                </RouterLink>
              </div>
              <p v-else class="note">当前没有可展示的差距摘要。</p>
            </template>
            <p v-else class="note">当前没有可展示的市场统计。</p>
          </section>
        </div>

        <div v-else-if="activeTab === 'growth'" class="profile-v2-body">
          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>成长记录</h3>
                <p>
                  阶段来自当前正式路线；点击查看对应阶段。
                  <template v-if="routeSummary">（{{ routeSummary }}）</template>
                </p>
              </div>
              <RouterLink to="/roadmap" class="link-button">去成长路线</RouterLink>
            </div>
            <div v-if="growthStages.length">
              <RouterLink
                v-for="(stage, index) in growthStages"
                :key="stage.id"
                :to="{ path: '/roadmap', query: { stage: stage.id } }"
                class="profile-growth-row"
              >
                <span class="stage-index">{{ index + 1 }}</span>
                <span class="profile-growth-copy">
                  <strong>{{ stage.title }}</strong>
                  <span>{{ stage.duration || '时间未记录' }}</span>
                </span>
                <span
                  class="tag"
                  :class="stageProgress(stage) === 100 ? 'tag-evidence' : 'tag'"
                >
                  {{ stageProgress(stage) }}%
                </span>
              </RouterLink>
            </div>
            <p v-else class="note">
              还没有正式成长路线；生成后会在这里按阶段展示。
            </p>
          </section>

          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>资料版本</h3>
                <p>
                  每次保存或导入都会留下版本，旧版本只读保留。
                  资料版本与路线版本是两套独立记录，不可直接比较。
                </p>
              </div>
              <span class="tag tag-muted">资料 v{{ revisions[0]?.version ?? 1 }}</span>
            </div>
            <div v-if="revisions.length">
              <div
                v-for="revision in revisions"
                :key="revision.id"
                class="profile-growth-row"
              >
                <span class="tag">v{{ revision.version }}</span>
                <span>
                  {{ CHANGE_SOURCE_LABELS[revision.change_source] ?? revision.change_source }}
                </span>
                <time>{{ formatProfileDate(revision.created_at) }}</time>
              </div>
            </div>
            <p v-else class="note">尚无版本记录。</p>
          </section>
        </div>

        <div v-else class="profile-v2-body">
          <section class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>Manage Profile</h3>
                <p>资料管理是唯一可编辑画像的地方；保存即确认并生成新版本。</p>
              </div>
              <div class="page-head-actions">
                <button

                  type="button"
                  class="button primary"
                  :disabled="saving"
                  @click="save"
                >
                  {{ saving ? '正在保存' : '保存画像' }}
                </button>
              </div>
            </div>
            <p v-if="!hasProfile" class="note">
              还没有正式职业画像，可以手动填写或上传一份虚构测试简历。
            </p>
            <ProfileEditor v-model="draft" collapsible />
          </section>

          <section class="card profile-v2-card">
            <details>
              <summary class="profile-subsection-summary">
                <h3>简历导入</h3>
                <span class="quiet-note">解析后需确认</span>
              </summary>
              <p class="note">
                支持 PDF / DOCX，解析结果需要你确认后才会进入画像。
              </p>
              <div class="upload-box">
                <label class="field">
                  <span>虚构测试简历文件（≤10MB）</span>
                  <input
                    type="file"
                    accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    aria-label="简历文件"
                    @change="onFileChange"
                  />
                </label>
                <button
                  type="button"
                  class="button secondary"
                  :disabled="!selectedFile || uploading"
                  @click="upload"
                >
                  {{ uploading ? '正在解析' : '上传并解析' }}
                </button>
              </div>

              <div v-if="resume" class="resume-review">
                <div class="resume-meta">
                  <strong>{{ resume.original_filename }}</strong>
                  <span>{{ fileSize(resume.file_size) }}</span>
                  <span class="tag">{{ resume.parse_mode === 'mock' ? '演示解析' : '解析结果' }}</span>
                  <span class="tag tag-muted">
                    {{ resume.status === 'pending_review' ? '待确认' : resume.status }}
                  </span>
                </div>
                <p v-if="resume.parse_mode === 'mock'" class="resume-warning">
                  当前为演示解析，结果仅用于体验，请核对后导入。
                </p>
                <div class="section-choice">
                  <span>选择要导入的区块</span>
                  <label v-for="[value, label] in PROFILE_SECTIONS" :key="value">
                    <input
                      type="checkbox"
                      :checked="selectedSections.includes(value)"
                      @change="toggleSection(value)"
                    />
                    {{ label }}
                  </label>
                </div>
                <ProfileEditor v-model="resumeDraft" />
                <div class="resume-actions">
                  <button
                    type="button"
                    class="button ghost"
                    :disabled="uploading || resume.status !== 'pending_review'"
                    @click="discard"
                  >
                    放弃本次解析
                  </button>
                  <button
                    type="button"
                    class="button secondary"
                    :disabled="uploading || resume.status !== 'pending_review'"
                    @click="confirmImport"
                  >
                    {{ uploading ? '正在处理' : '确认导入所选区块' }}
                  </button>
                </div>
              </div>
              <p v-else class="note">还没有待审核解析结果。</p>
            </details>
          </section>

          <section class="card profile-v2-card">
            <details>
              <summary class="profile-subsection-summary">
                <h3>AI 分析历史</h3>
                <span class="quiet-note">{{ analyses.length }} 次</span>
              </summary>
              <div class="page-head-actions" style="justify-content: flex-start">
                <button
                  type="button"
                  class="button secondary"
                  :disabled="analyzing || !hasProfile"
                  @click="analyze"
                >
                  {{ analyzing ? '正在分析' : hasProfile ? '重新分析' : '请先保存画像' }}
                </button>
              </div>

              <div v-if="selectedAnalysis" class="analysis-layout">
                <aside class="analysis-history">
                  <h4>历史分析</h4>
                  <button
                    v-for="item in analyses"
                    :key="item.id"
                    type="button"
                    class="analysis-history-item"
                    :class="{ 'is-active': item.id === selectedAnalysisId }"
                    @click="selectedAnalysisId = item.id"
                  >
                    <span>{{ formatDate(item.created_at) }}</span>
                    <small>{{ analysisHistoryLabel(item) }}</small>
                  </button>
                </aside>
                <article class="analysis-detail">
                  <div class="analysis-meta">
                    <span class="tag tag-inference">AI 推断 · 待确认</span>
                    <time>{{ formatDate(selectedAnalysis.created_at) }}</time>
                  </div>
                  <section class="analysis-section">
                    <h4>能力概况</h4>
                    <p>{{ friendly(selectedAnalysis.analysis.overview) }}</p>
                  </section>
                  <section class="analysis-section">
                    <h4>优势</h4>
                    <ul>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.strengths"
                        :key="index"
                      >
                        <span class="tag" :class="basisTagClass(item.basis)">
                          {{ basisLabel(item.basis) }}
                        </span>
                        <span class="tag tag-muted">{{ CONFIDENCE_LABELS[item.confidence] }}</span>
                        {{ friendly(item.statement) }}
                      </li>
                    </ul>
                  </section>
                  <section class="analysis-section">
                    <h4>待提升</h4>
                    <ul>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.gaps"
                        :key="index"
                      >
                        <span class="tag" :class="basisTagClass(item.basis)">
                          {{ basisLabel(item.basis) }}
                        </span>
                        <span class="tag tag-muted">{{ CONFIDENCE_LABELS[item.confidence] }}</span>
                        {{ friendly(item.statement) }}
                      </li>
                    </ul>
                  </section>
                  <section class="analysis-section">
                    <h4>与目标岗位的匹配</h4>
                    <p>{{ friendly(selectedAnalysis.analysis.fit.summary) }}</p>
                    <ul>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.fit.evidence"
                        :key="index"
                      >
                        {{ friendly(item) }}
                      </li>
                    </ul>
                    <p
                      v-if="selectedAnalysis.analysis.fit.uncertainty.length"
                      class="note"
                    >
                      不确定性：{{ friendly(selectedAnalysis.analysis.fit.uncertainty.join('；')) }}
                    </p>
                  </section>
                  <section class="analysis-section">
                    <h4>值得探索的方向</h4>
                    <ul>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.directions"
                        :key="index"
                      >
                        <span class="tag" :class="basisTagClass(item.basis)">
                          {{ basisLabel(item.basis) }}
                        </span>
                        {{ friendly(item.statement) }}
                      </li>
                    </ul>
                  </section>
                  <section class="analysis-section">
                    <h4>建议补充的信息</h4>
                    <ul>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.missing_information"
                        :key="index"
                      >
                        {{ friendly(item) }}
                      </li>
                    </ul>
                  </section>
                  <section class="analysis-section">
                    <h4>下一步行动</h4>
                    <ol>
                      <li
                        v-for="(item, index) in selectedAnalysis.analysis.next_actions"
                        :key="index"
                      >
                        {{ friendly(item) }}
                      </li>
                    </ol>
                  </section>
                </article>
              </div>
              <p v-else class="note">还没有职业分析，先保存画像再生成。</p>
            </details>
          </section>

          <section v-if="unknownItems.length" class="card profile-v2-card">
            <div class="profile-v2-card-head">
              <div>
                <h3>待补充信息</h3>
                <p>这里只列出缺口，不替你填写。</p>
              </div>
              <span class="tag tag-muted">待补充</span>
            </div>
            <ul class="unknown-list">
              <li v-for="item in unknownItems" :key="item">{{ friendly(item) }}</li>
            </ul>
          </section>

          <section v-if="hasProfile" class="card profile-v2-card danger-zone">
            <div class="profile-v2-card-head">
              <div>
                <h3>危险区</h3>
                <p>删除后画像与版本记录会移除，且不可恢复。</p>
              </div>
              <button
                type="button"
                class="button danger small"
                :disabled="saving"
                @click="removeProfile"
              >
                删除画像
              </button>
            </div>
          </section>
        </div>
      </template>
    </template>

    <ToastNotice v-if="toast" :message="toast" @close="toast = ''" />
  </section>
</template>