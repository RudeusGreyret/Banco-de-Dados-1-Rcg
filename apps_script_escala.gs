/**
 * Escala Dragão — ponte segura entre o Streamlit e o Google Sheets.
 *
 * Configurar nas PROPRIEDADES DO SCRIPT:
 *   SPREADSHEET_ID = ID da planilha privada
 *   API_TOKEN = token aleatório com 32 caracteres ou mais
 *
 * Implantar como aplicativo da Web (executar como proprietário).
 * O acesso público ao endpoint EXIGE token no corpo de cada requisição.
 * Não use sem aprovação para dados nominais reais.
 *
 * Abas "Estado" possuem snapshots JSON em base64, revisões anteriores
 * são preservadas. Nunca edite a aba Estado manualmente.
 */
const TABELAS = ["militares", "escala", "previsao_servico", "categoria_dia"];
const LIMITE_CHUNK = 30000;
const RETER_REVISOES = 15;

function resposta(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function abaEstado_() {
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty("SPREADSHEET_ID");
  if (!id) throw new Error("SPREADSHEET_ID ausente nas propriedades do script");
  const ss = SpreadsheetApp.openById(id);
  let sheet = ss.getSheetByName("Estado");
  if (!sheet) {
    sheet = ss.insertSheet("Estado");
    sheet.getRange("A1").setValue(0);
    sheet.getRange("A2:C2").setValues([["revisao", "parte", "conteudo_base64"]]);
    sheet.setFrozenRows(2);
  }
  return sheet;
}

function versao_(sheet) {
  return Number(sheet.getRange("A1").getValue()) || 0;
}

function snapshotVazio_() {
  return {
    militares: [], escala: [], previsao_servico: [], categoria_dia: []
  };
}

function carregar_(sheet) {
  const revision = versao_(sheet);
  if (revision === 0) return {revision: 0, snapshot: snapshotVazio_()};
  const ultima = sheet.getLastRow();
  const dados = ultima >= 3 ? sheet.getRange(3, 1, ultima - 2, 3).getValues() : [];
  const partes = dados.filter(row => Number(row[0]) === revision)
    .sort((a, b) => Number(a[1]) - Number(b[1]));
  if (!partes.length) throw new Error("Revisão atual incompleta");
  for (let i = 0; i < partes.length; i++) {
    if (Number(partes[i][1]) !== i + 1 || !partes[i][2]) {
      throw new Error("Partes de snapshot ausentes");
    }
  }
  const codificado = partes.map(row => String(row[2])).join("");
  const json = Utilities.newBlob(Utilities.base64DecodeWebSafe(codificado))
    .getDataAsString("UTF-8");
  const snapshot = JSON.parse(json);
  if (!TABELAS.every(t => Array.isArray(snapshot[t]))) {
    throw new Error("Snapshot incorreto");
  }
  return {revision, snapshot};
}

function validar_(snapshot) {
  if (!snapshot || typeof snapshot !== "object" ||
      !TABELAS.every(t => Array.isArray(snapshot[t]))) {
    throw new Error("Estrutura da planilha inválida");
  }
}

function salvar_(sheet, request) {
  const atual = versao_(sheet);
  if (Number(request.expected_revision) !== atual) {
    throw new Error("CONFLITO: dados alterados em outra sessão. Reinicie o serviço para recarregar o banco.");
  }
  validar_(request.snapshot);
  const dados = JSON.stringify(request.snapshot);
  const base64 = Utilities.base64EncodeWebSafe(Utilities.newBlob(dados).getBytes());
  const partes = [];
  for (let p = 0; p < base64.length; p += LIMITE_CHUNK) {
    partes.push(base64.substring(p, p + LIMITE_CHUNK));
  }
  const nova = atual + 1;
  const linhas = partes.map((chunk, index) => [nova, index + 1, chunk]);
  const primeira = sheet.getLastRow() + 1;
  sheet.getRange(primeira, 1, linhas.length, 3).setNumberFormat("@");
  sheet.getRange(primeira, 1, linhas.length, 3).setValues(linhas);
  SpreadsheetApp.flush();
  // O marcador A1 só muda após todas as partes serem gravadas.
  sheet.getRange("A1").setValue(nova);
  SpreadsheetApp.flush();
  // Mantém cópias de revisões anteriores, permitindo recuperação.
  try {
    const total = sheet.getLastRow();
    if (total > 2) {
      const historico = sheet.getRange(3, 1, total - 2, 1).getValues();
      let removidas = 0;
      for (let i = 0; i < historico.length; i++) {
        if (Number(historico[i][0]) < nova - RETER_REVISOES + 1) removidas++;
        else break;
      }
      if (removidas > 0) sheet.deleteRows(3, removidas);
    }
  } catch (err) {
    console.log("Limpeza de versões antigas falhou: " + err);
  }
  return {revision: nova};
}

/**
 * Consulta SOMENTE LEITURA da planilha AG.
 * A planilha AG é definida nas Propriedades do Script, não no código.
 * O usuário que executa o Apps Script precisa ter acesso a essa planilha.
 * Mantemos a origem isolada da planilha Estado, sem sobrescrever cadastros.
 */
function consultarAg_() {
  const propriedades = PropertiesService.getScriptProperties();
  const id = propriedades.getProperty("AG_SPREADSHEET_ID");
  if (!id) throw new Error("AG_SPREADSHEET_ID ausente nas propriedades do script");
  const ss = SpreadsheetApp.openById(id);
  const abas = ss.getSheets().map(aba => {
    const linhas = aba.getLastRow();
    const colunas = aba.getLastColumn();
    if (linhas === 0 || colunas === 0) {
      return {nome: aba.getName(), linhas: [], quantidade_linhas: 0};
    }
    if (linhas > 3000 || colunas > 50) {
      throw new Error("A aba " + aba.getName() + " excede o limite de leitura. Defina um intervalo menor.");
    }
    return {
      nome: aba.getName(),
      quantidade_linhas: linhas,
      linhas: aba.getRange(1, 1, linhas, colunas).getDisplayValues()
    };
  });
  return {abas: abas};
}

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    const request = JSON.parse(e.postData.contents || "{}");
    const esperado = PropertiesService.getScriptProperties().getProperty("API_TOKEN");
    if (!esperado || esperado.length < 32 || request.token !== esperado) {
      return resposta({ok: false, error: "Não autorizado"});
    }
    lock.waitLock(25000);
    const sheet = abaEstado_();
    let result;
    if (request.action === "load") {
      result = carregar_(sheet);
    } else if (request.action === "ag_load") {
      result = consultarAg_();
    } else if (request.action === "save") {
      result = salvar_(sheet, request);
    } else {
      throw new Error("Ação desconhecida");
    }
    return resposta(Object.assign({ok: true}, result));
  } catch (err) {
    console.error(err);
    return resposta({ok: false, error: String(err.message || err)});
  } finally {
    if (lock.hasLock()) lock.releaseLock();
  }
}
