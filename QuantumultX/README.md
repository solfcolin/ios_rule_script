<!-- 参考：https://github.com/w37fhy/QuantumultX/blob/master/task.conf -->

## 模块

圈X 无「模块」概念，拆成两个入口，两份都要导入才能完整生效（共用 CDN 上的广告素材靠 .conf 的路径重写拦截，只导入 .list 会漏）：

- [番茄小说广告屏蔽（分流/规则）](https://raw.githubusercontent.com/solfcolin/ios_rule_script/refs/heads/master/QuantumultX/FanQieNovel.list) — 导入到「分流」→「引用规则」，对应小火箭模块的 `[Rule]`。
- [番茄小说广告屏蔽（重写/MITM）](https://raw.githubusercontent.com/solfcolin/ios_rule_script/refs/heads/master/QuantumultX/FanQieNovel.conf) — 导入到「重写」→「远程」，对应 `[URL Rewrite]` + `[MITM]`。

---

# 签到脚本 cookie 获取说明

# 中国移动
#打开 APP , 进入签到页面, 系统提示: `获取刷新链接: 成功`,然后手动签到 1 次

# 美团
#打开 APP , 然后手动签到 1 次, (`首页` > `红包签到`)

# 京东
#浏览器登录 https://bean.m.jd.com 点击签到并且出现签到日历

# 爱奇艺
#打开App,访问下右下角 `我的`
