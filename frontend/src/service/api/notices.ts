import { request } from '../request';

/**
 * 系统公告接口
 * 对接后端 /api/notices
 */

export interface Notice {
  id: number;
  title: string;
  content: string;
  notice_type: string;
  is_published: boolean;
  created_at: string | null;
  updated_at: string | null;
}

export interface NoticePayload {
  title: string;
  content: string;
  notice_type?: string;
  is_published?: boolean;
}

/** 获取公告列表（默认已发布；all=true 获取全部） */
export function fetchNotices(all = false) {
  return request<{ list: Notice[] }>({
    url: '/api/notices',
    method: 'get',
    params: all ? { all: 'true' } : undefined
  });
}

/** 创建公告 */
export function createNotice(payload: NoticePayload) {
  return request<Notice>({
    url: '/api/notices',
    method: 'post',
    data: payload
  });
}

/** 更新公告 */
export function updateNotice(id: number, payload: Partial<NoticePayload>) {
  return request<Notice>({
    url: `/api/notices/${id}`,
    method: 'put',
    data: payload
  });
}

/** 删除公告 */
export function deleteNotice(id: number) {
  return request({
    url: `/api/notices/${id}`,
    method: 'delete'
  });
}
