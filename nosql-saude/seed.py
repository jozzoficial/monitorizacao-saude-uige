"""
Script de Povoamento de Dados 

  - municipios          :  16 documentos
  - unidades sanitarias :  52 documentos
  - medicamentos        :  22 documentos
  - registos_stock      : ~208,000 documentos  ← volume principal
  - surtos_malaria      :   ~480 documentos
  - alertas             :  ~2,600 documentos

Total estimado: >210,000 documentos
=============================================================================
USO:
  python seed.py                         # conecta ao MongoDB local (porta 27017)
  python seed.py --uri mongodb://host:27017
=============================================================================
"""

import random
import argparse
from datetime import datetime, timedelta
from pymongo import MongoClient, GEOSPHERE, ASCENDING, DESCENDING
from pymongo.errors import BulkWriteError
import math


# Argumentos de linha de comando
args = type('Args', (), {
    'uri': 'mongodb://localhost:27017/?directConnection=true',
    'db': 'saude_uige',
    'drop': True
})()

# Conexão
client = MongoClient(args.uri)
db = client[args.db]
print(f"\n{'='*65}")
print(f"  Conectado a: {args.uri}  |  Base de dados: {args.db}")
print(f"{'='*65}\n")

if args.drop:
    for col in ["municipios", "unidades_sanitarias", "medicamentos",
                "registos_stock", "surtos_malaria", "alertas"]:
        db[col].drop()
    print("[INFO] Coleções existentes removidas.\n")


# 1. MUNICÍPIOS DA PROVÍNCIA DO UÍGE 
MUNICIPIOS_DATA = [
    {"codigo":"MUN01","nome":"Uíge",          "populacao":534700,"area_km2":4641,"coords":[15.0581,-7.6094],"nivel_saude":4},
    {"codigo":"MUN02","nome":"Negage",         "populacao":143200,"area_km2":3876,"coords":[15.2667,-7.7667],"nivel_saude":3},
    {"codigo":"MUN03","nome":"Songo",          "populacao":118600,"area_km2":2987,"coords":[14.8500,-7.3500],"nivel_saude":2},
    {"codigo":"MUN04","nome":"Maquela do Zombo","populacao":95400,"area_km2":5219,"coords":[15.1167,-6.0667],"nivel_saude":2},
    {"codigo":"MUN05","nome":"Quimbele",       "populacao":78900,"area_km2":3412,"coords":[14.7833,-7.1500],"nivel_saude":2},
    {"codigo":"MUN06","nome":"Damba",          "populacao":67300,"area_km2":2876,"coords":[15.1833,-6.6833],"nivel_saude":2},
    {"codigo":"MUN07","nome":"Bembe",          "populacao":62100,"area_km2":4100,"coords":[14.4000,-7.0500],"nivel_saude":1},
    {"codigo":"MUN08","nome":"Bungo",          "populacao":58700,"area_km2":3650,"coords":[15.3500,-7.1000],"nivel_saude":1},
    {"codigo":"MUN09","nome":"Buengas",        "populacao":45200,"area_km2":2340,"coords":[15.6000,-7.4000],"nivel_saude":1},
    {"codigo":"MUN10","nome":"Cangola",        "populacao":42800,"area_km2":2780,"coords":[15.4500,-6.9000],"nivel_saude":1},
    {"codigo":"MUN11","nome":"Fazenda",        "populacao":38900,"area_km2":1980,"coords":[15.2000,-7.9000],"nivel_saude":1},
    {"codigo":"MUN12","nome":"Kangola",        "populacao":35600,"area_km2":2150,"coords":[15.7000,-7.6000],"nivel_saude":1},
    {"codigo":"MUN13","nome":"Mucaba",         "populacao":52300,"area_km2":2670,"coords":[15.1000,-6.4000],"nivel_saude":1},
    {"codigo":"MUN14","nome":"Puri",           "populacao":34100,"area_km2":1890,"coords":[14.9000,-6.8000],"nivel_saude":1},
    {"codigo":"MUN15","nome":"Sanza Pombo",    "populacao":48700,"area_km2":3120,"coords":[15.9000,-6.2667],"nivel_saude":2},
    {"codigo":"MUN16","nome":"Zombo",          "populacao":41500,"area_km2":2560,"coords":[16.0167,-6.1500],"nivel_saude":2},
]

municipios_docs = []
for m in MUNICIPIOS_DATA:
    doc = {
        "codigo": m["codigo"],
        "nome": m["nome"],
        "provincia": "Uíge",
        "populacao": m["populacao"],
        "area_km2": m["area_km2"],
        "localizacao": {"type": "Point", "coordinates": m["coords"]},
        "nivel_infraestrutura_saude": m["nivel_saude"],
        "indicadores_base": {
            "taxa_malaria_por_1000": round(random.uniform(80, 320), 1),
            "cobertura_vacinacao_pct": round(random.uniform(45, 85), 1),
            "distancia_media_unidade_saude_km": round(random.uniform(2, 35), 1)
        },
        "criado_em": datetime(2024, 1, 1)
    }
    municipios_docs.append(doc)

result = db.municipios.insert_many(municipios_docs)
print(f"[OK] municipios         : {len(result.inserted_ids):>7} documentos inseridos")

# Indexar geoespacialmente
db.municipios.create_index([("localizacao", GEOSPHERE)])
db.municipios.create_index([("codigo", ASCENDING)], unique=True)

# Mapa id -> documento
mun_ids = {doc["codigo"]: doc["_id"] for doc in db.municipios.find({}, {"codigo":1,"_id":1})}
mun_docs = {doc["codigo"]: doc for doc in db.municipios.find()}


# 2. UNIDADES SANITÁRIAS  (3-4 por município = ~52 total)
TIPOS_US = {
    4: ["Hospital Provincial"],
    3: ["Hospital Municipal"],
    2: ["Hospital Municipal", "Centro de Saúde"],
    1: ["Centro de Saúde", "Posto de Saúde"]
}

NOMES_RESPONSAVEIS = [
    "Dr. António Mamboniquina","Dra. Elisa Camacho","Dr. José Cunha da Silva",
    "Dra. Ilda Fineza","Dr. Armando Aragunês","Enf. Nlandu Tomás",
    "Dr. Filipe Mendes","Dra. Rosa Kiala","Dr. Sebastião Ndunge",
    "Dra. Helena Pinto","Dr. Adão Malungo","Dra. Cecília Bemba",
]

unidades_docs = []
for m in MUNICIPIOS_DATA:
    nivel = m["nivel_saude"]
    tipos = TIPOS_US[nivel]
    n_us = 4 if nivel >= 3 else 3 if nivel == 2 else 2

    for i in range(n_us):
        tipo = tipos[0] if i == 0 else random.choice(tipos)
        nivel_num = {"Hospital Provincial":4,"Hospital Municipal":3,
                     "Centro de Saúde":2,"Posto de Saúde":1}[tipo]
        lon_off = random.uniform(-0.12, 0.12)
        lat_off = random.uniform(-0.10, 0.10)
        doc = {
            "codigo": f"US-{m['codigo']}-{i+1:02d}",
            "nome": f"{'Hospital Provincial' if tipo=='Hospital Provincial' else tipo} {'de ' if i==0 else 'do Bairro '}{m['nome'] if i==0 else str(i)}",
            "tipo": tipo,
            "nivel": nivel_num,
            "municipio_id": mun_ids[m["codigo"]],
            "municipio_nome": m["nome"],
            "provincia": "Uíge",
            "localizacao": {
                "type": "Point",
                "coordinates": [m["coords"][0]+lon_off, m["coords"][1]+lat_off]
            },
            "capacidade_leitos": {"Hospital Provincial":450,"Hospital Municipal":120,
                                  "Centro de Saúde":25,"Posto de Saúde":5}[tipo],
            "tem_laboratorio": nivel_num >= 3,
            "tem_microscopio": nivel_num >= 2,
            "tem_energia_solar": random.random() < 0.6,
            "responsavel": random.choice(NOMES_RESPONSAVEIS),
            "contacto": f"+244 9{random.randint(20,39)}{random.randint(1000000,9999999)}",
            "criado_em": datetime(2023, random.randint(1,12), random.randint(1,28))
        }
        unidades_docs.append(doc)

result = db.unidades_sanitarias.insert_many(unidades_docs)
print(f"[OK] unidades_sanitarias: {len(result.inserted_ids):>7} documentos inseridos")

db.unidades_sanitarias.create_index([("localizacao", GEOSPHERE)])
db.unidades_sanitarias.create_index([("municipio_id", ASCENDING)])
db.unidades_sanitarias.create_index([("codigo", ASCENDING)], unique=True)

us_docs = list(db.unidades_sanitarias.find())


# 3. MEDICAMENTOS  (foco em antimaláricos + essenciais OMS/MINSA Angola)
MEDICAMENTOS_DATA = [
    # Antimaláricos (linha 1 e 2) 
    {"codigo":"MED01","nome":"Arteméter + Lumefantrina","comercial":"Coartem",
     "cat":"Antimalárico","sub":"ACT 1ª linha","forma":"Comprimido","dosagem":"20mg/120mg",
     "unidade":"comprimidos","min":600,"crit":250,"preco":185.0},
    {"codigo":"MED02","nome":"Artesunato + Amodiaquina","comercial":"ASAQ",
     "cat":"Antimalárico","sub":"ACT alternativo","forma":"Comprimido","dosagem":"100mg/270mg",
     "unidade":"comprimidos","min":400,"crit":150,"preco":142.0},
    {"codigo":"MED03","nome":"Artesunato IV","comercial":"Arinate",
     "cat":"Antimalárico","sub":"Malária grave","forma":"Injetável","dosagem":"60mg/vial",
     "unidade":"vials","min":80,"crit":30,"preco":1250.0},
    {"codigo":"MED04","nome":"Cloroquina","comercial":"Resochin",
     "cat":"Antimalárico","sub":"P. vivax / profilaxia","forma":"Comprimido","dosagem":"150mg",
     "unidade":"comprimidos","min":500,"crit":200,"preco":35.0},
    {"codigo":"MED05","nome":"Primaquina","comercial":"Primaquin",
     "cat":"Antimalárico","sub":"Radical cure P. vivax","forma":"Comprimido","dosagem":"15mg",
     "unidade":"comprimidos","min":300,"crit":100,"preco":62.0},
    {"codigo":"MED06","nome":"Quinina IV","comercial":"Quinine HCl",
     "cat":"Antimalárico","sub":"Malária grave 2ª linha","forma":"Injetável","dosagem":"300mg/mL",
     "unidade":"ampolas","min":60,"crit":20,"preco":980.0},
    #  Diagnóstico 
    {"codigo":"MED07","nome":"TDR Malária (kit)","comercial":"SD BIOLINE Malaria Ag",
     "cat":"Diagnóstico","sub":"Teste Rápido","forma":"Kit","dosagem":"N/A",
     "unidade":"testes","min":500,"crit":150,"preco":320.0},
    # Suporte Clínico 
    {"codigo":"MED08","nome":"Soro Fisiológico 0,9%","comercial":"NaCl 0,9%",
     "cat":"Soluções IV","sub":"Hidratação","forma":"Bolsa IV","dosagem":"500mL",
     "unidade":"bolsas","min":200,"crit":80,"preco":420.0},
    {"codigo":"MED09","nome":"Paracetamol 500mg","comercial":"Panadol",
     "cat":"Analgésico/Antipirético","sub":"Febre","forma":"Comprimido","dosagem":"500mg",
     "unidade":"comprimidos","min":1000,"crit":400,"preco":18.0},
    {"codigo":"MED10","nome":"Diazepam IV","comercial":"Valium",
     "cat":"Anticonvulsivante","sub":"Convulsões / malária cerebral","forma":"Injetável","dosagem":"5mg/mL",
     "unidade":"ampolas","min":50,"crit":15,"preco":680.0},
    {"codigo":"MED11","nome":"Sulfato Ferroso + Ácido Fólico","comercial":"Heferol",
     "cat":"Hematínico","sub":"Anemia / malária","forma":"Comprimido","dosagem":"200mg+0.4mg",
     "unidade":"comprimidos","min":800,"crit":300,"preco":28.0},
    {"codigo":"MED12","nome":"Amoxicilina 500mg","comercial":"Amoxil",
     "cat":"Antibiótico","sub":"Infeções bacterianas","forma":"Cápsula","dosagem":"500mg",
     "unidade":"capsulas","min":600,"crit":200,"preco":45.0},
    {"codigo":"MED13","nome":"Metronidazol 500mg","comercial":"Flagyl",
     "cat":"Antibiótico/Antiparasitário","sub":"Infeções","forma":"Comprimido","dosagem":"500mg",
     "unidade":"comprimidos","min":500,"crit":180,"preco":38.0},
    {"codigo":"MED14","nome":"Sulfato de Magnésio IV","comercial":"MgSO4",
     "cat":"Anticonvulsivante","sub":"Pré-eclâmpsia / eclâmpsia","forma":"Injetável","dosagem":"50%",
     "unidade":"ampolas","min":40,"crit":12,"preco":520.0},
    {"codigo":"MED15","nome":"Oxitocina","comercial":"Syntocinon",
     "cat":"Uterotónico","sub":"Parto / hemorragia","forma":"Injetável","dosagem":"10 UI/mL",
     "unidade":"ampolas","min":80,"crit":25,"preco":890.0},
    {"codigo":"MED16","nome":"Vitamina A (cápsula)","comercial":"Aquasol A",
     "cat":"Vitamina","sub":"Profilaxia / imunidade","forma":"Cápsula","dosagem":"200.000 UI",
     "unidade":"capsulas","min":400,"crit":150,"preco":55.0},
    {"codigo":"MED17","nome":"Sais de Reidratação Oral","comercial":"Pedialyte",
     "cat":"Reidratação Oral","sub":"Desidratação","forma":"Saqueta","dosagem":"20,5g",
     "unidade":"saquetas","min":600,"crit":200,"preco":75.0},
    {"codigo":"MED18","nome":"Luvas de Látex (caixa)","comercial":"Ansell",
     "cat":"Consumível","sub":"EPI","forma":"Caixa 100un","dosagem":"N/A",
     "unidade":"caixas","min":50,"crit":15,"preco":3500.0},
    {"codigo":"MED19","nome":"Seringas 5mL (caixa)","comercial":"BD Plastipak",
     "cat":"Consumível","sub":"Injetáveis","forma":"Caixa 100un","dosagem":"N/A",
     "unidade":"caixas","min":40,"crit":10,"preco":1800.0},
    {"codigo":"MED20","nome":"Mosquiteiros Impregnados (MILD)","comercial":"PermaNet 2.0",
     "cat":"Prevenção","sub":"Controlo vetorial","forma":"Unidade","dosagem":"N/A",
     "unidade":"unidades","min":100,"crit":30,"preco":1200.0},
    {"codigo":"MED21","nome":"Sulfadoxina + Pirimetamina","comercial":"Fansidar",
     "cat":"Antimalárico","sub":"TPI gestantes","forma":"Comprimido","dosagem":"500mg/25mg",
     "unidade":"comprimidos","min":350,"crit":100,"preco":95.0},
    {"codigo":"MED22","nome":"Gluconato de Cálcio IV","comercial":"Calciglucon",
     "cat":"Electrólito","sub":"Hipocalcemia / suporte","forma":"Injetável","dosagem":"10%",
     "unidade":"ampolas","min":30,"crit":10,"preco":450.0},
]

med_docs = []
for m in MEDICAMENTOS_DATA:
    doc = {
        "codigo": m["codigo"],
        "nome_generico": m["nome"],
        "nome_comercial": m["comercial"],
        "categoria": m["cat"],
        "subcategoria": m["sub"],
        "forma_farmaceutica": m["forma"],
        "dosagem": m["dosagem"],
        "unidade_medida": m["unidade"],
        "stock_minimo_padrao": m["min"],
        "stock_critico_padrao": m["crit"],
        "preco_unitario_kz": m["preco"],
        "essencial_oms": True,
        "relacionado_malaria": m["cat"] in ["Antimalárico","Diagnóstico"],
        "fornecedor_principal": random.choice(["CECOMA","ANGOFARMA","ANGOMED","Importação MINSA"]),
        "prazo_validade_meses": random.choice([12,18,24,36]),
        "criado_em": datetime(2023, 6, 1)
    }
    med_docs.append(doc)

result = db.medicamentos.insert_many(med_docs)
print(f"[OK] medicamentos        : {len(result.inserted_ids):>7} documentos inseridos")

db.medicamentos.create_index([("codigo", ASCENDING)], unique=True)
db.medicamentos.create_index([("categoria", ASCENDING)])

med_list = list(db.medicamentos.find())


# 4. REGISTOS DE STOCK  (série temporal - volume principal)
#    52 unidades × 22 medicamentos × 180 dias = ~205,920 registos
print("\n[...] Gerando registos_stock (pode demorar ~60s)...")

STATUS_MAP = lambda q, min_s, crit_s: (
    "rutura"   if q == 0           else
    "critico"  if q <= crit_s      else
    "alerta"   if q <= min_s       else
    "normal"
)

DATA_INICIO = datetime(2024, 1, 1)
N_DIAS = 180  # ~6 meses de dados diários
BATCH_SIZE = 5000

stock_batch = []
total_stock = 0
anomalia_tracker = {}  # (us_id, med_id) -> dias_em_alerta

for us in us_docs:
    for med in med_list:
        # Parâmetros realistas por tipo de unidade
        capacidade_factor = {4:3.0, 3:2.0, 2:1.2, 1:0.7}[us["nivel"]]
        stock_min = int(med["stock_minimo_padrao"] * capacidade_factor)
        stock_crit = int(med["stock_critico_padrao"] * capacidade_factor)

        # Stock inicial (pode já começar em situação difícil para alguns)
        inicio_pct = random.choices(
            [0.0, 0.2, 0.5, 1.0, 1.5, 2.0],
            weights=[2, 5, 20, 35, 25, 13]
        )[0]
        qty = int(stock_min * inicio_pct * capacidade_factor)

        # Taxa de consumo diário (unidades por dia)
        consumo_base = max(1, int(stock_min * random.uniform(0.01, 0.04)))

        # Probabilidade de reposição mensal
        for dia in range(N_DIAS):
            data_registo = DATA_INICIO + timedelta(days=dia)

            # Consumo diário (com variabilidade sazonal - mais malária na época chuvosa)
            mes = data_registo.month
            fator_sazonal = 1.6 if mes in [2,3,4,10,11,12] else 1.0  # época chuvosa
            consumo_dia = max(0, int(consumo_base * fator_sazonal * random.uniform(0.5, 1.8)))
            consumo_dia = min(consumo_dia, qty)  # não pode consumir mais do que existe

            # Entradas (reposição): probabilidade maior a cada ~30 dias
            entrada = 0
            if dia % random.randint(25, 45) == 0 and random.random() < 0.75:
                entrada = int(stock_min * random.uniform(1.5, 4.0) * capacidade_factor)

            qty = max(0, qty - consumo_dia + entrada)
            status = STATUS_MAP(qty, stock_min, stock_crit)

            # Dias restantes estimados (evitar divisão por zero)
            dias_rest = round(qty / consumo_base) if consumo_base > 0 else 999

            doc = {
                "unidade_sanitaria_id": us["_id"],
                "unidade_sanitaria_codigo": us["codigo"],
                "unidade_sanitaria_nome": us["nome"],
                "municipio_id": us["municipio_id"],
                "municipio_nome": us["municipio_nome"],
                "medicamento_id": med["_id"],
                "medicamento_codigo": med["codigo"],
                "medicamento_nome": med["nome_generico"],
                "categoria_medicamento": med["categoria"],
                "relacionado_malaria": med["relacionado_malaria"],
                "data_registo": data_registo,
                "ano": data_registo.year,
                "mes": data_registo.month,
                "semana": data_registo.isocalendar()[1],
                "quantidade_atual": qty,
                "quantidade_entrada": entrada,
                "quantidade_saida": consumo_dia,
                "stock_minimo": stock_min,
                "stock_critico": stock_crit,
                "status": status,
                "dias_restantes_estimado": min(dias_rest, 999),
                "registado_por": random.choice([
                    "Sistema Automático","Enfermeiro de Turno","Farmacêutico","Gestor de Stock"
                ]),
                "nivel_alerta_numerico": {"normal":0,"alerta":1,"critico":2,"rutura":3}[status]
            }
            stock_batch.append(doc)

            if len(stock_batch) >= BATCH_SIZE:
                db.registos_stock.insert_many(stock_batch, ordered=False)
                total_stock += len(stock_batch)
                stock_batch = []
                print(f"    {total_stock:>9,} registos inseridos...", end="\r")

# Inserir restantes
if stock_batch:
    db.registos_stock.insert_many(stock_batch, ordered=False)
    total_stock += len(stock_batch)

print(f"[OK] registos_stock      : {total_stock:>7,} documentos inseridos")

# Índices compostos para queries de desempenho
db.registos_stock.create_index([("municipio_id", ASCENDING), ("data_registo", DESCENDING)])
db.registos_stock.create_index([("medicamento_id", ASCENDING), ("data_registo", DESCENDING)])
db.registos_stock.create_index([("unidade_sanitaria_id", ASCENDING), ("data_registo", DESCENDING)])
db.registos_stock.create_index([("status", ASCENDING), ("data_registo", DESCENDING)])
db.registos_stock.create_index([("relacionado_malaria", ASCENDING), ("status", ASCENDING)])
db.registos_stock.create_index([("data_registo", DESCENDING)])
print("[OK] Índices de registos_stock criados")


# 5. SURTOS DE MALÁRIA
TIPOS_PLASMODIUM = ["falciparum","vivax","malariae","falciparum","falciparum"]  # falciparum dominante
MEDIDAS = [
    "fumigação residual interna","distribuição de mosquiteiros MILD",
    "campanha de diagnóstico e tratamento","pulverização espacial",
    "mobilização comunitária","formação de agentes de saúde comunitários"
]

surtos_docs = []
for m in MUNICIPIOS_DATA:
    pop = m["populacao"]
    # Gerar ~2-4 períodos de surto por município ao longo de 2 anos
    for ano in [2023, 2024]:
        # Época chuvosa: fev-abril e out-dez
        for periodo in [(2,3), (10,11), (3,4), (11,12)]:
            if random.random() < 0.65:  # nem todos os municípios têm surto declarado
                mes_ini = periodo[0]
                mes_fim = periodo[1]
                data_ini = datetime(ano, mes_ini, random.randint(1,15))
                data_fim = datetime(ano, mes_fim, random.randint(15,28))
                duracao = (data_fim - data_ini).days

                casos_conf = int(pop * random.uniform(0.002, 0.018))
                casos_susp = int(casos_conf * random.uniform(1.5, 3.2))
                obitos = int(casos_conf * random.uniform(0.005, 0.025))
                incidencia = round(casos_conf / pop * 1000, 2)

                nivel_alerta = (
                    "vermelho" if incidencia > 15 else
                    "laranja"  if incidencia > 8  else
                    "amarelo"  if incidencia > 3  else
                    "verde"
                )

                doc = {
                    "municipio_id": mun_ids[m["codigo"]],
                    "municipio_nome": m["nome"],
                    "provincia": "Uíge",
                    "data_inicio": data_ini,
                    "data_fim": data_fim,
                    "duracao_dias": duracao,
                    "ano": ano,
                    "mes_inicio": mes_ini,
                    "epoca": "chuvosa" if mes_ini in [2,3,4,10,11,12] else "seca",
                    "ativo": (datetime.now() - data_fim).days < 30,
                    "tipo_plasmodium": random.choice(TIPOS_PLASMODIUM),
                    "casos_confirmados": casos_conf,
                    "casos_suspeitos": casos_susp,
                    "obitos": obitos,
                    "taxa_letalidade_pct": round(obitos / casos_conf * 100, 2) if casos_conf > 0 else 0,
                    "incidencia_por_mil": incidencia,
                    "populacao_referencia": pop,
                    "nivel_alerta": nivel_alerta,
                    "nivel_alerta_numerico": {"verde":1,"amarelo":2,"laranja":3,"vermelho":4}[nivel_alerta],
                    "medidas_tomadas": random.sample(MEDIDAS, k=random.randint(2,5)),
                    "notificado_dps": True,
                    "notificado_minsa": incidencia > 10,
                    "criado_em": data_ini + timedelta(days=random.randint(2,7))
                }
                surtos_docs.append(doc)

result = db.surtos_malaria.insert_many(surtos_docs)
print(f"[OK] surtos_malaria      : {len(result.inserted_ids):>7} documentos inseridos")

db.surtos_malaria.create_index([("municipio_id", ASCENDING), ("data_inicio", DESCENDING)])
db.surtos_malaria.create_index([("nivel_alerta", ASCENDING)])
db.surtos_malaria.create_index([("ano", ASCENDING), ("mes_inicio", ASCENDING)])


# 6. ALERTAS GERADOS AUTOMATICAMENTE
TIPOS_ALERTA = ["RUTURA_STOCK","STOCK_CRITICO","STOCK_ALERTA","CORRELACAO_SURTO_STOCK"]
alertas_docs = []

# Gerar alertas baseados nos registos de stock em status crítico/rutura (amostra)
pipeline_alertas = [
    {"$match": {"status": {"$in": ["critico","rutura"]}}},
    {"$group": {
        "_id": {
            "us_id": "$unidade_sanitaria_id",
            "med_id": "$medicamento_id",
            "mes": "$mes", "ano": "$ano"
        },
        "status_max": {"$max": "$nivel_alerta_numerico"},
        "us_nome": {"$first": "$unidade_sanitaria_nome"},
        "mun_id": {"$first": "$municipio_id"},
        "mun_nome": {"$first": "$municipio_nome"},
        "med_nome": {"$first": "$medicamento_nome"},
        "data_first": {"$min": "$data_registo"},
        "qty_min": {"$min": "$quantidade_atual"}
    }},
    {"$limit": 3000}
]

for grp in db.registos_stock.aggregate(pipeline_alertas, allowDiskUse=True):
    tipo = "RUTURA_STOCK" if grp["status_max"] == 3 else "STOCK_CRITICO"
    sev  = "critica" if grp["status_max"] == 3 else "alta"
    doc = {
        "tipo": tipo,
        "severidade": sev,
        "unidade_sanitaria_id": grp["_id"]["us_id"],
        "unidade_sanitaria_nome": grp["us_nome"],
        "municipio_id": grp["mun_id"],
        "municipio_nome": grp["mun_nome"],
        "medicamento_id": grp["_id"]["med_id"],
        "medicamento_nome": grp["med_nome"],
        "quantidade_no_momento": grp["qty_min"],
        "data_criacao": grp["data_first"],
        "ano": grp["_id"]["ano"],
        "mes": grp["_id"]["mes"],
        "ativo": random.random() < 0.35,
        "notificados": random.sample(["DPS-Uíge","CECOMA","MINSA","Gestor Distrital"], k=random.randint(1,3)),
        "acoes_tomadas": random.sample([
            "Pedido urgente enviado",
            "Transferência de outra unidade",
            "Aguarda aprovação",
            "Stock reposto parcialmente",
            "Sem ação até ao momento"
        ], k=random.randint(0,2))
    }
    alertas_docs.append(doc)

if alertas_docs:
    result = db.alertas.insert_many(alertas_docs)
    print(f"[OK] alertas             : {len(result.inserted_ids):>7} documentos inseridos")

db.alertas.create_index([("municipio_id", ASCENDING), ("data_criacao", DESCENDING)])
db.alertas.create_index([("tipo", ASCENDING), ("ativo", ASCENDING)])
db.alertas.create_index([("severidade", ASCENDING)])


# RESUMO FINAL
print(f"\n{'='*65}")
print(f"  RESUMO DO POVOAMENTO - BASE DE DADOS: {args.db}")
print(f"{'='*65}")
total = 0
for col in ["municipios","unidades_sanitarias","medicamentos","registos_stock","surtos_malaria","alertas"]:
    n = db[col].count_documents({})
    total += n
    print(f"  {col:<30}: {n:>9,} documentos")
print(f"{'='*65}")
print(f"  {'TOTAL':<30}: {total:>9,} documentos")
print(f"{'='*65}\n")
print("  Índices criados:")
for col in ["municipios","unidades_sanitarias","medicamentos","registos_stock","surtos_malaria","alertas"]:
    idxs = list(db[col].list_indexes())
    print(f"  {col:<30}: {len(idxs)} índices")
print(f"\n[SUCESSO] Povoamento concluído!\n")
client.close()
