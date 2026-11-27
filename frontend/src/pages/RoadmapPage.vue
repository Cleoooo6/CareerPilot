<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import PageSkeleton from '@/components/PageSkeleton.vue'
import ToastNotice from '@/components/ToastNotice.vue'
import {
  adjustRoadmap,
  confirmRoadmap,
  discardRoadmap,
  generateRoadmap,
  getCurrentRoadmap,
  getRoadmap,
  getSkillGap,
  listRoadmapDrafts,
  listRoadmapHistory,
  updateRoadmapTask,
} from '@/api/roadmap'
import { ApiError } from '@/api/client'
import {
  GAP_BASIS_LABELS,
  PRIORITY_LABELS,
  ROADMAP_STATUS_LABELS,
  TASK_STATUS_LABELS,
  type Priority,
  type Roadmap,
  type RoadmapStage,
  type RoadmapSummary,
  type RoadmapTask,
  type SkillGap,
  type TaskStatus,
} from '@/types/roadmap'
import {
  countTaskStatuses,
  flattenRoadmapTasks,
  formatRoadmapDate,

  progressPercent,
} from '@/utils/roadmapView'
import { userFacingText } from '@/utils/userFacing'

type GapStatus = 'matched' | 'to_improve' | 'not_recorded'

interface GapRow {
  name: string
  market_share: number
  priority: Priority
  reason: string
  status: GapStatus
}

const route = useRoute()
const loading = ref(true)
const generating = ref(false)
const adjusting = ref(false)
const confirming = ref(false)
const discarding = ref(false)
const updatingTask = ref('')
const targetMissing = ref(false)
const error = ref('')
const toast = ref('')
const gap = ref<SkillGap | null>(null)
const current = ref<Roadmap | null>(null)
const draft = ref<Roadmap | null>(null)
const history = ref<RoadmapSummary[]>([])
const historyDetail = ref<Roadmap | null>(null)
const historyLoading = ref('')
const expandedStageId = ref('')
const gapExpanded = ref(false)
const historyOpen = ref(false)
const outcomeDrafts = ref<Record<string, string>>({})

const headerStatus = computed(() => {
  if (draft.value) return `待确认草稿 v${draft.value.version}`
  if (current.value) return `正式路线 v${current.value.version}`
  return '尚未生成'
})
const currentPercent = computed(() =>
  current.value
    ? progressPercent(current.value.task_total, current.value.task_completed)
    : 0,
)
const currentTasks = computed(() => flattenRoadmapTasks(current.value))
const taskCounts = computed(() => countTaskStatuses(currentTasks.value))
const totalTasks = computed(() => currentTasks.value.length)
const gapDatasetLabel = computed(() => {
  const kinds = gap.value?.meta.dataset_kinds ?? []
  if (kinds.includes('real') && kinds.includes('synthetic')) return '真实 + 演示'
  if (kinds.includes('real')) return '真实数据'
  if (kinds.includes('synthetic')) return '演示数据'
  return '无数据'
})
const gapSources = computed(
  () =>
    gap.value?.meta.sources
      .map((source) => userFacingText(source.name))
      .join('、') ?? '',
)
const gapNote = computed(() => {
  const parts: string[] = []
  if (gap.value?.meta.dataset_kinds.includes('synthetic')) {
    parts.push('演示数据，仅用于体验，不代表真实招聘市场')
  }
  if (gap.value?.reference_only) {
    parts.push('样本量较少，仅作参考')
  }
  return parts.join(' · ')
})
const generationLabel = computed(() =>
  current.value?.generation_mode === 'mock' ? '演示生成' : 'AI 生成',
)
const draftGenerationLabel = computed(() =>
  draft.value?.generation_mode === 'mock' ? '演示生成' : 'AI 生成',
)
const currentStageId = computed(() => {
  const roadmap = current.value
  if (!roadmap || !roadmap.stages.length) return ''
  const active = roadmap.stages.find((stage) =>
    stage.tasks.some(
      (task) => task.status === 'pending' || task.status === 'in_progress',
    ),
  )
  return active?.id ?? roadmap.stages[roadmap.stages.length - 1].id
})
const activeStage = computed(
  () =>
    current.value?.stages.find((stage) => stage.id === currentStageId.value) ??
    null,
)
const focusTask = computed(
  () =>
    currentTasks.value.find((task) => task.status === 'in_progress') ??
    currentTasks.value.find((task) => task.status === 'pending') ??
    null,
)
const gapRows = computed<GapRow[]>(() => {
  const result = gap.value
  if (!result) return []
  const priorityOrder: Record<Priority, number> = { high: 0, medium: 1, low: 2 }
  return [
    ...result.to_improve.map((item) => ({ ...item, status: 'to_improve' as const })),
    ...result.not_recorded.map((item) => ({
      ...item,
      status: 'not_recorded' as const,
    })),
    ...result.matched.map((item) => ({ ...item, status: 'matched' as const })),
  ].sort(
    (left, right) =>
      priorityOrder[left.priority] - priorityOrder[right.priority] ||
      left.name.localeCompare(right.name),
  )
})
const nextVersion = computed(() => (current.value?.version ?? 0) + 1)

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

function initOutcomes(roadmap: Roadmap | null) {
  if (!roadmap) return
  for (const task of flattenRoadmapTasks(roadmap)) {
    if (!(task.id in outcomeDrafts.value)) {
      outcomeDrafts.value[task.id] = task.outcome
    }
  }
}

function stageProgress(stage: RoadmapStage): number {
  const completed = stage.tasks.filter(
    (task) => task.status === 'completed',
  ).length
  return progressPercent(stage.tasks.length, completed)
}

function stageStatusLabel(stage: RoadmapStage): string {
  if (!stage.tasks.length) return '未开始'
  if (stage.tasks.every((task) => task.status === 'completed')) return '已完成'
  if (
    stage.tasks.some(
      (task) => task.status === 'in_progress' || task.status === 'completed',
    )
  ) {
    return '进行中'
  }
  return '未开始'
}

function gapStatusLabel(status: GapStatus): string {
  if (status === 'matched') return '有记录'
  if (status === 'to_improve') return '待提升'
  return '尚无记录'
}

function gapStatusClass(status: GapStatus): string {
  if (status === 'matched') return 'tag-evidence'
  if (status === 'to_improve') return 'tag-inference'
  return 'tag'
}

function toggleStage(stageId: string) {
  expandedStageId.value =
    expandedStageId.value === stageId ? '' : stageId
}

const drawerRef = ref<HTMLElement | null>(null)
let drawerReturnFocus: HTMLElement | null = null

async function openHistory() {
  drawerReturnFocus = document.activeElement as HTMLElement | null
  historyOpen.value = true
  await nextTick()
  drawerRef.value?.querySelector<HTMLElement>('button')?.focus()
}

function closeHistory() {
  if (!historyOpen.value) return
  historyOpen.value = false
  void nextTick(() => drawerReturnFocus?.focus())
}

function onDrawerKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    closeHistory()
    return
  }
  if (event.key !== 'Tab') return
  const focusables = drawerRef.value?.querySelectorAll<HTMLElement>(
    'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
  )
  if (!focusables?.length) return
  const first = focusables[0]
  const last = focusables[focusables.length - 1]
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault()
    first.focus()
  }
}

async function loadGap() {
  try {
    gap.value = await getSkillGap()
    targetMissing.value = false
  } catch (value) {
    if (
      value instanceof ApiError &&
      value.code === 'ROADMAP_TARGET_REQUIRED'
    ) {
      targetMissing.value = true
      gap.value = null
      return
    }
    throw value
  }
}

async function loadCurrent() {
  const result = await getCurrentRoadmap()
  current.value = result.roadmap
  initOutcomes(current.value)
  const requested = String(route.query.stage ?? '')
  const exists = current.value?.stages.some((stage) => stage.id === requested)
  expandedStageId.value = exists && requested ? requested : currentStageId.value
}

async function loadDraft() {
  const result = await listRoadmapDrafts()
  if (!result.items.length) {
    draft.value = null
    return
  }
  draft.value = await getRoadmap(result.items[0].id)
  initOutcomes(draft.value)
}

async function loadHistory() {
  const result = await listRoadmapHistory()
  history.value = result.items
}

async function loadPage() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([loadGap(), loadCurrent(), loadDraft(), loadHistory()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
}

async function generate() {
  if (
    typeof window !== 'undefined' &&
    !window.confirm(
      `将生成 v${nextVersion.value} 草稿，当前正式版本与历史版本会保留。继续？`,
    )
  ) {
    return
  }
  error.value = ''
  generating.value = true
  try {
    draft.value = await generateRoadmap(undefined, Boolean(draft.value))
    initOutcomes(draft.value)
    toast.value = `成长路线草稿已就绪 · ${timeLabel()}`
    await loadDraft()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    generating.value = false
  }
}

async function adjustCurrent() {
  if (!current.value || adjusting.value) return
  if (
    typeof window !== 'undefined' &&
    !window.confirm(
      '将基于最新画像与已完成任务生成调整草稿；正式路线会在你确认后替换。继续？',
    )
  ) {
    return
  }
  error.value = ''
  adjusting.value = true
  try {
    draft.value = await adjustRoadmap(current.value.id)
    initOutcomes(draft.value)
    toast.value = `调整草稿已就绪（已完成任务已保留）· ${timeLabel()}`
    await loadDraft()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    adjusting.value = false
  }
}

async function confirmDraft() {
  if (!draft.value) return
  error.value = ''
  confirming.value = true
  try {
    current.value = await confirmRoadmap(draft.value.id)
    draft.value = null
    toast.value = `成长路线已启用 · ${timeLabel()}`
    await Promise.all([loadHistory(), loadCurrent()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    confirming.value = false
  }
}

async function discardDraft() {
  if (!draft.value) return
  error.value = ''
  discarding.value = true
  try {
    await discardRoadmap(draft.value.id)
    draft.value = null
    toast.value = `草稿已放弃，正式路线未改变 · ${timeLabel()}`
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    discarding.value = false
  }
}

function applyTask(updated: RoadmapTask) {
  const roadmap = current.value
  if (!roadmap) return
  const tasks: RoadmapTask[] = []
  for (const stage of roadmap.stages) {
    const index = stage.tasks.findIndex((task) => task.id === updated.id)
    if (index >= 0) {
      stage.tasks[index] = updated
    }
    tasks.push(...stage.tasks)
  }
  roadmap.task_total = tasks.length
  roadmap.task_completed = tasks.filter(
    (task) => task.status === 'completed',
  ).length
}

async function updateTask(
  task: RoadmapTask,
  status: TaskStatus,
  recordOutcome = status === 'completed',
) {
  error.value = ''
  updatingTask.value = task.id
  try {
    const outcome = recordOutcome
      ? (outcomeDrafts.value[task.id] ?? '')
      : undefined
    const result = await updateRoadmapTask(task.id, status, outcome)
    applyTask(result.task)
    outcomeDrafts.value[task.id] = result.task.outcome
    toast.value =
      status === 'completed'
        ? `任务已完成，成果已记录 · ${timeLabel()}`
        : `任务状态已更新 · ${timeLabel()}`
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    updatingTask.value = ''
  }
}

async function saveOutcome(task: RoadmapTask) {
  await updateTask(task, task.status, true)
}

function primaryLabel(task: RoadmapTask): string {
  if (task.status === 'pending') return '开始任务'
  if (task.status === 'in_progress') return '标记完成'
  if (task.status === 'completed') return '重新打开'
  return '重新开始'
}

function primaryAction(task: RoadmapTask) {
  if (task.status === 'pending') {
    void updateTask(task, 'in_progress')
    return
  }
  if (task.status === 'in_progress') {
    void updateTask(task, 'completed')
    return
  }
  void updateTask(task, 'in_progress')
}

async function viewHistory(item: RoadmapSummary) {
  if (historyDetail.value?.id === item.id) {
    historyDetail.value = null
    return
  }
  error.value = ''
  historyLoading.value = item.id
  try {
    historyDetail.value = await getRoadmap(item.id)
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    historyLoading.value = ''
  }
}

onMounted(() => {
  void loadPage()
})
</script>

<template>
  <section class="page roadmap-page">
    <header class="page-head roadmap-v2-head">
      <div class="page-head-copy">
        <h1>My Roadmap <span class="page-title-cn">成长路线</span></h1>
        <p class="page-lede">
          <template v-if="current">
            目标 {{ current.target_role }} · 当前版本 v{{ current.version }}
          </template>
          <template v-else>
            把目标拆成阶段，把阶段拆成下一步。
          </template>
        </p>
        <p class="roadmap-v2-stats">
          进行中 {{ taskCounts.in_progress }} 项 · 已完成
          {{ taskCounts.completed }} 项 · 总计 {{ totalTasks }} 项
        </p>
      </div>
      <div class="page-head-actions roadmap-head-actions">
        <span class="badge">{{ headerStatus }}</span>
        <button
          type="button"
          class="button"
          :class="draft ? 'secondary' : 'primary'"
          :disabled="generating || targetMissing"
          @click="generate"
        >
          {{ generating ? '正在生成' : draft ? '重新生成草稿' : '生成新版本' }}
        </button>
        <button
          type="button"
          class="button secondary small"
          data-testid="roadmap-history"
          @click="openHistory"
        >
          历史版本
        </button>
        <RouterLink to="/profile" class="button ghost">查看职业画像</RouterLink>
      </div>
    </header>

    <ErrorNotice
      v-if="error"
      :error="{ code: 'ROADMAP_ERROR', message: error }"
      retryable
      @dismiss="error = ''"
      @retry="loadPage"
    />

    <PageSkeleton v-if="loading" variant="roadmap" />

    <template v-else>
      <div class="roadmap-top">
        <section class="gap-card card" data-testid="roadmap-gap">
        <div class="gap-card-head">
          <div>
            <p class="section-label">能力差距</p>
            <h3>技能差距（先看这里）</h3>
            <p class="note">对照目标岗位要求，差距决定阶段顺序。</p>
          </div>
          <div class="roadmap-badges">
            <span v-if="gap" class="tag">{{ GAP_BASIS_LABELS[gap.basis] }}</span>
            <span v-if="gap" class="tag">{{ gapDatasetLabel }}</span>
          </div>
        </div>
        <p v-if="targetMissing" class="note">
          尚未设置目标岗位。先到职业画像设置目标，才能计算差距。
        </p>
        <template v-else-if="gap">
          <div class="market-match-meta">
            <span>目标 {{ gap.target_role }}</span>
            <span>目标岗位样本 {{ gap.meta.sample_size }} 条</span>
            <span>来源 {{ gapSources || '未记录' }}</span>
          </div>
          <p v-if="gapNote" class="market-warning">{{ gapNote }}</p>
          <table
            v-if="gapRows.length"
            class="gap-table"
            :data-expanded="String(gapExpanded)"
            :data-total="gapRows.length"
          >
            <thead>
              <tr>
                <th>技能</th>
                <th>需求占比</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(item, index) in gapRows"
                v-show="gapExpanded || index < 6"
                :key="`${item.status}-${item.name}`"
              >
                <td :title="userFacingText(item.reason)">{{ item.name }}</td>
                <td class="gap-share-cell">
                  <span class="gap-share">
                    <span
                      class="gap-share-bar"
                      :style="{ width: `${Math.round(item.market_share * 100)}%` }"
                      aria-hidden="true"
                    ></span>
                    <span class="gap-share-value">
                      {{ Math.round(item.market_share * 100) }}%
                    </span>
                  </span>
                </td>
                <td>
                  <span class="tag" :class="gapStatusClass(item.status)">
                    {{ gapStatusLabel(item.status) }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <button
            v-if="gapRows.length > 6"
            type="button"
            class="link-button"
            style="margin-top: 8px"
            @click="gapExpanded = !gapExpanded"
          >
            {{ gapExpanded ? '收起' : `展开全部 ${gapRows.length} 项` }}
          </button>
          <p v-else class="note">暂无差距数据。</p>
          <p class="note">
            资料已确认不等于客观验证；没有记录不等于不具备。
          </p>
        </template>
        <p v-else class="note state-loading" role="status">
          正在读取市场数据…
        </p>
      </section>

        <aside class="roadmap-focus card" aria-label="当前阶段">
          <p class="section-label">Current stage</p>
          <h3>{{ activeStage?.title || '尚未开始' }}</h3>
          <p class="note">
            {{ activeStage?.goal || '先确认目标岗位，再生成路线。' }}
          </p>
          <div
            class="roadmap-focus-progress"
            role="progressbar"
            :aria-valuenow="currentPercent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <span :style="{ width: `${currentPercent}%` }"></span>
          </div>
          <p class="quiet-note">
            路线进度 {{ currentPercent }}% · {{ taskCounts.completed }}/{{ totalTasks }}
            任务
          </p>
          <div v-if="focusTask" class="roadmap-focus-next">
            <span class="section-label">Next move</span>
            <strong>{{ focusTask.title }}</strong>
            <p class="note">{{ focusTask.description }}</p>
          </div>
          <p v-else class="note">暂无待推进任务。</p>
        </aside>
      </div>

      <section class="route-block" data-testid="roadmap-current">
        <div class="route-hero">
          <div>
            <p class="section-label">当前正式路线</p>
            <template v-if="current">
              <h3>{{ current.title }}</h3>
              <p class="note">{{ current.summary }}</p>
              <div class="market-match-meta">
                <span>目标 {{ current.target_role }}</span>
                <span>进度 {{ current.task_completed }}/{{ current.task_total }}（{{ currentPercent }}%）</span>
                <span>更新 {{ formatRoadmapDate(current.updated_at) }}</span>
                <span class="tag">{{ generationLabel }}</span>
              </div>
            </template>
            <p v-else class="note">
              还没有正式路线。先生成草稿，核对后确认启用。
            </p>
          </div>
        </div>

        <p v-if="current?.stale" class="market-warning">
          画像或目标岗位已更新，当前路线可能过期；可基于最新进度生成调整草稿（已完成任务会保留）。
        </p>
        <div
          v-if="current"
          class="page-head-actions"
          style="justify-content: flex-start"
        >
          <button
            type="button"
            class="button secondary"
            :disabled="adjusting"
            @click="adjustCurrent"
          >
            {{ adjusting ? '正在调整' : '根据最新进度调整' }}
          </button>
        </div>

        <template v-if="current">
          <div
            class="roadmap-progress"
            role="progressbar"
            :aria-valuenow="currentPercent"
            aria-valuemin="0"
            aria-valuemax="100"
          >
            <div :style="{ width: `${currentPercent}%` }"></div>
          </div>

          <div class="stage-list">
            <div
              v-for="(stage, index) in current.stages"
              :key="stage.id"
              class="stage-row"
              :class="{
                'is-current': stage.id === currentStageId,
                'is-done': stageProgress(stage) === 100,
              }"
            >
              <button
                type="button"
                class="stage-row-head"
                @click="toggleStage(stage.id)"
              >
                <span class="stage-index">
                  {{ stageProgress(stage) === 100 ? '✓' : index + 1 }}
                </span>
                <span class="stage-row-copy">
                  <strong>{{ stage.title }}</strong>
                  <span>
                    {{ stage.goal }} ·
                    {{ stage.duration || '时间未记录' }}
                  </span>
                </span>
                <span class="stage-percent">{{ stageProgress(stage) }}%</span>
                <span class="tag">{{ stageStatusLabel(stage) }}</span>
              </button>

              <div
                v-if="expandedStageId === stage.id"
                class="stage-row-body"
              >
                <article
                  v-for="task in stage.tasks"
                  :key="task.id"
                  class="task-v2"
                  :class="{ 'is-current': task.status === 'in_progress' }"
                >
                  <div class="task-v2-head">
                    <strong>{{ task.title }}</strong>
                    <span class="tag">{{ TASK_STATUS_LABELS[task.status] }}</span>
                  </div>
                  <p class="task-v2-desc">{{ task.description }}</p>
                  <details>
                    <summary>验收标准</summary>
                    <p class="note">{{ task.acceptance_criteria }}</p>
                  </details>
                  <label
                    v-if="task.status === 'in_progress'"
                    class="field roadmap-outcome"
                  >
                    <span>实践成果（可选）</span>
                    <textarea
                      v-model="outcomeDrafts[task.id]"
                      rows="2"
                      maxlength="4000"
                      placeholder="成果、链接或复盘"
                    ></textarea>
                  </label>
                  <p v-if="task.outcome" class="task-outcome">
                    已记录成果：{{ task.outcome }}
                  </p>
                  <div class="task-v2-actions">
                    <button
                      type="button"
                      class="button small primary"
                      :disabled="updatingTask === task.id"
                      @click="primaryAction(task)"
                    >
                      {{ primaryLabel(task) }}
                    </button>
                    <button
                      v-if="task.status === 'in_progress'"
                      type="button"
                      class="link-button"
                      :disabled="updatingTask === task.id"
                      @click="saveOutcome(task)"
                    >
                      保存成果
                    </button>
                    <button
                      v-if="task.status === 'in_progress'"
                      type="button"
                      class="link-button"
                      :disabled="updatingTask === task.id"
                      @click="updateTask(task, 'abandoned')"
                    >
                      放弃任务
                    </button>
                  </div>
                </article>
              </div>
            </div>
          </div>
          <p class="note">任务完成不等于技能掌握；画像变化需要新的证据与确认。</p>
        </template>
      </section>

      <section class="panel draft-panel" data-testid="roadmap-draft">
        <div class="section-heading">
          <div>
            <p class="section-label">下一步</p>
            <h3>待确认草稿</h3>
          </div>
          <span v-if="draft" class="tag">v{{ draft.version }} · 草稿</span>
        </div>
        <p v-if="!draft" class="note">
          暂无草稿。点击「生成新版本」基于当前画像与市场数据生成。
        </p>
        <template v-else>
          <h4>{{ draft.title }}</h4>
          <p class="note">{{ draft.summary }}</p>
          <div class="market-match-meta">
            <span>目标 {{ draft.target_role }}</span>
            <span>任务 {{ draft.task_total }} 个</span>
            <span class="tag">{{ draftGenerationLabel }}</span>
            <span v-if="draft.gap" class="tag">{{ GAP_BASIS_LABELS[draft.gap.basis] }}</span>
          </div>
          <p v-if="draft.gap?.reference_only" class="market-warning">
            样本量较少，当前草稿仅作参考
          </p>
          <details class="draft-preview">
            <summary>查看阶段与任务（{{ draft.stages.length }} 个阶段）</summary>
            <article v-for="stage in draft.stages" :key="stage.id" class="draft-stage">
              <header class="route-stage-head">
                <div>
                  <h4>{{ stage.title }}</h4>
                  <p class="note">
                    {{ stage.goal }}
                    <template v-if="stage.duration"> · 预计 {{ stage.duration }}</template>
                  </p>
                </div>
                <span class="tag tag-muted">{{ PRIORITY_LABELS[stage.priority] }}</span>
              </header>
              <ul class="draft-task-list">
                <li v-for="task in stage.tasks" :key="task.id">
                  <div>
                    <strong>{{ task.title }}</strong>
                    <span class="tag tag-muted">{{ TASK_STATUS_LABELS[task.status] }}</span>
                  </div>
                  <p>验收：{{ task.acceptance_criteria }}</p>
                </li>
              </ul>
            </article>
          </details>
          <div class="roadmap-actions">
            <button
              type="button"
              class="button ghost"
              :disabled="discarding || confirming"
              @click="discardDraft"
            >
              放弃草稿
            </button>
            <button
              type="button"
              class="button primary"
              :disabled="confirming || discarding"
              @click="confirmDraft"
            >
              {{ confirming ? '正在启用' : '确认并启用' }}
            </button>
          </div>
          <p class="note">
            确认后旧正式路线归档，草稿成为新的正式路线；未确认草稿不会覆盖正式路线。
          </p>
        </template>
      </section>
    </template>

    <div
      v-if="historyOpen"
      class="drawer-backdrop"
      @click.self="closeHistory"
    >
      <aside
        ref="drawerRef"
        class="drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="roadmap-history-title"
        @keydown="onDrawerKeydown"
      >
        <div class="drawer-head">
          <div>
            <h3 id="roadmap-history-title">历史版本</h3>
            <p class="note">只读保留，不覆盖当前路线。</p>
            <p class="note">
              版本号按生成顺序递增；已放弃草稿不会出现在历史列表，因此编号可能跳号。
            </p>
          </div>
          <button type="button" class="button ghost small" @click="closeHistory">
            关闭
          </button>
        </div>
        <p v-if="!history.length" class="note">
          暂无历史版本；确认正式路线后会出现在这里。
        </p>
        <div
          v-for="item in history"
          :key="item.id"
          class="version-row"
        >
          <div>
            <strong>
              v{{ item.version }} · {{ ROADMAP_STATUS_LABELS[item.status] }}
            </strong>
            <p>
              {{ item.task_completed }}/{{ item.task_total }} 任务 ·
              {{ formatRoadmapDate(item.confirmed_at ?? item.updated_at) }}
            </p>
          </div>
          <button
            type="button"
            class="button secondary small"
            :disabled="historyLoading === item.id"
            @click="viewHistory(item)"
          >
            {{ historyDetail?.id === item.id ? '收起' : '查看' }}
          </button>
          <div v-if="historyDetail?.id === item.id" class="history-detail">
            <p class="note">{{ historyDetail.summary }}</p>
            <ul>
              <li v-for="stage in historyDetail.stages" :key="stage.id">
                {{ stage.title }}：{{ stage.tasks.length }} 个任务
              </li>
            </ul>
          </div>
        </div>
      </aside>
    </div>

    <ToastNotice v-if="toast" :message="toast" @close="toast = ''" />
  </section>
</template>