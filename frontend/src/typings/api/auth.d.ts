declare namespace Api {
  /**
   * namespace Auth
   *
   * backend api module: "auth" (对接后端 demo 登录，见 app/api/demo_auth.py)
   */
  namespace Auth {
    /** 登录返回的 token 信息 */
    interface LoginToken {
      token: string;
      /** 后端 auth_info 为用户信息 JSON 字符串 */
      auth_info?: string;
    }

    /** 验证码 */
    interface Captcha {
      content: string;
      key: string;
    }

    /** 用户信息 */
    interface UserInfo {
      userId: string;
      userName: string;
      mobile?: string;
      nickname?: string;
      roles: string[];
      buttons: string[];
    }
  }
}
