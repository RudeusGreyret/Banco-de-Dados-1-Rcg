"""Autenticação inicial: administrador único, credenciais via ambiente Render."""
import hmac
import os
import time
import streamlit as st

def exigir_login():
    usuario_config = os.environ.get("SISBOL_ADMIN_USER", "").strip()
    senha_config = os.environ.get("SISBOL_ADMIN_PASSWORD", "")
    if not usuario_config or len(senha_config) < 12:
        st.error("Acesso bloqueado: configure SISBOL_ADMIN_USER e SISBOL_ADMIN_PASSWORD (mínimo 12 caracteres) no Render.")
        st.stop()

    if st.session_state.get("autenticado") is True:
        with st.sidebar:
            st.caption(f"Conectado: {usuario_config} (administrador)")
            if st.button("Sair da conta", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        return

    st.title("🔐 Escala Dragão — Acesso restrito")
    st.info("Entre com suas credenciais de administrador.")
    falhas = st.session_state.get("falhas_login", 0)
    proxima_tentativa = st.session_state.get("proxima_tentativa", 0)
    if time.monotonic() < proxima_tentativa:
        st.error("Muitas tentativas nesta sessão. Tente novamente mais tarde.")
        st.stop()
    with st.form("login_sisbol"):
        usuario = st.text_input("Usuário", autocomplete="username")
        senha = st.text_input("Senha", type="password", autocomplete="current-password")
        entrar = st.form_submit_button("Entrar", type="primary", use_container_width=True)
    if entrar:
        valido = (hmac.compare_digest(usuario, usuario_config) and
                  hmac.compare_digest(senha, senha_config))
        if valido:
            st.session_state["autenticado"] = True
            st.session_state["falhas_login"] = 0
            st.session_state["proxima_tentativa"] = 0
            st.rerun()
        falhas += 1
        st.session_state["falhas_login"] = falhas
        if falhas >= 5:
            st.session_state["proxima_tentativa"] = time.monotonic() + 300
            st.session_state["falhas_login"] = 0
            st.error("Tentativas excedidas nesta sessão.")
        else:
            st.error("Usuário ou senha incorretos.")
    st.stop()
