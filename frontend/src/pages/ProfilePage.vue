<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import ProfileEditor from '@/components/ProfileEditor.vue'
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
import { getMarketOverview, getMarketSkills } from '@/api/market'
import { ApiError } from '@/api/client'
import {
  BASIS_LABELS,
  CHANGE_SOURCE_LABELS,
  CONFIDENCE_LABELS,
  PROFILE_SECTIONS,
  emptyProfileData,
  type ProfileAnalysisOut,
  type ProfileData,
  type ProfileOut,
  type ProfileRevisionOut,
  type ProfileSection,
  type ResumeParseOut,
} from '@/types/profile'
import type { MarketOverview, SkillDemand } from '@/types/market'
import {
  evidenceLabel,
  formatProfileDate,
  groupSkills,
  latestAnalysis,
  marketSkillGap,
  proficiencyLabel,
  profileFactSummary,
  sourceLabel,
  unknownInformation,
  verificationLabel,
} from '@/utils/profileView'
import { userFacingText } from '@/utils/userFacing'

type Tab = 'editor' | 'resume' | 'analysis'

const activeTab = ref<Tab>('editor')
const profile = ref<ProfileOut | null>(null)
const draft = ref<ProfileData>(emptyProfileData())
const analyses = ref<ProfileAnalysisOut[]>([])
const selectedAnalysisId = ref<string>('')
const revisions = ref<ProfileRevisionOut[]>([])
const loading = ref(true)
const saving = ref(false)
const analyzing = ref(false)
const uploading = ref(false)
const error = ref<string>('')
const success = ref<string>('')

const marketOverview = ref<MarketOverview | null>(null)
const marketSkills = ref<SkillDemand | null>(null)
const marketLoading = ref(false)
const marketError = ref('')

const selectedFile = ref<File | null>(null)
const resume = ref<ResumeParseOut | null>(null)
const resumeDraft = ref<ProfileData>(emptyProfileData())
const selectedSections = ref<ProfileSection[]>(
  PROFILE_SECTIONS.map(([value]) => value),
)

const hasProfile = computed(() => Boolean(profile.value))
const analysis = computed(() => latestAnalysis(analyses.value))
const targetRole = computed(
  () => profile.value?.data.goals.target_role.trim() ?? '',
)
const skillGroups = computed(() =>
  groupSkills(profile.value?.data.skills ?? []),
)
const facts = computed(() =>
  profile.value ? profileFactSummary(profile.value.data) : [],
)
const unknownItems = computed(() => {
  if (!profile.value) return []
  const items = [
    ...unknownInformation(profile.value.data),
    ...(analysis.value?.analysis.missing_information ?? []),
  ]
  return [...new Set(items.filter((item) => item.trim()))]
})
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
const datasetNote = computed(() => {
  const kinds = marketMeta.value?.dataset_kinds ?? []
  return kinds.includes('synthetic')
    ? '演示数据，仅用于体验，不代表真实招聘市场'
    : ''
})
const sampleNote = computed(() =>
  marketMeta.value && !marketMeta.value.sample_sufficient
    ? '样本量较少，仅作参考'
    : '',
)
const analysisModeLabel = computed(() => {
  if (!analysis.value) return '已确认资料'
  return analysis.value.llm_mode === 'mock' ? '演示分析' : 'AI 分析'
})
const resumeModeLabel = computed(() =>
  resume.value?.parse_mode === 'mock' ? '演示解析' : '解析结果',
)
const resumeStatusLabel = computed(() => {
  const status = resume.value?.status
  if (status === 'pending_review') return '待确认'
  if (status === 'confirmed') return '已导入'
  if (status === 'discarded') return '已放弃'
  if (status === 'failed') return '解析失败'
  return '处理中'
})
const demandSkills = computed(() => marketSkills.value?.items.slice(0, 10) ?? [])
const skillGap = computed(() =>
  marketSkillGap(profile.value?.data.skills ?? [], demandSkills.value),
)
const growthItems = computed(() => {
  if (!profile.value) return []
  const items: { label: string; meta: string }[] = []
  for (const project of profile.value.data.projects) {
    items.push({
      label: `项目：${project.name || '未命名项目'}`,
      meta: [project.role, project.start_date, project.end_date]
        .map((part) => part.trim())
        .filter(Boolean)
        .join(' · '),
    })
  }
  for (const experience of profile.value.data.experiences) {
    items.push({
      label: `经历：${experience.company || '未填写公司'} · ${
        experience.position || '未填写岗位'
      }`,
      meta: [experience.start_date, experience.end_date]
        .map((part) => part.trim())
        .filter(Boolean)
        .join(' · '),
    })
  }
  return items
})
const selectedAnalysis = computed(
  () =>
    analyses.value.find((item) => item.id === selectedAnalysisId.value) ??
    analyses.value[0] ??
    null,
)
const tabs: { value: Tab; label: string }[] = [
  { value: 'editor', label: '资料编辑' },
  { value: 'resume', label: '简历解析' },
  { value: 'analysis', label: 'AI 分析' },
]

function cloneData(data: ProfileData): ProfileData {
  return JSON.parse(JSON.stringify(data)) as ProfileData
}

function errorMessage(value: unknown): string {
  if (value instanceof ApiError) return value.message
  return '操作失败，请稍后重试'
}

function clearFeedback() {
  error.value = ''
  success.value = ''
}

async function loadProfile() {
  try {
    const result = await getProfile()
    profile.value = result.profile
    draft.value = result.profile
      ? cloneData(result.profile.data)
      : emptyProfileData()
  } catch (value) {
    error.value = errorMessage(value)
  }
}

async function loadAnalysisHistory() {
  try {
    const result = await listAnalyses()
    analyses.value = result.items
    if (!selectedAnalysisId.value && result.items.length) {
      selectedAnalysisId.value = result.items[0].id
    }
  } catch (value) {
    error.value = errorMessage(value)
  }
}

async function loadRevisions() {
  try {
    const result = await listProfileRevisions()
    revisions.value = result.items
  } catch (value) {
    error.value = errorMessage(value)
  }
}

async function loadMarket(role: string) {
  marketError.value = ''
  if (!role.trim()) {
    marketOverview.value = null
    marketSkills.value = null
    return
  }
  marketLoading.value = true
  try {
    const [overview, skills] = await Promise.all([
      getMarketOverview(role),
      getMarketSkills(role, 12),
    ])
    marketOverview.value = overview
    marketSkills.value = skills
  } catch (value) {
    marketOverview.value = null
    marketSkills.value = null
    marketError.value = errorMessage(value)
  } finally {
    marketLoading.value = false
  }
}

async function loadPage() {
  loading.value = true
  clearFeedback()
  try {
    await Promise.all([loadProfile(), loadAnalysisHistory(), loadRevisions()])
    await loadMarket(targetRole.value)
  } finally {
    loading.value = false
  }
}

async function refreshPortraitData() {
  await loadRevisions()
  await loadMarket(targetRole.value)
}

async function save() {
  clearFeedback()
  saving.value = true
  try {
    profile.value = await saveProfile(draft.value)
    draft.value = cloneData(profile.value.data)
    success.value = '职业画像已保存，并记录了新版本'
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
  clearFeedback()
  saving.value = true
  try {
    await deleteProfile()
    profile.value = null
    draft.value = emptyProfileData()
    analyses.value = []
    selectedAnalysisId.value = ''
    revisions.value = []
    marketOverview.value = null
    marketSkills.value = null
    success.value = '职业画像已删除'
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
  clearFeedback()
  uploading.value = true
  try {
    const result = await uploadResume(selectedFile.value)
    resume.value = result
    resumeDraft.value = cloneData(result.parsed_data)
    selectedSections.value = PROFILE_SECTIONS.map(([value]) => value)
    success.value = '简历已解析，请审核后确认导入'
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
  clearFeedback()
  uploading.value = true
  try {
    profile.value = await confirmResume(
      resume.value.id,
      resumeDraft.value,
      selectedSections.value,
    )
    draft.value = cloneData(profile.value.data)
    resume.value = { ...resume.value, status: 'confirmed' }
    success.value = '已确认并写入职业画像'
    activeTab.value = 'editor'
    await refreshPortraitData()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    uploading.value = false
  }
}

async function discard() {
  if (!resume.value) return
  clearFeedback()
  uploading.value = true
  try {
    resume.value = await discardResume(resume.value.id)
    success.value = '已放弃本次解析，正式画像未改变'
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    uploading.value = false
  }
}

function toggleSection(section: ProfileSection) {
  if (selectedSections.value.includes(section)) {
    selectedSections.value = selectedSections.value.filter((item) => item !== section)
  } else {
    selectedSections.value = [...selectedSections.value, section]
  }
}

async function analyze() {
  clearFeedback()
  analyzing.value = true
  try {
    const result = await analyzeProfile()
    analyses.value = [result, ...analyses.value]
    selectedAnalysisId.value = result.id
    success.value = 'AI 职业分析已完成并保存'
    await loadMarket(targetRole.value)
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    analyzing.value = false
  }
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

function openEditor() {
  activeTab.value = 'editor'
  if (typeof window === 'undefined') return
  window.requestAnimationFrame(() => {
    document
      .getElementById('profile-sources')
      ?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <section class="page profile-page">
    <header class="page-head profile-head">
      <div class="page-head-copy">

        <h2>你的职业画像</h2>
        <p class="page-lede">
          把经历、能力和目标放在一起，看到自己的方向与下一步。
        </p>
      </div>
      <div class="page-head-actions">
        <span class="badge">{{ hasProfile ? '画像已建立' : '尚未建立' }}</span>
        <span v-if="profile" class="quiet-note">
          更新于 {{ formatProfileDate(profile.updated_at) }}
        </span>
        <button
          type="button"
          class="button primary"
          :disabled="analyzing || !hasProfile"
          @click="analyze"
        >
          {{ analyzing ? '正在分析' : analysis ? '更新分析' : '生成分析' }}
        </button>
        <RouterLink to="/market" class="button ghost">查看市场洞察</RouterLink>
      </div>
    </header>

    <ErrorNotice
      v-if="error"
      :error="{ code: 'PROFILE_ERROR', message: error }"
      @dismiss="error = ''"
    />
    <p v-if="success" class="success-note">{{ success }}</p>

    <div v-if="loading" class="loading-state">正在加载职业画像…</div>

    <template v-else>
      <div v-if="!profile" class="empty-state">
        <h3>建立你的第一份职业画像</h3>
        <p>从基本信息、技能和一段经历开始，之后逐步补充证据。</p>
        <button type="button" class="button primary" @click="openEditor">
          开始补充资料
        </button>
      </div>

      <template v-else>
        <div class="profile-top">
          <section class="profile-overview">
            <div class="section-heading">
              <h3>职业概览</h3>
              <span class="tag">{{ analysisModeLabel }}</span>
            </div>
            <p v-if="analysis" class="profile-statement">
              {{ friendly(analysis.analysis.overview) }}
            </p>
            <ul v-else class="fact-list">
              <li v-for="fact in facts" :key="fact">{{ friendly(fact) }}</li>
              <li v-if="!facts.length">资料较少，还没有形成清晰的定位。</li>
            </ul>
            <p class="note">
              {{
                analysis
                  ? '基于已确认画像生成；事实、推断与建议在下方分开标注。'
                  : '这里展示的是已确认资料，不是 AI 结论。'
              }}
            </p>
          </section>

          <section class="direction-panel">
            <div class="section-heading">
              <h3>职业方向</h3>
            </div>
            <dl class="direction-list">
              <div>
                <dt>目标岗位</dt>
                <dd>{{ profile.data.goals.target_role || '尚未设置' }}</dd>
              </div>
              <div>
                <dt>目标行业</dt>
                <dd>{{ profile.data.goals.target_industry || '尚未设置' }}</dd>
              </div>
              <div>
                <dt>求职状态</dt>
                <dd>{{ profile.data.goals.job_status || '尚未设置' }}</dd>
              </div>
              <div>
                <dt>期望方向</dt>
                <dd>{{ profile.data.goals.desired_direction || '尚未设置' }}</dd>
              </div>
            </dl>
            <div v-if="analysis?.analysis.directions.length" class="direction-claims">
              <h4>可探索方向</h4>
              <ul class="claim-list">
                <li
                  v-for="(item, index) in analysis.analysis.directions"
                  :key="index"
                >
                  <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
                  {{ friendly(item.statement) }}
                </li>
              </ul>
            </div>
            <p v-else class="note">
              暂无方向建议；设置目标岗位并积累证据后，会更有依据。
            </p>
          </section>
        </div>

        <section class="section-block">
          <div class="section-heading">
            <h3>能力结构</h3>
            <span class="note">熟练度为自评</span>
          </div>
          <p v-if="!profile.data.skills.length" class="note">
            还没有技能记录，可以在资料管理中补充。
          </p>
          <div
            v-for="group in skillGroups"
            :key="group.category"
            class="skill-group"
          >
            <h4>{{ group.category }}</h4>
            <div class="skill-grid">
              <article
                v-for="skill in group.skills"
                :key="skill.id"
                class="skill-card"
              >
                <div class="skill-card-head">
                  <strong class="skill-name">{{ friendly(skill.name || '未命名技能') }}</strong>
                  <span class="tag">
                    {{ friendly(proficiencyLabel(skill.proficiency)) }}
                  </span>
                </div>
                <p class="skill-evidence">{{ friendly(evidenceLabel(skill)) }}</p>
                <div class="skill-meta">
                  <span>{{ sourceLabel(skill.source) }}</span>
                  <span>{{ verificationLabel(skill.verification) }}</span>
                  <span>
                    {{ skill.updated_at ? `更新 ${formatProfileDate(skill.updated_at)}` : '更新时间未记录' }}
                  </span>
                </div>
              </article>
            </div>
          </div>
        </section>

        <div class="profile-split">
          <section class="section-block">
            <div class="section-heading">
              <h3>已有优势</h3>
            </div>
            <ul v-if="analysis?.analysis.strengths.length" class="claim-list">
              <li
                v-for="(item, index) in analysis.analysis.strengths"
                :key="index"
              >
                <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
                <span class="tag tag-muted">
                  {{ CONFIDENCE_LABELS[item.confidence] }}
                </span>
                {{ friendly(item.statement) }}
              </li>
            </ul>
            <p v-else class="note">尚无足够证据形成优势判断。</p>
          </section>

          <section class="section-block">
            <div class="section-heading">
              <h3>待提升能力</h3>
            </div>
            <ul v-if="analysis?.analysis.gaps.length" class="claim-list">
              <li v-for="(item, index) in analysis.analysis.gaps" :key="index">
                <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
                <span class="tag tag-muted">
                  {{ CONFIDENCE_LABELS[item.confidence] }}
                </span>
                {{ friendly(item.statement) }}
              </li>
            </ul>
            <p v-else class="note">暂无分析结论；没有证据时不做短板判断。</p>
          </section>
        </div>

        <section class="section-block unknown-block">
          <div class="section-heading">
            <h3>未知信息</h3>
            <span class="tag tag-muted">待补充</span>
          </div>
          <ul v-if="unknownItems.length" class="unknown-list">
            <li v-for="item in unknownItems" :key="item">{{ friendly(item) }}</li>
          </ul>
          <p v-else class="note">暂无明显未知项。</p>
        </section>

        <section class="market-match" data-testid="profile-market-match">
          <div class="section-heading">
            <h3>市场匹配</h3>
            <span class="tag">{{ marketDatasetLabel }}</span>
          </div>
          <p v-if="!targetRole" class="note">
            先设置目标岗位，才能按方向查看市场要求。
          </p>
          <p v-else-if="marketLoading" class="note">正在读取市场数据…</p>
          <p v-else-if="marketError" class="note warning-text">
            暂时无法读取市场数据，画像本身不受影响。
          </p>
          <template v-else-if="marketOverview && marketMeta">
            <div class="market-match-meta">
              <span>样本 {{ marketMeta.sample_size }} 条</span>
              <span>
                统计周期 {{ formatProfileDate(marketMeta.period_start) }}–{{ formatProfileDate(marketMeta.period_end) }}
              </span>
              <span>来源 {{ marketSources || '未记录' }}</span>
              <span class="tag">
                {{ marketMeta.sample_sufficient ? '样本达标' : '样本量较少' }}
              </span>
            </div>
            <p v-if="datasetNote || sampleNote" class="market-warning">
              {{ [datasetNote, sampleNote].filter(Boolean).join(' · ') }}
            </p>
            <p v-if="marketOverview.total_jobs === 0" class="note">
              当前方向暂无市场样本，不能据此判断能力差距。
            </p>
            <div v-else class="match-columns">
              <div>
                <h4>市场高频技能</h4>
                <ul class="match-list">
                  <li v-for="item in demandSkills" :key="item.skill">
                    <span>{{ item.rank }}. {{ item.skill }}</span>
                    <strong>{{ item.count }}</strong>
                  </li>
                </ul>
              </div>
              <div>
                <h4>画像已记录</h4>
                <ul v-if="skillGap.matched.length" class="match-list">
                  <li v-for="item in skillGap.matched" :key="item">
                    <span>{{ friendly(item) }}</span>
                    <span class="tag">已记录</span>
                  </li>
                </ul>
                <p v-else class="note">尚未记录市场高频技能。</p>
              </div>
              <div>
                <h4>未记录的需求技能</h4>
                <ul v-if="skillGap.notRecorded.length" class="match-list">
                  <li v-for="item in skillGap.notRecorded" :key="item">
                    <span>{{ friendly(item) }}</span>
                    <span class="tag tag-muted">未记录</span>
                  </li>
                </ul>
                <p v-else class="note">高频技能均已记录。</p>
                <p class="note">
                  未记录不等于不具备；这里只做需求对比，不做能力评分。
                </p>
              </div>
            </div>
            <p class="note">统计口径为导入岗位计数，仅用于方向参考。</p>
          </template>
          <p v-else class="note">当前没有可展示的市场统计。</p>
        </section>

        <section class="section-block">
          <div class="section-heading">
            <h3>成长记录</h3>
            <span class="tag tag-muted">版本历史</span>
          </div>
          <p v-if="!revisions.length" class="note">
            尚无版本记录；下次保存画像后开始记录。
          </p>
          <ol v-else class="revision-list">
            <li v-for="revision in revisions" :key="revision.id">
              <span class="tag">v{{ revision.version }}</span>
              <span>
                {{ CHANGE_SOURCE_LABELS[revision.change_source] ?? revision.change_source }}
              </span>
              <time>{{ formatProfileDate(revision.created_at) }}</time>
            </li>
          </ol>
          <div v-if="growthItems.length" class="growth-list">
            <h4>项目与经历</h4>
            <ul>
              <li v-for="item in growthItems" :key="item.label">
                <strong>{{ friendly(item.label) }}</strong>
                <span v-if="item.meta">{{ friendly(item.meta) }}</span>
              </li>
            </ul>
          </div>
          <div v-if="profile.data.skills.length" class="growth-skills">
            <h4>技能更新时间</h4>
            <ul>
              <li v-for="skill in profile.data.skills" :key="skill.id">
                <span>{{ skill.name || '未命名技能' }}</span>
                <span>{{ skill.updated_at ? formatProfileDate(skill.updated_at) : '未记录' }}</span>
              </li>
            </ul>
          </div>
        </section>
      </template>
    </template>

    <section id="profile-sources" class="profile-aux">
      <div class="profile-aux-head">
        <div>
          <h3>资料管理</h3>
          <p>维护画像来源、简历与历史分析；未经确认的内容不会写入画像。</p>
        </div>
      </div>

      <div class="profile-tabs" role="tablist" aria-label="资料管理">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          class="profile-tab"
          :class="{ 'is-active': activeTab === tab.value }"
          role="tab"
          :aria-selected="activeTab === tab.value"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </div>

      <section v-if="activeTab === 'editor'" class="profile-panel">
        <div class="profile-panel-head">
          <div>
            <h3>资料编辑</h3>
            <p>保存即确认并生成新的画像版本。</p>
          </div>
          <div class="page-head-actions">
            <button
              v-if="hasProfile"
              type="button"
              class="button danger"
              :disabled="saving"
              @click="removeProfile"
            >
              删除画像
            </button>
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
        <ProfileEditor v-model="draft" />
      </section>

      <section v-else-if="activeTab === 'resume'" class="profile-panel">
        <div class="profile-panel-head">
          <div>
            <h3>简历解析</h3>
            <p>支持 PDF / DOCX，解析结果需要你确认后才会进入画像。</p>
          </div>
        </div>
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
            class="button primary"
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
            <span class="tag">{{ resumeModeLabel }}</span>
            <span class="tag tag-muted">{{ resumeStatusLabel }}</span>
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
              class="button primary"
              :disabled="uploading || resume.status !== 'pending_review'"
              @click="confirmImport"
            >
              {{ uploading ? '正在处理' : '确认导入所选区块' }}
            </button>
          </div>
        </div>
        <p v-else class="note">还没有待审核解析结果。</p>
      </section>

      <section v-else class="profile-panel">
        <div class="profile-panel-head">
          <div>
            <h3>AI 分析</h3>
            <p>分析基于已确认画像，历史版本会保留。</p>
          </div>
          <button
            type="button"
            class="button primary"
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
              <span class="tag">
                {{ selectedAnalysis.llm_mode === 'mock' ? '演示分析' : 'AI 分析' }}
              </span>
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
                  <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
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
                  <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
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
              <p v-if="selectedAnalysis.analysis.fit.uncertainty.length" class="note">
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
                  <span class="tag">{{ BASIS_LABELS[item.basis] }}</span>
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
      </section>
    </section>
  </section>
</template>