<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import {
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
  TASK_TYPE_LABELS,
  type Roadmap,
  type RoadmapSummary,
  type RoadmapTask,
  type SkillGap,
  type TaskStatus,
} from '@/types/roadmap'
import {
  flattenRoadmapTasks,
  formatRoadmapDate,
  marketSharePercent,
  progressPercent,
} from '@/utils/roadmapView'
import { userFacingText } from '@/utils/userFacing'

const loading = ref(true)
const generating = ref(false)
const confirming = ref(false)
const discarding = ref(false)
const updatingTask = ref('')
const targetMissing = ref(false)
const error = ref('')
const success = ref('')
const gap = ref<SkillGap | null>(null)
const current = ref<Roadmap | null>(null)
const draft = ref<Roadmap | null>(null)
const history = ref<RoadmapSummary[]>([])
const historyDetail = ref<Roadmap | null>(null)
const historyLoading = ref('')
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

function errorMessage(value: unknown): string {
  if (value instanceof ApiError) return value.message
  return '操作失败，请稍后重试'
}

function clearFeedback() {
  error.value = ''
  success.value = ''
}

function initOutcomes(roadmap: Roadmap | null) {
  if (!roadmap) return
  for (const task of flattenRoadmapTasks(roadmap)) {
    if (!(task.id in outcomeDrafts.value)) {
      outcomeDrafts.value[task.id] = task.outcome
    }
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
  clearFeedback()
  try {
    await Promise.all([loadGap(), loadCurrent(), loadDraft(), loadHistory()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    loading.value = false
  }
}

async function generate() {
  clearFeedback()
  generating.value = true
  try {
    draft.value = await generateRoadmap(undefined, Boolean(draft.value))
    initOutcomes(draft.value)
    success.value = '成长路线草稿已就绪，请确认后启用'
    await loadDraft()
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    generating.value = false
  }
}

async function confirmDraft() {
  if (!draft.value) return
  clearFeedback()
  confirming.value = true
  try {
    current.value = await confirmRoadmap(draft.value.id)
    draft.value = null
    success.value = '成长路线已启用'
    await Promise.all([loadHistory(), loadCurrent()])
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    confirming.value = false
  }
}

async function discardDraft() {
  if (!draft.value) return
  clearFeedback()
  discarding.value = true
  try {
    await discardRoadmap(draft.value.id)
    draft.value = null
    success.value = '草稿已放弃，正式路线未改变'
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
  clearFeedback()
  updatingTask.value = task.id
  try {
    const outcome = recordOutcome
      ? (outcomeDrafts.value[task.id] ?? '')
      : undefined
    const result = await updateRoadmapTask(task.id, status, outcome)
    applyTask(result.task)
    outcomeDrafts.value[task.id] = result.task.outcome
    success.value =
      status === 'completed' ? '任务已完成，成果已记录' : '任务状态已更新'
  } catch (value) {
    error.value = errorMessage(value)
  } finally {
    updatingTask.value = ''
  }
}

async function saveOutcome(task: RoadmapTask) {
  await updateTask(task, task.status, true)
}

async function toggleHistory(item: RoadmapSummary) {
  if (historyDetail.value?.id === item.id) {
    historyDetail.value = null
    return
  }
  clearFeedback()
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
    <header class="page-head roadmap-head">
      <div class="page-head-copy">

        <h2>从当前状态，走向目标</h2>
        <p class="page-lede">
          把目标拆成阶段，把阶段拆成下一步。
        </p>
      </div>
      <div class="page-head-actions roadmap-head-actions">
        <span class="badge">{{ headerStatus }}</span>
        <button
          type="button"
          class="button primary"
          :disabled="generating || targetMissing"
          @click="generate"
        >
          {{ generating ? '正在生成' : draft ? '重新生成草稿' : '生成成长路线' }}
        </button>
        <RouterLink to="/profile" class="button ghost">查看职业画像</RouterLink>
      </div>
    </header>

    <ErrorNotice
      v-if="error"
      :error="{ code: 'ROADMAP_ERROR', message: error }"
      @dismiss="error = ''"
    />
    <p v-if="success" class="success-note">{{ success }}</p>

    <div v-if="loading" class="loading-state">正在加载成长路线…</div>

    <template v-else>
      <section class="page-section roadmap-gap" data-testid="roadmap-gap">
        <div class="section-heading">
          <div>
            <p class="section-label">能力差距</p>
            <h3>技能差距</h3>
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
            <span>样本 {{ gap.meta.sample_size }} 条</span>
            <span>
              统计周期 {{ formatRoadmapDate(gap.meta.period_start) }}–{{ formatRoadmapDate(gap.meta.period_end) }}
            </span>
            <span>来源 {{ gapSources || '未记录' }}</span>
          </div>
          <p v-if="gapNote" class="market-warning">{{ gapNote }}</p>
          <div class="match-columns gap-columns">
            <div>
              <h4>有记录且有证据</h4>
              <p class="note">资料已确认，未做客观能力验证。</p>
              <ul v-if="gap.matched.length" class="gap-list">
                <li v-for="item in gap.matched" :key="item.name">
                  <div class="gap-line">
                    <span>{{ item.name }}</span>
                    <small>{{ marketSharePercent(item) }}%</small>
                  </div>
                  <p class="gap-reason">{{ item.reason }}</p>
                </li>
              </ul>
              <p v-else class="note">暂无有证据的技能。</p>
            </div>
            <div>
              <h4>待提升</h4>
              <ul v-if="gap.to_improve.length" class="gap-list">
                <li v-for="item in gap.to_improve" :key="item.name">
                  <div class="gap-line">
                    <span>{{ item.name }}</span>
                    <small>
                      {{ marketSharePercent(item) }}% ·
                      {{ PRIORITY_LABELS[item.priority] }}
                    </small>
                  </div>
                  <p class="gap-reason">{{ item.reason }}</p>
                </li>
              </ul>
              <p v-else class="note">暂无。</p>
            </div>
            <div>
              <h4>尚无记录（不等于不会）</h4>
              <ul v-if="gap.not_recorded.length" class="gap-list">
                <li v-for="item in gap.not_recorded" :key="item.name">
                  <div class="gap-line">
                    <span>{{ item.name }}</span>
                    <small>
                      {{ marketSharePercent(item) }}% ·
                      {{ PRIORITY_LABELS[item.priority] }}
                    </small>
                  </div>
                  <p class="gap-reason">{{ item.reason }}</p>
                </li>
              </ul>
              <p v-else class="note">暂无。</p>
            </div>
          </div>
          <p class="note">
            资料已确认不等于客观验证；没有记录不等于不具备。
          </p>
        </template>
        <p v-else class="note">正在读取市场数据…</p>
      </section>

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
            <p v-else class="note">还没有正式路线。先生成草稿，核对后确认启用。</p>
          </div>
          <span v-if="current" class="tag">正式 v{{ current.version }}</span>
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

          <ol class="route-timeline">
            <li
              v-for="(stage, stageIndex) in current.stages"
              :key="stage.id"
              class="route-stage"
              :class="{ 'is-current': stage.id === currentStageId }"
            >
              <div class="route-marker">{{ stageIndex + 1 }}</div>
              <div class="route-stage-body">
                <header class="route-stage-head">
                  <div>
                    <h4>{{ stage.title }}</h4>
                    <p class="note">
                      {{ stage.goal }}
                      <template v-if="stage.duration"> · 预计 {{ stage.duration }}</template>
                    </p>
                  </div>
                  <span class="tag tag-muted">{{ PRIORITY_LABELS[stage.priority] }}优先级</span>
                </header>

                <article
                  v-for="task in stage.tasks"
                  :key="task.id"
                  class="roadmap-task"
                >
                  <div class="roadmap-task-head">
                    <strong>{{ task.title }}</strong>
                    <span class="tag">{{ TASK_STATUS_LABELS[task.status] }}</span>
                    <span class="tag tag-muted">{{ TASK_TYPE_LABELS[task.task_type] }}</span>
                    <span class="tag tag-muted">{{ PRIORITY_LABELS[task.priority] }}</span>
                  </div>
                  <p class="roadmap-task-desc">{{ task.description }}</p>
                  <p class="roadmap-acceptance">
                    验收标准：{{ task.acceptance_criteria }}
                  </p>
                  <p class="note">
                    预计 {{ task.estimated_time || '未估算' }} · 完成时间
                    {{ task.completed_at ? formatRoadmapDate(task.completed_at) : '未完成' }}
                  </p>
                  <label class="field roadmap-outcome">
                    <span>实践成果（可选）</span>
                    <textarea
                      v-model="outcomeDrafts[task.id]"
                      rows="2"
                      maxlength="4000"
                      placeholder="成果、链接或复盘"
                    ></textarea>
                  </label>
                  <div class="roadmap-task-actions">
                    <button
                      v-if="task.status === 'pending'"
                      type="button"
                      class="button small"
                      :disabled="updatingTask === task.id"
                      @click="updateTask(task, 'in_progress')"
                    >
                      开始任务
                    </button>
                    <template v-if="task.status === 'in_progress'">
                      <button
                        type="button"
                        class="button small primary"
                        :disabled="updatingTask === task.id"
                        @click="updateTask(task, 'completed')"
                      >
                        标记完成
                      </button>
                      <button
                        type="button"
                        class="button small ghost"
                        :disabled="updatingTask === task.id"
                        @click="updateTask(task, 'abandoned')"
                      >
                        放弃任务
                      </button>
                    </template>
                    <button
                      v-if="task.status === 'completed'"
                      type="button"
                      class="button small ghost"
                      :disabled="updatingTask === task.id"
                      @click="updateTask(task, 'in_progress')"
                    >
                      重新打开
                    </button>
                    <button
                      v-if="task.status === 'abandoned'"
                      type="button"
                      class="button small ghost"
                      :disabled="updatingTask === task.id"
                      @click="updateTask(task, 'in_progress')"
                    >
                      重新开始
                    </button>
                    <button
                      type="button"
                      class="button small ghost"
                      :disabled="updatingTask === task.id"
                      @click="saveOutcome(task)"
                    >
                      保存成果
                    </button>
                  </div>
                  <p v-if="task.outcome" class="task-outcome">
                    已记录成果：{{ task.outcome }}
                  </p>
                </article>
              </div>
            </li>
          </ol>
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
          暂无草稿。点击「生成成长路线」基于当前画像与市场数据生成。
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
          <details open class="draft-preview">
            <summary>查看阶段与任务（{{ draft.stages.length }} 个阶段）</summary>
            <article
              v-for="stage in draft.stages"
              :key="stage.id"
              class="draft-stage"
            >
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

      <section class="section-block" data-testid="roadmap-history">
        <div class="section-heading">
          <h3>历史版本</h3>
          <span class="tag tag-muted">只读</span>
        </div>
        <p v-if="!history.length" class="note">
          暂无历史版本；确认正式路线后会出现在这里。
        </p>
        <ul v-else class="revision-list">
          <li v-for="item in history" :key="item.id">
            <span class="tag">v{{ item.version }}</span>
            <span>{{ ROADMAP_STATUS_LABELS[item.status] }}</span>
            <span>{{ item.title }}</span>
            <time>{{ formatRoadmapDate(item.confirmed_at ?? item.updated_at) }}</time>
            <button
              type="button"
              class="button small ghost"
              :disabled="historyLoading === item.id"
              @click="toggleHistory(item)"
            >
              {{ historyDetail?.id === item.id ? '收起' : '查看' }}
            </button>
          </li>
        </ul>
        <div v-if="historyDetail" class="history-detail">
          <h4>{{ historyDetail.title }} · v{{ historyDetail.version }}</h4>
          <p class="note">{{ historyDetail.summary }}</p>
          <ul>
            <li v-for="stage in historyDetail.stages" :key="stage.id">
              {{ stage.title }}：{{ stage.tasks.length }} 个任务
            </li>
          </ul>
        </div>
      </section>
    </template>
  </section>
</template>