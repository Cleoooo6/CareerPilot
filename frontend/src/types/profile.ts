export interface BasicInfo {
  name: string
  education_level: string
  major: string
  graduation_year: number | null
  location: string
}

export interface CareerGoals {
  target_role: string
  target_industry: string
  job_status: string
  desired_direction: string
}

export interface SkillItem {
  id: string
  name: string
  proficiency: string
  evidence: string
  category: string
  source: string
  verification: string
  updated_at: string
}

export interface EducationItem {
  id: string
  school: string
  degree: string
  major: string
  start_date: string
  end_date: string
  description: string
}

export interface ProjectItem {
  id: string
  name: string
  role: string
  description: string
  tech_stack: string
  achievements: string
  start_date: string
  end_date: string
}

export interface ExperienceItem {
  id: string
  company: string
  position: string
  start_date: string
  end_date: string
  description: string
}

export interface ProfileData {
  basic: BasicInfo
  goals: CareerGoals
  skills: SkillItem[]
  education: EducationItem[]
  projects: ProjectItem[]
  experiences: ExperienceItem[]
}

export interface ProfileOut {
  id: string
  user_id: string
  data: ProfileData
  created_at: string
  updated_at: string
}

export interface ProfileStateOut {
  profile: ProfileOut | null
}

export interface ResumeParseOut {
  id: string
  user_id: string
  original_filename: string
  file_size: number
  mime_type: string
  status: string
  parse_mode: string
  provider: string
  model: string
  parsed_data: ProfileData
  text_length: number
  error_type: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface ResumeParseListOut {
  items: ResumeParseOut[]
}

export interface AnalysisClaim {
  statement: string
  basis: 'fact' | 'inference' | 'suggestion'
  confidence: 'high' | 'medium' | 'low'
}

export interface ProfileFit {
  summary: string
  evidence: string[]
  uncertainty: string[]
}

export interface ProfileAnalysisResult {
  overview: string
  strengths: AnalysisClaim[]
  gaps: AnalysisClaim[]
  fit: ProfileFit
  directions: AnalysisClaim[]
  missing_information: string[]
  next_actions: string[]
}

export interface ProfileAnalysisOut {
  id: string
  user_id: string
  profile_id: string
  provider: string
  model: string
  llm_mode: string
  analysis: ProfileAnalysisResult
  created_at: string
}

export interface ProfileAnalysisListOut {
  items: ProfileAnalysisOut[]
}

export interface ProfileRevisionOut {
  id: string
  user_id: string
  profile_id: string
  version: number
  change_source: string
  created_at: string
}

export interface ProfileRevisionListOut {
  items: ProfileRevisionOut[]
}

export const PROFILE_SECTIONS = [
  ['basic', '基本信息'],
  ['goals', '职业目标'],
  ['skills', '技能'],
  ['education', '教育经历'],
  ['projects', '项目经历'],
  ['experiences', '工作/实习'],
] as const

export type ProfileSection = (typeof PROFILE_SECTIONS)[number][0]

export const INTENT_LABELS: Record<string, string> = {
  general_chat: '闲聊',
  career_advice: '职业建议',
  resume: '简历 / 能力',
  career_planning: '成长规划',
  market_analysis: '市场分析',
  unknown: '待澄清',
}

export const BASIS_LABELS: Record<AnalysisClaim['basis'], string> = {
  fact: '事实',
  inference: '推断',
  suggestion: '建议',
}

export const CONFIDENCE_LABELS: Record<AnalysisClaim['confidence'], string> = {
  high: '高置信',
  medium: '中置信',
  low: '低置信',
}

export const SKILL_SOURCE_LABELS: Record<string, string> = {
  manual: '手动录入',
  resume: '简历导入',
  ai: 'AI 推断',
}

export const SKILL_VERIFICATION_LABELS: Record<string, string> = {
  confirmed: '资料已确认',
  unverified: '待确认',
  pending: '待确认',
}

export const CHANGE_SOURCE_LABELS: Record<string, string> = {
  manual: '手动保存',
  resume: '简历确认导入',
}

export function itemId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `item-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function emptyProfileData(): ProfileData {
  return {
    basic: {
      name: '',
      education_level: '',
      major: '',
      graduation_year: null,
      location: '',
    },
    goals: {
      target_role: '',
      target_industry: '',
      job_status: '',
      desired_direction: '',
    },
    skills: [],
    education: [],
    projects: [],
    experiences: [],
  }
}