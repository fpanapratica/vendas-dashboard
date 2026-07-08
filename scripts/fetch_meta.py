# -*- coding: utf-8 -*-
"""Busca gastos Meta Ads 2026 via API do Windsor.ai e grava meta_ads_2026.json (dados intradia do Meta chegam com atraso de 1-3h)."""
import json, os, sys, urllib.parse, urllib.request
import os, sys
_missing = [k for k in ['WINDSOR_API_KEY'] if not os.environ.get(k)]
if _missing:
    print('ERRO: secrets não cadastrados no repositório:', ', '.join(_missing))
    sys.exit(1)

from datetime import datetime
from zoneinfo import ZoneInfo

API_KEY = os.environ["WINDSOR_API_KEY"]
ACCOUNT = "1252232061903512"
TERMS = ["claude", "pricing", "excel com ia", "curso de contabilidade",
         "curso de auditoria", "curso de ia", "ia para finanças", "power bi"]

today = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d")
params = urllib.parse.urlencode({
    "api_key": API_KEY,
    "date_from": "2026-01-01",
    "date_to": today,
    "fields": "date,campaign,campaign_id,spend,clicks,impressions",
    "select_accounts": ACCOUNT,
})
url = "https://connectors.windsor.ai/facebook?" + params
with urllib.request.urlopen(url, timeout=120) as resp:
    payload = json.load(resp)

rows = payload.get("data", payload if isinstance(payload, list) else [])
if not rows:
    print("ERRO fetch_meta: resposta sem dados. chaves:", list(payload.keys()) if isinstance(payload, dict) else type(payload))
    sys.exit(1)

out = []
for r in rows:
    name = (r.get("campaign") or "").lower()
    if "investimento" in name:
        continue
    if any(t in name for t in TERMS):
        out.append({k: r.get(k) for k in ("date", "campaign", "campaign_id", "spend", "clicks", "impressions")})

gasto = sum(float(r["spend"] or 0) for r in out)
camps = {r["campaign"] for r in out}
print(f"fetch_meta: {len(out)} registros | {len(camps)} campanhas | gasto R$ {gasto:.2f}")
if gasto < 100000:
    print("ERRO fetch_meta: gasto implausivelmente baixo, abortando")
    sys.exit(1)

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json.dump(out, open(os.path.join(base, "meta_ads_2026.json"), "w", encoding="utf-8"), ensure_ascii=False)
