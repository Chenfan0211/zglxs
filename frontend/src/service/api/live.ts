import { request } from '../request';

/**
 * 直播模块接口
 * 对接后端 /apiv1/*（见 app/api/live.py）
 */

export interface LiveRoom {
  id: number;
  name: string;
  live_name?: string;
  live_uid: string | null;
  live_uuid: string | null;
  department_id: number | null;
  department_name?: string;
  room_id: string | null;
  memo: string | null;
  ordid: number;
  status: boolean;
  created_at?: string | null;
}

export interface LiveRoomMember {
  id: number;
  live_room_id: number;
  staff_id: number;
  anchor_uid: string | null;
  is_control: boolean;
  role: string;
  status: boolean;
  nickname?: string;
  created_at?: string | null;
}

export interface LiveRoomConsole {
  id: number;
  live_room_id: number;
  staff_id: number;
  console_uid: string | null;
  status: boolean;
  nickname?: string;
  created_at?: string | null;
}

export interface WorkLog {
  id: number;
  live_room_id: number | null;
  staff_id: number | null;
  work_type: string;
  remark: string | null;
  created_at?: string | null;
}

interface ListResult<T> {
  total: number;
  list: T[];
}

// ---------- 直播间 ----------
export function fetchLiveRooms(params: Record<string, unknown> = {}) {
  return request<ListResult<LiveRoom>>({ url: '/apiv1/user/liverooms/index', method: 'post', data: params });
}
export function addLiveRoom(data: Record<string, unknown>) {
  return request<LiveRoom>({ url: '/apiv1/user/liverooms/add', method: 'post', data });
}
export function editLiveRoom(data: Record<string, unknown>) {
  return request<LiveRoom>({ url: '/apiv1/user/liverooms/edit', method: 'post', data });
}
export function delLiveRoom(id: number) {
  return request({ url: '/apiv1/user/liverooms/del', method: 'post', data: { id } });
}

// ---------- 主播（成员） ----------
export function fetchLiveRoomMembers(params: Record<string, unknown> = {}) {
  return request<ListResult<LiveRoomMember>>({ url: '/apiv1/user/liveroommembers/index', method: 'post', data: params });
}
export function addLiveRoomMember(data: Record<string, unknown>) {
  return request<LiveRoomMember>({ url: '/apiv1/user/liveroommembers/add', method: 'post', data });
}
export function editLiveRoomMember(data: Record<string, unknown>) {
  return request<LiveRoomMember>({ url: '/apiv1/user/liveroommembers/edit', method: 'post', data });
}
export function delLiveRoomMember(id: number) {
  return request({ url: '/apiv1/user/liveroommembers/del', method: 'post', data: { id } });
}

// ---------- 中控 ----------
export function fetchLiveRoomConsoles(params: Record<string, unknown> = {}) {
  return request<ListResult<LiveRoomConsole>>({ url: '/apiv1/user/liveroomconsoles/index', method: 'post', data: params });
}
export function addLiveRoomConsole(data: Record<string, unknown>) {
  return request<LiveRoomConsole>({ url: '/apiv1/user/liveroomconsoles/add', method: 'post', data });
}
export function delLiveRoomConsole(id: number) {
  return request({ url: '/apiv1/user/liveroomconsoles/del', method: 'post', data: { id } });
}

// ---------- 工作日志 ----------
export function fetchWorkLogs(params: Record<string, unknown> = {}) {
  return request<ListResult<WorkLog>>({ url: '/apiv1/console/worklog', method: 'post', data: params });
}
export function addWorkLog(data: Record<string, unknown>) {
  return request<WorkLog>({ url: '/apiv1/console/startwork', method: 'post', data });
}
