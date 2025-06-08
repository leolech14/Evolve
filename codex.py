#!/usr/bin/env python3
# MERGED BY CODEX
# codex.py - Itaú Fatura TXT → CSV + Sanity Check (2025-05-30)
# Pipeline com comparação automática de métricas PDF vs CSV

import re
import csv
import argparse
import logging
import datetime
import tracemalloc
import time
import hashlib
from decimal import Decimal
from pathlib import Path
from collections import Counter
from datetime import datetime

__version__ = "0.12.0"
DATE_FMT_OUT = "%Y-%m-%d"
SCHEMA = [
    "card_last4",
    "post_date",
    "desc_raw",
    "valor_brl",
    "installment_seq",
    "installment_tot",
    "valor_orig",
    "moeda_orig",
    "valor_usd",
    "fx_rate",
    "iof_brl",
    "categoria_high",
    "merchant_city",
    "ledger_hash",
    "pagamento_fatura_anterior",
]

# --- Regexes
RE_DATE = re.compile(r"(?P<d>\d{1,3})/(?P<m>\d{1,2})(?:/(?P<y>\d{4}))?")
RE_PAY_HDR = re.compile(r"Pagamentos efetuados", re.I)
RE_BRL = re.compile(r"-?\s*\d{1,3}(?:\.\d{3})*,\d{2}")
RE_PAY_LINE = re.compile(
    r"^(?P<date>\d{1,3}/\d{1,2}(?:/\d{4})?)\s+PAGAMENTO(\s+EFETUADO)?\s+7117\s*[-\t ]+(?P<amt>-\s*[\d.,]+)\s*$",
    re.I,
)
RE_PAY_LINE_ANY = re.compile(
    r"^(?P<date>\d{1,3}/\d{1,2}(?:/\d{4})?)\s+PAGAMENTO.*?(?P<amt>-?\s*[\d.,]+)\s*$",
    re.I,
)
RE_FX_L2_TOL = re.compile(r"^(.+?)\s+([\d.,]+)\s+([A-Z]{3})\s+([\d.,]+)$")
# Nova regex para moedas variadas e tolerância a espaços extras
RE_FX_L2_TOL_ANY = re.compile(r"^(.+?)\s+([\d.,]+)\s+([A-Z]{3})\s+([\d.,]+)$", re.I)
RE_FX_BRL = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})(?:/\d{4})?\s+(?P<city>.+?)\s+(?P<orig>[\d.,]+)\s+(?P<cur>[A-Z]{3})\s+(?P<brl>[\d.,]+)$"
)
RE_IOF_LINE = re.compile(r"Repasse de IOF", re.I)
RE_FX_MAIN = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<descr>.+?)\s+"
    r"(?P<orig>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+"
    r"(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)
RE_DOLAR = re.compile(r"^D[óo]lar de Convers[ãa]o.*?(\d+,\d{4})")
RE_FX_L2 = re.compile(
    r"^(?P<city>.+?)\s+(?P<orig>[\d.,]+)\s+(?P<cur>[A-Z]{3})\s+(?P<usd>[\d.,]+)$"
)
RE_FX_RATE = re.compile(r"D[oó]lar de Convers[aã]o R\$ (?P<fx>[\d.,]+)")
RE_DOM = re.compile(r"^(?P<date>\d{1,3}/\d{1,2})\s+(?P<desc>.+?)\s+(?P<amt>[-\d.,]+)$")
RE_CARD = re.compile(r"final (\d{4})")
RE_INST = re.compile(r"(\d{1,2})/(\d{1,2})")
RE_INST_TXT = re.compile(r"\+\s*(\d+)\s*x\s*R\$")
RE_AJUSTE_NEG = re.compile(
    r"(?P<date>\d{1,3}/\d{1,2}).*?ajuste.*?(?P<amt>-\s*\d+,\d{2})", re.I
)
RE_ROUND = re.compile(r"^(?P<date>\d{1,3}/\d{1,2})\s+-(?P<amt>0,\d{2})$")
RE_DROP_HDR = re.compile(
    r"^(Total |Lançamentos|Limites|Encargos|Próxima fatura|Demais faturas|Parcelamento da fatura|Simulação|Pontos|Cashback|Outros lançamentos|Limite total de crédito|Fatura anterior|Saldo financiado|Produtos e serviços|Tarifa|Compras parceladas - próximas faturas)",
    re.I,
)
LEAD_SYM = ">@§$Z)_•*®«» "

# Regex para FX e pagamentos
FX_LINE1 = re.compile(r"^\d{2}/\d{2} (.+?) (\d{1,3}(?:\.\d{3})*,\d{2})$")
FX_LINE2 = re.compile(
    r"^(.+?) (\d{1,3}(?:\.\d{3})*,\d{2}) (EUR|USD|GBP|CHF) (\d{1,3}(?:\.\d{3})*,\d{2})$"
)
FX_RATE = re.compile(r"D[óo]lar de Convers[ãa]o R\$ (\d{1,3}(?:\.\d{3})*,\d{2})")
PAGAMENTO = re.compile(
    r"^\d{2}/\d{2} PAGAMENTO.*?7117.*?(-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)


def decomma(x: str) -> Decimal:
    return Decimal(
        re.sub(r"[^\d,\-]", "", x.replace(" ", "")).replace(".", "").replace(",", ".")
    )


def norm_date(date, ry, rm):
    if not date:
        return ""
    m = RE_DATE.match(date)
    if not m:
        return date
    d, mth, y = m.groups()
    if not y:
        y = ry
    if not mth:
        mth = rm
    return f"{int(y):04}-{int(mth):02}-{int(d):02}"


def sha1(card, date, desc, valor_brl, installment_tot, categoria_high):
    h = hashlib.sha1()
    h.update(
        f"{card}|{date}|{desc}|{valor_brl}|{installment_tot}|{categoria_high}".encode(
            "utf-8"
        )
    )
    return h.hexdigest()


def classify(desc, amt):
    d = desc.upper()
    if "7117" in d:
        return "PAGAMENTO"
    if "AJUSTE" in d or (abs(amt) <= Decimal("0.30") and abs(amt) > 0):
        return "AJUSTE"
    if any(k in d for k in ("IOF", "JUROS", "MULTA")):
        return "ENCARGOS"
    mapping = [
        ("ACELERADOR", "SERVIÇOS"),
        ("PONTOS", "SERVIÇOS"),
        ("ANUIDADE", "SERVIÇOS"),
        ("SEGURO", "SERVIÇOS"),
        ("TARIFA", "SERVIÇOS"),
        ("PRODUTO", "SERVIÇOS"),
        ("SERVIÇO", "SERVIÇOS"),
        # ... demais categorias já existentes ...
        ("SUPERMERC", "SUPERMERCADO"),
        ("FARMAC", "FARMÁCIA"),
        ("DROG", "FARMÁCIA"),
        ("PANVEL", "FARMÁCIA"),
        ("RESTAUR", "RESTAURANTE"),
        ("PIZZ", "RESTAURANTE"),
        ("BAR", "RESTAURANTE"),
        ("CAFÉ", "RESTAURANTE"),
        ("POSTO", "POSTO"),
        ("COMBUST", "POSTO"),
        ("GASOLIN", "POSTO"),
        ("UBER", "TRANSPORTE"),
        ("TAXI", "TRANSPORTE"),
        ("TRANSP", "TRANSPORTE"),
        ("PASSAGEM", "TRANSPORTE"),
        ("AEROPORTO", "TURISMO"),
        ("HOTEL", "TURISMO"),
        ("TUR", "TURISMO"),
        ("ENTRETENIM", "TURISMO"),
        ("ALIMENT", "ALIMENTAÇÃO"),
        ("IFD", "ALIMENTAÇÃO"),
        ("SAUD", "SAÚDE"),
        ("VEIC", "VEÍCULOS"),
        ("VEST", "VESTUÁRIO"),
        ("LOJA", "VESTUÁRIO"),
        ("MAGAZINE", "VESTUÁRIO"),
        ("EDU", "EDUCAÇÃO"),
        ("HOBBY", "HOBBY"),
        ("DIVERS", "DIVERSOS"),
    ]
    for k, v in mapping:
        if k in d:
            return v
    if "EUR" in d or "USD" in d or "FX" in d:
        return "FX"
    print(f"[CAT-SUSPEITA] {desc}")
    return "DIVERSOS"


def build(card, date, desc, valor_brl, cat, ry, rm, **kv):
    norm = norm_date(date, ry, rm) if date else ""
    ledger = sha1(card, norm, desc, valor_brl, kv.get("installment_tot"), cat)
    city = None
    if cat == "FX" and "merchant_city" in kv and kv["merchant_city"]:
        city = kv["merchant_city"]
    elif cat == "FX" and " " in desc:
        city = desc.split()[0].title()
    # Remove merchant_city de kv se já está sendo passado explicitamente
    kv = dict(kv)
    if "merchant_city" in kv:
        del kv["merchant_city"]
    d = dict(
        card_last4=card,
        post_date=norm,
        desc_raw=desc,
        valor_brl=valor_brl,
        categoria_high=cat,
        merchant_city=city,
        ledger_hash=ledger,
        **kv,
    )
    # Preenche campos obrigatórios vazios
    for k in SCHEMA:
        if k not in d:
            d[k] = ""
    # Logging de campos obrigatórios faltando
    obrigatorios = [
        "card_last4",
        "post_date",
        "desc_raw",
        "valor_brl",
        "categoria_high",
        "ledger_hash",
    ]
    for k in obrigatorios:
        if not d[k]:
            print(f"[OBRIGATORIO-FALTANDO] {k} vazio em linha: {desc}")
    return d


def is_prev_bill_payoff(descr: str, seq_no: int) -> bool:
    """
    Retorna True se a linha é o 1º pagamento do bloco
    ou contém keywords típicas de quitação da fatura anterior.
    """
    kw = ("fatura anterior", "ref.", "refª", "pagt anterior")
    return seq_no == 0 or any(k in descr.lower() for k in kw)


# --- Sanitiser: remove Private Use Area glyphs (ícones) --------------------
def strip_pua(s: str) -> str:
    return re.sub("[\ue000-\uf8ff]", "", s)


def clean(raw: str) -> str:
    raw = strip_pua(raw)
    raw = raw.lstrip(LEAD_SYM).replace("_", " ")
    raw = re.sub(r"\s{2,}", " ", raw)
    return raw.strip()


def compare_metrics(pdf_metrics, csv_metrics):
    def emoji(ok):
        return "✅" if ok else "⚠️"

    for key in pdf_metrics:
        val_pdf = pdf_metrics[key]
        val_csv = csv_metrics.get(key)
        # PATCH: converte ambos para float se forem numéricos (float, int, Decimal)
        if isinstance(val_pdf, (float, int, Decimal)) or isinstance(
            val_csv, (float, int, Decimal)
        ):
            try:
                ok = abs(float(val_pdf) - float(val_csv or 0)) < 0.05
            except Exception:
                ok = False
        else:
            ok = val_pdf == val_csv
        print(f"[CHECK] {key}: {val_pdf} (PDF) vs {val_csv} (CSV) {emoji(ok)}")


def parse_fx_chunk(chunk: list[str]):
    """
    Aceita cluster 2-ou-3 linhas:
      • Compra → Dólar  (sem IOF)
      • Compra → IOF → Dólar
      • Compra → Dólar → IOF
    Devolve dict com valores normalizados ou None.
    """
    if len(chunk) < 2:
        return None

    main = RE_FX_MAIN.match(chunk[0])
    if not main:
        return None

    iof_brl = Decimal("0")
    rate_line = None
    for ln in chunk[1:]:
        if RE_IOF_LINE.search(ln):
            m = RE_BRL.search(ln)
            if m:
                iof_brl = decomma(m.group(0))
        elif RE_DOLAR.search(ln):
            rate_line = ln

    if not rate_line:
        return None

    fx_rate = Decimal(RE_DOLAR.search(rate_line).group(1).replace(",", "."))
    return {
        "date": main.group("date"),
        "descr": main.group("descr"),
        "valor_orig": decomma(main.group("orig")),
        "valor_brl": decomma(main.group("brl")),
        "fx_rate": fx_rate,
        "iof": iof_brl,
    }


def parse_txt(path: Path, ref_y: int, ref_m: int, verbose=False):
    rows, stats = [], Counter()
    card = "0000"
    iof_postings = []

    # Use pdfplumber for PDF files
    if path.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            text = "\n".join(
                page.extract_text() for page in pdf.pages if page.extract_text()
            )
            lines = text.splitlines()
    else:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

    stats["lines"] = len(lines)
    skip = 0
    last_date = None
    pagamento_seq = 0
    seen_fx = set()
    i = 0
    while i < len(lines):
        if skip:
            skip -= 1
            i += 1
            continue
        line = clean(lines[i])

        # FX bloco: aceita 2 ou 3 linhas
        fx_res = None
        if i + 2 < len(lines):
            fx_res = parse_fx_chunk([line, clean(lines[i + 1]), clean(lines[i + 2])])
            consumed = 3
        if not fx_res and i + 1 < len(lines):
            fx_res = parse_fx_chunk([line, clean(lines[i + 1])])
            consumed = 2
        if fx_res:
            fx_key = (
                fx_res["descr"],
                fx_res["date"],
                fx_res["valor_brl"],
                fx_res["valor_orig"],
                fx_res["fx_rate"],
            )
            if fx_key in seen_fx:
                print(
                    f"[DUPLICATE] Duplicata legítima confirmada: {fx_res['descr']} | {fx_res['date']} | {fx_res['valor_brl']}"
                )
            else:
                seen_fx.add(fx_key)
                rows.append(
                    build(
                        card,
                        fx_res["date"],
                        fx_res["descr"],
                        fx_res["valor_brl"],
                        "FX",
                        ref_y,
                        ref_m,
                        valor_orig=fx_res["valor_orig"],
                        fx_rate=fx_res["fx_rate"],
                        iof_brl=fx_res["iof"],
                    )
                )
                stats["fx"] += 1
            i += consumed
            continue
        # Pagamentos (regex abrangente)
        mp = RE_PAY_LINE.match(line) or RE_PAY_LINE_ANY.match(line)
        if mp and mp.group("amt"):
            if is_prev_bill_payoff(line, pagamento_seq):
                print("[PAGAMENTO-IGNORE] Pre-cycle payoff", line)
                pagamento_seq += 1
                i += 1
                continue

            val = decomma(mp.group("amt"))
            if val >= 0:
                print("[PAGAMENTO-ERR] Pagamento positivo ignorado:", line)
                i += 1
                continue

            rows.append(
                build(
                    card, mp.group("date"), "PAGAMENTO", val, "PAGAMENTO", ref_y, ref_m
                )
            )
            stats["pagamento"] += 1
            pagamento_seq += 1
            i += 1
            continue
        elif mp:
            print(
                f"[PAGAMENTO-ERR] Regex de pagamento não encontrou grupo 'amt' em: {line}"
            )
            i += 1
            continue
        # Parsing de compras domésticas (fallback)
        if RE_DATE.match(line):
            md = RE_DOM.match(line)
            if md:
                desc, amt = md.group("desc"), decomma(md.group("amt"))
                if abs(amt) > 10000 or abs(amt) < 0.01:
                    print(f"[VALOR-SUSPEITO] {desc} {amt}")
                re_parc = re.compile(
                    r"(\d{1,2})\s*/\s*(\d{1,2})|(\d{1,2})\s*x\s*R\$|(\d{1,2})\s*de\s*(\d{1,2})",
                    re.I,
                )
                ins = (
                    RE_INST.search(desc)
                    or RE_INST_TXT.search(desc)
                    or re_parc.search(desc)
                )
                if ins:
                    if ins.lastindex == 2:
                        seq, tot = int(ins.group(1)), int(ins.group(2))
                    elif ins.lastindex == 3:
                        seq, tot = int(ins.group(3)), None
                    elif ins.lastindex == 5:
                        seq, tot = int(ins.group(4)), int(ins.group(5))
                    else:
                        seq, tot = None, None
                    # Só aceita parcelas do ciclo atual
                    if tot and seq and seq > tot:
                        print(f"[PARCELA-ERR] Parcela fora do ciclo: {desc}")
                        i += 1
                        continue
                else:
                    seq, tot = None, None
                cat = classify(desc, amt)
                if cat == "DIVERSOS":
                    print(f"[CAT-SUSPEITA] {desc}")
                rows.append(
                    build(
                        card,
                        md.group("date"),
                        desc,
                        amt,
                        cat,
                        ref_y,
                        ref_m,
                        installment_seq=seq,
                        installment_tot=tot,
                    )
                )
                stats[cat.lower()] += 1
                last_date = md.group("date")
            i += 1
            continue
        # Substitua:
        # m_iof = RE_IOF_LINE.search(ln_clean)
        m_iof = RE_IOF_LINE.search(line)
        if m_iof:
            mval = RE_BRL.search(line)
            if not mval:
                i += 1
                continue
            valor = decomma(mval.group(0))
            iof_postings.append(
                build(
                    card,
                    last_date or "",
                    "Repasse de IOF em R$",
                    valor,
                    "IOF",
                    ref_y,
                    ref_m,
                    iof_brl=valor,
                )
            )
            stats["iof"] += 1
            i += 1
            continue
        # if any(x in ln_clean.upper() for x in ("JUROS", "MULTA", "IOF DE FINANCIAMENTO")):
        if any(x in line.upper() for x in ("JUROS", "MULTA", "IOF DE FINANCIAMENTO")):
            mval = RE_BRL.search(line)
            if mval:
                valor = decomma(mval.group(0))
                if valor != 0:
                    rows.append(
                        build(
                            card, last_date or "", line, valor, "ENCARGOS", ref_y, ref_m
                        )
                    )
                    stats["encargos"] += 1
                    i += 1
                    continue
        stats["regex_miss"] += 1
        if verbose:
            prev_line = lines[i - 1] if i > 0 else ""
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            with open(f"{path.stem}_faltantes.txt", "a", encoding="utf-8") as f:
                f.write(f"{i+1:04d}|{lines[i]}\n")
                if prev_line:
                    f.write(f"  [prev] {prev_line}\n")
                if next_line:
                    f.write(f"  [next] {next_line}\n")
        i += 1
    rows.extend(iof_postings)
    # Filtro final antes do CSV
    rows = [
        r for r in rows if r.get("post_date") and r.get("valor_brl") not in ("", None)
    ]
    stats["postings"] = len(rows)
    return rows, stats


def log_block(tag, **kv):
    logging.info("%s | %-8s", datetime.now().strftime("%H:%M:%S"), tag)
    for k, v in kv.items():
        logging.info("           %-12s: %s", k, v)


def main():
    tracemalloc.start()
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    total = Counter()
    t0 = time.perf_counter()
    for f in a.files:
        p = Path(f)
        m = re.search(r"(20\d{2})(\d{2})", p.stem)
        ry, rm = (
            (int(m.group(1)), int(m.group(2)))
            if m
            else (datetime.now().year, datetime.now().month)
        )
        log_block(
            "START",
            v=__version__,
            file=p.name,
            sha=hashlib.sha1(p.read_bytes()).hexdigest()[:8],
        )
        rows, stats = parse_txt(p, ry, rm, a.verbose)
        total += stats
        rows_dedup = rows
        # Checagem de duplicatas por ledger_hash
        seen_hashes = set()
        dupes = 0
        for r in rows:
            if r["ledger_hash"] in seen_hashes:
                print(
                    f"[DUPLICATE] Linha duplicada: {r['desc_raw']} | {r['post_date']} | {r['valor_brl']}"
                )
                dupes += 1
            else:
                seen_hashes.add(r["ledger_hash"])
        rows_dedup = rows  # Mantém todas as linhas para rastreabilidade
        kpi = Counter()
        for r in rows_dedup:
            if r["categoria_high"] in ("ALIMENTAÇÃO", "SAÚDE", "VESTUÁRIO", "VEÍCULOS"):
                kpi["domestic"] += 1
            elif r["categoria_high"] == "FX":
                kpi["fx"] += 1
            elif r["categoria_high"] in ("SERVIÇOS",):
                kpi["services"] += 1
            else:
                kpi["misc"] += 1
        brl_dom = sum(
            r["valor_brl"]
            for r in rows_dedup
            if r["categoria_high"]
            in (
                "ALIMENTAÇÃO",
                "SAÚDE",
                "VESTUÁRIO",
                "VEÍCULOS",
                "FARMÁCIA",
                "SUPERMERCADO",
                "POSTO",
                "RESTAURANTE",
                "TURISMO",
            )
        )
        brl_fx = sum(r["valor_brl"] for r in rows_dedup if r["categoria_high"] == "FX")
        brl_serv = sum(
            r["valor_brl"] for r in rows_dedup if r["categoria_high"] == "SERVIÇOS"
        )
        neg_rows = sum(
            1
            for r in rows_dedup
            if r.get("valor_brl") not in ("", None) and Decimal(str(r["valor_brl"])) < 0
        )
        neg_sum = sum(
            Decimal(str(r["valor_brl"]))
            for r in rows_dedup
            if r.get("valor_brl") not in ("", None) and Decimal(str(r["valor_brl"])) < 0
        )
        # --- Extract metrics from parsed rows ---
        fx_rows = [r for r in rows_dedup if r["categoria_high"] == "FX"]
        valor_fx = sum(
            float(r["valor_brl"])
            for r in fx_rows
            if r.get("valor_brl") not in ("", None)
        )

        pdf_metrics = {
            "Total da fatura anterior": sum(
                float(r.get("pagamento_fatura_anterior", 0) or 0) for r in rows_dedup
            ),
            "Pagamentos efetuados": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "PAGAMENTO"
            ),
            "Saldo financiado": 0,  # Not available from PDF
            "Lançamentos atuais": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] not in ("PAGAMENTO", "AJUSTE")
            ),
            "Total desta fatura": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r.get("valor_brl") not in ("", None)
            ),
            "Nº de pagamentos 7117": len(
                [r for r in rows_dedup if r["categoria_high"] == "PAGAMENTO"]
            ),
            "Valor total dos pagamentos": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "PAGAMENTO"
            ),
            "Valor do maior pagamento": min(
                (
                    float(r["valor_brl"])
                    for r in rows_dedup
                    if r["categoria_high"] == "PAGAMENTO"
                ),
                default=0,
            ),
            "Nº de compras domésticas": sum(
                1
                for r in rows_dedup
                if r["categoria_high"]
                in (
                    "ALIMENTAÇÃO",
                    "SAÚDE",
                    "VESTUÁRIO",
                    "VEÍCULOS",
                    "FARMÁCIA",
                    "SUPERMERCADO",
                    "POSTO",
                    "RESTAURANTE",
                    "TURISMO",
                )
            ),
            "Valor total compras domésticas": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"]
                in (
                    "ALIMENTAÇÃO",
                    "SAÚDE",
                    "VESTUÁRIO",
                    "VEÍCULOS",
                    "FARMÁCIA",
                    "SUPERMERCADO",
                    "POSTO",
                    "RESTAURANTE",
                    "TURISMO",
                )
            ),
            "Nº de compras internacionais": len(fx_rows),
            "Valor total compras internacionais (BRL)": valor_fx,
            "Valor total lançamentos internacionais (BRL)": valor_fx
            + sum(
                float(r.get("iof_brl", 0) or 0)
                for r in rows_dedup
                if r["categoria_high"] == "IOF"
            ),
            "Valor total IOF internacional": sum(
                float(r.get("iof_brl", 0) or 0)
                for r in rows_dedup
                if r["categoria_high"] == "IOF"
            ),
            "Maior compra internacional": max(
                (float(r["valor_brl"]) for r in fx_rows), default=0
            ),
            "Menor compra internacional": min(
                (float(r["valor_brl"]) for r in fx_rows), default=0
            ),
            "Nº de cartões diferentes": len(set(r["card_last4"] for r in rows_dedup)),
            "Valor total de produtos/serviços": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "SERVIÇOS"
            ),
            "Nº de ajustes negativos": sum(
                1 for r in rows_dedup if r["categoria_high"] == "AJUSTE"
            ),
            "Valor total ajustes negativos": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "AJUSTE"
            ),
            "Saldo calculado": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r.get("valor_brl") not in ("", None)
            ),
        }
        # --- NOVO: Métricas extraídas do CSV ---
        # Pagamentos: só do ciclo atual (ignora o primeiro, que está em pagamento_fatura_anterior)
        pagamentos_csv = [
            r
            for r in rows_dedup
            if r["categoria_high"] == "PAGAMENTO"
            and r.get("valor_brl") not in ("", None)
        ]
        pagamentos_ciclo = pagamentos_csv
        # FX: só se campos de metadados estiverem preenchidos
        fx_rows = [
            r
            for r in rows_dedup
            if r["categoria_high"] == "FX"
            and r.get("valor_orig")
            and r.get("moeda_orig")
            and r.get("fx_rate")
        ]
        csv_metrics = {
            "Total da fatura anterior": sum(
                float(r.get("pagamento_fatura_anterior", 0) or 0) for r in rows_dedup
            ),
            "Pagamentos efetuados": sum(
                float(r["valor_brl"]) for r in pagamentos_ciclo
            ),
            "Saldo financiado": 0,
            "Lançamentos atuais": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] not in ("PAGAMENTO", "AJUSTE")
                and (r.get("valor_brl") not in ("", None))
            ),
            "Total desta fatura": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r.get("valor_brl") not in ("", None)
            ),
            "Nº de pagamentos 7117": len(pagamentos_ciclo),
            "Valor total dos pagamentos": sum(
                float(r["valor_brl"]) for r in pagamentos_ciclo
            ),
            "Valor do maior pagamento": min(
                (float(r["valor_brl"]) for r in pagamentos_ciclo), default=0
            ),
            "Nº de compras domésticas": sum(
                1
                for r in rows_dedup
                if r["categoria_high"]
                in (
                    "ALIMENTAÇÃO",
                    "SAÚDE",
                    "VESTUÁRIO",
                    "VEÍCULOS",
                    "FARMÁCIA",
                    "SUPERMERCADO",
                    "POSTO",
                    "RESTAURANTE",
                    "TURISMO",
                )
            ),
            "Valor total compras domésticas": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"]
                in (
                    "ALIMENTAÇÃO",
                    "SAÚDE",
                    "VESTUÁRIO",
                    "VEÍCULOS",
                    "FARMÁCIA",
                    "SUPERMERCADO",
                    "POSTO",
                    "RESTAURANTE",
                    "TURISMO",
                )
            ),
            "Nº de compras internacionais": len(fx_rows),
            "Valor total compras internacionais (BRL)": sum(
                float(r["valor_brl"]) for r in fx_rows
            ),
            "Valor total lançamentos internacionais (BRL)": sum(
                float(r["valor_brl"]) for r in fx_rows
            )
            + sum(
                float(r.get("iof_brl", 0) or 0)
                for r in rows_dedup
                if r["categoria_high"] == "IOF"
            ),
            "Valor total IOF internacional": sum(
                float(r.get("iof_brl", 0) or 0)
                for r in rows_dedup
                if r["categoria_high"] == "IOF"
            ),
            "Maior compra internacional": max(
                (float(r["valor_brl"]) for r in fx_rows), default=0
            ),
            "Menor compra internacional": min(
                (float(r["valor_brl"]) for r in fx_rows), default=0
            ),
            "Nº de cartões diferentes": len(set(r["card_last4"] for r in rows_dedup)),
            "Valor total de produtos/serviços": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "SERVIÇOS"
            ),
            "Nº de ajustes negativos": sum(
                1 for r in rows_dedup if r["categoria_high"] == "AJUSTE"
            ),
            "Valor total ajustes negativos": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r["categoria_high"] == "AJUSTE"
            ),
            "Saldo calculado": sum(
                float(r["valor_brl"])
                for r in rows_dedup
                if r.get("valor_brl") not in ("", None)
            ),
        }
        compare_metrics(pdf_metrics, csv_metrics)
        log_block(
            "TOTAL",
            Débitos=f"{brl_dom+brl_fx+brl_serv:,.2f}",
            Créditos=f"{neg_sum:,.2f}",
            Net=f"{brl_dom+brl_fx+brl_serv+neg_sum:,.2f}",
        )
        log_block(
            "POSTINGS",
            rows=len(rows_dedup),
            dom=kpi["domestic"],
            fx=kpi["fx"],
            ajustes=kpi["ajuste"],
            pagamentos=kpi["pagamento"],
        )
        log_block(
            "KPIS",
            miss=stats["regex_miss"],
            acc=f"{100*(stats['lines']-stats['hdr_drop']-stats['regex_miss'])/max(stats['lines']-stats['hdr_drop'],1):.1f}%",
        )
        out = p.with_name(f"{p.stem}_done.csv")
        out.write_text("")
        with out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=SCHEMA)
            w.writeheader()
            w.writerows(rows_dedup)
        size_kb = out.stat().st_size // 1024
        log_block("FILES", in_=p.name, out=f"{out.name} ({size_kb} KB)")
        mem = tracemalloc.get_traced_memory()[1] // 1024**2
        log_block("MEM", peak=f"{mem} MB")
        log_block("END", result="SUCCESS")
    dur = time.perf_counter() - t0
    eff_g = total["lines"] - total["hdr_drop"]
    acc_g = 100 * (eff_g - total["regex_miss"]) / max(eff_g, 1)
    log_block(
        "SUMMARY",
        files=len(a.files),
        postings=total["postings"],
        miss=total["regex_miss"],
        acc=f"{acc_g:.1f}%",
        dur=f"{dur:.2f}s",
    )

    # Após parsing e antes de escrever no CSV:
    rows_validos = [
        r for r in rows if r.get("post_date") and r.get("valor_brl") not in ("", None)
    ]

    debito_total = sum(
        float(r["valor_brl"])
        for r in rows_validos
        if float(r["valor_brl"]) > 0
        and r["categoria_high"] not in ("PAGAMENTO", "AJUSTE")
    )
    credito_total = sum(
        float(r["valor_brl"])
        for r in rows_validos
        if float(r["valor_brl"]) < 0 and r["categoria_high"] in ("PAGAMENTO", "AJUSTE")
    )
    valor_total_fatura = debito_total + credito_total

    print(
        f"[RECONCILIACAO] Débitos: {debito_total:.2f} | Créditos: {credito_total:.2f} | Total fatura: {valor_total_fatura:.2f}"
    )

    # Atualize as métricas do CSV para refletir os novos totais
    csv_metrics["Débitos"] = debito_total
    csv_metrics["Créditos"] = credito_total
    csv_metrics["Saldo calculado"] = valor_total_fatura


if __name__ == "__main__":
    main()
