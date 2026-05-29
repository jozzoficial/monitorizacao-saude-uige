# Trabalho Prático de SGBD II - Uíge, Angola

**Tema:** Sistema de Monitorização de Rutura de Medicamentos Essenciais e Surtos de Malária na Província do Uíge

**Autor:** JOÃO JOSÉ ANTÓNIO DA SILVA | FRANCISCO BRÁULIO FIGUEIREDO ANTÓNIO | KUMBI MANUEL DOMINGOS | PAULO BUNGA RODRIGUES
**Data:** Maio 2026  
**Docente:** Moyo Kanivengidio

---

## Visão Geral

Este projecto implementa uma camada de persistência NoSQL (MongoDB) para monitorizar em tempo real o stock de medicamentos antimaláricos e a ocorrência de surtos de malária na província do Uíge, Angola. O sistema contém mais de 167.000 documentos distribuídos em 6 coleções.

---

## Requisitos para Reproduzir

- Windows 10/11 ou Linux
- Docker Desktop instalado e em execução
- Python 3.14+ com a biblioteca `pymongo` instalada (`pip install pymongo`)
- Acesso à internet (para o Docker descarregar a imagem do MongoDB)

---

## Como Levantar o Ambiente (Passo a Passo)

### 1. Clonar o repositório

```bash
git clone https://github.com/jozzoficial/monitorizacao-saude-uige.git
cd monitorizacao-saude-uige

2. Iniciar o cluster MongoDB com Docker Compose
docker compose up -d
Aguarde cerca de 30 segundos para o replica set ser iniciado automaticamente.

3. Verificar que o cluster está saudável
docker exec -it mongo-primary mongosh --eval "rs.status().ok"
Deve retornar 1.

4. Instalar dependências Python
pip install pymongo

5. Povoar a base de dados (inserir os 167.000 documentos)
python seed.py
O processo demora 2-5 minutos. No final verá o resumo das inserções.

6. Executar as 7 queries avançadas

type queries.js | docker exec -i mongo-primary mongosh saude_uige
Ou, dentro do contentor:


docker exec -it mongo-primary mongosh saude_uige
load("queries.js")
Estrutura do Repositório
Ficheiro	Descrição
seed.py	Script de geração e inserção dos dados (167k documentos)
queries.js	7 consultas agregadas/geoespaciais/atualizações
docker-compose.yml	Cluster MongoDB com 3 nós e replica set
relatorio_tecnico.pdf	Relatório completo com justificações, modelação e análises
Resultados Esperados
Base de dados saude_uige com 6 coleções.

Query 1: lista municípios com surto activo e rutura de antimaláricos.

Query 3: unidades geoespacialmente mais próximas de um surto.

Query 5: ranking de criticidade composta por município.

Query 7: unidades com múltiplos antimaláricos em rutura.

Notas de Resolução de Problemas
Se o seed.py falhar com erro de ligação, certifique-se de que o cluster está Up (docker compose ps).

Se o mongosh não for reconhecido no Windows, use docker exec -it mongo-primary mongosh em vez do comando directo.

Para parar o cluster (preservando dados): docker compose down

Para recomeçar do zero: docker compose down -v e depois docker compose up -d e python seed.py

Referências
MongoDB Aggregation Pipeline: https://www.mongodb.com/docs/manual/aggregation/

Docker Compose: https://docs.docker.com/compose/

Dados de base populacional do Uíge: INE Angola (estimativas 2024)
