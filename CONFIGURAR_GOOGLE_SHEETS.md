# Configurar o armazenamento Google Sheets — Escala Dragão

## Importante
- Execute este roteiro primeiro com militares fictícios.
- O Google Sheets será o armazenamento autoritativo; o site mantém um cache SQLite **somente em memória**.
- A aba `Estado` armazena revisões codificadas em base64 e **não deve ser editada**.
- Não é um banco relacional nem uma solução pronta para dados operacionais reais.
- O histórico de revisões guarda as **15 últimas versões**; faça backups independentes regularmente.
- Cadastros perdidos no SQLite antigo não são recuperados automaticamente.
- Se mais de uma instância do Render for utilizada, atualizações concorrentes podem causar conflito. A escrita conflitante é recusada, nunca substituída silenciosamente. Um reinício da instância recarrega o estado mais recente.

## Etapa 1 — Criar planilha
1. Em https://sheets.google.com crie uma planilha chamada `Escala Dragão - Dados`.
2. Mantenha a planilha **Restrita**; não altere para "Qualquer pessoa com o link".
3. Na URL da planilha, copie somente o texto entre `/d/` e `/edit`: esse é o `SPREADSHEET_ID`.

## Etapa 2 — Criar Apps Script
1. Dentro da planilha vá em **Extensões → Apps Script**.
2. Apague o código inicial do arquivo `Código.gs`.
3. Copie e cole **todo o conteúdo** do arquivo `apps_script_escala.gs` deste repositório.
4. Salve.
5. No Apps Script abra **Configurações do projeto → Propriedades do script**.
6. Cadastre as duas propriedades:
   - `SPREADSHEET_ID` = ID da planilha.
   - `API_TOKEN` = token aleatório secreto com **mínimo 32 caracteres**.
7. Para gerar o token no computador, execute Python: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
   Guarde o token em local seguro e **não o cole em arquivos do GitHub**.

## Etapa 3 — Implantar Apps Script
1. Selecione **Implantar → Nova implantação → Aplicativo da Web**.
2. **Executar como:** você (o proprietário autorizado da planilha).
3. **Quem pode acessar:** qualquer pessoa (o endpoint depende do token secreto no POST; a planilha continua privada). Se a organização não autoriza esse tipo de endpoint, **não implante**: será necessário outro modelo de autenticação.
4. Autorize o acesso à planilha e copie a URL terminada em `/exec`.
5. O token **nunca deve constar da URL** nem das mensagens deste chat.

## Etapa 4 — Variáveis no Render
No serviço `Banco-de-Dados-1-Rcg` abra **Environment** e configure:
- `GOOGLE_APPS_SCRIPT_URL` = URL completa do aplicativo da Web, final `/exec`.
- `GOOGLE_SHEETS_TOKEN` = **o mesmo** `API_TOKEN` configurado no script.

O site não requer `DATABASE_URL`. O arquivo `database.py` é legado e não é importado pelo app.
Depois, faça **Manual Deploy → Deploy latest commit**. Se o Render estiver com **Auto Deploy**, ele pode tentar publicar a alteração antes da configuração; o site bloqueará o banco até as variáveis existirem.

## Etapa 5 — Teste de persistência
1. Abra o site, entre com o login e cadastre **um militar fictício**.
2. Confira a aba `Estado` na planilha: A1 deve ser um número maior que zero.
3. Reinicie o serviço Render ou faça um novo deploy.
4. O militar fictício deve continuar aparecendo.
5. Teste também previsão, exceção de data e edição. Mantenha backups independentes.

## Limites e segurança
- Apps Script possui cotas de execução e chamadas; uso intenso pode exigir PostgreSQL. 
- Não compartilhe a planilha publicamente; restrinja edição e acesso à conta institucional autorizada.
- A autenticação do endpoint depende de um segredo no lado servidor. Adicione controle de acesso por usuário/SU e auditoria antes de dados reais.
- A revisão é salva em uma aba de snapshots codificados, não em tabelas Google Sheets editáveis diretamente.
- Se o site indicar **CONFLITO**, pare de editar e reinicie o serviço para carregar a revisão mais atual.

## Planilha AG online (consulta contínua)

Para usar a planilha AG como fonte de efetivo, sem fazer downloads repetidos:

1. Abra o projeto Apps Script já ligado ao banco da Escala Dragão.
2. Substitua o código do editor pelo arquivo atualizado `apps_script_escala.gs` deste repositório.
3. Nas **Propriedades do script**, adicione:
   - `AG_SPREADSHEET_ID` = `1B83jYoPQ8FHNq2-gMHLF-CdC5xTWYFJb5bH_ifaiQbo`.
4. A conta que executa o Apps Script precisa ter permissão de leitura da planilha AG.
5. Em **Implantar → Gerenciar implantações → Editar**, selecione **Nova versão** e implante.
6. Publique o app.py atualizado no Render e acesse o item **Efetivo online — AG** no menu lateral.
7. Selecione uma aba para ver os dados atuais. Para atualizar os valores, recarregue a página.

**Proteção dos dados:** a consulta AG é somente leitura e não modifica o banco da Escala Dragão nem os históricos de serviço. Antes de ativar sincronização automática de cadastros, identifique e confira na AG a coluna de nome, SU, status e um identificador estável. Nunca exclua cadastros/históricos apenas porque uma linha foi removida da AG. Não cole tokens ou senhas neste repositório.

A conexão ao Google Sheets depende de um endpoint Apps Script autenticado, com cotas e limites de tempo/tamanho. Não use informações nominais reais sem autorização institucional e controle de acesso adequado.
