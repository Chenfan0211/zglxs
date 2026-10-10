<script setup lang="ts">
import { watch } from 'vue';
import { useAppStore } from '@/store/modules/app';
import { useEcharts } from '@/hooks/common/echarts';
import type { HomeSummary } from '@/service/api';

defineOptions({
  name: 'LineChart'
});

const props = defineProps<{
  summary: HomeSummary | null;
}>();

const appStore = useAppStore();

const { domRef, updateOptions } = useEcharts(() => ({
  tooltip: {
    trigger: 'axis',
    axisPointer: {
      type: 'cross',
      label: {
        backgroundColor: '#6a7985'
      }
    }
  },
  legend: {
    data: ['订单数', '成交额(元)'],
    top: '0'
  },
  grid: {
    left: '3%',
    right: '4%',
    bottom: '3%',
    top: '15%'
  },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: [] as string[]
  },
  yAxis: {
    type: 'value'
  },
  series: [
    {
      color: '#8e9dff',
      name: '订单数',
      type: 'line',
      smooth: true,
      stack: 'Total',
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0.25, color: '#8e9dff' },
            { offset: 1, color: '#fff' }
          ]
        }
      },
      emphasis: { focus: 'series' },
      data: [] as number[]
    },
    {
      color: '#26deca',
      name: '成交额(元)',
      type: 'line',
      smooth: true,
      stack: 'Total',
      areaStyle: {
        color: {
          type: 'linear',
          x: 0,
          y: 0,
          x2: 0,
          y2: 1,
          colorStops: [
            { offset: 0.25, color: '#26deca' },
            { offset: 1, color: '#fff' }
          ]
        }
      },
      emphasis: { focus: 'series' },
      data: []
    }
  ]
}));

function applyTrend() {
  const trend = props.summary?.trend;
  if (!trend) {
    return;
  }

  updateOptions(opts => {
    opts.xAxis.data = trend.dates;
    opts.series[0].data = trend.orders;
    opts.series[1].data = trend.amounts.map(amount => Number((amount / 100).toFixed(2)));

    return opts;
  });
}

function updateLocale() {
  updateOptions((opts, factory) => {
    const originOpts = factory();
    opts.legend.data = originOpts.legend.data;
    opts.series[0].name = originOpts.series[0].name;
    opts.series[1].name = originOpts.series[1].name;
    return opts;
  });
}

watch(
  () => props.summary,
  () => {
    applyTrend();
  }
);

watch(
  () => appStore.locale,
  () => {
    updateLocale();
  }
);

// init
applyTrend();
</script>

<template>
  <NCard :bordered="false" class="card-wrapper">
    <div ref="domRef" class="h-360px overflow-hidden"></div>
  </NCard>
</template>

<style scoped></style>
