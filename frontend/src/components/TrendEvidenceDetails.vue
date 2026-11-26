<script setup lang="ts">
import type { TrendEvidence } from '@/types/industryTrends'

defineProps<{ evidence: TrendEvidence; gaps: string[] }>()

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleDateString('zh-CN') : '—'
}

function percent(value: number) {
  return `${Math.round(value * 100)}%`
}
</script>

<template>
  <details class="trend-evidence">
    <summary>查看证据与口径</summary>
    <div class="trend-evidence-body">
      <div class="trend-evidence-grid">
        <div>
          <p class="section-label">岗位证据（本行业月度）</p>
          <p>
            样本 {{ evidence.job_count }} 条，覆盖 {{ evidence.job_month_count }} 个月
            <span v-if="evidence.synthetic" class="trend-evidence-warn">
              · 含合成数据
            </span>
          </p>
          <p v-if="evidence.job_period_start || evidence.job_period_end" class="quiet-note">
            {{ formatDate(evidence.job_period_start) }} 至
            {{ formatDate(evidence.job_period_end) }}
          </p>
          <div v-if="evidence.job_months.length" class="trend-month-list">
            <span v-for="month in evidence.job_months" :key="month.period">
              {{ month.period }}：{{ month.count }}
            </span>
          </div>
          <p v-if="evidence.roles.length" class="trend-evidence-line">
            岗位：{{ evidence.roles.map((item) => `${item.name} ${item.count}`).join(' · ') }}
          </p>
          <p v-if="evidence.skills.length" class="trend-evidence-line">
            技能：
            {{ evidence.skills.map((item) => `${item.skill} ${percent(item.share)}`).join(' · ') }}
          </p>
          <p v-if="evidence.locations.length" class="trend-evidence-line">
            地区：{{ evidence.locations.map((item) => `${item.name} ${item.count}`).join(' · ') }}
          </p>
        </div>
        <div>
          <p class="section-label">新闻证据</p>
          <p>
            {{ evidence.news_count }} 篇，来自 {{ evidence.news_source_count }} 个来源，
            时间跨度 {{ evidence.news_span_days }} 天
          </p>
          <p v-if="evidence.news_count < 2 || evidence.news_source_count < 2" class="trend-evidence-warn">
            新闻不足以独立证明长期趋势
          </p>
          <div v-if="evidence.news_examples.length" class="trend-news-list">
            <a
              v-for="news in evidence.news_examples"
              :key="news.id"
              :href="news.url || undefined"
              target="_blank"
              rel="noopener noreferrer"
            >
              <span>{{ news.title }}</span>
              <small>{{ news.source }} · {{ formatDate(news.published_at) }}</small>
            </a>
          </div>
        </div>
      </div>
      <div v-if="gaps.length" class="trend-gaps">
        <strong>数据不足：</strong>
        <span>{{ gaps.join('；') }}</span>
      </div>
      <p v-if="evidence.sources.length" class="quiet-note">
        来源：{{ evidence.sources.join('、') }}
      </p>
    </div>
  </details>
</template>