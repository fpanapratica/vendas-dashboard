# -*- coding: utf-8 -*-
"""Prepara dados do dashboard: vendas Kiwify 2026 (produtos selecionados) + Meta Ads."""
import csv, json, os
from datetime import datetime
from zoneinfo import ZoneInfo
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + os.sep
OUT = os.path.join(BASE, "index.html")

PRODUTOS = [
 "Oferta Formação Claude",
 "Oferta de lançamento Programa de Formação Claude para Finanças",
 "Acesso vitalício Formação em Claude para Finanças",
 "Acesso vitalício Claude para BPO",
 "Acesso vitalício Claude para FP&A",
 "Acesso vitalício Claude Fiscal e Tributário",
 "Acesso vitalício Claude para Financeiro",
 "Acesso vitalício Claude para Contabilidade",
 "Acesso vitalício Claude para Auditoria",
 "Acesso vitalício Claude para Valuation",
 "Formação em Claude para Finanças",
 "Claude para Valuation",
 "Claude para BPO",
 "Claude para Auditoria",
 "Claude para Fiscal e Tributário",
 "Claude para Contabilidade",
 "Claude para FP&A",
 "Claude para Financeiro",
 "Oferta Combo Claude 2.0",
 "Acesso Vitalício Excel com IA",
 "Excel com IA",
 "Skills do Claude",
 "Combo Contabilidade + Auditoria na Pratica",
 "Combo Vitalício IA para finanças + Power BI + Excel com IA",
 "Acesso vitalício Claude para finanças",
 "Claude para Finanças",
 "Contabilidade Na Prática",
 "Pricing na Prática",
 "Oferta Lançamento IA para finanças 3.0",
 "Oferta Lançamento IA para finanças 3.0 (alunos)",
 "Agente IA CFO",
 "Acesso Vitalício Auditoria Na Prática",
 "Mentoria Individual",
 "Auditoria Na Prática",
 "🥝 Acesso Vitalício Power Bi",
 "🥝Acesso Vitalício Business English",
 "🥝Consultoria em Power Bi",
 "🥝Pack de Dashboards Power Bi",
 "🥝Curso de Business English",
 "🥝Power Bi para Finanças 2.0",
 "Apresentando Projetos de IA ao Board",
 "Acesso Vitalício Curso de IA para Finanças",
 "Checklist de Implantação de IA no setor financeiro da sua empresa",
 "Inteligência Artificial aplicada a Finanças",
 "Consultoria Online - 5 Horas",
 "Consultoria Online - 4 Horas",
 "Consultoria Online - 3 Horas",
 "Consultoria Online - 2 Horas",
 "Consultoria Individual - 1 Hora",
 "Curso de SQL",
 "Pack de Apresentações em Inglês",
 "Acesso Vitalício Business English",
 "Business English",
 "Consultoria em Power Bi",
 "Acesso Vitalício Power Bi",
 "Pack Dashboards Power Bi",
 "Power Bi para Finanças Na Prática",
]
PSET = set(PRODUTOS)
ST = {"paid": 0, "refunded": 1, "chargedback": 2}

rows = list(csv.DictReader(open(BASE+"kiwify_sales_raw.csv", encoding="utf-8-sig")))
sales = []
skipped_prod = {}
for r in rows:
    try:
        dt = datetime.strptime(r["Data de Criação"], "%d/%m/%Y %H:%M:%S")
    except Exception:
        continue
    if dt.year != 2026:
        continue
    st = r["Status"]
    if st not in ST:
        continue
    p = r["Produto"].strip()
    if p not in PSET:
        skipped_prod[p] = skipped_prod.get(p, 0) + 1
        continue
    try:
        v = float(r["Valor líquido"] or 0)
    except Exception:
        v = 0.0
    sales.append([
        r["ID da venda"],
        dt.strftime("%Y-%m-%dT%H:%M"),
        PRODUTOS.index(p),
        r["Cliente"].strip(),
        r["Email"].strip().lower(),
        round(v, 2),
        ST[st],
        r["Pagamento"] or "",
    ])
sales.sort(key=lambda x: x[1])

meta = json.load(open(BASE+"meta_ads_2026.json", encoding="utf-8"))
camps = sorted({(m["campaign_id"], m["campaign"]) for m in meta})
cidx = {c[0]: i for i, c in enumerate(camps)}
spend = [[m["date"][:10], cidx[m["campaign_id"]], round(float(m["spend"] or 0), 2),
          int(m.get("clicks") or 0), int(m.get("impressions") or 0)] for m in meta]
spend.sort(key=lambda x: x[0])

data = {
    "geradoEm": datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M"),
    "produtos": PRODUTOS,
    "vendas": sales,
    "campanhas": [c[1] for c in camps],
    "campanhaIds": [c[0] for c in camps],
    "gastos": spend,
}
json.dump(data, open(BASE+"dash_data.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

# CSV histórico p/ Google Sheets
with open(BASE+"historico_para_planilha.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["order_id", "status", "data", "produto", "cliente", "email", "valor_liquido", "pagamento"])
    inv = {0: "paid", 1: "refunded", 2: "chargedback"}
    for s in sales:
        w.writerow([s[0], inv[s[6]], s[1].replace("T", " "), PRODUTOS[s[2]], s[3], s[4], s[5], s[7]])

# Verificação
paid = [s for s in sales if s[6] == 0]
rec = sum(s[5] for s in paid)
buyers = len({s[4] for s in paid})
gasto = sum(s[2] for s in spend)
print("vendas selecionadas (paid/refund/cbk):", len(sales))
print("pagas:", len(paid), "| receita líquida: R$ %.2f" % rec)
print("compradores únicos:", buyers)
print("ticket médio geral: R$ %.2f" % (rec / len(paid)))
print("ticket médio por comprador: R$ %.2f" % (rec / buyers))
print("reembolsos+cbk:", len(sales) - len(paid), "| R$ %.2f" % sum(s[5] for s in sales if s[6] != 0))
print("gasto meta: R$ %.2f | campanhas:", gasto, len(camps))
print("produtos ignorados (top10):", sorted(skipped_prod.items(), key=lambda x: -x[1])[:10])
import os
print("dash_data.json bytes:", os.path.getsize(BASE+"dash_data.json"))

assert rec > 900000, "receita implausível (%.2f), abortando publicação" % rec
assert gasto > 100000, "gasto meta implausível (%.2f), abortando publicação" % gasto

# injeta no template e publica na raiz do repo (index.html)
tpl = open(BASE+"template.html", encoding="utf-8").read()
data = open(BASE+"dash_data.json", encoding="utf-8").read()
html = tpl.replace("const EMBED = null;", "const EMBED = " + data + ";")
open(OUT, "w", encoding="utf-8").write(html)
print("publicado:", OUT, os.path.getsize(OUT))
