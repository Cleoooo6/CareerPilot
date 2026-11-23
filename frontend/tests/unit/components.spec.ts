import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import ErrorNotice from '@/components/ErrorNotice.vue'
import MessageInput from '@/components/MessageInput.vue'
import MessageList from '@/components/MessageList.vue'
import StatusTimeline from '@/components/StatusTimeline.vue'

describe('stage-one components', () => {
  it('renders user and assistant messages', () => {
    const wrapper = mount(MessageList, {
      props: {
        messages: [
          {
            id: 'm1',
            role: 'user',
            content: '你好',
            createdAt: '2026-11-23T12:00:00Z',
          },
          {
            id: 'm2',
            role: 'assistant',
            content: '你好，我是 CareerPilot AI',
            createdAt: '2026-11-23T12:00:01Z',
          },
        ],
      },
    })
    expect(wrapper.text()).toContain('你好')
    expect(wrapper.text()).toContain('CareerPilot AI')
    expect(wrapper.findAll('.message')).toHaveLength(2)
  })

  it('emits send on Enter and blocks empty input', async () => {
    const wrapper = mount(MessageInput, { props: { streaming: false } })
    const textarea = wrapper.get('textarea')
    await textarea.setValue('hello')
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })
    expect(wrapper.emitted('send')?.[0]).toEqual(['hello'])
    expect((textarea.element as HTMLTextAreaElement).value).toBe('')
  })

  it('shows a stop button while streaming', async () => {
    const wrapper = mount(MessageInput, { props: { streaming: true } })
    const stop = wrapper.get('button.ghost')
    await stop.trigger('click')
    expect(wrapper.emitted('stop')).toHaveLength(1)
    expect(wrapper.get('button.primary').attributes('disabled')).toBeDefined()
  })

  it('renders timeline statuses', () => {
    const wrapper = mount(StatusTimeline, {
      props: {
        items: [
          { node: 'INTENT', status: 'completed', updatedAt: 'x' },
          { node: 'ECHO', status: 'running', updatedAt: 'x' },
        ],
      },
    })
    expect(wrapper.text()).toContain('INTENT')
    expect(wrapper.text()).toContain('执行中')
    expect(wrapper.findAll('.timeline-item')).toHaveLength(2)
  })

  it('renders and dismisses an error notice', async () => {
    const wrapper = mount(ErrorNotice, {
      props: { error: { code: 'WORKFLOW_FAILED', message: '执行失败' } },
    })
    expect(wrapper.text()).toContain('执行失败')
    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })
})