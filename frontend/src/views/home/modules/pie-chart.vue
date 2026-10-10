<script setup lang="ts">
import { watch } from 'vue';
import { useAppStore } from '@/store/modules/app';
import { useEcharts } from '@/hooks/common/echarts';
import type { HomeSummary } from '@/service/api';

defineOptions({
  name: 'PieChart'
});

const props = defineProps<{
  summary: HomeSummary | null;
}>();

const appStore = useAppStore();

const { domRef, updateOptions } = useEcharts(() => ({
  tooltip: {
    trigger: 'item'
  },
  legend: {
    bottom: '1%',
    left: 'center',
    itemStyle: {
      borderWidth: 0
    }
  },
  series: [
    {
      color: ['#5da8ff', '#8e9dff', '#fedc69', '#26deca', '#ec4786', '#f68057'],
      name: '订单状态分布',
      type: 'pie',
      radius: ['45%', '75%'],
      avoidLabelOverlap: false,
      itemStyle: {
        borderRadius: 10,
        borderColor: '#fff',
        borderWidth: 1
      },
      label: {
        show: false,
        position: 'center'
      },
      emphasis: {
        label: {
          show: true,
          fontSize: '12'
        }
      },
      labelLine: {
        show: false
      },
      data: [] as { name: string; value: number }[]
    }
  ]
}));

function applyDistribution() {
  const distribution = props.summary?.distribution;
  if (!distribution || distribution.length === 0) {
    return;
  }

  updateOptions(opts => {
    opts.series[0].data = distribution;
    return opts;
  });
}

function updateLocale() {
  updateOptions((opts, factory) => {
    const originOpts = factory();
    opts.series[0].name = originOpts.series[0].name;
    return opts;
  });
}

watch(
  () => props.summary,
  () => {
    applyDistribution();
  }
);

watch(
  () => appStore.locale,
  () => {
    updateLocale();
  }
);

// init
applyDistribution();
</script>

<template>
  <NCard :bordered="false" class="card-wrapper">
    <div ref="domRef" class="h-360px overflow-hidden"></div>
  </NCard>
</template>

<style scoped></style>
