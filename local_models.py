# -*- coding: utf-8 -*-
"""本机已接入平台的动态免费模型巡检（radar 附属模块）
输出：今日免费模型全景表（模型/平台/限额/接入状态）——清单说有不算数，
能拉到自己账号的模型列表才算数。巡检失败如实上报，不静默跳过。
加新平台：仿照写一个 xxx_models()，注册进 PLATFORMS。
密钥来源（优先级）：环境变量 > SECRETS_FILE（KEY=VALUE 格式）。零硬编码密钥。
"""
import os, json, urllib.request, subprocess

SECRETS = os.environ.get('SECRETS_FILE', os.path.expanduser('~/.free-compute-radar/secrets.env'))

def load_secrets():
    out = {}
    if os.path.exists(SECRETS):
        for line in open(SECRETS, encoding='utf-8', errors='replace'):
            if '=' in line and not line.strip().startswith('#'):
                k, v = line.strip().split('=', 1)
                out[k] = v.strip().strip('"')
    return out

def secret(key):
    return os.environ.get(key) or load_secrets().get(key, '')

def cf_models():
    token, account = secret('CF_API_TOKEN'), secret('CF_ACCOUNT_ID')
    if not (token and account):
        raise RuntimeError('未配置 CF_API_TOKEN/CF_ACCOUNT_ID，跳过')
    url = f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/models/search?per_page=200"
    req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    names = sorted(m.get('name', '') for m in d.get('result', []) if m.get('task', {}).get('name', '').startswith('Text Generation'))
    return ('Cloudflare Workers AI（免费 10K neurons/天）', names)

def sf_models():
    key = secret('SILICONFLOW_KEY')
    if not key:
        raise RuntimeError('未配置 SILICONFLOW_KEY，跳过')
    req = urllib.request.Request('https://api.siliconflow.cn/v1/models', headers={'Authorization': 'Bearer ' + key})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
    names = sorted(m['id'] for m in d.get('data', []))
    # 实测：SiliconFlow 标「免费」的模型也要求账户正余额（30001），此处仅拉清单供对照
    return ('SiliconFlow（⚠️ 实测免费档也需正余额，仅供对照）', [n for n in names if '/V2' not in n][:40])

def codebuddy_models():
    # 依赖本机安装的 CodeBuddy CLI；无 CLI 时抛异常由外层降级
    out = subprocess.run(['codebuddy', '--help'], capture_output=True, encoding='utf-8', errors='replace', timeout=60).stdout
    line = next((l for l in out.splitlines() if 'Currently supported' in l), '')
    models = []
    if '(' in line:
        inner = line.split('(', 1)[1].rsplit(')', 1)[0]
        models = [m.strip() for m in inner.split(',')]
    return ('CodeBuddy（积分池，免费档=hy4free）', models)

PLATFORMS = (cf_models, codebuddy_models, sf_models)

def all_platforms():
    result = []
    for fn in PLATFORMS:
        try:
            result.append(fn())
        except Exception as e:
            result.append((fn.__name__ + '（巡检失败）', [str(e)[:100]]))
    return result

if __name__ == '__main__':
    for plat, models in all_platforms():
        print(f'== {plat} ==')
        for m in models:
            print('  -', m)
