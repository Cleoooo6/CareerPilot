<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'

import ErrorNotice from '@/components/ErrorNotice.vue'
import PageSkeleton from '@/components/PageSkeleton.vue'
import { ApiError } from '@/api/client'
import { getMarketOverview } from '@/api/market'
import { getProfile, listAnalyses } from '@/api/profile'
import { getCurrentRoadmap, getSkillGap } from '@/api/roadmap'
import type { MarketOverview } from '@/types/market'
import type { ProfileAnalysisOut, ProfileOut } from '@/types/profile'
import type { Roadmap, RoadmapTask, SkillGap } from '@/types/roadmap'
import {
  currentStage,
  dashboardGreeting,
  formatDashboardDate,
  nextTasks,
  profileCompletion,
  topCountTitle,
} from '@/utils/dashboardView'
import { latestAnalysis } from '@/utils/profileView'
import { flattenRoadmapTasks, progressPercent } from '@/utils/roadmapView'

const loading = ref(true)
const error = ref('')
const profile = ref<ProfileOut | null>(null)
const analyses = ref<ProfileAnalysisOut[]>([])
const roadmap = ref<Roadmap | null>(null)
const gap = ref<SkillGap | null>(null)
const market = ref<MarketOverview | null>(null)

const profileData = computed(() => profile.value?.data ?? null)
const completion = computed(() => profileCompletion(profileData.value))
const name = computed(() => profileData.value?.basic.name.trim() || '你好')
const targetRole = computed(
  () => profileData.value?.goals.target_role.trim() || '',
)
const analysis = computed(() => latestAnalysis(analyses.value))
const advice = computed(() => {
  const result = analysis.value?.analysis
  if (!result) return ''
  return result.next_actions[0] ?? result.overview
})
const stage = computed(() => currentStage(roadmap.value))
const pendingTasks = computed(() =>
  nextTasks(flattenRoadmapTasks(roadmap.value), 3),
)
const displayTasks = computed(() =>
  stage.value?.tasks.length ? stage.value.tasks.slice(0, 3) : pendingTasks.value,
)
const focusTask = computed(() => pendingTasks.value[0] ?? null)
const progress = computed(() =>
  roadmap.value
    ? progressPercent(roadmap.value.task_total, roadmap.value.task_completed)
    : 0,
)
const gaps = computed(() => gap.value?.to_improve.slice(0, 3) ?? [])
const gapTitle = computed(() => topCountTitle('能力差距', gaps.value.length, 3))
const focusContext = computed(
  () =>
    stage.value?.goal ||
    focusTask.value?.description ||
    '完成这一项后，路线会自动推进。',
)

function taskMeta(task: RoadmapTask): string {
  const parts: string[] = []
  if (stage.value?.title) parts.push(stage.value.title)
  if (task.estimated_time) parts.push(`预计 ${task.estimated_time}`)
  return parts.join(' · ') || task.description || '待补充说明'
}
const marketRole = computed(() => {
  const roles = market.value?.top_roles ?? []
  if (!roles.length) return null
  return (
    roles.find((item) => item.name === targetRole.value) ?? roles[0]
  )
})
const marketSample = computed(() => market.value?.meta.sample_size ?? 0)
const marketSynthetic = computed(
  () => market.value?.meta.dataset_kinds.includes('synthetic') ?? false,
)

function errorMessage(value: unknown): string {
  if (value instanceof ApiError) return value.message
  return '总览数据加载失败，请稍后重试'
}

async function load() {
  loading.value = true
  error.value = ''
  const [profileResult, analysisResult, roadmapResult, gapResult, marketResult] =
    await Promise.allSettled([
      getProfile(),
      listAnalyses(),
      getCurrentRoadmap(),
      getSkillGap(),
      getMarketOverview(),
    ])
  profile.value =
    profileResult.status === 'fulfilled' ? profileResult.value.profile : null
  analyses.value =
    analysisResult.status === 'fulfilled' ? analysisResult.value.items : []
  roadmap.value =
    roadmapResult.status === 'fulfilled' ? roadmapResult.value.roadmap : null
  gap.value = gapResult.status === 'fulfilled' ? gapResult.value : null
  market.value = marketResult.status === 'fulfilled' ? marketResult.value : null
  if (profileResult.status === 'rejected') {
    error.value = errorMessage(profileResult.reason)
  }
  loading.value = false
}

onMounted(load)
</script>

<template>
  <section class="page dashboard-page">
    <header class="page-head">
      <div class="page-head-copy">
        <h2>Dashboard <span class="page-title-cn">职业发展总览</span></h2>
        <p v-if="loading" class="page-lede">
          <span class="skeleton skeleton-line md" style="display: block"></span>
        </p>
        <p v-else-if="error && !profile" class="page-lede">
          画像读取失败，暂时无法显示目标岗位与完善度。
        </p>
        <p v-else class="page-lede">
          {{ dashboardGreeting() }}，{{ name }}。
          {{ targetRole ? `目标 ${targetRole}。` : '目标岗位待设置。' }}
          {{ formatDashboardDate() }}。
        </p>
      </div>
      <div v-if="loading" style="display: flex; align-items: center; gap: 10px">
        <div
          class="skeleton skeleton-avatar"
          style="width: 74px; height: 74px; border-radius: 50%"
        ></div>
        <div class="skeleton skeleton-line sm" style="width: 96px"></div>
      </div>
      <RouterLink
        v-else-if="error && !profile"
        to="/profile?tab=overview"
        class="dash-metric-link"
      >
        <span class="dash-error-metric">—</span>
        <span class="quiet-note">画像读取失败</span>
      </RouterLink>
      <RouterLink v-else to="/profile?tab=overview" class="dash-metric-link">
        <div class="dash-metric-ring" :style="{ '--pct': completion }">
          <span>{{ completion }}%</span>
        </div>
        <span class="quiet-note">画像完善度<br />按已确认资料计算</span>
      </RouterLink>
    </header>

    <PageSkeleton v-if="loading" variant="dashboard" />

    <template v-else>
      <ErrorNotice
        v-if="error"
        :error="{ code: 'DASHBOARD_ERROR', message: error }"
        retryable
        @dismiss="error = ''"
        @retry="load"
      />

      <section class="dash-focus">
        <div class="dash-focus-eyebrow">
          <span class="tag tag-suggestion">下一步 · 来自你的成长路线</span>
        </div>
        <template v-if="focusTask">
          <h3>{{ focusTask.title }}</h3>
          <p>{{ focusContext }}</p>
          <div class="dash-focus-foot">
            <div>
              <RouterLink
                to="/roadmap"
                class="link-button"
                style="color: #a9cfc6"
              >
                阶段进度 {{ progress }}%
              </RouterLink>
              <div class="dash-progress">
                <span :style="{ width: `${progress}%` }"></span>
              </div>
            </div>
            <RouterLink to="/roadmap" class="button primary">
              查看全部任务
            </RouterLink>
          </div>
        </template>
        <template v-else-if="error && !profile">
          <h3>暂时无法读取画像</h3>
          <p>数据加载失败，请重试；不会用 0% 或空目标代替真实数据。</p>
          <button type="button" class="button primary" @click="load">
            重新加载
          </button>
        </template>
        <template v-else-if="!profile">
          <h3>先建立你的职业画像</h3>
          <p>画像会决定差距判断与路线生成；从基本信息和目标开始。</p>
          <RouterLink to="/profile" class="button primary">去建立画像</RouterLink>
        </template>
        <template v-else>
          <h3>下一步还没有排好</h3>
          <p>先生成一份成长路线，Dashboard 会同步当前阶段与任务。</p>
          <RouterLink to="/roadmap" class="button primary">
            生成成长路线
          </RouterLink>
        </template>
      </section>

      <div class="dash-grid">
        <section class="dash-card card">
          <div class="dash-card-head">
            <div>
              <h3>本周要推进的事</h3>
              <p class="note">来自成长路线 · {{ displayTasks.length }} 项</p>
            </div>
            <RouterLink to="/roadmap" class="link-button">查看全部</RouterLink>
          </div>
          <template v-if="displayTasks.length">
            <div
              v-for="task in displayTasks"
              :key="task.id"
              class="dash-task"
            >
              <span
                class="dash-task-mark"
                :class="{ 'is-done': task.status === 'completed' }"
              ></span>
              <div class="dash-task-copy">
                <strong>{{ task.title }}</strong>
                <span>{{ taskMeta(task) }}</span>
              </div>
            </div>
          </template>
          <p v-else class="note">还没有待推进的任务。</p>
        </section>

        <div style="display: flex; flex-direction: column; gap: 18px">
          <section class="dash-card card">
            <div class="dash-card-head">
              <div>
                <h3>{{ gapTitle }}</h3>
                <p class="note">来自目标岗位的技能差距</p>
              </div>
              <RouterLink to="/roadmap" class="link-button">查看差距</RouterLink>
            </div>
            <div v-if="gaps.length">
              <div
                v-for="item in gaps"
                :key="item.name"
                class="dash-gap-row"
              >
                <span>{{ item.name }}</span>
                <span class="tag">
                  {{ item.priority === 'high' ? '优先' : '待提升' }}
                </span>
              </div>
            </div>
            <p v-else class="note">还没有差距数据；先设置目标岗位。</p>
          </section>

          <section class="dash-card card">
            <div class="dash-card-head">
              <div>
                <h3>市场风向</h3>
                <p class="note">与你目标方向相关的一条</p>
              </div>
              <RouterLink to="/market" class="link-button">去市场洞察</RouterLink>
            </div>
            <div v-if="marketRole" class="dash-gap-row">
              <span>{{ marketRole.name }}</span>
              <RouterLink to="/market" class="link-button">{{ marketRole.count }} 条岗位</RouterLink>
            </div>
            <p v-else class="note">暂无市场样本。</p>
            <p class="note">
              样本 {{ marketSample }} 条{{ marketSynthetic ? ' · 合成演示数据' : '' }}
            </p>
          </section>
        </div>
      </div>

      <section class="dash-advisor card">
        <div>
          <h3>AI Career Advisor</h3>
          <p>{{ advice || '还没有分析结论；可以先和顾问聊聊你的方向。' }}</p>
        </div>
        <RouterLink to="/chat" class="button secondary">继续对话</RouterLink>
      </section>
    </template>
  </section>
</template>