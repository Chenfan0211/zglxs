<script setup lang="ts">
import { h, onMounted, reactive, ref } from 'vue';
import { NTag, NButton } from 'naive-ui';
import type { DataTableColumns } from 'naive-ui';
import { addAccount, addAccountProduct, delAccount, delAccountProduct, editAccount, fetchAccountProducts, fetchAccounts } from '@/service/api';
import type { Account, AccountProduct } from '@/service/api';

const loading = ref(false);
const list = ref<Account[]>([]);
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
const formModel = reactive({ username: '', password: '', account_name: '', account_id: '', check_msg: '', memo: '', status: true });

// 商品管理弹窗
const showProductModal = ref(false);
const productList = ref<AccountProduct[]>([]);
const productLoading = ref(false);
const operatorAccountId = ref<number | null>(null);
const productForm = reactive({ product_id: '', out_product_id: '', product_name: '' });

const columns: DataTableColumns<Account> = [
  { title: 'ID', key: 'id', width: 70 },
  { title: '账号', key: 'username', minWidth: 120 },
  { title: '账号名称', key: 'account_name', minWidth: 140, render: row => row.account_name || '-' },
  { title: '来客账号ID', key: 'account_id', minWidth: 140, render: row => row.account_id || '-' },
  {
    title: '商品数',
    key: 'product_num',
    width: 90,
    align: 'center',
    render(row) {
      return h(NButton, { size: 'tiny', type: 'primary', secondary: true, onClick: () => showProducts(row) }, { default: () => String(row.product_num ?? 0) });
    }
  },
  { title: '状态', key: 'status_str', width: 90, render: row => (row.status ? h(NTag, { type: 'success', size: 'small' }, { default: () => row.status_str || '正常' }) : h(NTag, { type: 'default', size: 'small' }, { default: () => row.status_str || '禁用' })) },
  { title: '审核失败原因', key: 'check_msg', minWidth: 160, render: row => row.check_msg || '-' },
  { title: '备注', key: 'memo', minWidth: 160, render: row => row.memo || '-' },
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
    const { data, error } = await fetchAccounts({ page: pagination.page, page_size: pagination.pageSize, keyword: keyword.value });
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
  formModel.username = '';
  formModel.password = '';
  formModel.account_name = '';
  formModel.account_id = '';
  formModel.check_msg = '';
  formModel.memo = '';
  formModel.status = true;
  showModal.value = true;
}

function openEdit(row: Account) {
  editingId.value = row.id;
  formModel.username = row.username;
  formModel.password = '';
  formModel.account_name = row.account_name || '';
  formModel.account_id = row.account_id || '';
  formModel.check_msg = row.check_msg || '';
  formModel.memo = row.memo || '';
  formModel.status = row.status;
  showModal.value = true;
}

async function handleSubmit() {
  if (!formModel.username.trim()) {
    window.$message?.warning('账号不能为空');
    return;
  }
  if (editingId.value === null && !formModel.password) {
    window.$message?.warning('密码不能为空');
    return;
  }
  saving.value = true;
  try {
    const payload: Record<string, unknown> = {
      username: formModel.username,
      account_name: formModel.account_name,
      account_id: formModel.account_id,
      check_msg: formModel.check_msg,
      memo: formModel.memo,
      status: formModel.status
    };
    if (formModel.password) payload.password = formModel.password;
    if (editingId.value === null) {
      const { error } = await addAccount(payload);
      if (error) return;
      window.$message?.success('新增成功');
    } else {
      const { error } = await editAccount({ id: editingId.value, ...payload });
      if (error) return;
      window.$message?.success('编辑成功');
    }
    showModal.value = false;
    loadData();
  } finally {
    saving.value = false;
  }
}

async function handleDelete(row: Account) {
  window.$dialog?.warning({
    title: '确认删除',
    content: `确定删除账号「${row.username}」吗？`,
    positiveText: '确定',
    negativeText: '取消',
    onPositiveClick: async () => {
      const { error } = await delAccount(row.id);
      if (error) return;
      window.$message?.success('删除成功');
      loadData();
    }
  });
}

async function showProducts(row: Account) {
  operatorAccountId.value = row.id;
  showProductModal.value = true;
  await loadProducts();
}

async function loadProducts() {
  if (operatorAccountId.value === null) return;
  productLoading.value = true;
  try {
    const { data } = await fetchAccountProducts(operatorAccountId.value);
    productList.value = data?.list || [];
  } finally {
    productLoading.value = false;
  }
}

async function handleAddProduct() {
  if (operatorAccountId.value === null) return;
  if (!productForm.product_id.trim()) {
    window.$message?.warning('商品ID不能为空');
    return;
  }
  const { error } = await addAccountProduct({
    account_id: operatorAccountId.value,
    product_id: productForm.product_id,
    out_product_id: productForm.out_product_id,
    product_name: productForm.product_name
  });
  if (error) return;
  window.$message?.success('添加成功');
  productForm.product_id = '';
  productForm.out_product_id = '';
  productForm.product_name = '';
  await loadProducts();
  loadData();
}

async function handleDelProduct(row: AccountProduct) {
  const { error } = await delAccountProduct(row.id);
  if (error) return;
  window.$message?.success('删除成功');
  await loadProducts();
  loadData();
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
    <NCard :bordered="false" title="账号管理">
      <template #header-extra>
        <NSpace>
          <NInput v-model:value="keyword" placeholder="输入来客账号ID或账号名称" clearable class="w-220px" @keyup.enter="handleSearch" />
          <NButton type="primary" @click="handleSearch">筛选</NButton>
          <NButton type="primary" @click="openCreate">新增账号</NButton>
        </NSpace>
      </template>

      <NDataTable :loading="loading" :columns="columns" :data="list" :bordered="false" :pagination="pagination" remote :scroll-x="1200" />
    </NCard>

    <NModal v-model:show="showModal" preset="card" :title="editingId === null ? '新增账号' : '编辑账号'" class="w-560px">
      <NForm label-placement="left" label-width="110">
        <NFormItem label="账号">
          <NInput v-model:value="formModel.username" placeholder="请输入账号" :disabled="editingId !== null" />
        </NFormItem>
        <NFormItem :label="editingId === null ? '密码' : '新密码'">
          <NInput v-model:value="formModel.password" type="password" placeholder="留空则不修改" />
        </NFormItem>
        <NFormItem label="账号名称">
          <NInput v-model:value="formModel.account_name" placeholder="请输入账号名称" />
        </NFormItem>
        <NFormItem label="来客账号ID">
          <NInput v-model:value="formModel.account_id" placeholder="请输入来客账号ID" />
        </NFormItem>
        <NFormItem label="审核失败原因">
          <NInput v-model:value="formModel.check_msg" type="textarea" :rows="2" placeholder="审核失败原因" />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="formModel.memo" type="textarea" :rows="2" placeholder="请输入备注" />
        </NFormItem>
        <NFormItem label="状态">
          <NSwitch v-model:value="formModel.status">
            <template #checked>正常</template>
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

    <NModal v-model:show="showProductModal" preset="card" title="商品信息" class="w-720px">
      <NSpace vertical>
        <NSpace>
          <NInput v-model:value="productForm.product_id" placeholder="商品ID" class="w-160px" />
          <NInput v-model:value="productForm.out_product_id" placeholder="直连商品编码" class="w-160px" />
          <NInput v-model:value="productForm.product_name" placeholder="商品名称" class="w-160px" />
          <NButton type="primary" @click="handleAddProduct">添加商品</NButton>
        </NSpace>
        <NDataTable
          :loading="productLoading"
          :columns="[
            { title: 'ID', key: 'id', width: 70 },
            { title: '商品ID', key: 'product_id', minWidth: 140 },
            { title: '直连商品编码', key: 'out_product_id', minWidth: 140, render: r => r.out_product_id || '-' },
            { title: '商品名称', key: 'product_name', minWidth: 140, render: r => r.product_name || '-' },
            { title: '操作', key: 'actions', width: 100, render: r => h(NButton, { size: 'small', type: 'error', onClick: () => handleDelProduct(r) }, { default: () => '删除' }) }
          ]"
          :data="productList"
          :bordered="false"
        />
      </NSpace>
    </NModal>
  </div>
</template>

<style scoped></style>
