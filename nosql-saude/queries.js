/**
 * CONSULTAS AVANCADAS
 * 
 * COMO EXECUTAR:
 *   type queries.js | docker exec -i mongo-primary mongosh saude_uige
 *   ou interativamente: docker exec -it mongo-primary mongosh saude_uige -> load("queries.js")
 */

// Utilitario de formatacao de resultados
function printSection(n, titulo, descricao) {
  print("\n" + "=".repeat(70));
  print(`  QUERY ${n}: ${titulo}`);
  print(`  Objetivo: ${descricao}`);
  print("=".repeat(70));
}

function printResult(label, cursor_or_val) {
  print(`\n  [${label}]`);
  if (typeof cursor_or_val === "object" && cursor_or_val !== null) {
    if (Array.isArray(cursor_or_val)) {
      cursor_or_val.forEach((doc, i) => {
        print(`  ${i+1}. ${JSON.stringify(doc, null, 2)}`);
      });
    } else {
      print(`  ${JSON.stringify(cursor_or_val, null, 2)}`);
    }
  } else {
    print(`  ${cursor_or_val}`);
  }
}

const db_name = "saude_uige";
print(`\nConectado a base de dados: ${db_name}`);
print(`Data de execucao: ${new Date().toISOString()}`);


/* ============================================================================
   QUERY 1: CORRELACAO SURTO-RUTURA
   ============================================================================ */
printSection(1,
  "CORRELACAO SURTO-MALARIA x RUTURA DE STOCK",
  "Identificar municipios com surto ativo E rutura simultanea de antimalaricos"
);

const t1_start = new Date();

const q1_result = db.surtos_malaria.aggregate([
  {
    $match: {
      nivel_alerta: { $in: ["laranja", "vermelho"] },
      data_inicio: { $gte: new Date("2024-01-01") }
    }
  },
  {
    $lookup: {
      from: "alertas",
      let: { mun_id: "$municipio_id", data_surto: "$data_inicio" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$municipio_id", "$$mun_id"] },
                { $in: ["$tipo", ["RUTURA_STOCK", "STOCK_CRITICO"]] },
                { $gte: ["$data_criacao", "$$data_surto"] }
              ]
            }
          }
        },
        {
          $group: {
            _id: "$medicamento_nome",
            n_alertas: { $sum: 1 },
            severidade_max: { $max: "$severidade" }
          }
        }
      ],
      as: "alertas_stock"
    }
  },
  { $match: { "alertas_stock.0": { $exists: true } } },
  {
    $group: {
      _id: {
        municipio_nome: "$municipio_nome",
        municipio_id: "$municipio_id"
      },
      casos_totais: { $sum: "$casos_confirmados" },
      obitos_totais: { $sum: "$obitos" },
      incidencia_media: { $avg: "$incidencia_por_mil" },
      nivel_alerta_max: { $max: "$nivel_alerta_numerico" },
      n_surtos: { $sum: 1 },
      medicamentos_em_rutura: { $push: "$alertas_stock" }
    }
  },
  {
    $project: {
      _id: 0,
      municipio: "$_id.municipio_nome",
      indicadores_surto: {
        casos_confirmados: "$casos_totais",
        obitos: "$obitos_totais",
        incidencia_media_por_mil: { $round: ["$incidencia_media", 1] },
        n_periodos_surto: "$n_surtos",
        nivel_alerta_maximo: "$nivel_alerta_max"
      },
      score_risco_combinado: {
        $add: [
          { $multiply: ["$incidencia_media", 2] },
          { $multiply: ["$nivel_alerta_max", 10] },
          { $size: "$medicamentos_em_rutura" }
        ]
      }
    }
  },
  { $sort: { score_risco_combinado: -1 } },
  { $limit: 10 }
], { allowDiskUse: true }).toArray();

const t1_ms = new Date() - t1_start;
printResult(`Municipios em risco combinado (${q1_result.length} encontrados, ${t1_ms}ms)`, q1_result);


/* ============================================================================
   QUERY 2: SERIE TEMPORAL DE STOCK
   ============================================================================ */
printSection(2,
  "SERIE TEMPORAL: EVOLUCAO MENSAL DO STOCK DE COARTEM POR MUNICIPIO",
  "Analisar tendencia de stock do antimalarico principal ao longo de 6 meses"
);

const t2_start = new Date();

const q2_result = db.registos_stock.aggregate([
  {
    $match: {
      medicamento_codigo: "MED01",
      data_registo: { $gte: new Date("2024-01-01"), $lte: new Date("2024-06-30") }
    }
  },
  {
    $group: {
      _id: { municipio: "$municipio_nome", mes: "$mes", ano: "$ano" },
      stock_medio: { $avg: "$quantidade_atual" },
      stock_minimo_registado: { $min: "$quantidade_atual" },
      stock_maximo_registado: { $max: "$quantidade_atual" },
      total_consumido: { $sum: "$quantidade_saida" },
      total_reposto: { $sum: "$quantidade_entrada" },
      dias_em_rutura: { $sum: { $cond: [{ $eq: ["$status", "rutura"] }, 1, 0] } },
      dias_em_alerta: { $sum: { $cond: [{ $in: ["$status", ["alerta", "critico"]] }, 1, 0] } },
      total_dias: { $sum: 1 }
    }
  },
  {
    $addFields: {
      pct_dias_rutura: { $round: [{ $multiply: [{ $divide: ["$dias_em_rutura", "$total_dias"] }, 100] }, 1] },
      pct_dias_alerta_critico: { $round: [{ $multiply: [{ $divide: ["$dias_em_alerta", "$total_dias"] }, 100] }, 1] },
      cobertura_dias: { $round: [{ $divide: ["$stock_medio", { $max: [1, { $divide: ["$total_consumido", "$total_dias"] }] }] }, 0] }
    }
  },
  {
    $project: {
      _id: 0,
      municipio: "$_id.municipio",
      periodo: { $concat: [{ $toString: "$_id.ano" }, "-", { $toString: "$_id.mes" }] },
      stock_medio: { $round: ["$stock_medio", 0] },
      stock_minimo_registado: 1,
      total_consumido: 1,
      total_reposto: 1,
      pct_dias_rutura: 1,
      pct_dias_alerta_critico: 1,
      cobertura_dias_estimada: "$cobertura_dias"
    }
  },
  { $sort: { municipio: 1, periodo: 1 } },
  { $limit: 48 }
], { allowDiskUse: true }).toArray();

const t2_ms = new Date() - t2_start;
printResult(`Evolucao mensal por municipio (${q2_result.length} registos, ${t2_ms}ms)`, q2_result.slice(0, 6));
print(`  ... [${q2_result.length - 6} registos adicionais omitidos por brevidade]`);


/* ============================================================================
   QUERY 3: GEOESPACIAL
   ============================================================================ */
printSection(3,
  "GEOESPACIAL: UNIDADES COM STOCK DE COARTEM PROXIMAS DE UM SURTO",
  "Localizar as unidades sanitarias mais proximas com stock disponivel do antimalarico principal"
);

const t3_start = new Date();

const ponto_surto = { type: "Point", coordinates: [14.7833, -7.1500] };

const us_com_stock = db.registos_stock.aggregate([
  { $match: { medicamento_codigo: "MED01", status: { $in: ["normal", "alerta"] }, data_registo: { $gte: new Date("2024-06-01") } } },
  { $group: { _id: "$unidade_sanitaria_id", stock_medio_recente: { $avg: "$quantidade_atual" }, ultimo_status: { $last: "$status" } } },
  { $match: { stock_medio_recente: { $gt: 100 } } }
], { allowDiskUse: true }).toArray();

const us_ids_com_stock = us_com_stock.map(x => x._id);

const q3_result = db.unidades_sanitarias.aggregate([
  { $geoNear: { near: ponto_surto, distanceField: "distancia_metros", maxDistance: 150000, spherical: true } },
  { $match: { _id: { $in: us_ids_com_stock } } },
  { $project: { _id: 0, nome: 1, tipo: 1, municipio_nome: 1, distancia_km: { $round: [{ $divide: ["$distancia_metros", 1000] }, 1] }, coordenadas: "$localizacao.coordinates", tem_laboratorio: 1, nivel: 1 } },
  { $sort: { distancia_metros: 1 } },
  { $limit: 5 }
], { allowDiskUse: true }).toArray();

const t3_ms = new Date() - t3_start;
printResult(`5 unidades mais proximas com stock de Coartem (${t3_ms}ms)`, q3_result);


/* ============================================================================
   QUERY 4: ATUALIZACAO PARCIAL
   ============================================================================ */
printSection(4,
  "ATUALIZACAO PARCIAL COMPLEXA: REGISTO DE REPOSICAO DE STOCK",
  "Actualizar atomicamente o stock e adicionar evento ao historico de uma unidade"
);

const t4_start = new Date();

const rutura_ex = db.registos_stock.findOne({ status: "rutura", medicamento_codigo: "MED01" });

if (rutura_ex) {
  const resultado_update = db.registos_stock.updateMany(
    {
      unidade_sanitaria_id: rutura_ex.unidade_sanitaria_id,
      medicamento_codigo: "MED01",
      data_registo: { $gte: new Date("2024-06-01") },
      status: "rutura"
    },
    {
      $set: {
        status: "alerta",
        "reposicao_emergencia.efectuada": true,
        "reposicao_emergencia.fonte": "CECOMA - Entrega Urgente",
        "reposicao_emergencia.lote": "LOT-EMG-2024-06"
      },
      $inc: { quantidade_atual: 450, quantidade_entrada: 450 },
      $currentDate: { ultima_atualizacao: true },
      $push: {
        historico_eventos: {
          $each: [{
            tipo: "REPOSICAO_EMERGENCIA",
            data: new Date("2024-06-15"),
            quantidade: 450,
            origem: "CECOMA",
            lote: "LOT-EMG-2024-06",
            efectuado_por: "Responsavel DPS-Uige",
            motivo: "Surto de malaria na regiao"
          }],
          $slice: -10
        }
      }
    }
  );

  const t4_ms = new Date() - t4_start;
  printResult(`Resultado da atualizacao (${t4_ms}ms)`, {
    matched: resultado_update.matchedCount,
    modified: resultado_update.modifiedCount,
    unidade: rutura_ex.unidade_sanitaria_nome,
    municipio: rutura_ex.municipio_nome,
    medicamento: rutura_ex.medicamento_nome
  });

  const doc_pos = db.registos_stock.findOne(
    { _id: rutura_ex._id },
    { status: 1, quantidade_atual: 1, reposicao_emergencia: 1, historico_eventos: 1, _id: 0 }
  );
  printResult("Estado do documento apos atualizacao", doc_pos);
}


/* ============================================================================
   QUERY 5: RANKING DE CRITICIDADE POR MUNICIPIO (CORRIGIDA - SEM ACENTOS)
   ============================================================================ */
printSection(5,
  "DASHBOARD: RANKING DE CRITICIDADE INTEGRADA POR MUNICIPIO",
  "Score composto: rutura de stock + incidencia malaria + capacidade de resposta"
);

const t5_start = new Date();

const q5_result = db.municipios.aggregate([
  {
    $lookup: {
      from: "registos_stock",
      let: { mun_id: "$_id" },
      pipeline: [
        {
          $match: {
            $expr: { $eq: ["$municipio_id", "$$mun_id"] },
            relacionado_malaria: true,
            data_registo: { $gte: new Date("2024-04-01") }
          }
        },
        {
          $group: {
            _id: null,
            total_registos: { $sum: 1 },
            registos_rutura: { $sum: { $cond: [{ $eq: ["$status", "rutura"] }, 1, 0] } },
            registos_critico: { $sum: { $cond: [{ $eq: ["$status", "critico"] }, 1, 0] } },
            stock_medio_antimalaricos: { $avg: "$quantidade_atual" }
          }
        }
      ],
      as: "dados_stock"
    }
  },
  {
    $lookup: {
      from: "surtos_malaria",
      let: { mun_id: "$_id" },
      pipeline: [
        {
          $match: {
            $expr: { $eq: ["$municipio_id", "$$mun_id"] },
            data_inicio: { $gte: new Date("2024-01-01") }
          }
        },
        {
          $group: {
            _id: null,
            total_casos: { $sum: "$casos_confirmados" },
            total_obitos: { $sum: "$obitos" },
            incidencia_max: { $max: "$incidencia_por_mil" },
            incidencia_media: { $avg: "$incidencia_por_mil" },
            n_surtos: { $sum: 1 },
            nivel_alerta_max: { $max: "$nivel_alerta_numerico" }
          }
        }
      ],
      as: "dados_surtos"
    }
  },
  {
    $addFields: {
      stock_info: { $arrayElemAt: ["$dados_stock", 0] },
      surto_info: { $arrayElemAt: ["$dados_surtos", 0] }
    }
  },
  {
    $addFields: {
      "score.pct_ruturas": {
        $round: [{
          $multiply: [{
            $divide: [
              { $ifNull: ["$stock_info.registos_rutura", 0] },
              { $max: [1, { $ifNull: ["$stock_info.total_registos", 1] }] }
            ]
          }, 100]
        }, 1]
      },
      "score.incidencia_media_malaria": { $round: [{ $ifNull: ["$surto_info.incidencia_media", 0] }, 1] },
      "score.n_surtos_ano": { $ifNull: ["$surto_info.n_surtos", 0] },
      "score.total_casos": { $ifNull: ["$surto_info.total_casos", 0] },
      "score.total_obitos": { $ifNull: ["$surto_info.total_obitos", 0] }
    }
  },
  {
    $addFields: {
      "score.criticidade_composta": {
        $round: [{
          $add: [
            { $multiply: ["$score.pct_ruturas", 0.40] },
            { $multiply: ["$score.incidencia_media_malaria", 1.5] },
            { $multiply: ["$score.n_surtos_ano", 3] },
            { $multiply: [{
                $divide: ["$score.total_obitos",
                          { $max: [1, { $divide: ["populacao", 1000] }] }]
              }, 10]
            }
          ]
        }, 1]
      }
    }
  },
  {
    $addFields: {
      nivel_emergencia: {
        $switch: {
          branches: [
            { case: { $gte: ["$score.criticidade_composta", 60] }, then: "EMERGENCIA" },
            { case: { $gte: ["$score.criticidade_composta", 35] }, then: "CRITICO" },
            { case: { $gte: ["$score.criticidade_composta", 15] }, then: "ALERTA" }
          ],
          default: "NORMAL"
        }
      }
    }
  },
  {
    $project: {
      _id: 0,
      municipio: "$nome",
      populacao: 1,
      nivel_emergencia: 1,
      score_criticidade: "$score.criticidade_composta",
      rutura_stock_pct: "$score.pct_ruturas",
      incidencia_malaria_por_mil: "$score.incidencia_media_malaria",
      casos_malaria_2024: "$score.total_casos",
      obitos_malaria_2024: "$score.total_obitos",
      n_surtos_registados: "$score.n_surtos_ano"
    }
  },
  { $sort: { score_criticidade: -1 } }
], { allowDiskUse: true }).toArray();

const t5_ms = new Date() - t5_start;
printResult(`Ranking de criticidade por municipio (${t5_ms}ms)`, q5_result);


/* ============================================================================
   QUERY 6: ANALISE DE REPOSICAO
   ============================================================================ */
printSection(6,
  "ANALISE DE REPOSICAO: TEMPO MEDIO PARA SAIR DE RUTURA POR TIPO DE UNIDADE",
  "Medir eficiencia logistica - quantos dias uma unidade permanece em rutura antes de repor stock"
);

const t6_start = new Date();

const q6_result = db.registos_stock.aggregate([
  {
    $match: {
      quantidade_entrada: { $gt: 0 },
      relacionado_malaria: true,
      data_registo: { $gte: new Date("2024-01-01") }
    }
  },
  {
    $lookup: {
      from: "unidades_sanitarias",
      localField: "unidade_sanitaria_id",
      foreignField: "_id",
      as: "us_info"
    }
  },
  { $unwind: "$us_info" },
  {
    $group: {
      _id: {
        tipo_unidade: "$us_info.tipo",
        categoria_med: "$categoria_medicamento"
      },
      media_dias_cobertura_pos_reposicao: { $avg: "$dias_restantes_estimado" },
      media_quantidade_reposta: { $avg: "$quantidade_entrada" },
      n_reposicoes: { $sum: 1 },
      quantidade_total_reposta: { $sum: "$quantidade_entrada" }
    }
  },
  {
    $project: {
      _id: 0,
      tipo_unidade: "$_id.tipo_unidade",
      categoria_medicamento: "$_id.categoria_med",
      media_dias_cobertura: { $round: ["$media_dias_cobertura_pos_reposicao", 0] },
      media_quantidade_por_reposicao: { $round: ["$media_quantidade_reposta", 0] },
      n_reposicoes_registadas: "$n_reposicoes",
      eficiencia: {
        $cond: {
          if: { $gte: ["$media_dias_cobertura_pos_reposicao", 30] },
          then: "Adequada (>30 dias cobertura)",
          else: {
            $cond: {
              if: { $gte: ["$media_dias_cobertura_pos_reposicao", 14] },
              then: "Marginal (14-30 dias)",
              else: "Insuficiente (<14 dias)"
            }
          }
        }
      }
    }
  },
  { $sort: { tipo_unidade: 1, categoria_medicamento: 1 } }
], { allowDiskUse: true }).toArray();

const t6_ms = new Date() - t6_start;
printResult(`Analise de reposicao por tipo de unidade (${t6_ms}ms)`, q6_result);


/* ============================================================================
   QUERY 7: DASHBOARD OPERACIONAL (CORRIGIDA - SEM ACENTOS)
   ============================================================================ */
printSection(7,
  "DASHBOARD OPERACIONAL: UNIDADES COM MULTIPLOS ANTIMALARICOS EM RUTURA",
  "Identificar as unidades em crise multipla para intervencao prioritaria imediata"
);

const t7_start = new Date();

const q7_result = db.registos_stock.aggregate([
  {
    $match: {
      relacionado_malaria: true,
      status: { $in: ["critico", "rutura"] },
      data_registo: { $gte: new Date("2024-05-01"), $lte: new Date("2024-06-30") }
    }
  },
  {
    $group: {
      _id: {
        us_id: "$unidade_sanitaria_id",
        us_nome: "$unidade_sanitaria_nome",
        municipio: "$municipio_nome"
      },
      medicamentos_em_rutura: {
        $addToSet: {
          $cond: [{ $eq: ["$status", "rutura"] }, "$medicamento_nome", "$$REMOVE"]
        }
      },
      medicamentos_em_critico: {
        $addToSet: {
          $cond: [{ $eq: ["$status", "critico"] }, "$medicamento_nome", "$$REMOVE"]
        }
      },
      stock_total_antimalaricos: { $sum: "$quantidade_atual" },
      total_dias_rutura: { $sum: { $cond: [{ $eq: ["$status", "rutura"] }, 1, 0] } }
    }
  },
  {
    $addFields: {
      n_meds_rutura: { $size: "$medicamentos_em_rutura" },
      n_meds_critico: { $size: "$medicamentos_em_critico" }
    }
  },
  {
    $match: {
      $or: [
        { n_meds_rutura: { $gte: 2 } },
        { $and: [{ n_meds_rutura: { $gte: 1 } }, { n_meds_critico: { $gte: 2 } }] }
      ]
    }
  },
  {
    $addFields: {
      score_urgencia: {
        $add: [
          { $multiply: ["$n_meds_rutura", 10] },
          { $multiply: ["$n_meds_critico", 5] },
          { $divide: ["$total_dias_rutura", 3] }
        ]
      }
    }
  },
  {
    $project: {
      _id: 0,
      unidade_sanitaria: "$_id.us_nome",
      municipio: "$_id.municipio",
      medicamentos_em_RUTURA: "$medicamentos_em_rutura",
      medicamentos_em_CRITICO: "$medicamentos_em_critico",
      n_meds_rutura: 1,
      n_meds_critico: 1,
      stock_total_antimalaricos_restante: "$stock_total_antimalaricos",
      dias_acumulados_rutura: "$total_dias_rutura",
      score_urgencia: { $round: ["$score_urgencia", 1] },
      prioridade_intervencao: {
        $cond: [{ $gte: ["$score_urgencia", 30] }, "IMEDIATA", "URGENTE"]
      }
    }
  },
  { $sort: { score_urgencia: -1 } },
  { $limit: 15 }
], { allowDiskUse: true }).toArray();

const t7_ms = new Date() - t7_start;
printResult(`Unidades em crise multipla - intervencao prioritaria (${t7_ms}ms)`, q7_result);


/* ============================================================================
   SUMARIO DE DESEMPENHO
   ============================================================================ */
print("\n" + "=".repeat(70));
print("  SUMARIO DE DESEMPENHO DAS QUERIES");
print("=".repeat(70));
const tempos = [t1_ms, t2_ms, t3_ms, t4_ms, t5_ms, t6_ms, t7_ms];
const labels = [
  "Q1: Correlacao Surto x Rutura",
  "Q2: Serie Temporal Coartem",
  "Q3: Geoespacial + Stock",
  "Q4: Atualizacao Complexa",
  "Q5: Dashboard Criticidade",
  "Q6: Analise Reposicao",
  "Q7: Crise Multipla"
];
labels.forEach((l, i) => {
  const bar = "█".repeat(Math.round(tempos[i] / 50));
  print(`  ${l.padEnd(35)}: ${String(tempos[i]).padStart(6)}ms  ${bar}`);
});
print("=".repeat(70));
print(`  TODAS AS QUERIES EXECUTADAS COM SUCESSO`);
print("=".repeat(70) + "\n");