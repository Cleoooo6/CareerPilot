export type PulseIndustry = 'internet' | 'finance' | 'ai' | 'energy'

export interface PulseIndustryOption {
  id: PulseIndustry
  label: string
}

export interface PulseItem {
  id: string
  industry: PulseIndustry
  industryLabel: string
  topic: string
  title: string
  source: string
  publishedAt: string
  summary: string
  aiRead: string
  careerImpact: string
  url: string
  isExample: true
}

export const PULSE_INDUSTRIES: PulseIndustryOption[] = [
  { id: 'internet', label: '互联网' },
  { id: 'finance', label: '金融' },
  { id: 'ai', label: '人工智能' },
  { id: 'energy', label: '新能源' },
]

export const PULSE_EXAMPLES: PulseItem[] = [
  {
    id: 'example-internet-1',
    industry: 'internet',
    industryLabel: '互联网',
    topic: '平台业务',
    title: '示例：平台业务调整，团队更重视数据闭环',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 20 日',
    summary:
      '示例摘要：平台团队把增长指标拆到留存与转化两段，要求产品、运营与分析共同维护同一套口径。招聘要求中出现了更多「能独立完成取数与复盘」的描述。',
    aiRead: '行业重心从拉新规模转向存量经营，数据闭环成为协作基础。',
    careerImpact: '更看重 SQL、指标体系与业务复盘能力，单纯报表交付的岗位要求会变窄。',
    url: 'https://example.invalid/industry/internet-1',
    isExample: true,
  },
  {
    id: 'example-internet-2',
    industry: 'internet',
    industryLabel: '互联网',
    topic: '技术趋势',
    title: '示例：前端团队开始要求理解接口与性能预算',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 18 日',
    summary:
      '示例摘要：多个团队在岗位说明中补充了接口协作、性能预算与可观测性要求。页面交付不再是唯一目标，能定位线上问题成为共同期望。',
    aiRead: '前端岗位的边界向工程化与全链路排障延伸。',
    careerImpact: 'TypeScript、接口设计与性能分析会更常见；只会还原静态页面的竞争力下降。',
    url: 'https://example.invalid/industry/internet-2',
    isExample: true,
  },
  {
    id: 'example-finance-1',
    industry: 'finance',
    industryLabel: '金融',
    topic: '银行数字化',
    title: '示例：银行数字化项目增加，风控与数据分析同步扩招',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 19 日',
    summary:
      '示例摘要：示例项目把风控规则、客户分层与经营分析放在同一条数据链路上，要求候选人理解业务约束，而不只是工具操作。',
    aiRead: '金融数据岗位更强调合规、口径与可解释性。',
    careerImpact: 'SQL、统计分析与风控意识会成为常见组合；需要能说明指标背后的业务含义。',
    url: 'https://example.invalid/industry/finance-1',
    isExample: true,
  },
  {
    id: 'example-finance-2',
    industry: 'finance',
    industryLabel: '金融',
    topic: '金融科技',
    title: '示例：金融科技团队补充模型评估与人工复核流程',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 16 日',
    summary:
      '示例摘要：示例团队在模型上线前增加了评估记录与人工复核环节，强调结果可追溯。岗位描述中出现了更多跨团队沟通与文档要求。',
    aiRead: 'AI 应用进入受监管场景后，评估与审计流程成为交付的一部分。',
    careerImpact: '模型评估、文档表达与合规协作能力更受重视。',
    url: 'https://example.invalid/industry/finance-2',
    isExample: true,
  },
  {
    id: 'example-ai-1',
    industry: 'ai',
    industryLabel: '人工智能',
    topic: 'Agent',
    title: '示例：Agent 框架更新，工具调用与状态管理成为重点',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 21 日',
    summary:
      '示例摘要：示例框架把工具调用的失败重试、任务状态持久化与可观测性做成标配。团队开始要求候选人能解释任务在失败后如何恢复。',
    aiRead: '行业重心从参数竞赛转向 Agent 工程化与交付稳定性。',
    careerImpact: '更看重编排框架、状态管理与错误处理，直接对应路线中的 Agent 实践任务。',
    url: 'https://example.invalid/industry/ai-1',
    isExample: true,
  },
  {
    id: 'example-ai-2',
    industry: 'ai',
    industryLabel: '人工智能',
    topic: '应用商业化',
    title: '示例：AI 应用团队把评估集与用户反馈放在同一流程',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 17 日',
    summary:
      '示例摘要：示例团队在产品迭代中同时维护离线评估集与线上反馈，要求工程与产品共同定义「回答是否可用」。',
    aiRead: 'AI 应用从演示走向可运营产品，评估能力成为工程能力的一部分。',
    careerImpact: '需要理解评估指标、数据标注与产品反馈闭环。',
    url: 'https://example.invalid/industry/ai-2',
    isExample: true,
  },
  {
    id: 'example-energy-1',
    industry: 'energy',
    industryLabel: '新能源',
    topic: '产业政策',
    title: '示例：储能项目扩产，工程与数据分析复合背景受关注',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 15 日',
    summary:
      '示例摘要：示例项目在扩产计划中增加了运行数据分析与设备监测岗位，要求候选人能读懂工程数据并形成可执行结论。',
    aiRead: '新能源岗位从单一工程背景转向「工程 + 数据」复合能力。',
    careerImpact: '数据分析、可视化与工程基础会成为差异化组合。',
    url: 'https://example.invalid/industry/energy-1',
    isExample: true,
  },
  {
    id: 'example-energy-2',
    industry: 'energy',
    industryLabel: '新能源',
    topic: '技术突破',
    title: '示例：电池管理团队增加故障预测与数据质量岗位',
    source: '示例媒体',
    publishedAt: '示例时间 · 11 月 13 日',
    summary:
      '示例摘要：示例团队把故障预测与数据质量治理拆成独立职责，强调异常检测与跨部门协作。',
    aiRead: '设备数据规模上升后，数据质量与异常检测成为稳定交付的前提。',
    careerImpact: '统计、异常检测与领域知识结合更紧密；通用数据分析需要补充工程语境。',
    url: 'https://example.invalid/industry/energy-2',
    isExample: true,
  },
]