# Escala Dragão — Escalas do 1º RCG

Protótipo de escala de serviço em Python e Streamlit.

## Recursos
- Quadro de serviço com datas, nomes e categorias PRETA e VERMELHA
- Geração automática simplificada, com uma vaga por dia
- Edição manual de SV, IMP e ausência de serviço
- Preservação das alterações manuais na regeneração
- Cadastro de militares e exportação CSV

## Executar localmente

```bash
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

O aplicativo cria automaticamente um banco SQLite local `escala_local.db`, ignorado pelo Git.

**Segurança:** protótipo sem login, controle de acesso por SU, auditoria ou regras oficiais completas de descanso e revezamento. Use apenas dados fictícios durante os testes. Não disponibilize o serviço na internet nem coloque dados operacionais ou nominais no GitHub.

## Regras atuais
- Segunda a sexta: PRETA; sábado e domingo: VERMELHA
- Só militares ATIVO e habilitados à categoria são considerados
- Prioriza menor contagem de serviços já registrados
- Alterações manuais não são substituídas automaticamente
- Não é uma escala oficial; requer revisão e validação humana


## Login administrativo (Render)
Configure em **Render → Web Service → Environment**:
- `ESCALA_DRAGAO_ADMIN_USER`: identificador do administrador
- `ESCALA_DRAGAO_ADMIN_PASSWORD`: senha única forte de pelo menos 12 caracteres

O aplicativo **bloqueia o acesso** se as variáveis não estiverem configuradas. Nunca salve credenciais no repositório. Após salvar as variáveis, atualize a implantação do serviço.

**Limitações atuais:** o login é de administrador único e não possui usuários por SU, persistência de sessão entre reinícios, bloqueio global de tentativas nem trilha de auditoria. O limitador de tentativas é apenas por sessão do navegador e não substitui uma solução de autenticação corporativa. O banco SQLite local do Render gratuito é efêmero; não use esta implantação para dados reais ou escala operacional. Para produção, use autenticação centralizada, HTTPS, autorização de cada operação no backend, armazenamento persistente e auditoria.
