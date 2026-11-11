# Escala Dragão — 1º RCG

Site de previsão e geração de escalas de serviço em Streamlit.

## Recursos
- Login administrativo por variáveis `SISBOL_ADMIN_USER` e `SISBOL_ADMIN_PASSWORD` (mínimo 12 caracteres).
- Cadastro, edição, exclusão e numeração automática de militares.
- Quadro de serviço de 24h com contagem de dias sem serviço, edição manual e exportação CSV.
- Escalas PRETA (dias úteis) e VERMELHA (finais de semana e feriados nacionais); ajuste extraordinário por data.
- Previsão visual por função (OF DIA, ADJUNTO, CMT GDA, GDA, HFA, MOT DIA etc.).
- Cinco escalas independentes: Oficial de Dia, Adjunto, Comandante da Guarda, Cabo da Guarda e Motorista de Dia.
- Cada escala mostra **0** quando o militar está de serviço e conta **1, 2, 3...** nos dias seguintes.
- Serviço de 24 horas: a geração evita militares em dias consecutivos quando houver outra pessoa elegível; apresenta aviso de exceção quando não houver.
- Contagens PRETA/VERMELHA equilibradas por escala, sem sobrescrever vagas preenchidas.
- Quadro com Ord/Nome/SU fixos, serviço 0 destacado e classificação preta/vermelha.
- Quantidade padrão: 2 cabos da guarda e 1 motorista por dia, com configuração de reforços por data.
- Menu "Militares por Escala" para cadastrar, organizar e transferir o efetivo entre as cinco escalas.

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

## Como usar as cinco escalas
1. Entre em **Militares por Escala** e atribua militares à função desejada. Os militares já cadastrados não precisam ser duplicados.
2. Selecione uma das cinco escalas no menu lateral.
3. Ajuste o período (7, 14, 21, 28 ou 31 dias).
4. Confira o quadro: **0** indica serviço, números maiores indicam dias sem serviço.
5. Clique em **Gerar apenas vagas livres** para preencher sem substituir o que já estiver escalado.
6. Para corrigir um dia, escolha **Correção manual por data**, selecione os militares e salve.
7. Para alterar quantidade de cabos ou motoristas, acesse **Previsão da Escala → Quantidade por data**.
8. Antes de uso operacional, revise alertas e confira a planilha/backup.

**Importante:** o código armazena a distribuição por função nos registros internos da aba Estado do Apps Script. Não é necessária alteração do Apps Script para esse recurso. O gerador geral antigo foi mantido apenas por compatibilidade e não substitui as cinco novas escalas.
