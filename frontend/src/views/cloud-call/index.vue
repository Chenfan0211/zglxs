<script setup lang="ts">
import { ref } from 'vue';

const activeTab = ref('config');
</script>

<template>
  <div class="p-16px">
    <NCard :bordered="false" title="云呼叫">
      <NTabs v-model:value="activeTab" type="line">
        <NTabPane name="config" tab="云呼叫配置">
          <NAlert type="warning" class="mb-16px">
            云呼叫依赖第三方云电话服务商（如阿里云、腾讯云），当前未配置。配置后即可使用电话拨打功能。
          </NAlert>
          <NEmpty description="暂无云呼叫配置" />
        </NTabPane>
        <NTabPane name="seat" tab="坐席管理">
          <NEmpty description="暂无坐席数据" />
        </NTabPane>
        <NTabPane name="calllog" tab="通话记录">
          <NEmpty description="暂无通话记录" />
        </NTabPane>
      </NTabs>
    </NCard>
  </div>
</template>

<style scoped></style>
