import { request } from '../request';

/**
 * 获取验证码
 * 对接后端 POST /apiv1/common/captcha
 */
export function fetchCaptcha() {
  return request<Api.Auth.Captcha>({
    url: '/apiv1/common/captcha',
    method: 'post'
  });
}

/**
 * 登录（带验证码）
 * 对接后端 POST /apiv1/user/login
 *
 * @param mobile 账号（手机号）
 * @param password 密码
 * @param captcha 验证码
 * @param captchaKey 验证码 key
 */
export function fetchLogin(mobile: string, password: string, captcha: string, captchaKey: string) {
  return request<Api.Auth.LoginToken>({
    url: '/apiv1/user/login',
    method: 'post',
    data: {
      mobile,
      password,
      captcha,
      captcha_key: captchaKey
    }
  });
}

/**
 * 登出
 * 对接后端 POST /apiv1/user/logout
 */
export function fetchLogout() {
  return request({
    url: '/apiv1/user/logout',
    method: 'post'
  });
}
