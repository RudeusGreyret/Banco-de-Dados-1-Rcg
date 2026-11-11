from datetime import date, timedelta
from pathlib import Path
import sqlite3
import pandas as pd
import streamlit as st

st.set_page_config(page_title="SisBol | Escalas 1º RCG", page_icon="📅", layout="wide")

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
.stApp {background:#f5f7fb}
h1 {color:#162e49}
[data-testid="stMetric"] {background:white;padding:12px;border:1px solid #e1e8f0;border-radius:10px}
</style>""", unsafe_allow_html=True)
st.title("SisBol | Escalas — 1º RCG")
st.warning("PROTÓTIPO SEM LOGIN: use apenas dados fictícios. Não exponha esta aplicação à internet.", icon="🔒")

with st.sidebar:
    st.header("Configurações")
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

quadro, automatico, cadastro = st.tabs(["📅 Quadro", "⚙️ Geração automática", "👤 Cadastro"])
with quadro:
    a, b, c = st.columns(3)
    a.metric("Militares", len(ps))
    b.metric("Serviços no período", int((servicos.valor == "SV").sum()) if not servicos.empty else 0)
    c.metric("Células manuais", int(servicos.manual.sum()) if not servicos.empty else 0)
    if ps.empty:
        st.info("Nenhum militar cadastrado nesta seleção.")
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
    st.subheader("Gerar serviços")
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
    st.subheader("Adicionar militar fictício")
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
