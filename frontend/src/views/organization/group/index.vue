<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addGroup, delGroup, editGroup, fetchGroups } from '@/service/api';
import type { Group } from '@/service/api';

const loading = ref(false);
const list = ref<Group[]>([]);
const keyword = ref('');

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
const formModel = reactive({ name: '', allocation_type: '', department_id: null as number | null, web_hook: '', memo: '', ordid: 0, status: true });

const allocationOptions = [
  { label: '轮询分配', value: 'polling' },
  { label: '权重分配', value: 'weight' }
];

const columns: DataTableColumns<Group> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '组名', key: 'name', minWidth: 140 },
  { title: '分配规则', key: 'allocation_type', width: 110, render: row => allocationOptions.find(o => o.value === row.allocation_type)?.label || row.allocation_type || '-' },
  { title: '部门', key: 'department_name', width: 120, render: row => row.department_name || '-' },
  { title: '群报单机器人WebHook地址', key: 'web_hook', minWidth: 220, render: row => row.web_hook || '-' },
  { title: '备注', key: 'memo', minWidth: 160, render: row => row.memo || '-' },
  { title: '排序号', key: 'ordid', width: 90, align: 'center' },
  { title: '是否生效', key: 'status', width: 90, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => '是' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => '否' })) },
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
    const { data, error } = await fetchGroups({ page: pagination.page, page_size: pagination.pageSize, keyword: keyword.value });
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
  formModel.allocation_type = 'polling';
  formModel.department_id = null;
  formModel.web_hook = '';
  formModel.memo = '';
  formModel.ordid = 0;
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: Group) {
  editingId.value = row.id;
  formModel.name = row.name;
  formModel.allocation_type = row.allocation_type || 'polling';
  formModel.department_id = row.department_id;
  formModel.web_hook = row.web_hook || '';
  formModel.memo = row.memo || '';
  formModel.ordid = row.ordid;
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.name.trim()) {
    window.$message?.warning('组名称不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = {
      name: formModel.name,
      allocation_type: formModel.allocation_type,
      department_id: formModel.department_id,
      web_hook: formModel.web_hook,
      memo: formModel.memo,
      ordid: formModel.ordid,
      status: formModel.status
    };
    if (editingId.value === null) {
      const { error } = await addGroup(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editGroup({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: Group) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除客服组「${row.name}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delGroup(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadData();
    }
  });
}

function handleSearch() {
  pagination.page = 1;
  loadData();
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="客服组管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="输入关键字" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">筛选</NButton>
          <NButton type="primary" @click="openCreate">新增客服组</NButton>
        </NSpace>
      </template>

      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1200" />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增客服组' : '编辑客服组'" class="w-620px">
      <NForm label-placement="left" label-width="180">
        <NFormItem label="客服组名：">
          <NInput v-model:value="formModel.name" placeholder="请输入客服组名" />
        </NFormItem>
        <NFormItem label="分配规则：">
          <NSelect v-model:value="formModel.allocation_type" :options="allocationOptions" />
        </NFormItem>
        <NFormItem label="部门：">
          <NInputNumber v-model:value="formModel.department_id" placeholder="部门ID" clearable />
        </NFormItem>
        <NFormItem label="报单机器人WebHook地址：">
          <NInput v-model:value="formModel.web_hook" placeholder="请输入群报单机器人WebHook地址" />
        </NFormItem>
        <NFormItem label="备注：">
          <NInput v-model:value="formModel.memo" type="textarea" :rows="2" placeholder="请输入备注" />
        </NFormItem>
        <NFormItem label="排序：">
          <NInputNumber v-model:value="formModel.ordid" placeholder="请输入排序号" />
        </NFormItem>
        <NFormItem label="是否生效">
          <NSwitch v-model:value="formModel.status">
            <template #checked>是</template>
            <template #unchecked>否</template>
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
