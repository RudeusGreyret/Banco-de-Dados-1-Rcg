from datetime import date, timedelta
from pathlib import Path
import base64
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Escala Dragão | Escalas 1º RCG", page_icon="📅", layout="wide")

from auth import exigir_login
exigir_login()
DB = Path(__file__).with_name("escala_local.db")
SU = ["EM", "1º Esqd", "2º Esqd", "3º Esqd", "Esqd Crm", "Esqd C Ap", "CHDI", "Fanfarra"]
DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]

@st.cache_resource
def conectar():
    db = sqlite3.connect(DB, timeout=20, check_same_thread=False)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS militares
      (id INTEGER PRIMARY KEY, ord INTEGER NOT NULL, nome TEXT NOT NULL,
       su TEXT NOT NULL, status TEXT NOT NULL, obs TEXT NOT NULL DEFAULT '',
       tipo TEXT NOT NULL DEFAULT 'AMBAS')""")
    db.execute("""CREATE TABLE IF NOT EXISTS escala
      (dia TEXT NOT NULL, militar_id INTEGER NOT NULL,
       valor TEXT NOT NULL, manual INTEGER NOT NULL DEFAULT 0,
       PRIMARY KEY(dia, militar_id))""")
    db.commit()
    return db

db = conectar()

def pessoas():
    return pd.read_sql_query("SELECT * FROM militares ORDER BY ord, id", db)

def escala(inicio, fim):
    return pd.read_sql_query(
        "SELECT * FROM escala WHERE dia BETWEEN ? AND ?",
        db, params=(inicio.isoformat(), fim.isoformat()))

def categoria(d):
    return "VERMELHA" if d.weekday() >= 5 else "PRETA"

def gerar(inicio, qtd, recalcular):
    ps = pessoas()
    if ps.empty:
        return 0, ["Cadastre militares primeiro."]
    contagem = dict(db.execute(
        "SELECT militar_id, COUNT(*) FROM escala WHERE valor='SV' GROUP BY militar_id").fetchall())
    gerados, avisos = 0, []
    with db:
        for n in range(qtd):
            dia = inicio + timedelta(days=n)
            ds = dia.isoformat()
            existentes = db.execute(
                "SELECT militar_id, valor, manual FROM escala WHERE dia=?", (ds,)).fetchall()
            fixos = [r for r in existentes if r[2] and r[1] == "SV"]
            if len(fixos) > 1:
                avisos.append(f"{dia:%d/%m/%Y}: vários serviços fixados manualmente.")
                continue
            if fixos:
                continue
            if not recalcular and any(r[1] == "SV" for r in existentes):
                continue
            if recalcular:
                db.execute("DELETE FROM escala WHERE dia=? AND manual=0", (ds,))
            impedidos = {r[0] for r in existentes if r[2]}
            elegiveis = ps[
                (ps.status == "ATIVO")
                & (ps.tipo.isin(["AMBAS", categoria(dia)]))
                & (~ps.id.isin(impedidos))
            ]
            if elegiveis.empty:
                avisos.append(f"{dia:%d/%m/%Y}: sem militar elegível.")
                continue
            escolhido = min(elegiveis.itertuples(),
                            key=lambda p: (contagem.get(p.id, 0), p.ord, p.id))
            db.execute(
                "INSERT OR REPLACE INTO escala(dia,militar_id,valor,manual) VALUES (?,?,?,0)",
                (ds, int(escolhido.id), "SV"))
            contagem[escolhido.id] = contagem.get(escolhido.id, 0) + 1
            gerados += 1
    return gerados, avisos

st.markdown("""<style>
:root {color-scheme: dark;}
.stApp {background:linear-gradient(160deg,#091526 0%,#101e33 60%,#0c182a 100%);color:#e9f1fc;}
[data-testid="stSidebar"] {background:#0b1628;border-right:1px solid #273b54;}
[data-testid="stSidebar"] * {color:#e5eefb;}
.block-container {max-width:1700px;padding-top:1.5rem;padding-bottom:3rem;}
h1,h2,h3 {color:#f3f7fc !important;letter-spacing:-.025em;}
h1 {font-size:2rem !important;}
p, label {color:#d5e1f0;}
[data-testid="stMetric"] {background:#14253b;padding:20px;border:1px solid #29405c;border-radius:14px;box-shadow:0 5px 18px #0002;}
[data-testid="stMetricLabel"] {color:#b9cce2;}
[data-testid="stMetricValue"] {color:#f8fafc;}
[data-baseweb="tab-list"] {gap:.65rem;background:#132339;padding:.45rem;border-radius:12px;}
button[data-baseweb="tab"] {color:#b9cce2;border-radius:9px;padding:10px 16px;}
button[data-baseweb="tab"][aria-selected="true"] {background:#23466a;color:#fff;}
[data-testid="stDataFrame"] {border:1px solid #314964;border-radius:12px;overflow:hidden;}
[data-testid="stForm"] {background:#13243b;border:1px solid #2b4260;border-radius:14px;padding:1.1rem;}
[data-testid="stAlert"] {border-radius:10px;}
[data-testid="stHeader"] {background:transparent;}
.brand {border:1px solid #345477;border-left:5px solid #e2b45d;background:linear-gradient(115deg,#162d4a,#102039);padding:22px 26px;border-radius:16px;margin-bottom:15px;}
.brand .eyebrow {color:#e4bf77;font-size:12px;letter-spacing:2px;font-weight:750;}
.brand .name {font-size:clamp(28px,3.5vw,42px);font-weight:800;color:white;margin:3px 0;}
.brand .sub {color:#bfd0e5;font-size:14px;}
.legend {color:#cbd8e8;margin:8px 0 12px;font-size:13px;}
@media (max-width:700px) {.block-container{padding:1rem .65rem}.brand{padding:18px 15px}}
</style>""", unsafe_allow_html=True)
# Foto de fundo opcional; carregada apenas na aplicação após o login.
foto_fundo = Path(__file__).with_name("fundo.jpg")
if foto_fundo.is_file():
    imagem_b64 = base64.b64encode(foto_fundo.read_bytes()).decode("ascii")
    st.markdown(
        "<style>"
        ".stApp {background-image:linear-gradient(rgba(7,19,35,.87),rgba(7,19,35,.92)),"
        "url('data:image/jpeg;base64," + imagem_b64 + "') !important;"
        "background-size:cover !important;background-position:center center !important;"
        "background-attachment:fixed !important;}"
        "[data-testid='stSidebar'] {background:rgba(9,21,39,.97) !important;}"
        "[data-testid='stMetric'] {background:rgba(20,37,59,.96) !important;}"
        "[data-testid='stForm'] {background:rgba(19,36,59,.98) !important;}"
        "[data-baseweb='tab-list'] {background:rgba(19,35,57,.97) !important;}"
        "</style>",
        unsafe_allow_html=True
    )

st.markdown("""<div class="brand">
<div class="eyebrow">1º REGIMENTO DE CAVALARIA DE GUARDAS • CONTROLE DE SERVIÇO</div>
<div class="name">🐉 Escala Dragão</div>
<div class="sub">Painel de escalas · Geração automática e ajustes manuais</div>
</div>""", unsafe_allow_html=True)
st.info("Ambiente de testes com login administrativo. Utilize somente dados fictícios: controle por SU, auditoria e armazenamento persistente ainda não estão implementados.", icon="🔐")

with st.sidebar:
    st.header("🐉 Escala Dragão")
    st.caption("Filtros e período da escala")
    inicio = st.date_input("Início", value=date.today().replace(day=1), format="DD/MM/YYYY")
    qtd = st.selectbox("Quantidade de dias", [7, 14, 21, 28, 31], index=3)
    filtro = st.selectbox("Subunidade", ["Todas"] + SU)
    st.caption("PRETA: dias úteis | VERMELHA: fins de semana. Regras de descanso ainda não implementadas.")

ps_all = pessoas()
ps = ps_all if filtro == "Todas" else ps_all[ps_all.su == filtro]
fim = inicio + timedelta(days=qtd - 1)
servicos = escala(inicio, fim)
indice = {(int(r.militar_id), r.dia): (r.valor, bool(r.manual))
          for r in servicos.itertuples()}
datas = [inicio + timedelta(days=n) for n in range(qtd)]

quadro, automatico, cadastro = st.tabs(["📋 Quadro de serviço", "⚙️ Escala automática", "👥 Efetivo"])
with quadro:
    a, b, c = st.columns(3)
    a.metric("Militares", len(ps))
    b.metric("Serviços no período", int((servicos.valor == "SV").sum()) if not servicos.empty else 0)
    c.metric("Células manuais", int(servicos.manual.sum()) if not servicos.empty else 0)
    st.markdown('<div class="legend">🔴 Vermelha: sábado e domingo &nbsp;&nbsp; ⚫ Preta: segunda a sexta &nbsp;&nbsp; ✏️ Alterações manuais preservadas</div>', unsafe_allow_html=True)
    if ps.empty:
        st.info("Nenhum militar cadastrado nesta seleção. Acesse a aba Efetivo para começar.")
    else:
        rotulos = [f"{d:%d/%m} {DIAS[d.weekday()]} {'🔴' if categoria(d)=='VERMELHA' else '⚫'}" for d in datas]
        linhas = []
        for p in ps.itertuples():
            linha = {"ID": p.id, "Ord": p.ord, "Nome": p.nome, "SU": p.su,
                     "Status": p.status, "OBS": p.obs, "Escala": p.tipo}
            for d, titulo in zip(datas, rotulos):
                linha[titulo] = indice.get((p.id, d.isoformat()), ("", False))[0]
            linhas.append(linha)
        original = pd.DataFrame(linhas)
        st.caption("SV = serviço | IMP = impedimento | — = sem serviço. Após editar, clique em Salvar.")
        alterado = st.data_editor(
            original, hide_index=True, use_container_width=True, height=520,
            disabled=["ID", "Ord", "Nome", "SU", "Status", "OBS", "Escala"],
            column_config={titulo: st.column_config.SelectboxColumn(
                titulo, options=["", "SV", "IMP", "—"], width="small")
                for titulo in rotulos},
            key=f"grade-{inicio}-{qtd}-{filtro}")
        if st.button("💾 Salvar edições manuais", type="primary"):
            total = 0
            with db:
                for i, row in alterado.iterrows():
                    for d, titulo in zip(datas, rotulos):
                        novo = "" if pd.isna(row[titulo]) else str(row[titulo])
                        if novo != original.at[i, titulo]:
                            db.execute(
                                "INSERT OR REPLACE INTO escala(dia,militar_id,valor,manual) VALUES (?,?,?,1)",
                                (d.isoformat(), int(row["ID"]), novo))
                            total += 1
            st.success(f"{total} alteração(ões) registrada(s).")
            st.rerun()
        csv = original.drop(columns=["ID"]).to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button("⬇️ Exportar CSV", csv,
                           file_name=f"escala_{inicio.isoformat()}.csv", mime="text/csv")

with automatico:
    st.subheader("⚙️ Gerador de escala")
    recalcular = st.checkbox("Recalcular somente serviços automáticos", value=True)
    st.write("Edições manuais ficam preservadas. Um militar é designado por dia, privilegiando menor número de serviços.")
    if st.button("Gerar escala", type="primary"):
        numero, avisos = gerar(inicio, qtd, recalcular)
        st.success(f"{numero} serviço(s) gerado(s).")
        for aviso in avisos:
            st.warning(aviso)
        if numero:
            st.rerun()
    st.info("A lógica ainda não considera descanso mínimo, feriados, antiguidade ou regras oficiais. Revise antes de utilizar.")

with cadastro:
    st.subheader("👤 Cadastrar militar fictício")
    with st.form("cadastrar"):
        ordem = st.number_input("Ordem", min_value=1, step=1)
        nome = st.text_input("Nome")
        su = st.selectbox("SU", SU)
        status = st.selectbox("Status", ["ATIVO", "FÉRIAS", "BAIXADO", "CURSO", "OUTRO"])
        obs = st.text_input("Observações")
        tipo = st.selectbox("Tipo de escala", ["AMBAS", "PRETA", "VERMELHA", "FORA"])
        if st.form_submit_button("Cadastrar", type="primary"):
            if not nome.strip():
                st.error("Informe o nome.")
            else:
                with db:
                    db.execute("INSERT INTO militares(ord,nome,su,status,obs,tipo) VALUES (?,?,?,?,?,?)",
                               (int(ordem), nome.strip(), su, status, obs, tipo))
                st.success("Cadastro concluído.")
                st.rerun()
    st.dataframe(ps_all, hide_index=True, use_container_width=True)
