<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchUpversionNum } from '@/service/api';

const versionNum = ref(0);

async function loadData() {
  const { data } = await fetchUpversionNum();
  if (data) versionNum.value = data.num;
}

onMounted(() => {
  loadData();
});
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="程序升级">
      <NDescriptions :column="1" bordered>
        <NDescriptionsItem label="当前版本号">{{ versionNum }}</NDescriptionsItem>
        <NDescriptionsItem label="最新版本">-</NDescriptionsItem>
        <NDescriptionsItem label="更新说明">暂无更新</NDescriptionsItem>
      </NDescriptions>
      <NAlert type="info" class="mt-16px">
        程序升级功能用于查看系统版本信息，正式升级需通过发布流程（releases 目录 + publish 脚本）完成。
      </NAlert>
    </NCard>
  </div>
</template>

<style scoped></style>
