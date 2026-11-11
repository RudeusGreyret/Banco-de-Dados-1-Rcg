"""Escalas individuais inspiradas na ESCALA PADRÃO 2026.

Os registros são mantidos na tabela previsao_servico, já sincronizada
com o Google Sheets. Não altera as escalas anteriores.
"""
from datetime import timedelta
import pandas as pd
import streamlit as st

SERVICOS = [
    "Oficial de Dia",
    "Adjunto de Dia",
    "Comandante da Guarda",
    "Cabo da Guarda",
    "Motorista de Dia",
]
PREFIXO = "SERVICO::"
CONFIGS = {
    "Cabo da Guarda": ("__CONFIG__::CABOS_GUARDA", 2),
    "Motorista de Dia": ("__CONFIG__::MOTORISTA_DIA", 1),
}


def _chave(servico, posicao):
    return f"{PREFIXO}{servico}::{posicao}"


def _quantidade(db, servico, dia):
    chave, padrao = CONFIGS.get(servico, (None, 1))
    if not chave:
        return padrao
    registro = db.execute(
        "SELECT descricao FROM previsao_servico WHERE dia=? AND funcao=?",
        (dia.isoformat(), chave)
    ).fetchone()
    try:
        return max(1, min(int(registro[0]), 10)) if registro else padrao
    except (TypeError, ValueError):
        return padrao


def _ler_servicos(db):
    dados = db.execute(
        "SELECT dia,funcao,descricao FROM previsao_servico "
        "WHERE funcao LIKE 'SERVICO::%' AND dia NOT LIKE '\\_%' ESCAPE '\\'"
    ).fetchall()
    resultado = {}
    for dia, chave, valor in dados:
        if not str(chave).startswith(PREFIXO):
            continue
        try:
            mid = int(valor)
            resultado[(str(dia), str(chave))] = mid
        except (ValueError, TypeError):
            continue
    return resultado


def _todos_servicos(db, marcacoes):
    # Inclui serviços históricos registrados no quadro principal.
    result = {}
    for (data, chave), mid in marcacoes.items():
        result.setdefault(data, set()).add(mid)
    for dia, mid in db.execute(
        "SELECT dia,militar_id FROM escala WHERE valor='SV'"
    ).fetchall():
        result.setdefault(str(dia), set()).add(int(mid))
    return result


def _pessoas_habilitadas(ps, lotacoes, servico, tipo):
    if ps.empty:
        return []
    return [
        p for p in ps.itertuples()
        if lotacoes.get(int(p.id)) == servico
        and str(p.status).strip().upper() in ("ATIVO", "PRONTO")
        and str(p.tipo).strip().upper() in ("AMBAS", tipo)
    ]


def _contagens_por_tipo(marcacoes, servico, categoria):
    contagens = {}
    for (ds, chave), mid in marcacoes.items():
        if chave.startswith(f"{PREFIXO}{servico}::"):
            tipo = categoria(__import__("datetime").date.fromisoformat(ds))
            contagens[(mid, tipo)] = contagens.get((mid, tipo), 0) + 1
    return contagens


def _matriz(db, ps_escala, servico, datas, marcacoes):
    if ps_escala.empty:
        return pd.DataFrame()
    anteriores = {}
    primeiro = datas[0].isoformat()
    for (ds, chave), mid in marcacoes.items():
        if ds < primeiro and chave.startswith(f"{PREFIXO}{servico}::"):
            if mid not in anteriores or ds > anteriores[mid]:
                anteriores[mid] = ds
    nomes_dias = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
    rows = []
    for p in ps_escala.itertuples():
        mid = int(p.id)
        anterior = anteriores.get(mid)
        dias = 0
        row = {
            "Ord": int(p.ord), "Nome": str(p.nome), "SU": str(p.su),
            "Status": str(p.status), "OBS": str(p.obs),
            "Escala": str(p.tipo)
        }
        for d in datas:
            titulo = f"{d:%d/%m} {nomes_dias[d.weekday()]}"
            escalado = any(
                m == mid and data == d.isoformat()
                and chave.startswith(f"{PREFIXO}{servico}::")
                for (data, chave), m in marcacoes.items()
            )
            if escalado:
                row[titulo] = "0"
                anterior = d.isoformat()
                dias = 0
            else:
                if anterior:
                    dias = (d - __import__("datetime").date.fromisoformat(anterior)).days
                else:
                    dias += 1
                row[titulo] = str(dias)
        rows.append(row)
    return pd.DataFrame(rows)


def exibir_escala(db, servico, inicio, qtd, pessoas, lotacoes, categoria):
    """Renderiza quadro, geração e edições da escala selecionada."""
    st.subheader(f"📋 {servico}")
    st.caption(
        "Modelo do Excel: 0 = serviço de 24h; 1, 2, 3… = dias sem serviço. "
        "Ord, Nome e SU são fixos e não são alterados aqui."
    )
    datas = [inicio + timedelta(days=i) for i in range(qtd)]
    marcacoes = _ler_servicos(db)
    equipe = pessoas[
        pessoas.id.apply(lambda mid: lotacoes.get(int(mid)) == servico)
    ].copy() if not pessoas.empty else pessoas.copy()
    a, b, c = st.columns(3)
    a.metric("Militares nesta escala", len(equipe))
    b.metric(
        "Serviços no período",
        sum(1 for (ds, chave) in marcacoes
            if inicio.isoformat() <= ds <= datas[-1].isoformat()
            and chave.startswith(f"{PREFIXO}{servico}::"))
    )
    c.metric("Vagas por dia (padrão)", CONFIGS.get(servico, (None, 1))[1])
    if equipe.empty:
        st.warning(
            "Esta escala ainda não possui militares atribuídos. "
            "Abra 👥 Militares por Escala para cadastrar ou transferir militares."
        )
        return

    df = _matriz(db, equipe, servico, datas, marcacoes)
    st.markdown("#### 🗓️ Quadro de serviço")
    st.caption("🔴 Vermelha = fins de semana, feriados e exceções manuais · ⚫ Preta = dias úteis.")
    colunas = {
        "Ord": st.column_config.NumberColumn("Ord", pinned=True, width="small"),
        "Nome": st.column_config.TextColumn("Nome", pinned=True, width="medium"),
        "SU": st.column_config.TextColumn("SU", pinned=True, width="small"),
    }
    def cor_por_coluna(col):
        if col.name in ("Ord", "Nome", "SU"):
            return ["background-color:#1d405e;color:white"] * len(col)
        dias = {f"{d:%d/%m} {['SEG','TER','QUA','QUI','SEX','SÁB','DOM'][d.weekday()]}": d for d in datas}
        if col.name not in dias:
            return [""] * len(col)
        cor_base = "#ab2c2e" if categoria(dias[col.name]) == "VERMELHA" else "#26374c"
        return [
            "background-color:#efc451;color:#192639;font-weight:bold"
            if str(v) == "0" else f"background-color:{cor_base};color:white"
            for v in col
        ]
    st.dataframe(
        df.style.apply(cor_por_coluna, axis=0),
        hide_index=True, use_container_width=True, height=520,
        column_config=colunas
    )
    st.download_button(
        "⬇️ Exportar quadro CSV",
        df.to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name=f"escala_{servico.lower().replace(' ', '_')}_{inicio:%Y%m%d}.csv",
        mime="text/csv"
    )

    st.markdown("#### ⚙️ Gerar serviços automaticamente")
    st.caption(
        "Preenche somente vagas vazias, sem sobrescrever escalados manualmente. "
        "Equilibra serviços PRETA e VERMELHA separadamente e evita serviço "
        "em dois dias seguidos, exceto se não houver outro militar elegível."
    )
    if st.button("Gerar apenas vagas livres", type="primary", key=f"auto_{servico}"):
        contagens = _contagens_por_tipo(marcacoes, servico, categoria)
        ocupados = _todos_servicos(db, marcacoes)
        avisos, gerados = [], 0
        novas = dict(marcacoes)
        with db:
            for d in datas:
                ds = d.isoformat()
                tipo = categoria(d)
                quant = _quantidade(db, servico, d)
                habilitados = _pessoas_habilitadas(equipe, lotacoes, servico, tipo)
                for slot in range(1, quant + 1):
                    chave = _chave(servico, slot)
                    if (ds, chave) in novas:
                        continue
                    livres_hoje = [
                        p for p in habilitados
                        if int(p.id) not in ocupados.get(ds, set())
                    ]
                    anteriores = (d - timedelta(days=1)).isoformat()
                    seguintes = (d + timedelta(days=1)).isoformat()
                    descansados = [
                        p for p in livres_hoje
                        if int(p.id) not in ocupados.get(anteriores, set())
                        and int(p.id) not in ocupados.get(seguintes, set())
                    ]
                    candidatos = descansados or livres_hoje
                    if not candidatos:
                        avisos.append(f"{d:%d/%m}: vaga {slot} sem militar disponível.")
                        continue
                    if not descansados:
                        avisos.append(
                            f"{d:%d/%m}: folga insuficiente na vaga {slot}. "
                            "Exceção: não havia outra pessoa elegível."
                        )
                    escolhido = min(
                        candidatos,
                        key=lambda p: (
                            contagens.get((int(p.id), tipo), 0),
                            sum(contagens.get((int(p.id), t), 0)
                                for t in ("PRETA", "VERMELHA")),
                            int(p.ord), int(p.id)
                        )
                    )
                    db.execute(
                        "INSERT INTO previsao_servico(dia,funcao,descricao) VALUES (?,?,?) "
                        "ON CONFLICT(dia,funcao) DO UPDATE SET descricao=EXCLUDED.descricao",
                        (ds, chave, str(int(escolhido.id)))
                    )
                    novas[(ds, chave)] = int(escolhido.id)
                    ocupados.setdefault(ds, set()).add(int(escolhido.id))
                    contagens[(int(escolhido.id), tipo)] = (
                        contagens.get((int(escolhido.id), tipo), 0) + 1
                    )
                    gerados += 1
        st.success(f"{gerados} serviço(s) gerado(s).")
        for aviso in avisos:
            st.warning(aviso)
        if gerados:
            st.rerun()

    st.markdown("#### ✏️ Correção manual por data")
    data_manual = st.selectbox(
        "Selecione a data",
        options=datas,
        format_func=lambda d: (
            f"{d:%d/%m/%Y} · {categoria(d)} "
            f"· {_quantidade(db, servico, d)} vaga(s)"
        ),
        key=f"data_manual_{servico}"
    )
    quantidade = _quantidade(db, servico, data_manual)
    elegiveis = equipe.sort_values(["ord", "id"])
    nomes = {
        int(p.id): f"{int(p.ord):03d} — {p.nome} ({p.su})"
        for p in elegiveis.itertuples()
    }
    opcoes = [None] + list(nomes)
    with st.form(f"manual_{servico}_{data_manual.isoformat()}"):
        st.caption(
            "Altere apenas quem fará o serviço na data. Os nomes e números "
            "do cadastro não podem ser editados neste quadro."
        )
        escolhas = []
        for slot in range(1, quantidade + 1):
            chave = _chave(servico, slot)
            atual = marcacoes.get((data_manual.isoformat(), chave))
            index = opcoes.index(atual) if atual in opcoes else 0
            escolhas.append(
                st.selectbox(
                    f"Vaga {slot}", options=opcoes, index=index,
                    format_func=lambda mid: "— Sem militar —" if mid is None else nomes[mid],
                    key=f"manual_{servico}_{data_manual.isoformat()}_{slot}"
                )
            )
        confirmar_excecao = st.checkbox(
            "Confirmo a exceção se houver serviço em dias consecutivos."
        )
        salvar = st.form_submit_button("💾 Salvar correção", type="primary")
    if salvar:
        ids = [int(mid) for mid in escolhas if mid is not None]
        if len(ids) != len(set(ids)):
            st.error("Um mesmo militar não pode ocupar duas vagas no mesmo dia.")
        else:
            dia = data_manual.isoformat()
            anteriores = (data_manual - timedelta(days=1)).isoformat()
            seguintes = (data_manual + timedelta(days=1)).isoformat()
            servicos_gerais = _todos_servicos(db, marcacoes)
            outros_hoje = set()
            for (ds, chave), mid in marcacoes.items():
                if ds == dia and not chave.startswith(f"{PREFIXO}{servico}::"):
                    outros_hoje.add(mid)
            if any(mid in outros_hoje for mid in ids):
                st.error("Um militar já foi escalado em outra função nesta data.")
            else:
                conflito = [
                    mid for mid in ids
                    if mid in servicos_gerais.get(anteriores, set())
                    or mid in servicos_gerais.get(seguintes, set())
                ]
                if conflito and not confirmar_excecao:
                    st.error(
                        "Há militar escalado no dia anterior ou seguinte. "
                        "Revise e marque a confirmação de exceção para continuar."
                    )
                else:
                    with db:
                        for slot, mid in enumerate(escolhas, 1):
                            chave = _chave(servico, slot)
                            if mid is None:
                                db.execute(
                                    "DELETE FROM previsao_servico WHERE dia=? AND funcao=?",
                                    (dia, chave)
                                )
                            else:
                                db.execute(
                                    "INSERT INTO previsao_servico(dia,funcao,descricao) "
                                    "VALUES (?,?,?) ON CONFLICT(dia,funcao) "
                                    "DO UPDATE SET descricao=EXCLUDED.descricao",
                                    (dia, chave, str(int(mid)))
                                )
                    st.success("Escala manual salva.")
                    st.rerun()
    st.info(
        "A distribuição automática é uma previsão e precisa ser conferida. "
        "Ainda não considera todas as restrições e autorizações do serviço."
    )
