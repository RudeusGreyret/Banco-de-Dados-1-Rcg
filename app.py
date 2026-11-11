from datetime import date, timedelta
from pathlib import Path
import base64
from html import escape
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
    db.execute("""CREATE TABLE IF NOT EXISTS previsao_servico
        (dia TEXT NOT NULL, funcao TEXT NOT NULL, descricao TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (dia, funcao))""")
    db.execute("""CREATE TABLE IF NOT EXISTS categoria_dia
        (dia TEXT PRIMARY KEY, tipo TEXT NOT NULL CHECK(tipo IN ('PRETA','VERMELHA')))""")
    db.commit()
    return db

db = conectar()

def pessoas():
    return pd.read_sql_query("SELECT * FROM militares ORDER BY ord, id", db)

def escala(inicio, fim):
    return pd.read_sql_query(
        "SELECT * FROM escala WHERE dia BETWEEN ? AND ?",
        db, params=(inicio.isoformat(), fim.isoformat()))

def pascoa(ano):
    """Computus gregoriano para apuração da Sexta-Feira Santa."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(ano, mes, dia)


def feriados_nacionais(ano):
    fixos = {
        (1, 1): "Confraternização Universal",
        (4, 21): "Tiradentes",
        (5, 1): "Dia do Trabalho",
        (9, 7): "Independência do Brasil",
        (10, 12): "Nossa Senhora Aparecida",
        (11, 2): "Finados",
        (11, 15): "Proclamação da República",
        (11, 20): "Consciência Negra",
        (12, 25): "Natal",
    }
    feriados = {date(ano, mes, dia): nome for (mes, dia), nome in fixos.items()}
    feriados[pascoa(ano) - timedelta(days=2)] = "Paixão de Cristo"
    return feriados


def motivo_calendario(d):
    if d.weekday() >= 5:
        return "Fim de semana"
    return feriados_nacionais(d.year).get(d)


def categoria(d):
    ajuste = db.execute("SELECT tipo FROM categoria_dia WHERE dia=?", (d.isoformat(),)).fetchone()
    if ajuste:
        return ajuste[0]
    return "VERMELHA" if motivo_calendario(d) else "PRETA"


def verificar_consecutivos(militar_id, dia):
    anterior = (dia - timedelta(days=1)).isoformat()
    return bool(db.execute(
        "SELECT 1 FROM escala WHERE militar_id=? AND dia=? AND valor='SV' LIMIT 1",
        (militar_id, anterior)
    ).fetchone())


def gerar(inicio, qtd, recalcular):
    ps = pessoas()
    if ps.empty:
        return 0, ["Cadastre militares primeiro."]
    # Contadores independentes de escala PRETA e VERMELHA.
    contagens = {int(p.id): {"PRETA": 0, "VERMELHA": 0} for p in ps.itertuples()}
    historico = db.execute(
        "SELECT dia,militar_id FROM escala WHERE valor='SV' ORDER BY dia"
    ).fetchall()
    # Reconstruir as contagens a partir do calendário atual, inclusive ajustes manuais.
    # Ao recalcular, desconsiderar as designações automáticas dentro do período.
    automaticos_no_periodo = {
        (r[0], int(r[1])) for r in db.execute(
            "SELECT dia,militar_id FROM escala WHERE manual=0 AND valor='SV' AND dia BETWEEN ? AND ?",
            (inicio.isoformat(), (inicio + timedelta(days=qtd - 1)).isoformat())
        ).fetchall()
    } if recalcular else set()
    for dia_str, mid in historico:
        if (dia_str, int(mid)) in automaticos_no_periodo:
            continue
        if int(mid) in contagens:
            contagens[int(mid)][categoria(date.fromisoformat(dia_str))] += 1
    gerados, avisos = 0, []
    with db:
        for n in range(qtd):
            dia = inicio + timedelta(days=n)
            ds = dia.isoformat()
            tipo_dia = categoria(dia)
            existentes = db.execute(
                "SELECT militar_id, valor, manual FROM escala WHERE dia=?", (ds,)
            ).fetchall()
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
            impedidos = {int(r[0]) for r in existentes if r[2]}
            elegiveis = ps[
                (ps.status == "ATIVO")
                & (ps.tipo.isin(["AMBAS", tipo_dia]))
                & (~ps.id.isin(impedidos))
            ]
            if elegiveis.empty:
                avisos.append(f"{dia:%d/%m/%Y}: não há militar disponível para {tipo_dia}.")
                continue
            descansados = [
                p for p in elegiveis.itertuples()
                if not verificar_consecutivos(int(p.id), dia)
            ]
            # Só aceitar serviço em dias consecutivos se não houver outra pessoa
            # elegível; a exceção é registrada como aviso.
            candidatos = descansados if descansados else list(elegiveis.itertuples())
            if not descansados:
                avisos.append(
                    f"{dia:%d/%m/%Y}: EXCEÇÃO — militar com serviço no dia anterior "
                    "por falta de outro elegível. Revisar antes de publicar."
                )
            escolhido = min(
                candidatos,
                key=lambda p: (
                    contagens[int(p.id)][tipo_dia],
                    sum(contagens[int(p.id)].values()),
                    int(p.ord), int(p.id)
                )
            )
            db.execute(
                "INSERT OR REPLACE INTO escala(dia,militar_id,valor,manual) VALUES (?,?,?,0)",
                (ds, int(escolhido.id), "SV")
            )
            contagens[int(escolhido.id)][tipo_dia] += 1
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
foto_compacta = Path(__file__).with_name("fundo.b64")
imagem_b64 = (
    base64.b64encode(foto_fundo.read_bytes()).decode("ascii")
    if foto_fundo.is_file()
    else foto_compacta.read_text(encoding="utf-8").strip() if foto_compacta.is_file() else ""
)
if imagem_b64:
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
    st.caption("MENU DE ESCALAS")
    # As novas escalas são apenas áreas de navegação; ainda não fazem
    # leitura ou gravação de escala no banco atual.
    escala_aberta = st.radio(
        "Selecionar escala",
        ["📅 Escala principal", "🛡️ Escala da Guarda", "🎖️ Oficial de Dia",
         "🔰 Cabo de Dia", "📋 Sargento de Dia"],
        label_visibility="collapsed",
        key="menu_escalas"
    )
    st.divider()
    if escala_aberta == "📅 Escala principal":
        st.caption("FILTROS DA ESCALA PRINCIPAL")
        inicio = st.date_input("Início", value=date.today().replace(day=1), format="DD/MM/YYYY")
        qtd = st.selectbox("Quantidade de dias", [7, 14, 21, 28, 31], index=3)
        filtro = st.selectbox("Subunidade", ["Todas"] + SU)
        st.caption("PRETA: dias úteis comuns | VERMELHA: fins de semana e feriados nacionais. Ajustes extraordinários por data na Previsão.")
    else:
        st.caption("Em preparação — sem alterações no banco de dados.")

if escala_aberta != "📅 Escala principal":
    st.markdown(f"### {escala_aberta}")
    st.info(
        "Esta área já está no menu lateral. O cadastro, as regras e as escalas "
        "específicas serão configurados antes de ativar a geração automática."
    )
    st.caption("As escalas existentes e os cadastros não são modificados ao abrir esta seção.")
    st.stop()

ps_all = pessoas()
ps = ps_all if filtro == "Todas" else ps_all[ps_all.su == filtro]
fim = inicio + timedelta(days=qtd - 1)
servicos = escala(inicio, fim)
indice = {(int(r.militar_id), r.dia): (r.valor, bool(r.manual))
          for r in servicos.itertuples()}
datas = [inicio + timedelta(days=n) for n in range(qtd)]

FUNCOES_PREVISAO = {
    "OFICIAIS": ["SUP DIA", "OF DIA"],
    "SARGENTOS": ["ADJUNTO", "CMT GDA", "GDA HFA"],
    "CABOS": ["GDA", "HFA"],
    "MOTORISTAS": ["SUP DE DIA", "MOT DIA"],
    "APOIO": ["BLOCO EXTERNO", "PRONTIDÃO"],
}
CORES_PREVISAO = {
    "OFICIAIS": "#b9dd8a", "SARGENTOS": "#4cdb4c",
    "CABOS": "#f2cc3c", "MOTORISTAS": "#58d6da",
    "APOIO": "#4688d6",
}
NOMES_DIAS = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA",
              "QUINTA-FEIRA", "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]
quadro, previsao_tab, automatico, cadastro = st.tabs(
    ["📋 Quadro de serviço", "🗓️ Previsão da escala", "⚙️ Escala automática", "👥 Efetivo"]
)
with quadro:
    a, b, c = st.columns(3)
    a.metric("Militares", len(ps))
    b.metric("Serviços no período", int((servicos.valor == "SV").sum()) if not servicos.empty else 0)
    c.metric("Células manuais", int(servicos.manual.sum()) if not servicos.empty else 0)
    st.markdown('<div class="legend">🔴 Vermelha: feriados nacionais e fins de semana &nbsp;&nbsp; ⚫ Preta: demais dias &nbsp;&nbsp; ✏️ Correções manuais preservadas</div>', unsafe_allow_html=True)
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

        # Quadro de leitura: dias consecutivos sem serviço são contados como
        # 1, 2, 3...; no dia de SV o contador zera e recomeça no seguinte.
        # A consulta ao histórico evita reiniciar a contagem ao trocar o período.
        ultimo_servico = {
            int(mid): date.fromisoformat(dia_str)
            for mid, dia_str in db.execute(
                """SELECT militar_id, MAX(dia)
                   FROM escala WHERE valor='SV' AND dia < ?
                   GROUP BY militar_id""", (inicio.isoformat(),)
            ).fetchall()
        }
        visualizacao = []
        for p in ps.itertuples():
            ultima_data = ultimo_servico.get(int(p.id))
            dias_livres = 0
            visual = {"Ord": int(p.ord), "Nome": p.nome, "SU": p.su}
            for d, titulo in zip(datas, rotulos):
                marcacao = indice.get((int(p.id), d.isoformat()), ("", False))[0]
                if marcacao == "SV":
                    visual[titulo] = "SV"
                    ultima_data = d
                    dias_livres = 0
                else:
                    if ultima_data is not None:
                        dias_livres = (d - ultima_data).days
                    else:
                        # Sem serviço anterior registrado: inicia em 1 no
                        # primeiro dia visível do intervalo.
                        dias_livres += 1
                    visual[titulo] = (
                        f"{dias_livres} · IMP" if marcacao == "IMP"
                        else str(dias_livres)
                    )
            visualizacao.append(visual)
        st.markdown("#### 📆 Dias sem serviço")
        st.caption("SV = serviço de 24h (zera a contagem). Sem SV = 1, 2, 3… a partir do último serviço registrado. IMP continua contado como dia sem serviço.")
        st.dataframe(
            pd.DataFrame(visualizacao), hide_index=True,
            use_container_width=True, height=430
        )
        st.caption("Se não existir serviço anterior registrado, a contagem começa em 1 no início do período exibido.")
        with st.expander("✏️ Editar escala manualmente", expanded=False):
            st.caption("Altere somente as datas: SV = serviço, IMP = impedimento, — = sem serviço. Clique em Salvar.")
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

with previsao_tab:
    st.subheader("🗓️ PREVISÃO DA ESCALA — 1º RCG")
    st.caption("Funções nas linhas e datas nas colunas, conforme o modelo enviado.")
    st.markdown("#### 📆 Tipo de escala por data")
    st.caption("Calendário automático: dias úteis = PRETA; feriados nacionais e fins de semana = VERMELHA. Para situações extraordinárias, mude só a classificação do dia. AUTO restaura o calendário.")
    tipos_dia = []
    for d in datas:
        manual_dia = db.execute("SELECT tipo FROM categoria_dia WHERE dia=?", (d.isoformat(),)).fetchone()
        tipos_dia.append({
            "Data": d.strftime("%d/%m/%Y"),
            "Dia": NOMES_DIAS[d.weekday()],
            "Motivo": motivo_calendario(d) or "Dia útil comum",
            "Classificação": categoria(d),
            "Alteração extraordinária": manual_dia[0] if manual_dia else "AUTO"
        })
    tipos_originais = pd.DataFrame(tipos_dia)
    tipos_editados = st.data_editor(
        tipos_originais,
        use_container_width=True, hide_index=True,
        disabled=["Data", "Dia", "Motivo", "Classificação"],
        column_config={
            "Alteração extraordinária": st.column_config.SelectboxColumn(
                "Alteração extraordinária", options=["AUTO", "PRETA", "VERMELHA"],
                required=True
            )
        },
        key=f"categorias_datas_{inicio.isoformat()}_{qtd}"
    )
    if st.button("💾 Salvar tipos de escala por data", type="primary", key="salvar_categorias"):
        alteracoes_datas = 0
        with db:
            for idx, d in enumerate(datas):
                novo = tipos_editados.iloc[idx]["Alteração extraordinária"]
                anterior = tipos_originais.iloc[idx]["Alteração extraordinária"]
                if novo == anterior:
                    continue
                if novo == "AUTO":
                    db.execute("DELETE FROM categoria_dia WHERE dia=?", (d.isoformat(),))
                else:
                    db.execute(
                        "INSERT OR REPLACE INTO categoria_dia(dia,tipo) VALUES (?,?)",
                        (d.isoformat(), novo)
                    )
                alteracoes_datas += 1
        st.success(f"{alteracoes_datas} data(s) atualizada(s).")
        if alteracoes_datas:
            st.rerun()
    st.divider()
    st.info("Previsão manual, independente do quadro de serviço. A geração automática por função depende de regras próprias.", icon="ℹ️")
    linhas = [(grupo, funcao, f"{grupo}::{funcao}")
              for grupo, funcoes in FUNCOES_PREVISAO.items() for funcao in funcoes]
    encontrados = db.execute(
        "SELECT dia, funcao, descricao FROM previsao_servico WHERE dia BETWEEN ? AND ?",
        (inicio.isoformat(), fim.isoformat())
    ).fetchall()
    valores = {(dia, funcao): descricao for dia, funcao, descricao in encontrados}
    tabela_html = ['<div style="overflow-x:auto;width:100%;border-radius:12px;border:1px solid #52627b">']
    tabela_html.append('<table style="border-collapse:collapse;min-width:1100px;width:max-content;text-align:center;font-size:13px">')
    tabela_html.append('<thead><tr><th colspan="2" style="background:#111827;color:#fff;min-width:265px;padding:14px">1º RCG<br>DRAGÕES DA INDEPENDÊNCIA</th>')
    for d in datas:
        fundo = "#c63229" if d.weekday() >= 5 else "#a9dd85"
        cor = "#ffe6a0" if d.weekday() >= 5 else "#15371d"
        tabela_html.append(f'<th style="background:{fundo};color:{cor};min-width:190px;padding:10px;border:1px solid #566276">{d:%d/%m/%Y}<br>{NOMES_DIAS[d.weekday()]}</th>')
    tabela_html.append("</tr></thead><tbody>")
    for grupo, funcoes in FUNCOES_PREVISAO.items():
        for pos, funcao in enumerate(funcoes):
            tabela_html.append("<tr>")
            if pos == 0:
                tabela_html.append(f'<th rowspan="{len(funcoes)}" style="background:{CORES_PREVISAO[grupo]};color:#13252a;border:1px solid #52627b;padding:12px">{escape(grupo)}</th>')
            tabela_html.append(f'<th style="background:{CORES_PREVISAO[grupo]};color:#13252a;border:1px solid #52627b;padding:12px;min-width:140px">{escape(funcao)}</th>')
            chave = f"{grupo}::{funcao}"
            for d in datas:
                fundo = "#bc3029" if d.weekday() >= 5 else "#f1f4fa"
                cor = "#ffe9ad" if d.weekday() >= 5 else "#19283a"
                valor = escape(valores.get((d.isoformat(), chave), "")).replace("\n", "<br>") or "—"
                tabela_html.append(f'<td style="background:{fundo};color:{cor};border:1px solid #52627b;max-width:220px;overflow-wrap:anywhere;padding:12px;height:56px">{valor}</td>')
            tabela_html.append("</tr>")
    tabela_html.append("</tbody></table></div>")
    st.markdown("".join(tabela_html), unsafe_allow_html=True)
    st.markdown("#### ✏️ Preencher e corrigir a previsão")
    rotulos_prev = [d.strftime("%d/%m/%Y") for d in datas]
    dados_prev = []
    for grupo, funcao, chave in linhas:
        row = {"Grupo": grupo, "Função": funcao}
        for d, titulo in zip(datas, rotulos_prev):
            row[titulo] = valores.get((d.isoformat(), chave), "")
        dados_prev.append(row)
    original_prev = pd.DataFrame(dados_prev)
    editado_prev = st.data_editor(
        original_prev, hide_index=True, use_container_width=True, height=490,
        disabled=["Grupo", "Função"],
        column_config={titulo: st.column_config.TextColumn(titulo, width="medium") for titulo in rotulos_prev},
        key=f"previsao_editor_{inicio.isoformat()}_{qtd}"
    )
    if st.button("💾 Salvar previsão", type="primary", key="salvar_previsao"):
        total = 0
        with db:
            for idx, (_, _, chave) in enumerate(linhas):
                for d, titulo in zip(datas, rotulos_prev):
                    novo = str(editado_prev.iloc[idx][titulo] or "").strip()
                    antigo = str(original_prev.iloc[idx][titulo] or "").strip()
                    if novo == antigo:
                        continue
                    if novo:
                        db.execute(
                            "INSERT OR REPLACE INTO previsao_servico(dia,funcao,descricao) VALUES (?,?,?)",
                            (d.isoformat(), chave, novo)
                        )
                    else:
                        db.execute("DELETE FROM previsao_servico WHERE dia=? AND funcao=?",
                                   (d.isoformat(), chave))
                    total += 1
        st.success(f"{total} alteração(ões) na previsão salvas.")
        if total:
            st.rerun()
    st.warning("O armazenamento do Render gratuito ainda é temporário. Não use dados reais até configurarmos persistência e backups.")


with automatico:
    st.subheader("⚙️ Gerador de escala")
    recalcular = st.checkbox("Recalcular somente serviços automáticos", value=True)
    st.write("Cada serviço dura 24 horas. O gerador evita serviços em dias seguidos, com exceção sinalizada se não houver outro militar elegível. Contagens PRETA e VERMELHA são equilibradas separadamente; cada serviço exige ao menos o dia seguinte livre, sempre que possível. Edições manuais são preservadas.")
    if st.button("Gerar escala", type="primary"):
        numero, avisos = gerar(inicio, qtd, recalcular)
        st.success(f"{numero} serviço(s) gerado(s).")
        for aviso in avisos:
            st.warning(aviso)
        if numero:
            st.rerun()
    st.info("O descanso implementado impede, em condições normais, serviço em dois dias consecutivos. Feriados locais, pontos facultativos, regras de antiguidade e descanso maior precisam de validação e ajustes. Revise o resultado antes de utilizar.")

with cadastro:
    topo, acao = st.columns([3, 1], vertical_alignment="center")
    with topo:
        st.subheader("👥 Efetivo cadastrado")
        st.caption("Selecione um militar na lista para editar a ficha à direita.")
    with acao:
        if st.button("➕ Adicionar militar" if not st.session_state.get("mostrar_cadastro") else "✕ Fechar cadastro",
                     use_container_width=True, type="primary"):
            st.session_state["mostrar_cadastro"] = not st.session_state.get("mostrar_cadastro", False)
            st.rerun()

    if st.session_state.get("mostrar_cadastro", False):
        with st.container(border=True):
            st.markdown("### ➕ Novo cadastro de militar")
            st.caption("Preencha os campos abaixo. A numeração é atribuída automaticamente.")
            with st.form("cadastrar", clear_on_submit=True):
                proxima_ordem = int(db.execute(
                    "SELECT COALESCE(MAX(ord), 0) + 1 FROM militares"
                ).fetchone()[0])
                st.text_input("Número de ordem automático", value=str(proxima_ordem), disabled=True)
                nome = st.text_input("Nome completo")
                col_su, col_status = st.columns(2)
                with col_su:
                    su = st.selectbox("Subunidade (SU)", SU)
                with col_status:
                    status = st.selectbox("Status", ["ATIVO", "FÉRIAS", "BAIXADO", "CURSO", "OUTRO"])
                tipo = st.selectbox("Tipo de escala", ["AMBAS", "PRETA", "VERMELHA", "FORA"])
                obs = st.text_area("Observações", height=110)
                if st.form_submit_button("✅ Cadastrar militar", type="primary", use_container_width=True):
                    if not nome.strip():
                        st.error("Informe o nome.")
                    else:
                        try:
                            db.execute("BEGIN IMMEDIATE")
                            ordem_gerada = int(db.execute(
                                "SELECT COALESCE(MAX(ord), 0) + 1 FROM militares"
                            ).fetchone()[0])
                            db.execute(
                                "INSERT INTO militares(ord,nome,su,status,obs,tipo) VALUES (?,?,?,?,?,?)",
                                (ordem_gerada, nome.strip(), su, status, obs, tipo)
                            )
                            db.commit()
                        except Exception:
                            db.rollback()
                            raise
                        st.session_state["mostrar_cadastro"] = False
                        st.toast(f"Militar cadastrado com número {ordem_gerada}.", icon="✅")
                        st.rerun()

    lista, ficha = st.columns([1, 1.4], gap="large")
    with lista:
        if ps_all.empty:
            st.info("Nenhum militar cadastrado. Clique em + Adicionar militar.")
        else:
            visivel = ps_all.rename(columns={
                "ord": "Ord", "nome": "Nome", "su": "SU",
                "status": "Status", "obs": "Observações", "tipo": "Escala"
            })
            resultado = st.dataframe(
                visivel[["Ord", "Nome", "SU", "Status", "Escala", "Observações"]],
                use_container_width=True,
                hide_index=True,
                height=510,
                on_select="rerun",
                selection_mode="single-row",
                key="selecao_efetivo"
            )
            selecionadas = resultado.selection.rows
            if selecionadas:
                st.session_state["militar_selecionado"] = int(ps_all.iloc[selecionadas[0]]["id"])
            elif "militar_selecionado" not in st.session_state:
                st.caption("Selecione uma linha para editar.")
    with ficha:
        selecionado_id = st.session_state.get("militar_selecionado")
        registro = ps_all[ps_all.id == selecionado_id] if selecionado_id is not None else ps_all.iloc[0:0]
        if registro.empty:
            st.info("📋 Selecione um militar na lista à esquerda para abrir a ficha aqui.")
        else:
            militar = registro.iloc[0]
            st.markdown(f"### ✏️ Editar militar nº {int(militar['ord'])}")
            st.caption("Ficha ampliada: edite os campos e clique em Salvar alterações.")
            with st.form(f"editar_militar_{int(militar['id'])}"):
                st.text_input("Número de ordem (automático)", value=str(int(militar["ord"])), disabled=True)
                novo_nome = st.text_input("Nome", value=str(militar["nome"]))
                novo_su = st.selectbox("SU", SU, index=SU.index(str(militar["su"])) if str(militar["su"]) in SU else 0)
                statuses = ["ATIVO", "FÉRIAS", "BAIXADO", "CURSO", "OUTRO"]
                status_atual = str(militar["status"])
                if status_atual not in statuses:
                    statuses.append(status_atual)
                novo_status = st.selectbox("Status", statuses, index=statuses.index(status_atual))
                tipos = ["AMBAS", "PRETA", "VERMELHA", "FORA"]
                tipo_atual = str(militar["tipo"])
                if tipo_atual not in tipos:
                    tipos.append(tipo_atual)
                novo_tipo = st.selectbox("Tipo de escala", tipos, index=tipos.index(tipo_atual))
                nova_obs = st.text_area("Observações", value=str(militar["obs"] or ""), height=130)
                salvar = st.form_submit_button("💾 Salvar alterações", type="primary", use_container_width=True)
                if salvar:
                    if not novo_nome.strip():
                        st.error("Informe o nome.")
                    else:
                        with db:
                            db.execute(
                                "UPDATE militares SET nome=?,su=?,status=?,obs=?,tipo=? WHERE id=?",
                                (novo_nome.strip(), novo_su, novo_status,
                                 nova_obs, novo_tipo, int(militar["id"]))
                            )
                        st.success("Informações atualizadas.")
                        st.rerun()

            st.divider()
            with st.popover("🗑️ Excluir militar", use_container_width=True):
                st.error("Esta exclusão é permanente.")
                st.write(f"Militar: **{militar['nome']}** — ordem {int(militar['ord'])}.")
                st.caption("As marcações de serviço e impedimento deste militar também serão apagadas.")
                confirmar = st.checkbox(
                    "Confirmo que desejo excluir este militar e seus registros de escala",
                    key=f"confirmar_exclusao_{int(militar['id'])}"
                )
                if st.button(
                    "Excluir definitivamente",
                    type="primary",
                    disabled=not confirmar,
                    use_container_width=True,
                    key=f"botao_excluir_{int(militar['id'])}"
                ):
                    mid = int(militar["id"])
                    try:
                        db.execute("BEGIN IMMEDIATE")
                        db.execute("DELETE FROM escala WHERE militar_id = ?", (mid,))
                        cursor = db.execute("DELETE FROM militares WHERE id = ?", (mid,))
                        if cursor.rowcount != 1:
                            raise ValueError("O cadastro não foi encontrado. Atualize a página.")
                        db.commit()
                    except Exception as exc:
                        db.rollback()
                        st.error(f"Não foi possível excluir o militar: {exc}")
                    else:
                        st.session_state.pop("militar_selecionado", None)
                        st.toast("Militar e registros de escala excluídos.", icon="✅")
                        st.rerun()
