import { request } from '../request';

/**
 * 系统模块接口
 * 对接后端 /apiv1/common/* 与 /apiv1/user/usertablecolumns/*（见 app/api/system.py）
 */

export function fetchSystemConfig() {
  return request<{ name: string; logo: string | null; web_name: string; config: Record<string, string | null> }>({
    url: '/apiv1/common/getconfiginfo',
    method: 'post',
    data: {}
  });
}
export function updateSystemConfig(data: Record<string, unknown>) {
  return request<{ updated: string[] }>({ url: '/apiv1/common/updateconfiginfo', method: 'post', data });
}
export function fetchUpversionNum() {
  return request<{ num: number }>({ url: '/apiv1/common/getupversionnum', method: 'post', data: {} });
}
export function fetchTableColumns(table_key: string, user_key = 'default') {
  return request<{ content: string }>({
    url: '/apiv1/user/usertablecolumns/detail',
    method: 'post',
    data: { table_key, user_key }
  });
}
export function saveTableColumns(table_key: string, content: string, user_key = 'default') {
  return request({ url: '/apiv1/user/usertablecolumns/edit', method: 'post', data: { table_key, user_key, content } });
}
