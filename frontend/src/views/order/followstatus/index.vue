<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addFollowStatus, delFollowStatus, editFollowStatus, fetchFollowStatuses } from '@/service/api';
import type { FollowStatus } from '@/service/api';

const loading = ref(false);
const list = ref<FollowStatus[]>([]);

const pagination = reactive({
  page: 1,
  pageSize: 20,
  itemCount: 0,
  showSizePicker: true,
  pageSizes: [10, 20, 50, 100],
  onChange: (page: number) => {
    pagination.page = page;
    loadData();
  },
  onUpdatePageSize: (pageSize: number) => {
    pagination.pageSize = pageSize;
    pagination.page = 1;
    loadData();
  }
});

const showModal = ref(false);
const editingId = ref<number | null>(null);
const saving = ref(false);
const formModel = reactive({ name: '', sort_order: 0, status: true });

const columns: DataTableColumns<FollowStatus> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '状态名称', key: 'name', minWidth: 180 },
  { title: '排序', key: 'sort_order', width: 100, align: 'center' },
  { title: '状态', key: 'status', width: 100, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => '启用' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '禁用' })) },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    render(row) {
      return h('div', { class: 'flex gap-8px' }, [
        h(NButton, { size: 'small', type: 'primary', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', onClick: () => toggleStatus(row) }, { default: () => (row.status ? '禁用' : '启用') }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' })
      ]);
    }
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchFollowStatuses({ page: pagination.page, page_size: pagination.pageSize });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  formModel.name = '';
  formModel.sort_order = 0;
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: FollowStatus) {
  editingId.value = row.id;
  formModel.name = row.name;
  formModel.sort_order = row.sort_order;
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.name.trim()) {
    window.$message?.warning('状态名称不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = { name: formModel.name, sort_order: formModel.sort_order, status: formModel.status };
    if (editingId.value === null) {
      const { error } = await addFollowStatus(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editFollowStatus({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function toggleStatus(row: FollowStatus) {
  const { error } = await editFollowStatus({ id: row.id, status: !row.status });
  if (error) return;
  window.$message?.success(row.status ? '已禁用' : '已启用');
  loadData();
}

async function handleDelete(row: FollowStatus) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除状态「${row.name}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delFollowStatus(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadData();
    }
  });
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="跟单状态管理">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">新增状态</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增状态' : '编辑状态'" class="w-440px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="状态名称">
          <NInput v-model:value="formModel.name" placeholder="请输入状态名称" />
        </NFormItem>
        <NFormItem label="排序">
          <NInputNumber v-model:value="formModel.sort_order" placeholder="排序号" />
        </NFormItem>
        <NFormItem label="状态">
          <NSwitch v-model:value="formModel.status">
            <template #checked>启用</template>
            <template #unchecked>禁用</template>
          </NSwitch>
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-12px">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="handleSubmit">确定</NButton>
        </div>
      </template>
    </NModal>
  </div>
</template>

<style scoped></style>
