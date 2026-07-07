# -*- coding: utf-8 -*-
"""Busca vendas 2026 via API oficial da Kiwify e grava kiwify_sales_raw.csv
no mesmo formato do export CSV do painel (colunas usadas pelo build.py)."""
import os, sys
_missing = [k for k in ['KIWIFY_CLIENT_ID', 'KIWIFY_CLIENT_SECRET', 'KIWIFY_ACCOUNT_ID'] if not os.environ.get(k)]
if _missing:
    print('ERRO: secrets não cadastrados no repositório:', ', '.join(_missing))
    sys.exit(1)

import csv, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE_URL = "https://public-api.kiwify.com/v1"
CLIENT_ID = os.environ["KIWIFY_CLIENT_ID"]
CLIENT_SECRET = os.environ["KIWIFY_CLIENT_SECRET"]
ACCOUNT_ID = os.environ["KIWIFY_ACCOUNT_ID"]
SP = ZoneInfo("America/Sao_Paulo")

PAY_LABEL = {"credit_card": "Cartão de crédito", "pix": "Pix", "boleto": "Boleto"}


def request(url, data=None, headers=None, retries=3):
    for i in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers=headers or {})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode()[:500]
            except Exception:
                pass
            print(f"HTTP {e.code} em {url.split('?')[0]}: {body}")
            if i == retries - 1:
                raise
            time.sleep(3 * (i + 1))
        except Exception as e:
            if i == retries - 1:
                raise
            print(f"retry {i+1} apos erro: {type(e).__name__}: {e}")
            time.sleep(3 * (i + 1))


# --- OAuth ---
tok = request(
    BASE_URL + "/oauth/token",
    data=urllib.parse.urlencode({"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET}).encode(),
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
access_token = tok.get("access_token")
if not access_token:
    print("ERRO fetch_kiwify: sem access_token. chaves da resposta:", list(tok.keys()))
    sys.exit(1)
HDR = {"Authorization": "Bearer " + access_token, "x-kiwify-account-id": ACCOUNT_ID}


def first(d, *paths):
    """Retorna o primeiro valor presente. path: 'a.b' navega dicts."""
    for p in paths:
        cur = d
        ok = True
        for part in p.split("."):
            if isinstance(cur, dict) and part in cur and cur[part] is not None:
                cur = cur[part]
            else:
                ok = False
                break
        if ok:
            return cur
    return None


def to_local_str(iso):
    s = str(iso).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(SP).strftime("%d/%m/%Y %H:%M:%S")


# --- Paginação de vendas (janelas de <=90 dias) ---
from datetime import timedelta
sales, page_size = [], 100
statuses_seen = {}
sample_keys_printed = False
win_start = datetime(2026, 1, 1, tzinfo=timezone.utc)
now_utc = datetime.now(timezone.utc)
total_pages = 0
while win_start < now_utc:
    win_end = min(win_start + timedelta(days=85), now_utc)
    page = 1
    while True:
        q = urllib.parse.urlencode({
            "start_date": win_start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "end_date": win_end.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "page_size": page_size,
            "page_number": page,
        })
        payload = request(f"{BASE_URL}/sales?{q}", headers=HDR)
        data = payload.get("data") or payload.get("sales") or []
        if not isinstance(data, list):
            print("ERRO fetch_kiwify: formato inesperado. chaves:", list(payload.keys()))
            sys.exit(1)
        if data and not sample_keys_printed:
            print("chaves de uma venda:", sorted(data[0].keys()))
            sample_keys_printed = True
        for s in data:
            st = str(first(s, "status") or "")
            statuses_seen[st] = statuses_seen.get(st, 0) + 1
            created = first(s, "created_at", "create_date", "reference_date")
            net = first(s, "net_amount", "commissions.my_commission", "commissioned_stores.0.value")
            pay = str(first(s, "payment_method", "payment.method") or "")
            sales.append({
                "ID da venda": str(first(s, "id", "order_id", "reference") or ""),
                "Status": st,
                "Data de Criação": to_local_str(created) or "",
                "Produto": str(first(s, "product.name", "product_name") or "").strip(),
                "Cliente": str(first(s, "customer.name", "customer.full_name", "customer_name") or "").strip(),
                "Email": str(first(s, "customer.email", "customer_email") or "").strip(),
                "net_cents": net,
                "Pagamento": PAY_LABEL.get(pay, pay),
            })
        total_pages += 1
        pag = payload.get("pagination") or {}
        total = pag.get("count") or pag.get("total") or pag.get("total_count")
        if len(data) < page_size or (total and page * page_size >= int(total)):
            break
        page += 1
        if page > 500:
            print("ERRO fetch_kiwify: mais de 500 páginas na janela, abortando")
            sys.exit(1)
    win_start = win_end
page = total_pages

print(f"fetch_kiwify: {len(sales)} vendas | páginas: {page} | status: {statuses_seen}")

paid = [s for s in sales if s["Status"] == "paid"]
if len(paid) < 5000:
    print("ERRO fetch_kiwify: menos vendas pagas que o esperado, abortando")
    sys.exit(1)

# net_amount vem em centavos na API; o CSV do painel usa reais.
# Heurística validada por sanidade: receita paga esperada ~ R$ 0,9–2M em 2026.
def to_reais(v):
    if v is None:
        return 0.0
    v = float(v)
    return round(v / 100.0, 2)

total_cents = sum(to_reais(s["net_cents"]) for s in paid)
total_plain = sum(float(s["net_cents"] or 0) for s in paid)
if 700000 <= total_cents <= 3000000:
    conv = to_reais
    print(f"net_amount interpretado como CENTAVOS. receita paga: R$ {total_cents:.2f}")
elif 700000 <= total_plain <= 3000000:
    conv = lambda v: round(float(v or 0), 2)
    print(f"net_amount interpretado como REAIS. receita paga: R$ {total_plain:.2f}")
else:
    print(f"ERRO fetch_kiwify: receita fora da faixa plausível (centavos: {total_cents:.2f} / reais: {total_plain:.2f})")
    sys.exit(1)

base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(base, "kiwify_sales_raw.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["ID da venda", "Status", "Data de Criação", "Produto",
                                      "Cliente", "Email", "Valor líquido", "Pagamento"])
    w.writeheader()
    for s in sales:
        net = conv(s.pop("net_cents"))
        s["Valor líquido"] = f"{net:.2f}"
        w.writerow(s)
print("kiwify_sales_raw.csv gravado")
