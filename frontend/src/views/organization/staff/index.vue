<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addStaff, delStaff, editStaff, fetchStaff } from '@/service/api';
import type { Staff } from '@/service/api';

const loading = ref(false);
const list = ref<Staff[]>([]);
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
const formModel = reactive({ name: '', nickname: '', mobile: '', department_id: null as number | null, service_cate_id: '', password: '', role: 'staff' });

const roleOptions = [
  { label: '超级管理员', value: 'super' },
  { label: '直播部门负责人', value: 'live_leader' },
  { label: '转化部门负责人', value: 'custom_leader' },
  { label: '直播员工', value: 'live_staff' },
  { label: '转化客服', value: 'custom_staff' },
  { label: '中控员工', value: 'console_staff' },
  { label: '售后部门负责人', value: 'maintenance_leader' },
  { label: '售后员工', value: 'maintenance_staff' },
  { label: '普通员工', value: 'staff' }
];

const columns: DataTableColumns<Staff> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '姓名', key: 'name', minWidth: 100 },
  { title: '昵称', key: 'nickname', minWidth: 100, render: row => row.nickname || '-' },
  { title: '账号', key: 'mobile', minWidth: 130, render: row => row.mobile || '-' },
  { title: '部门', key: 'department_name', minWidth: 130, render: row => row.department_name || '-' },
  { title: '角色', key: 'role_str', width: 130, render: row => row.role_str || row.role },
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
    const { data, error } = await fetchStaff({ page: pagination.page, page_size: pagination.pageSize, keyword: keyword.value });
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
  formModel.nickname = '';
  formModel.mobile = '';
  formModel.department_id = null;
  formModel.service_cate_id = '';
  formModel.password = '';
  formModel.role = 'staff';
  showModal.value = true;
}

function openEdit(row: Staff) {
  editingId.value = row.id;
  formModel.name = row.name;
  formModel.nickname = row.nickname || '';
  formModel.mobile = row.mobile || '';
  formModel.department_id = row.department_id;
  formModel.service_cate_id = row.service_cate_id || '';
  formModel.password = '';
  formModel.role = row.role;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.name.trim()) {
    window.$message?.warning('员工姓名不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload: Record<string, unknown> = {
      name: formModel.name,
      nickname: formModel.nickname,
      mobile: formModel.mobile,
      department_id: formModel.department_id,
      service_cate_id: formModel.service_cate_id,
      role: formModel.role
    };
    if (formModel.password) payload.password = formModel.password;
    if (editingId.value === null) {
      const { error } = await addStaff(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editStaff({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: Staff) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除员工「${row.name}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delStaff(row.id);
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
    <NCard :bordered="false" title="员工管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="输入关键字" clearable class="w-180px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">筛选</NButton>
          <NButton type="primary" @click="openCreate">新增员工</NButton>
        </NSpace>
      </template>

      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增员工' : '编辑员工'" class="w-520px">
      <NForm label-placement="left" label-width="90">
        <NFormItem label="姓名">
          <NInput v-model:value="formModel.name" placeholder="请输入姓名" />
        </NFormItem>
        <NFormItem label="昵称">
          <NInput v-model:value="formModel.nickname" placeholder="请输入昵称" />
        </NFormItem>
        <NFormItem label="账号">
          <NInput v-model:value="formModel.mobile" placeholder="请输入账号/手机号" />
        </NFormItem>
        <NFormItem label="密码">
          <NInput v-model:value="formModel.password" type="password" placeholder="请输入密码" />
        </NFormItem>
        <NFormItem label="部门">
          <NInputNumber v-model:value="formModel.department_id" placeholder="部门ID" clearable />
        </NFormItem>
        <NFormItem label="客服分类">
          <NInput v-model:value="formModel.service_cate_id" placeholder="客服所属分类(多个以逗号分隔)" />
        </NFormItem>
        <NFormItem label="角色">
          <NSelect v-model:value="formModel.role" :options="roleOptions" />
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
