# Escala Dragão — 1º RCG

Site de previsão e geração de escalas de serviço em Streamlit.

## Recursos
- Login administrativo por variáveis `SISBOL_ADMIN_USER` e `SISBOL_ADMIN_PASSWORD` (mínimo 12 caracteres).
- Cadastro, edição, exclusão e numeração automática de militares.
- Quadro de serviço de 24h com contagem de dias sem serviço, edição manual e exportação CSV.
- Escalas PRETA (dias úteis) e VERMELHA (finais de semana e feriados nacionais); ajuste extraordinário por data.
- Previsão visual por função (OF DIA, ADJUNTO, CMT GDA, GDA, HFA, MOT DIA etc.).
- Armazenamento remoto na planilha Google via Apps Script. **Não usa SQLite no disco do Render.**

## Instalação
O Render usa:
- Build Command: `pip install -r requirements.txt`
- Start Command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`

Configurar em Render → Environment:
- `SISBOL_ADMIN_USER`: usuário administrador.
- `SISBOL_ADMIN_PASSWORD`: senha forte de 12 caracteres ou mais.
- `GOOGLE_APPS_SCRIPT_URL`: URL do aplicativo Apps Script terminada em `/exec`.
- `GOOGLE_SHEETS_TOKEN`: token aleatório secreto (mínimo 32 caracteres), igual ao `API_TOKEN` do Apps Script.

Siga [CONFIGURAR_GOOGLE_SHEETS.md](CONFIGURAR_GOOGLE_SHEETS.md) para criar a planilha e implantar o Apps Script.

## Avisos de segurança
O site bloqueia o carregamento se o Google Sheets não estiver configurado. Os dados perdidos do SQLite anterior **não são restaurados automaticamente**. Esta integração é uma implementação inicial sujeita a cotas e limites de concorrência; precisa ser testada com dados fictícios. Não utilize dados nominais/operacionais reais antes de obter autorização institucional, validar autenticação/autorização por SU, auditoria e backups externos. Nunca commite tokens, planilhas privadas ou senhas no GitHub.
