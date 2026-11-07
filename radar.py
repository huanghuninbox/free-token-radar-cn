# -*- coding: utf-8 -*-
"""免费算力雷达（Free Compute Radar）
每日抓取免费 LLM 算力信息源 → 与上日快照 diff → 日报落 REPORT_DIR。
源列表在 SOURCES，可追加；本机平台巡检见 local_models.py。
配置全部走环境变量 / .env（见 .env.example），零硬编码密钥。
"""
import os, json, difflib, urllib.request, datetime, glob

BASE = os.path.dirname(os.path.abspath(__file__))

def load_dotenv():
    """读同目录 .env（KEY=VALUE），不覆盖已有环境变量。"""
    p = os.path.join(BASE, '.env')
    if os.path.exists(p):
        for line in open(p, encoding='utf-8', errors='replace'):
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))

load_dotenv()

REPORTS = os.path.abspath(os.environ.get('REPORT_DIR', os.path.join(BASE, 'reports')))
SNAP = os.path.abspath(os.environ.get('SNAPSHOT_DIR', os.path.join(BASE, 'snapshots')))
PROXY = os.environ.get('PROXY', '').strip() or None  # 如 http://127.0.0.1:10809；空=直连

SOURCES = [
    {'id': 'awesome-free-llm-apis', 'desc': 'mnfst 永久免费层清单(每日更新)',
     'url': 'https://raw.githubusercontent.com/mnfst/awesome-free-llm-apis/main/README.md'},
    {'id': 'awesome-freellm-apis-mr', 'desc': 'open-free-llm-api 机器可读目录(134+含限流/上下文)',
     'url': 'https://raw.githubusercontent.com/open-free-llm-api/awesome-freellm-apis/main/README.md'},
]
# 扩展点：后续可加厂商公告页/状态页（fetch 逻辑按 html 纯文本处理即可）
# 选源铁律（v1.0.1 实测教训）：①信息源必须核实上游主仓，fork 不作源（曾误用 4 月停更的 fork 致 diff 全程失效）；
# ②新源入列前必须 curl 实测 200（网传权威仓 cheahjs/free-llm-api-resources 实测全 404，挂起待核实）。

def fetch(url):
    proxies = [PROXY, None] if PROXY else [None]  # 先代理后直连；未配代理只直连
    last = None
    for proxy in proxies:
        try:
            handlers = [urllib.request.ProxyHandler({'http': proxy, 'https': proxy})] if proxy else [urllib.request.ProxyHandler({})]
            opener = urllib.request.build_opener(*handlers)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 freecompute-radar/1.0'})
            with opener.open(req, timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            last = e
    raise RuntimeError(f'fetch fail {url}: {last}')

def latest_snapshot(src_id):
    files = sorted(glob.glob(os.path.join(SNAP, src_id, '*.md')))
    return files[-1] if len(files) >= 2 else None  # 需要至少两份才有 diff（跳过今天自己）

def main():
    today = datetime.date.today().isoformat()
    os.makedirs(REPORTS, exist_ok=True)
    report = [f'# 免费算力雷达日报 {today}\n', f'> 生成：radar.py（Free Compute Radar）\n']
    any_change = False
    for src in SOURCES:
        sid = src['id']
        content = fetch(src['url'])
        d = os.path.join(SNAP, sid)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, today + '.md'), 'w', encoding='utf-8') as f:
            f.write(content)
        prev = latest_snapshot(sid)
        report.append(f'\n## {sid}（{src["desc"]}）\n')
        report.append(f'- 今日快照：{len(content)} 字符，已存 snapshots/{sid}/{today}.md\n')
        if prev:
            old = open(prev, encoding='utf-8').read()
            diff = list(difflib.unified_diff(old.splitlines(), content.splitlines(), lineterm='', n=1))
            changed = [l for l in diff if (l.startswith('+') or l.startswith('-')) and not l.startswith(('+++', '---'))]
            if changed:
                any_change = True
                report.append(f'- ⚠️ **有变化**：{len(changed)} 行增删（对照 {os.path.basename(prev)}）\n')
                adds = [l[1:].strip() for l in changed if l.startswith('+')][:20]
                dels = [l[1:].strip() for l in changed if l.startswith('-')][:20]
                if adds: report.append('- 新增要点：\n' + '\n'.join('  - ' + a[:160] for a in adds if a) + '\n')
                if dels: report.append('- 移除要点：\n' + '\n'.join('  - ' + x[:160] for x in dels if x) + '\n')
            else:
                report.append('- 无变化（与上一份快照一致）\n')
        else:
            report.append('- 首次快照（无对照基线，明日开始出 diff）\n')
    report.append('\n## 日报使用方式\n')
    report.append('- 变化行即「各家免费政策动态」：发现新免费源/砍档 → 评估是否注册或下线。\n')
    # 本机已接入平台实时巡检（可选：无 key/无 CLI 时对应平台降级为「巡检失败」并写明原因）
    try:
        import local_models
        report.append('## 今日免费模型全景表（本机已接入平台实时巡检）' + chr(10))
        for plat, models in local_models.all_platforms():
            report.append('### ' + plat + chr(10))
            for m in models:
                report.append('- ' + m + chr(10))
    except Exception as e:
        report.append('## 本机平台巡检失败：' + str(e) + chr(10))

    out = os.path.join(REPORTS, f'{today}_免费算力雷达.md')
    open(out, 'w', encoding='utf-8').write(''.join(report))
    print('REPORT:', out, '| changes:', any_change)

if __name__ == '__main__':
    main()
