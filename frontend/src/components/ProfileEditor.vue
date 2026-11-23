<script setup lang="ts">
import {
  emptyProfileData,
  itemId,
  type EducationItem,
  type ExperienceItem,
  type ProfileData,
  type ProjectItem,
  type SkillItem,
} from '@/types/profile'

const model = defineModel<ProfileData>({ required: true })

function addSkill() {
  model.value.skills.push({
    id: itemId(),
    name: '',
    proficiency: '',
    evidence: '',
    category: '',
    source: '',
    verification: '',
    updated_at: '',
  })
}

function addEducation() {
  model.value.education.push({
    id: itemId(),
    school: '',
    degree: '',
    major: '',
    start_date: '',
    end_date: '',
    description: '',
  })
}

function addProject() {
  model.value.projects.push({
    id: itemId(),
    name: '',
    role: '',
    description: '',
    tech_stack: '',
    achievements: '',
    start_date: '',
    end_date: '',
  })
}

function addExperience() {
  model.value.experiences.push({
    id: itemId(),
    company: '',
    position: '',
    start_date: '',
    end_date: '',
    description: '',
  })
}

function removeAt<T>(items: T[], index: number) {
  items.splice(index, 1)
}

function setGraduationYear(event: Event) {
  const value = (event.target as HTMLInputElement).value
  model.value.basic.graduation_year = value ? Number(value) : null
}

function resetDemoShape() {
  model.value = emptyProfileData()
}
</script>

<template>
  <div class="profile-editor">
    <section class="editor-section">
      <div class="editor-section-head">
        <h3>基本信息</h3>
      </div>
      <div class="editor-grid">
        <label class="field">
          <span>姓名</span>
          <input v-model="model.basic.name" maxlength="100" placeholder="你的姓名" />
        </label>
        <label class="field">
          <span>学历</span>
          <input
            v-model="model.basic.education_level"
            maxlength="50"
            placeholder="本科 / 硕士 / 其他"
          />
        </label>
        <label class="field">
          <span>专业</span>
          <input v-model="model.basic.major" maxlength="100" placeholder="专业名称" />
        </label>
        <label class="field">
          <span>毕业时间</span>
          <input
            :value="model.basic.graduation_year ?? ''"
            inputmode="numeric"
            placeholder="2026"
            @input="setGraduationYear"
          />
        </label>
        <label class="field">
          <span>所在地</span>
          <input v-model="model.basic.location" maxlength="100" placeholder="城市" />
        </label>
      </div>
    </section>

    <section class="editor-section">
      <div class="editor-section-head">
        <h3>职业目标</h3>
      </div>
      <div class="editor-grid">
        <label class="field">
          <span>目标岗位</span>
          <input
            v-model="model.goals.target_role"
            maxlength="200"
            placeholder="例如：数据分析师"
          />
        </label>
        <label class="field">
          <span>目标行业</span>
          <input
            v-model="model.goals.target_industry"
            maxlength="200"
            placeholder="例如：互联网"
          />
        </label>
        <label class="field">
          <span>求职状态</span>
          <input
            v-model="model.goals.job_status"
            maxlength="50"
            placeholder="求职中 / 在职 / 观望"
          />
        </label>
        <label class="field wide">
          <span>期望方向</span>
          <textarea
            v-model="model.goals.desired_direction"
            maxlength="500"
            rows="2"
            placeholder="希望从事的方向、偏好或约束"
          ></textarea>
        </label>
      </div>
    </section>

    <section class="editor-section">
      <div class="editor-section-head">
        <h3>技能</h3>
        <button type="button" class="button ghost small" @click="addSkill">
          添加技能
        </button>
      </div>
      <p v-if="!model.skills.length" class="editor-empty">
        还没有技能记录。
      </p>
      <div v-for="(skill, index) in model.skills" :key="skill.id" class="editor-item">
        <div class="editor-row">
          <label class="field grow">
            <span>技能名称</span>
            <input v-model="skill.name" maxlength="100" placeholder="例如：Python" />
          </label>
          <label class="field">
            <span>熟练程度</span>
            <input v-model="skill.proficiency" maxlength="30" placeholder="熟练" />
          </label>
          <label class="field grow">
            <span>相关证据</span>
            <input v-model="skill.evidence" maxlength="500" placeholder="项目 / 课程 / 工作" />
          </label>
          <button
            type="button"
            class="button danger small"
            @click="removeAt<SkillItem>(model.skills, index)"
          >
            删除
          </button>
        </div>
        <div class="editor-row">
          <label class="field grow">
            <span>技能分类</span>
            <input
              v-model="skill.category"
              maxlength="50"
              placeholder="编程语言 / 数据工具 / 通用能力"
            />
          </label>
          <p class="editor-hint">
            熟练程度为自评；来源与确认状态由系统记录。
          </p>
        </div>
      </div>
    </section>

    <section class="editor-section">
      <div class="editor-section-head">
        <h3>教育经历</h3>
        <button type="button" class="button ghost small" @click="addEducation">
          添加教育
        </button>
      </div>
      <p v-if="!model.education.length" class="editor-empty">
        还没有教育经历。
      </p>
      <div v-for="(edu, index) in model.education" :key="edu.id" class="editor-item">
        <div class="editor-row">
          <label class="field grow">
            <span>学校</span>
            <input v-model="edu.school" maxlength="150" placeholder="学校名称" />
          </label>
          <label class="field">
            <span>学历</span>
            <input v-model="edu.degree" maxlength="50" placeholder="本科" />
          </label>
          <label class="field">
            <span>专业</span>
            <input v-model="edu.major" maxlength="100" placeholder="专业" />
          </label>
          <button
            type="button"
            class="button danger small"
            @click="removeAt<EducationItem>(model.education, index)"
          >
            删除
          </button>
        </div>
        <div class="editor-row">
          <label class="field">
            <span>开始</span>
            <input v-model="edu.start_date" maxlength="20" placeholder="2022-09" />
          </label>
          <label class="field">
            <span>结束</span>
            <input v-model="edu.end_date" maxlength="20" placeholder="2026-06" />
          </label>
          <label class="field grow">
            <span>补充说明</span>
            <input v-model="edu.description" maxlength="1000" placeholder="可选" />
          </label>
        </div>
      </div>
    </section>

    <section class="editor-section">
      <div class="editor-section-head">
        <h3>项目经历</h3>
        <button type="button" class="button ghost small" @click="addProject">
          添加项目
        </button>
      </div>
      <p v-if="!model.projects.length" class="editor-empty">
        还没有项目经历。
      </p>
      <div v-for="(project, index) in model.projects" :key="project.id" class="editor-item">
        <div class="editor-row">
          <label class="field grow">
            <span>项目名称</span>
            <input v-model="project.name" maxlength="150" placeholder="项目名称" />
          </label>
          <label class="field">
            <span>承担角色</span>
            <input v-model="project.role" maxlength="100" placeholder="负责人 / 开发者" />
          </label>
          <label class="field">
            <span>技术栈</span>
            <input v-model="project.tech_stack" maxlength="500" placeholder="Python, SQL" />
          </label>
          <button
            type="button"
            class="button danger small"
            @click="removeAt<ProjectItem>(model.projects, index)"
          >
            删除
          </button>
        </div>
        <label class="field">
          <span>项目描述</span>
          <textarea
            v-model="project.description"
            maxlength="2000"
            rows="2"
            placeholder="你做了什么、解决了什么问题"
          ></textarea>
        </label>
        <div class="editor-row">
          <label class="field grow">
            <span>成果</span>
            <input v-model="project.achievements" maxlength="1000" placeholder="量化成果" />
          </label>
          <label class="field">
            <span>开始</span>
            <input v-model="project.start_date" maxlength="20" placeholder="2025-03" />
          </label>
          <label class="field">
            <span>结束</span>
            <input v-model="project.end_date" maxlength="20" placeholder="2025-06" />
          </label>
        </div>
      </div>
    </section>

    <section class="editor-section">
      <div class="editor-section-head">
        <h3>工作与实习</h3>
        <button type="button" class="button ghost small" @click="addExperience">
          添加经历
        </button>
      </div>
      <p v-if="!model.experiences.length" class="editor-empty">
        还没有工作或实习经历。
      </p>
      <div
        v-for="(experience, index) in model.experiences"
        :key="experience.id"
        class="editor-item"
      >
        <div class="editor-row">
          <label class="field grow">
            <span>公司</span>
            <input v-model="experience.company" maxlength="150" placeholder="公司名称" />
          </label>
          <label class="field">
            <span>岗位</span>
            <input v-model="experience.position" maxlength="100" placeholder="岗位名称" />
          </label>
          <button
            type="button"
            class="button danger small"
            @click="removeAt<ExperienceItem>(model.experiences, index)"
          >
            删除
          </button>
        </div>
        <div class="editor-row">
          <label class="field">
            <span>开始</span>
            <input v-model="experience.start_date" maxlength="20" placeholder="2025-07" />
          </label>
          <label class="field">
            <span>结束</span>
            <input v-model="experience.end_date" maxlength="20" placeholder="2025-09" />
          </label>
          <label class="field grow">
            <span>工作内容</span>
            <input
              v-model="experience.description"
              maxlength="2000"
              placeholder="主要职责和成果"
            />
          </label>
        </div>
      </div>
    </section>

    <button type="button" class="editor-reset" @click="resetDemoShape">
      清空当前编辑内容
    </button>
  </div>
</template>