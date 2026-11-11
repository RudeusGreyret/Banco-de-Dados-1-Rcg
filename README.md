# SisBol — Escalas do 1º RCG

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
