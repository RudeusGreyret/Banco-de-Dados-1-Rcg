# Escala Dragão — 1º RCG

Aplicativo Streamlit com escala automática, edição manual e cadastro de efetivo.

## Implantação segura

Esta mudança está inicialmente na branch `preparar-banco-persistente`. **Não publique antes de configurar um banco PostgreSQL persistente e testar a conexão.**

1. Crie um PostgreSQL gerenciado (por exemplo, Supabase).
2. No Render → Environment, configure `DATABASE_URL` com a string de conexão PostgreSQL, mantendo-a **secreta**.
3. Confira `SISBOL_ADMIN_USER` e `SISBOL_ADMIN_PASSWORD` já configurados.
4. Atualize o ambiente de testes primeiro, com nomes fictícios.
5. Somente após validar, atualize o serviço principal.

A aplicação **não inicia no Render sem DATABASE_URL** para impedir novos cadastros no SQLite temporário. Localmente, o SQLite continua disponível para testes.

## Cópias de segurança

Na aba Escala automática, exporte separadamente `backup_militares.csv` e `backup_escala.csv`. Guarde em local seguro. Esse backup manual é complementar às rotinas de backup gerenciadas do PostgreSQL.

## Limitações

- A migração não recupera automaticamente arquivos SQLite perdidos de instâncias antigas.
- O login é de administrador único; não há ainda autorização por SU, auditoria ou regras operacionais completas.
- Não use cadastros nominais ou escalas reais até validar segurança, hospedagem, backups, controle de acesso e conformidade institucional.
