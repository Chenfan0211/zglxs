<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addCate, delCate, editCate, fetchCates } from '@/service/api';
import type { Cate } from '@/service/api';

const loading = ref(false);
const list = ref<Cate[]>([]);
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
const formModel = reactive({ name: '', status: true });

const columns: DataTableColumns<Cate> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '分类名称', key: 'name', minWidth: 200 },
  { title: '状态', key: 'status', width: 100, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => '启用' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '禁用' })) },
  {
    title: '操作',
    key: 'actions',
    width: 160,
    render(row) {
      return h('div', { class: 'flex gap-8px' }, [
        h(NButton, { size: 'small', type: 'primary', onClick: () => openEdit(row) }, { default: () => '编辑' }),
        h(NButton, { size: 'small', type: 'error', onClick: () => handleDelete(row) }, { default: () => '删除' })
      ]);
    }
  }
];

async function loadData() {
  loading.value = true;
  try {
    const { data, error } = await fetchCates({ page: pagination.page, page_size: pagination.pageSize });
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
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: Cate) {
  editingId.value = row.id;
  formModel.name = row.name;
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.name.trim()) {
    window.$message?.warning('分类名称不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = { name: formModel.name, status: formModel.status };
    if (editingId.value === null) {
      const { error } = await addCate(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editCate({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: Cate) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除分类「${row.name}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delCate(row.id);
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
    <NCard :bordered="false" title="客服分类">
      <template #header-extra>
        <NButton type="primary" @click="openCreate">新增分类</NButton>
      </template>
      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增分类' : '编辑分类'" class="w-420px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="分类名称">
          <NInput v-model:value="formModel.name" placeholder="请输入分类名称" />
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
