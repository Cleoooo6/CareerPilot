const REPLACEMENTS: Array<[RegExp, string]> = [
  [/【Mock 模式】/g, '【演示】'],
  [/【Mock 分析】/g, '【演示分析】'],
  [/【Mock 解析】/g, '【演示解析】'],
  [/【Mock LLM】/g, '【演示】'],
  [/当前未调用真实模型[^。；]*[。；]/g, '当前为体验环境。'],
  [/这是用于验证[^。；]*[。；]/g, ''],
  [/LangGraph|SSE|Tool Calling|Agent Trace|持久化链路/g, ''],
  [/简历解析（Mock）/g, '简历导入（演示）'],
  [/Mock 分析/g, '演示分析'],
  [/Mock 解析/g, '演示解析'],
  [/general_chat/g, '日常对话'],
  [/career_advice/g, '职业建议'],
  [/career_planning/g, '成长规划'],
  [/market_analysis/g, '市场分析'],
  [/resume/g, '简历'],
  [/unknown/g, '待澄清'],
  [/合成数据/g, '演示数据'],
  [/合成/g, '演示'],
  [/Mock/g, '演示'],
]

export function userFacingText(value: string): string {
  let text = value
  for (const [pattern, replacement] of REPLACEMENTS) {
    text = text.replace(pattern, replacement)
  }
  return text.replace(/\s{2,}/g, ' ').trim()
}