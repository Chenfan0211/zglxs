<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addDepartment, delDepartment, editDepartment, fetchDepartments, fetchStaff } from '@/service/api';
import type { Department, Staff } from '@/service/api';

const loading = ref(false);
const list = ref<Department[]>([]);
const typeList = ref<{ key: string; value: string }[]>([]);
const keyword = ref('');
const typeFilter = ref<string>('');

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
const formModel = reactive({ department_name: '', type: 'live', ordid: 255 });

// 员工列表弹窗
const showStaffModal = ref(false);
const staffList = ref<Staff[]>([]);
const staffLoading = ref(false);
const staffDeptName = ref('');

const columns: DataTableColumns<Department> = [
  { title: 'ID', key: 'id', width: 80 },
  { title: '部门名称', key: 'department_name', minWidth: 160 },
  { title: '类型', key: 'type_str', width: 120, render: row => { type TagType = 'default' | 'primary' | 'info' | 'success' | 'warning' | 'error';
      const map = { live: { label: '直播部门', type: 'success' }, custom: { label: '转化部门', type: 'info' }, maintenance: { label: '售后部门', type: 'warning' } } as Record<string, { label: string; type: TagType }>; const item = map[row.type || row.dept_type]; return item ? h(NTag, { type: item.type, size: 'small' }, { default: () => item.label }) : (row.type_str || '-'); } },
  { title: '排序', key: 'ordid', width: 90, align: 'center' },
  {
    title: '员工数',
    key: 'user_num',
    width: 100,
    align: 'center',
    render(row) {
      return h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => showStaff(row) }, { default: () => String(row.user_num ?? 0) });
    }
  },
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
    const { data, error } = await fetchDepartments({
      page: pagination.page,
      page_size: pagination.pageSize,
      department_name: keyword.value,
      type: typeFilter.value
    });
    if (!error && data) {
      list.value = data.list || [];
      pagination.itemCount = data.total || 0;
      typeList.value = data.department_type_list || [];
    }
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  formModel.department_name = '';
  formModel.type = 'live';
  formModel.ordid = 255;
  showModal.value = true;
}

function openEdit(row: Department) {
  editingId.value = row.id;
  formModel.department_name = row.department_name || row.name;
  formModel.type = row.type || row.dept_type;
  formModel.ordid = row.ordid;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.department_name.trim()) {
    window.$message?.warning('部门名称不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload = { department_name: formModel.department_name, type: formModel.type, ordid: formModel.ordid };
    if (editingId.value === null) {
      const { error } = await addDepartment(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editDepartment({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: Department) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定要删除该部门吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delDepartment(row.id);
      if (error) return;
      window.$message?.success('删除部门成功');
      loadData();
    }
  });
}

async function showStaff(row: Department) {
  staffDeptName.value = row.department_name || row.name;
  showStaffModal.value = true;
  staffLoading.value = true;
  try {
    const { data } = await fetchStaff({ department_id: row.id, page_size: 999 });
    staffList.value = data?.list || [];
  } finally {
    staffLoading.value = false;
  }
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
    <NCard :bordered="false" title="部门管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="输入关键字" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NSelect v-model:value="typeFilter" placeholder="选择类型" clearable class="w-140px" :options="[{ label: '全部', value: '' }, ...typeList.map(t => ({ label: t.value, value: t.key }))]" />
          <NButton type="primary" @click="handleSearch">筛选</NButton>
          <NButton @click="keyword = ''; typeFilter = ''; handleSearch()">重置</NButton>
          <NButton type="primary" @click="openCreate">新增部门</NButton>
        </NSpace>
      </template>

      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增部门' : '编辑部门'" class="w-500px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="部门名称">
          <NInput v-model:value="formModel.department_name" placeholder="请输入部门名称" />
        </NFormItem>
        <NFormItem label="类型">
          <NSelect v-model:value="formModel.type" :options="typeList.map(t => ({ label: t.value, value: t.key }))" />
        </NFormItem>
        <NFormItem label="排序号">
          <NInputNumber v-model:value="formModel.ordid" placeholder="请输入排序号" />
        </NFormItem>
      </NForm>
      <template #footer>
        <div class="flex justify-end gap-12px">
          <NButton @click="showModal = false">取消</NButton>
          <NButton type="primary" :loading="saving" @click="handleSubmit">确定</NButton>
        </div>
      </template>
    </NModal>

    <NModal v-model:show="showStaffModal" preset="card" :title="`【${staffDeptName}】员工列表`" class="w-640px">
      <NDataTable
        :loading="staffLoading"
        :columns="[
          { title: '姓名', key: 'nickname', minWidth: 120 },
          { title: '账户名', key: 'mobile', minWidth: 140 }
        ]"
        :data="staffList"
        :bordered="false"
      />
    </NModal>
  </div>
</template>

<style scoped></style>
