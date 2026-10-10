<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag } from 'naive-ui';
import { NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { createNotice, deleteNotice, fetchNotices, updateNotice } from '@/service/api';
import type { Notice } from '@/service/api';

const loading = ref(false);
const list = ref<Notice[]>([]);

const showModal = ref(false);
const editingId = ref<number | null>(null);
const formModel = reactive({
  title: '',
  content: '',
  is_published: true
});
const saving = ref(false);

const columns: DataTableColumns<Notice> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '标题', key: 'title', minWidth: 200 },
  { title: '内容', key: 'content', minWidth: 280, ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'is_published',
    width: 90,
    render(row) {
      return row.is_published
        ? h(NTag, { type: 'success', size: 'small' }, { default: () => '已发布' })
        : h(NTag, { type: 'default', size: 'small' }, { default: () => '未发布' });
    }
  },
  {
    title: '更新时间',
    key: 'updated_at',
    width: 180,
    render(row) {
      return row.updated_at ? row.updated_at.replace('T', ' ').slice(0, 19) : '-';
    }
  },
  {
    title: '操作',
    key: 'actions',
    width: 200,
    render(row) {
      return h('div', { class: 'flex gap-8px' }, [
        h(
          NButton,
          { size: 'small', type: 'primary', onClick: () => openEdit(row) },
          { default: () => '编辑' }
        ),
        h(
          NButton,
          { size: 'small', type: row.is_published ? 'warning' : 'success', onClick: () => togglePublish(row) },
          { default: () => (row.is_published ? '下架' : '发布') }
        ),
        h(
          NButton,
          { size: 'small', type: 'error', onClick: () => handleDelete(row) },
          { default: () => '删除' }
        )
      ]);
    }
  }
];

async function loadNotices() {
  loading.value = true;
  try {
    const { data, error } = await fetchNotices(true);
    if (!error && data) {
      list.value = data.list || [];
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  formModel.title = '';
  formModel.content = '';
  formModel.is_published = true;
  showModal.value = true;
}

function openEdit(row: Notice) {
  editingId.value = row.id;
  formModel.title = row.title;
  formModel.content = row.content;
  formModel.is_published = row.is_published;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.title.trim() || !formModel.content.trim()) {
    window.$message?.warning('标题和内容不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      title: formModel.title,
      content: formModel.content,
      is_published: formModel.is_published
    };
    if (editingId.value === null) {
      const { error } = await createNotice(payload);
      if (error) return;
      window.$message?.success('创建成功');
    } else {
      const { error } = await updateNotice(editingId.value, payload);
      if (error) return;
      window.$message?.success('更新成功');
    }
    showModal.value = false;
    loadNotices();
  } finally {
    saving.value = false;
  }
}

async function togglePublish(row: Notice) {
  const { error } = await updateNotice(row.id, { is_published: !row.is_published });
  if (error) return;
  window.$message?.success(row.is_published ? '已下架' : '已发布');
  loadNotices();
}

async function handleDelete(row: Notice) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除公告「${row.title}」吗？`,
    positiveText: '删除',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await deleteNotice(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadNotices();
    }
  });
}

onMounted(() => {
  loadNotices();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="公告管理">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">新增公告</NButton>
      </template>

      <NDataTable
        :loading="loading"
        :columns="columns"
        :data="list"
        :bordered="false"
        :scroll-x="1200"
      />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增公告' : '编辑公告'" class="w-600px">
      <NForm label-placement="left" label-width="80">
        <NFormItem label="标题">
          <NInput v-model:value="formModel.title" placeholder="请输入公告标题" />
        </NFormItem>
        <NFormItem label="内容">
          <NInput
            v-model:value="formModel.content"
            type="textarea"
            :rows="5"
            placeholder="请输入公告内容"
          />
        </NFormItem>
        <NFormItem label="发布状态">
          <NSwitch v-model:value="formModel.is_published">
            <template #checked>发布</template>
            <template #unchecked>草稿</template>
          </NSwitch>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-12px">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="handleSubmit">保存</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped></style>

